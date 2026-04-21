#!/usr/bin/env python3
"""
Extract transcript from a video URL.

Tries in order:
1. Manual/human subtitles via yt-dlp
2. Auto-generated captions via yt-dlp
3. Audio download + Whisper transcription

Produces timestamped segments, section-split output with TOC timestamps,
and optional visual summaries (ffmpeg frame capture or DALL-E fallback).

Usage:
    python extract_transcript.py <video-url> [--output-dir ./output] [--whisper-model medium]
    python extract_transcript.py <video-url> --no-images --no-timestamps
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


def run_cmd(cmd: list[str], check: bool = True, capture: bool = True) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    try:
        return subprocess.run(cmd, check=check, capture_output=capture, text=True)
    except FileNotFoundError:
        print(f"Error: '{cmd[0]}' not found. Please install it first.", file=sys.stderr)
        sys.exit(1)


def get_video_info(url: str) -> dict:
    """Get video metadata via yt-dlp."""
    result = run_cmd([
        "yt-dlp", "--dump-json", "--no-download", url
    ])
    return json.loads(result.stdout)


def list_subtitles(url: str) -> dict:
    """List available subtitles."""
    result = run_cmd(["yt-dlp", "--list-subs", "--no-download", url], check=False)
    return result.stdout


def download_subtitles(url: str, output_dir: Path) -> Path | None:
    """Try to download subtitles. Returns path to subtitle file or None."""
    lang_priority = ["en", "zh-Hans", "zh", "ja", "ko", "fr", "de", "es", "ru", "pt", "ar"]
    lang_str = ",".join(lang_priority)

    # Try manual subtitles first
    for write_flag in ["--write-sub", "--write-auto-sub"]:
        result = run_cmd([
            "yt-dlp",
            write_flag,
            "--sub-lang", lang_str,
            "--skip-download",
            "--sub-format", "vtt/srt/best",
            "-o", str(output_dir / "subtitle"),
            url
        ], check=False)

        # Find downloaded subtitle file
        for ext in [".vtt", ".srt", ".ass", ".ssa"]:
            for f in output_dir.glob(f"subtitle*{ext}"):
                if f.stat().st_size > 0:
                    return f

    return None


def clean_vtt(text: str) -> str:
    """Clean VTT/SRT subtitle text into plain transcript."""
    lines = text.split("\n")
    cleaned = []
    prev_line = ""

    for line in lines:
        line = line.strip()

        # Skip VTT header
        if line.startswith("WEBVTT") or line.startswith("Kind:") or line.startswith("Language:"):
            continue

        # Skip sequence numbers (SRT format)
        if re.match(r"^\d+$", line):
            continue

        # Skip timestamp lines
        if re.match(r"^\d{2}:\d{2}:\d{2}", line) or "-->" in line:
            continue

        # Skip empty lines
        if not line:
            if cleaned and cleaned[-1] != "":
                cleaned.append("")
            continue

        # Remove HTML/formatting tags
        line = re.sub(r"<[^>]+>", "", line)
        line = re.sub(r"\{[^}]+\}", "", line)  # ASS format tags

        # Remove position/alignment markers
        line = re.sub(r"align:start position:\d+%", "", line)
        line = re.sub(r"^\s*-\s*", "", line)  # Leading dashes in some formats

        line = line.strip()

        # Skip duplicates (common in auto-generated subs)
        if line and line != prev_line:
            cleaned.append(line)
            prev_line = line

    # Join lines into paragraphs
    result = "\n".join(cleaned)

    # Merge lines that are part of the same sentence
    result = re.sub(r"(?<![.!?。！？\n])\n(?!\n)", " ", result)

    # Clean up multiple blank lines
    result = re.sub(r"\n{3,}", "\n\n", result)

    return result.strip()


def _parse_timestamp_to_seconds(ts: str) -> float:
    """Convert VTT/SRT timestamp string to seconds.

    Accepts formats like:
      00:01:23.456  (HH:MM:SS.mmm)
      00:01:23,456  (SRT style)
      01:23.456     (MM:SS.mmm)
    """
    ts = ts.replace(",", ".")
    parts = ts.strip().split(":")
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    elif len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    return 0.0


def parse_vtt_with_timestamps(text: str) -> list[dict]:
    """Parse VTT/SRT text and return structured segments with timestamps.

    Returns:
        List of {"start": float, "end": float, "text": str}
    """
    segments = []
    lines = text.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # Look for timestamp lines: "00:00:01.000 --> 00:00:04.000"
        arrow_match = re.match(
            r"(\d{1,2}:\d{2}:\d{2}[.,]\d{2,3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[.,]\d{2,3})",
            line,
        )
        if arrow_match:
            start = _parse_timestamp_to_seconds(arrow_match.group(1))
            end = _parse_timestamp_to_seconds(arrow_match.group(2))

            # Collect text lines until blank line or next timestamp
            i += 1
            cue_lines = []
            while i < len(lines) and lines[i].strip():
                cue_text = lines[i].strip()
                # Skip if it's a sequence number or another timestamp
                if re.match(r"^\d+$", cue_text):
                    i += 1
                    continue
                if "-->" in cue_text:
                    break
                # Remove HTML/ASS tags
                cue_text = re.sub(r"<[^>]+>", "", cue_text)
                cue_text = re.sub(r"\{[^}]+\}", "", cue_text)
                cue_text = re.sub(r"align:start position:\d+%", "", cue_text)
                cue_text = re.sub(r"^\s*-\s*", "", cue_text)
                cue_text = cue_text.strip()
                if cue_text:
                    cue_lines.append(cue_text)
                i += 1

            text_content = " ".join(cue_lines)
            if text_content:
                # Deduplicate: skip if identical to previous segment
                if segments and segments[-1]["text"] == text_content:
                    i += 1 if i < len(lines) else 0
                    continue
                segments.append({"start": start, "end": end, "text": text_content})
            continue

        i += 1

    return segments


def clean_vtt_with_timestamps(text: str) -> tuple[str, list[dict]]:
    """Clean VTT/SRT text and return both plain text and timestamped segments.

    Returns:
        (plain_text, segments) where segments is list of {"start", "end", "text"}
    """
    segments = parse_vtt_with_timestamps(text)
    plain_text = clean_vtt(text)
    return plain_text, segments


def download_audio(url: str, output_dir: Path) -> Path:
    """Download audio from video."""
    output_path = output_dir / "audio.wav"
    run_cmd([
        "yt-dlp",
        "-x", "--audio-format", "wav",
        "--audio-quality", "0",
        "-o", str(output_dir / "audio.%(ext)s"),
        url
    ])

    # Find the audio file (yt-dlp might use different extension)
    for ext in [".wav", ".mp3", ".m4a", ".webm", ".ogg"]:
        candidate = output_dir / f"audio{ext}"
        if candidate.exists():
            return candidate

    raise FileNotFoundError("Audio download failed - no audio file found")


def transcribe_whisper_local(audio_path: Path, output_dir: Path, model: str = "medium") -> tuple[str, list[dict]]:
    """Transcribe audio using local Whisper. Returns (text, segments)."""
    # Use JSON output to get timestamps
    # Omit --language to let Whisper auto-detect
    result = run_cmd([
        "whisper",
        str(audio_path),
        "--model", model,
        "--output_format", "json",
        "--output_dir", str(output_dir),
    ], check=False)

    json_file = output_dir / f"{audio_path.stem}.json"
    segments = []
    text = ""

    if json_file.exists():
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            text = data.get("text", "")
            for seg in data.get("segments", []):
                segments.append({
                    "start": seg.get("start", 0.0),
                    "end": seg.get("end", 0.0),
                    "text": seg.get("text", "").strip(),
                })
        except (json.JSONDecodeError, KeyError):
            pass

    # Fallback to txt output if JSON parsing failed
    if not text:
        txt_file = output_dir / f"{audio_path.stem}.txt"
        if txt_file.exists():
            text = txt_file.read_text(encoding="utf-8")
        elif result.stdout:
            text = result.stdout

    return text, segments


def transcribe_whisper_api(audio_path: Path) -> tuple[str, list[dict]]:
    """Transcribe audio using OpenAI Whisper API. Returns (text, segments)."""
    try:
        from openai import OpenAI
    except ImportError:
        print("Error: openai package not installed. Run: pip install openai", file=sys.stderr)
        sys.exit(1)

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY not set.", file=sys.stderr)
        sys.exit(1)

    client = OpenAI(api_key=api_key)

    # Split large files (Whisper API has 25MB limit)
    file_size = audio_path.stat().st_size
    if file_size > 24 * 1024 * 1024:
        print("Audio file is large. Consider using local Whisper for files >25MB.", file=sys.stderr)

    with open(audio_path, "rb") as f:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            response_format="verbose_json",
            timestamp_granularities=["segment"],
        )

    text = transcript.text if hasattr(transcript, "text") else str(transcript)
    segments = []
    if hasattr(transcript, "segments") and transcript.segments:
        for seg in transcript.segments:
            segments.append({
                "start": getattr(seg, "start", 0.0),
                "end": getattr(seg, "end", 0.0),
                "text": getattr(seg, "text", "").strip(),
            })

    return text, segments


def detect_language(text: str) -> str:
    """Simple language detection from text content."""
    # Count Chinese characters
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text[:1000]))
    total_chars = len(text[:1000])

    if total_chars == 0:
        return "unknown"

    if chinese_chars / total_chars > 0.3:
        return "zh"

    # Check for other CJK
    japanese_chars = len(re.findall(r"[\u3040-\u309f\u30a0-\u30ff]", text[:1000]))
    if japanese_chars / total_chars > 0.1:
        return "ja"

    korean_chars = len(re.findall(r"[\uac00-\ud7af]", text[:1000]))
    if korean_chars / total_chars > 0.1:
        return "ko"

    return "en"  # Default to English for Latin-script languages


def main():
    parser = argparse.ArgumentParser(description="Extract transcript from video URL")
    parser.add_argument("url", help="Video URL (YouTube, Bilibili, etc.)")
    parser.add_argument("--output-dir", default="./output", help="Output directory")
    parser.add_argument("--whisper-model", default="medium", help="Whisper model size")
    parser.add_argument("--prefer-api", action="store_true", help="Prefer OpenAI API over local Whisper")
    parser.add_argument("--no-images", action="store_true", help="Skip image capture/generation")
    parser.add_argument("--no-timestamps", action="store_true", help="Use old behavior without timestamps")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Fetching video info from: {args.url}")
    try:
        info = get_video_info(args.url)
        title = info.get("title", "untitled")
        duration = info.get("duration", 0)
        print(f"Title: {title}")
        print(f"Duration: {duration // 60}m {duration % 60}s")
    except Exception as e:
        print(f"Warning: Could not fetch video info: {e}", file=sys.stderr)
        title = "untitled"
        duration = 0
        info = {}

    # Save metadata
    metadata = {
        "url": args.url,
        "title": title,
        "duration": info.get("duration"),
        "uploader": info.get("uploader"),
        "upload_date": info.get("upload_date"),
        "platform": info.get("extractor", "unknown"),
    }
    (output_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2))

    # Step 1: Try subtitles
    transcript = ""
    segments = []
    method = ""

    print("\n--- Attempting subtitle extraction ---")
    with tempfile.TemporaryDirectory() as tmpdir:
        sub_path = download_subtitles(args.url, Path(tmpdir))

        if sub_path:
            print(f"Found subtitles: {sub_path.name}")
            raw_text = sub_path.read_text(encoding="utf-8", errors="replace")
            transcript, segments = clean_vtt_with_timestamps(raw_text)
            method = "subtitles"
        else:
            print("No subtitles found. Falling back to audio transcription...")

            # Download audio
            print("\n--- Downloading audio ---")
            audio_path = download_audio(args.url, output_dir)
            print(f"Audio saved: {audio_path}")

            # Transcribe
            print("\n--- Transcribing with Whisper ---")
            if args.prefer_api and os.environ.get("OPENAI_API_KEY"):
                print("Using OpenAI Whisper API...")
                transcript, segments = transcribe_whisper_api(audio_path)
                method = "whisper-api"
            else:
                print(f"Using local Whisper (model: {args.whisper_model})...")
                transcript, segments = transcribe_whisper_local(audio_path, output_dir, args.whisper_model)
                method = "whisper-local"

    if not transcript.strip():
        print("Error: Failed to extract any transcript.", file=sys.stderr)
        sys.exit(1)

    # Detect language
    lang = detect_language(transcript)
    print(f"\nDetected language: {lang}")
    print(f"Extraction method: {method}")
    print(f"Transcript length: {len(transcript)} characters")
    print(f"Timestamped segments: {len(segments)}")

    # Save raw transcript
    raw_output = output_dir / "raw_transcript.txt"
    raw_output.write_text(transcript, encoding="utf-8")
    print(f"\nRaw transcript saved to: {raw_output}")

    # Step 2: Save timestamped segments
    if segments and not args.no_timestamps:
        ts_output = output_dir / "timestamped_transcript.json"
        ts_output.write_text(
            json.dumps({"segments": segments}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"Timestamped transcript saved to: {ts_output}")

        # Step 3: Split into sections
        print("\n--- Splitting into sections ---")
        from section_splitter import split_into_sections, format_timestamp
        sections = split_into_sections(segments)
        sections_output = output_dir / "sections.json"
        sections_output.write_text(
            json.dumps({"sections": sections}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"Split into {len(sections)} sections → {sections_output}")
    else:
        sections = []

    # Step 4: Capture visual summaries
    image_map = {}
    if not args.no_images and sections:
        print("\n--- Capturing visual summaries ---")
        from capture_frames import download_video, capture_section_frames, generate_section_images

        images_dir = output_dir / "images"

        # Try downloading video for frame capture
        video_path = download_video(args.url, output_dir)
        if video_path:
            image_map = capture_section_frames(video_path, sections, images_dir)

        # DALL-E fallback for sections without frames
        missing = [s for s in sections if s["section_number"] not in image_map]
        if missing and os.environ.get("OPENAI_API_KEY"):
            print(f"Generating AI images for {len(missing)} sections without frames...")
            ai_images = generate_section_images(missing, images_dir)
            image_map.update(ai_images)

        if image_map:
            print(f"Visual summaries: {len(image_map)}/{len(sections)} sections")

    # Step 5: Build enhanced Markdown output
    if sections and not args.no_timestamps:
        print("\n--- Building enhanced Markdown output ---")
        md_lines = _build_markdown_with_timestamps(
            title=title,
            url=args.url,
            info=info,
            duration=duration,
            sections=sections,
            image_map=image_map,
        )
        md_output = output_dir / "transcript_enhanced.md"
        md_output.write_text("\n".join(md_lines), encoding="utf-8")
        print(f"Enhanced Markdown saved to: {md_output}")

    # Save extraction info
    extraction_info = {
        **metadata,
        "method": method,
        "language": lang,
        "char_count": len(transcript),
        "word_count": len(transcript.split()),
        "segment_count": len(segments),
        "section_count": len(sections),
        "images_captured": len(image_map),
    }
    (output_dir / "extraction_info.json").write_text(
        json.dumps(extraction_info, ensure_ascii=False, indent=2)
    )

    print(f"\n--- Done! ---")
    print(f"Output directory: {output_dir}")
    files = ["metadata.json", "raw_transcript.txt", "extraction_info.json"]
    if segments and not args.no_timestamps:
        files.extend(["timestamped_transcript.json", "sections.json", "transcript_enhanced.md"])
    if image_map:
        files.append("images/")
    print(f"Files: {', '.join(files)}")
    print(f"\nNext: Use Claude to structure, translate (if needed), and format the transcript.")


def _build_markdown_with_timestamps(
    title: str,
    url: str,
    info: dict,
    duration: int,
    sections: list[dict],
    image_map: dict,
) -> list[str]:
    """Build Markdown output with timestamp TOC and section images."""
    from section_splitter import format_timestamp

    lines = []
    lines.append(f"# {title}")
    lines.append("")

    # Metadata block
    lines.append(f"> **Source**: {url}")
    uploader = info.get("uploader", "")
    if uploader:
        lines.append(f"> **Speaker**: {uploader}")
    upload_date = info.get("upload_date", "")
    if upload_date:
        # Format YYYYMMDD → YYYY-MM-DD
        if len(upload_date) == 8:
            upload_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"
        lines.append(f"> **Date**: {upload_date}")
    if duration:
        lines.append(f"> **Duration**: {format_timestamp(duration)}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Table of Contents with timestamps
    lines.append("## Table of Contents")
    lines.append("")
    for section in sections:
        anchor = _heading_to_anchor(section["title"])
        ts = section["timestamp_display"]
        lines.append(f"- [{section['title']}](#{anchor}) `[{ts}]`")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Sections with timestamps and images
    for section in sections:
        ts = section["timestamp_display"]
        lines.append(f"## {section['title']} `[{ts}]`")
        lines.append("")

        # Image if available
        sec_num = section["section_number"]
        if sec_num in image_map:
            img_path = image_map[sec_num]
            # Use relative path from output dir
            rel_path = f"images/{Path(img_path).name}"
            lines.append(f"![Section {sec_num} Summary]({rel_path})")
            lines.append("")

        lines.append(section["text"])
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("*Transcript extracted and formatted by Video Transcript Skill*")

    return lines


def _heading_to_anchor(heading: str) -> str:
    """Convert a heading to a Markdown anchor ID."""
    anchor = heading.lower().strip()
    anchor = re.sub(r"[^\w\s-]", "", anchor)
    anchor = re.sub(r"[\s]+", "-", anchor)
    return anchor


if __name__ == "__main__":
    main()
