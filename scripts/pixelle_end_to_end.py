#!/usr/bin/env python3
"""
Run a minimal end-to-end pipeline:

YouTube/Shorts URL -> transcript extraction -> fixed script prep -> Pixelle static render

The script prefers a user-provided manual script file for best quality. If none is provided,
it falls back to a deterministic sentence-selection strategy.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import site
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse


VIDEO_TRANSCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = VIDEO_TRANSCRIPT_ROOT.parent
SCRIPTS_DIR = VIDEO_TRANSCRIPT_ROOT / "scripts"
PIXELLE_ROOT = WORKSPACE_ROOT / "Pixelle-Video"
EXTRACT_SCRIPT = SCRIPTS_DIR / "extract_transcript.py"
NEWSROOM_BUILDER_DIR = SCRIPTS_DIR


def run_cmd(cmd: list[str], cwd: Path | None = None) -> None:
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True)


def normalize_text(text: str) -> str:
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n\n", text)
    return text.strip()


def split_sentences(text: str) -> list[str]:
    cleaned = normalize_text(text).replace("\n", " ")
    pieces = re.split(r"(?<=[.!?。！？])\s+", cleaned)
    sentences: list[str] = []
    seen: set[str] = set()
    for piece in pieces:
        sentence = piece.strip(" -")
        if not sentence:
            continue
        dedupe_key = sentence.lower()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        sentences.append(sentence)
    return sentences


def build_fallback_script(metadata: dict, transcript_text: str) -> tuple[str, str]:
    title = metadata.get("title", "Short Video Recap").strip()
    sentences = split_sentences(transcript_text)
    if not sentences:
        raise ValueError("No transcript sentences found for fallback script generation")

    chosen: list[str] = []

    def maybe_add(predicate) -> None:
        for sentence in sentences:
            if predicate(sentence) and sentence not in chosen:
                chosen.append(sentence)
                return

    maybe_add(lambda s: True)
    maybe_add(lambda s: "$" in s or re.search(r"\b\d+(\.\d+)?\b", s))
    maybe_add(lambda s: "revenue" in s.lower() or "valuation" in s.lower())
    maybe_add(lambda s: "prices in perfection" in s.lower() or "capital" in s.lower())
    maybe_add(lambda s: "12 to 18 months" in s.lower() or "holds its value" in s.lower())

    if len(chosen) < 5:
        for sentence in sentences:
            if sentence not in chosen:
                chosen.append(sentence)
            if len(chosen) >= 5:
                break

    script = "\n\n".join(chosen[:5])
    return title, script


def ensure_transcript(url: str, output_dir: Path) -> None:
    raw_transcript = output_dir / "raw_transcript.txt"
    metadata = output_dir / "metadata.json"
    if raw_transcript.exists() and metadata.exists():
        return
    output_dir.mkdir(parents=True, exist_ok=True)
    run_cmd(
        [
            sys.executable,
            str(EXTRACT_SCRIPT),
            url,
            "--output-dir",
            str(output_dir),
            "--no-images",
        ],
        cwd=VIDEO_TRANSCRIPT_ROOT,
    )


def ensure_source_video(url: str, output_dir: Path) -> Path:
    return ensure_downloaded_video(url, output_dir / "source_video")


def ensure_downloaded_video(url: str, output_stem: Path) -> Path:
    for ext in [".mp4", ".mov", ".mkv", ".webm"]:
        candidate = output_stem.with_suffix(ext)
        if candidate.exists():
            return candidate

    output_stem.parent.mkdir(parents=True, exist_ok=True)
    run_cmd(
        [
            "yt-dlp",
            "-f",
            "mp4/bestvideo+bestaudio/best",
            "-o",
            str(output_stem) + ".%(ext)s",
            url,
        ],
        cwd=VIDEO_TRANSCRIPT_ROOT,
    )

    for ext in [".mp4", ".mov", ".mkv", ".webm"]:
        candidate = output_stem.with_suffix(ext)
        if candidate.exists():
            return candidate

    raise FileNotFoundError(f"Failed to download video asset for {url}")


def extract_youtube_video_id(url: str) -> str | None:
    parsed = urlparse(url.strip())
    if parsed.netloc.endswith("youtu.be"):
        return parsed.path.strip("/") or None
    if parsed.path.startswith("/shorts/"):
        return parsed.path.split("/shorts/", 1)[1].split("/", 1)[0] or None
    query = parse_qs(parsed.query)
    values = query.get("v")
    if values:
        return values[0]
    return None


def build_pip_url_pool(primary_url: str, extra_urls: list[str]) -> list[str]:
    pool: list[str] = []
    seen: set[str] = set()
    for raw_url in [primary_url, *extra_urls]:
        url = raw_url.strip()
        if not url or url in seen:
            continue
        seen.add(url)
        pool.append(url)
    return pool


def probe_video_duration(video_path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())


def ensure_pip_support_videos(urls: list[str], output_dir: Path) -> list[Path]:
    support_dir = output_dir / "pip_pool_sources"
    support_paths: list[Path] = []
    for index, url in enumerate(urls, start=1):
        video_id = extract_youtube_video_id(url) or f"clip_{index:02d}"
        stem = support_dir / f"pip_source_{index:02d}_{video_id}"
        support_paths.append(ensure_downloaded_video(url, stem))
    return support_paths


def resolve_pip_support_files(paths: list[str]) -> list[Path]:
    resolved: list[Path] = []
    seen: set[Path] = set()
    for raw_path in paths:
        candidate = Path(raw_path).expanduser().resolve()
        if not candidate.exists():
            raise FileNotFoundError(f"PIP support file not found: {candidate}")
        if candidate in seen:
            continue
        seen.add(candidate)
        resolved.append(candidate)
    return resolved


def select_story_pip_sources(source_video: Path, support_videos: list[Path]) -> list[Path]:
    if support_videos:
        return support_videos
    return [source_video]


def build_pip_montage(video_paths: list[Path], output_dir: Path, clip_seconds: float) -> Path:
    if len(video_paths) == 1:
        return video_paths[0]

    segments_dir = output_dir / "pip_pool_segments"
    segments_dir.mkdir(parents=True, exist_ok=True)
    concat_list = output_dir / "pip_pool_concat.txt"
    montage_path = output_dir / "pip_pool_montage.mp4"

    segment_paths: list[Path] = []
    for index, video_path in enumerate(video_paths, start=1):
        duration = probe_video_duration(video_path)
        max_offset = max(0.0, duration - clip_seconds - 0.35)
        offset = min(index * 1.15, max_offset)
        segment_path = segments_dir / f"segment_{index:02d}.mp4"
        run_cmd(
            [
                "ffmpeg",
                "-y",
                "-ss",
                f"{offset:.2f}",
                "-t",
                f"{clip_seconds:.2f}",
                "-i",
                str(video_path),
                "-vf",
                "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,setsar=1,fps=30",
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "20",
                "-pix_fmt",
                "yuv420p",
                str(segment_path),
            ],
            cwd=VIDEO_TRANSCRIPT_ROOT,
        )
        segment_paths.append(segment_path)

    concat_text = "\n".join(f"file '{path}'" for path in segment_paths) + "\n"
    concat_list.write_text(concat_text, encoding="utf-8")
    run_cmd(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_list),
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            str(montage_path),
        ],
        cwd=VIDEO_TRANSCRIPT_ROOT,
    )
    return montage_path


def build_story_pip_segments_from_pool(
    video_paths: list[Path],
    output_dir: Path,
    frame_total: int,
    clip_seconds: float = 10.0,
) -> list[Path]:
    if frame_total <= 0:
        return []
    if not video_paths:
        raise ValueError("video_paths cannot be empty when building PIP segments from a pool")

    segments_dir = output_dir / "story_pip_segments"
    segments_dir.mkdir(parents=True, exist_ok=True)

    segment_paths: list[Path] = []
    for index in range(frame_total):
        source_video = video_paths[index % len(video_paths)]
        duration = probe_video_duration(source_video)
        usable_clip = min(clip_seconds, max(3.5, duration))
        max_offset = max(0.0, duration - usable_clip - 0.1)

        cycle_index = index // len(video_paths)
        ratio = min(0.16 + cycle_index * 0.28, 0.76)
        offset = max_offset * ratio

        segment_path = segments_dir / f"story_pip_{index + 1:02d}.mp4"
        run_cmd(
            [
                "ffmpeg",
                "-y",
                "-ss",
                f"{offset:.2f}",
                "-t",
                f"{usable_clip:.2f}",
                "-i",
                str(source_video),
                "-vf",
                "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,setsar=1,fps=30",
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "20",
                "-pix_fmt",
                "yuv420p",
                str(segment_path),
            ],
            cwd=VIDEO_TRANSCRIPT_ROOT,
        )
        segment_paths.append(segment_path)

    return segment_paths


def build_story_pip_segments(
    source_video: Path,
    output_dir: Path,
    frame_total: int,
    clip_seconds: float = 10.0,
) -> list[Path]:
    if frame_total <= 0:
        return []

    segments_dir = output_dir / "story_pip_segments"
    segments_dir.mkdir(parents=True, exist_ok=True)

    duration = probe_video_duration(source_video)
    if duration <= 0:
        return [source_video for _ in range(frame_total)]

    usable_clip = min(clip_seconds, max(3.5, duration))
    max_offset = max(0.0, duration - usable_clip - 0.1)
    def sampling_ratios(total: int) -> list[float]:
        if total <= 0:
            return []
        if total == 1:
            return [0.04]

        # Keep the first chapter close to the opening, then use a low-discrepancy
        # sequence so adjacent chapters do not all pull from the same visual region.
        ratios = [0.04]
        golden = 0.61803398875
        for index in range(1, total):
            value = (0.17 + (index - 1) * golden) % 1.0
            ratios.append(0.12 + value * 0.80)
        return ratios

    chapter_ratios = sampling_ratios(frame_total)

    segment_paths: list[Path] = []
    for index in range(frame_total):
        center = min(chapter_ratios[index] * duration, duration - usable_clip / 2)
        offset = max(0.0, min(center - usable_clip / 2, max_offset))
        segment_path = segments_dir / f"story_pip_{index + 1:02d}.mp4"
        run_cmd(
            [
                "ffmpeg",
                "-y",
                "-ss",
                f"{offset:.2f}",
                "-t",
                f"{usable_clip:.2f}",
                "-i",
                str(source_video),
                "-vf",
                "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,setsar=1,fps=30",
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "20",
                "-pix_fmt",
                "yuv420p",
                str(segment_path),
            ],
            cwd=VIDEO_TRANSCRIPT_ROOT,
        )
        segment_paths.append(segment_path)

    return segment_paths


def load_transcript_bundle(output_dir: Path) -> tuple[dict, str]:
    metadata = json.loads((output_dir / "metadata.json").read_text(encoding="utf-8"))
    transcript_text = (output_dir / "raw_transcript.txt").read_text(encoding="utf-8")
    return metadata, transcript_text


def resolve_script(title: str | None, script_file: Path | None, metadata: dict, transcript_text: str) -> tuple[str, str]:
    if script_file:
        text = normalize_text(script_file.read_text(encoding="utf-8"))
        final_title = title or metadata.get("title") or "Short Video Recap"
        return final_title.strip(), text
    fallback_title, fallback_script = build_fallback_script(metadata, transcript_text)
    return (title or fallback_title).strip(), fallback_script


def build_newsroom_story_frames(
    metadata: dict,
    transcript_text: str,
    source_video: Path,
    output_dir: Path,
    story_mode: str,
    pip_sources: list[Path] | None = None,
) -> tuple[str, list[dict]]:
    sys.path.insert(0, str(NEWSROOM_BUILDER_DIR))
    try:
        from newsroom_story_builder import build_newsroom_story  # type: ignore
    finally:
        if str(NEWSROOM_BUILDER_DIR) in sys.path:
            sys.path.remove(str(NEWSROOM_BUILDER_DIR))

    chapter_count = 10 if story_mode == "newsroom-longform" else 6
    story = build_newsroom_story(metadata, transcript_text, chapter_count=chapter_count)
    frame_total = len(story["frames"])
    pip_box = (
        {"x": 582, "y": 112, "width": 458, "height": 836}
        if story_mode == "newsroom-longform"
        else {"x": 656, "y": 222, "width": 344, "height": 560}
    )
    resolved_pip_sources = [path for path in (pip_sources or [source_video]) if path.exists()]
    if len(resolved_pip_sources) > 1:
        pip_segments = build_story_pip_segments_from_pool(
            video_paths=resolved_pip_sources,
            output_dir=output_dir,
            frame_total=frame_total,
            clip_seconds=11.0 if story_mode == "newsroom-longform" else 8.0,
        )
    else:
        pip_segments = build_story_pip_segments(
            source_video=source_video,
            output_dir=output_dir,
            frame_total=frame_total,
            clip_seconds=11.0 if story_mode == "newsroom-longform" else 8.0,
        )
    story_frames = []
    for index, frame in enumerate(story["frames"]):
        story_frames.append(
            {
                "narration": frame["body"],
                "headline": frame["headline"],
                "source": frame["source"],
                "kicker": "科技解释" if story_mode == "newsroom-longform" else "科技简报",
                "pip_mode": frame.get("pip_mode", "support"),
                "pip_video_path": str(pip_segments[index]) if index < len(pip_segments) else str(source_video),
                "pip_box": pip_box,
                "template_context": {
                    "angle_title": frame.get("angle_title", ""),
                    "angle_body": frame.get("angle_body", ""),
                    "angle_note": frame.get("angle_note", ""),
                    "angle_fact": frame.get("angle_fact") or frame["body"].split("\n", 1)[0],
                    "angle_watch": frame.get("angle_watch", ""),
                    "frame_total": frame_total,
                    "chapter_slug": f"CHAPTER {index + 1:02d}",
                    "body_label": "这一章重点" if story_mode == "newsroom-longform" else "这一屏重点",
                },
            }
        )
    return story["title"], story_frames


def resolve_template_path(story_mode: str, template: str) -> str:
    if template != "1080x1920/static_newsroom_card.html":
        return template
    if story_mode == "newsroom":
        return "1080x1920/video_newsroom_latepost.html"
    if story_mode == "newsroom-longform":
        return "1080x1920/video_warroom_spacex_longform.html"
    return template


def write_payload_files(
    output_dir: Path,
    title: str,
    script_text: str,
    template: str,
    voice: str,
    tts_speed: float,
    story_frames: list[dict] | None = None,
) -> tuple[Path, Path]:
    script_path = output_dir / "pixelle_script.txt"
    payload_path = output_dir / "pixelle_payload.json"
    script_path.write_text(script_text.strip() + "\n", encoding="utf-8")
    payload = {
        "title": title,
        "text": script_text,
        "mode": "fixed",
        "split_mode": "paragraph",
        "frame_template": template,
        "tts_inference_mode": "local",
        "tts_voice": voice,
        "tts_speed": tts_speed,
    }
    if story_frames:
        payload["story_frames"] = story_frames
    payload_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return script_path, payload_path


async def render_with_pixelle(
    pixelle_repo: Path,
    title: str,
    script_text: str,
    output_video: Path,
    template: str,
    voice: str,
    tts_speed: float,
    story_frames: list[dict] | None = None,
) -> str:
    old_cwd = Path.cwd()
    os.chdir(pixelle_repo)
    try:
        sys.path.insert(0, str(pixelle_repo))
        pixelle_venv = pixelle_repo / ".venv" / "lib"
        if pixelle_venv.exists():
            for site_packages in pixelle_venv.glob("python*/site-packages"):
                site.addsitedir(str(site_packages))
        from pixelle_video import PixelleVideoCore  # type: ignore

        core = PixelleVideoCore(config_path="config.yaml")
        await core.initialize()
        try:
            result = await core.generate_video(
                text=script_text,
                mode="fixed",
                split_mode="paragraph",
                title=title,
                frame_template=template,
                tts_inference_mode="local",
                tts_voice=voice,
                tts_speed=tts_speed,
                pipeline="standard",
                output_path=str(output_video),
                story_frames=story_frames,
            )
            return result.video_path
        finally:
            await core.cleanup()
    finally:
        os.chdir(old_cwd)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Transcript -> Pixelle end-to-end pipeline")
    parser.add_argument("url", help="YouTube or Shorts URL")
    parser.add_argument("--output-dir", required=True, help="Directory for transcript and render artifacts")
    parser.add_argument("--pixelle-repo", default=str(PIXELLE_ROOT), help="Path to Pixelle-Video repo")
    parser.add_argument("--script-file", help="Optional manual fixed-script file")
    parser.add_argument("--title", help="Optional video title override")
    parser.add_argument("--template", default="1080x1920/static_newsroom_card.html", help="Pixelle frame template")
    parser.add_argument("--voice", default="zh-CN-YunjianNeural", help="Edge TTS voice")
    parser.add_argument("--tts-speed", type=float, help="Optional TTS speed multiplier override")
    parser.add_argument("--final-name", default="final_short.mp4", help="Final video filename")
    parser.add_argument("--story-mode", choices=["fixed", "newsroom", "newsroom-longform"], default="fixed", help="Output story mode")
    parser.add_argument("--pip-url", action="append", default=[], help="Additional YouTube/Shorts URLs to build a PIP montage from")
    parser.add_argument("--pip-file", action="append", default=[], help="Additional local video files to build chapter PIP clips from")
    parser.add_argument("--pip-clip-seconds", type=float, default=7.0, help="Seconds to sample from each PIP clip when building a montage")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir).expanduser().resolve()
    pixelle_repo = Path(args.pixelle_repo).expanduser().resolve()
    script_file = Path(args.script_file).expanduser().resolve() if args.script_file else None
    template = resolve_template_path(args.story_mode, args.template)
    tts_speed = args.tts_speed if args.tts_speed is not None else (1.0 if args.story_mode == "newsroom-longform" else 1.2)

    ensure_transcript(args.url, output_dir)
    metadata, transcript_text = load_transcript_bundle(output_dir)
    story_frames = None
    if args.story_mode in {"newsroom", "newsroom-longform"}:
        source_video = ensure_source_video(args.url, output_dir)
        support_videos: list[Path] = []
        if args.pip_url:
            support_videos.extend(ensure_pip_support_videos(args.pip_url, output_dir))
        if args.pip_file:
            support_videos.extend(resolve_pip_support_files(args.pip_file))
        pip_sources = select_story_pip_sources(source_video, support_videos)
        deduped_pip_sources: list[Path] = []
        seen_sources: set[Path] = set()
        for source in pip_sources:
            if source in seen_sources:
                continue
            seen_sources.add(source)
            deduped_pip_sources.append(source)
        title, story_frames = build_newsroom_story_frames(
            metadata,
            transcript_text,
            source_video,
            output_dir,
            args.story_mode,
            pip_sources=deduped_pip_sources,
        )
        if args.title:
            title = args.title.strip()
        script_text = "\n\n".join(frame["narration"] for frame in story_frames)
    else:
        title, script_text = resolve_script(args.title, script_file, metadata, transcript_text)
    script_path, payload_path = write_payload_files(
        output_dir,
        title,
        script_text,
        template,
        args.voice,
        tts_speed,
        story_frames=story_frames,
    )

    final_video = output_dir / args.final_name
    result_path = asyncio.run(
        render_with_pixelle(
            pixelle_repo=pixelle_repo,
            title=title,
            script_text=script_text,
            output_video=final_video,
            template=template,
            voice=args.voice,
            tts_speed=tts_speed,
            story_frames=story_frames,
        )
    )

    print(f"Transcript directory: {output_dir}")
    print(f"Script file: {script_path}")
    print(f"Payload file: {payload_path}")
    print(f"Final video: {result_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
