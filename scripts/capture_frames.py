#!/usr/bin/env python3
"""
Capture video frames at specific timestamps for section visual summaries.

Primary: ffmpeg frame extraction from downloaded video.
Fallback: AI-generated summary images via OpenAI DALL-E.

Usage:
    python capture_frames.py --video video.mp4 --sections sections.json --output-dir ./images
    python capture_frames.py --sections sections.json --output-dir ./images --dalle-fallback
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def capture_frame(video_path: str | Path, timestamp_seconds: float, output_path: str | Path) -> Path | None:
    """
    Capture a single frame from a video at the given timestamp.

    Uses ffmpeg to extract one JPEG frame.
    Returns the output path on success, None on failure.
    """
    video_path = Path(video_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-ss", str(timestamp_seconds),
                "-i", str(video_path),
                "-vframes", "1",
                "-q:v", "2",
                str(output_path),
            ],
            capture_output=True,
            check=True,
        )
        if output_path.exists() and output_path.stat().st_size > 0:
            return output_path
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"Warning: Frame capture failed at {timestamp_seconds}s: {e}", file=sys.stderr)

    return None


def capture_section_frames(
    video_path: str | Path,
    sections: list[dict],
    output_dir: str | Path,
    offset: float = 5.0,
) -> dict[int, Path]:
    """
    Capture a representative frame for each section.

    Args:
        video_path: Path to the video file.
        sections: List of section dicts with "section_number" and "start_time".
        output_dir: Directory to save captured frames.
        offset: Seconds to add to start_time to skip intro/transition frames.

    Returns:
        Dict mapping section_number → image path.
    """
    video_path = Path(video_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    results = {}
    for section in sections:
        num = section["section_number"]
        start = section.get("start_time", 0.0)
        end = section.get("end_time", start + 60)
        # Capture at start_time + offset, but don't exceed end_time
        ts = min(start + offset, end)

        img_path = output_dir / f"section_{num:02d}.jpg"
        result = capture_frame(video_path, ts, img_path)
        if result:
            results[num] = result
            print(f"  Captured frame for section {num} at {ts:.1f}s → {img_path.name}")
        else:
            print(f"  Failed to capture frame for section {num}", file=sys.stderr)

    return results


def download_video(url: str, output_dir: str | Path) -> Path | None:
    """
    Download video at lowest quality sufficient for screenshots.

    Returns video path or None if download fails.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "video.mp4"

    try:
        subprocess.run(
            [
                "yt-dlp",
                "-f", "worst[ext=mp4]/worst",
                "-o", str(output_path),
                url,
            ],
            capture_output=True,
            check=True,
        )
        if output_path.exists() and output_path.stat().st_size > 0:
            print(f"Video downloaded: {output_path}")
            return output_path
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"Warning: Video download failed: {e}", file=sys.stderr)

    return None


def generate_section_image(section_text: str, output_path: str | Path) -> Path | None:
    """
    Generate a concept image for a section using OpenAI DALL-E.

    Requires OPENAI_API_KEY environment variable.
    Returns image path or None on failure.
    """
    try:
        from openai import OpenAI
    except ImportError:
        print("Warning: openai package not installed. Cannot generate images.", file=sys.stderr)
        return None

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Warning: OPENAI_API_KEY not set. Cannot generate images.", file=sys.stderr)
        return None

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Condense the section text into a visual description
    # Take first 500 chars as context for the prompt
    snippet = section_text[:500].strip()
    prompt = (
        f"A clean, professional illustration summarizing this topic: {snippet}. "
        "Minimal design, soft colors, no text overlays."
    )
    # DALL-E prompt limit is 1000 chars
    prompt = prompt[:1000]

    try:
        client = OpenAI(api_key=api_key)
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1792x1024",
            quality="standard",
            n=1,
        )

        image_url = response.data[0].url
        # Download the image
        import urllib.request
        urllib.request.urlretrieve(image_url, str(output_path))

        if output_path.exists() and output_path.stat().st_size > 0:
            print(f"  Generated image → {output_path.name}")
            return output_path
    except Exception as e:
        print(f"Warning: DALL-E image generation failed: {e}", file=sys.stderr)

    return None


def generate_section_images(
    sections: list[dict],
    output_dir: str | Path,
) -> dict[int, Path]:
    """
    Generate AI images for each section as fallback.

    Returns dict mapping section_number → image path.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    results = {}
    for section in sections:
        num = section["section_number"]
        text = section.get("text", "")
        if not text:
            continue

        img_path = output_dir / f"section_{num:02d}.jpg"
        result = generate_section_image(text, img_path)
        if result:
            results[num] = result

    return results


def main():
    parser = argparse.ArgumentParser(description="Capture video frames for section summaries")
    parser.add_argument("--video", default=None, help="Path to video file")
    parser.add_argument("--url", default=None, help="Video URL (will download)")
    parser.add_argument("--sections", required=True, help="Path to sections.json")
    parser.add_argument("--output-dir", default="./images", help="Output directory for images")
    parser.add_argument("--dalle-fallback", action="store_true", help="Use DALL-E if frame capture fails")
    args = parser.parse_args()

    sections_path = Path(args.sections)
    if not sections_path.exists():
        print(f"Error: Sections file not found: {sections_path}", file=sys.stderr)
        sys.exit(1)

    data = json.loads(sections_path.read_text(encoding="utf-8"))
    sections = data.get("sections", data if isinstance(data, list) else [])

    output_dir = Path(args.output_dir)

    video_path = None
    if args.video:
        video_path = Path(args.video)
        if not video_path.exists():
            print(f"Warning: Video file not found: {video_path}", file=sys.stderr)
            video_path = None
    elif args.url:
        print("Downloading video for frame capture...")
        video_path = download_video(args.url, output_dir.parent)

    image_map = {}
    if video_path:
        print("Capturing frames from video...")
        image_map = capture_section_frames(video_path, sections, output_dir)

    # Fallback to DALL-E for sections without frames
    if args.dalle_fallback:
        missing = [s for s in sections if s["section_number"] not in image_map]
        if missing:
            print(f"Generating AI images for {len(missing)} sections without frames...")
            ai_images = generate_section_images(missing, output_dir)
            image_map.update(ai_images)

    # Save image map
    serializable = {str(k): str(v) for k, v in image_map.items()}
    map_path = output_dir / "image_map.json"
    map_path.parent.mkdir(parents=True, exist_ok=True)
    map_path.write_text(json.dumps(serializable, indent=2), encoding="utf-8")

    print(f"\nCaptured {len(image_map)} images → {output_dir}")
    if len(image_map) < len(sections):
        print(f"  ({len(sections) - len(image_map)} sections have no image)")


if __name__ == "__main__":
    main()
