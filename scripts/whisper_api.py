#!/usr/bin/env python3
"""
Transcribe audio using the OpenAI Whisper API.

Handles files larger than 25MB by splitting into chunks.

Usage:
    python whisper_api.py audio.wav [--output transcript.txt]
"""

import argparse
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from openai import OpenAI
except ImportError:
    print("Error: openai package not installed. Run: pip install openai", file=sys.stderr)
    sys.exit(1)


MAX_FILE_SIZE = 24 * 1024 * 1024  # 24MB (leave margin from 25MB limit)
CHUNK_DURATION_SECONDS = 600  # 10 minutes per chunk


def get_audio_duration(audio_path: Path) -> float:
    """Get audio duration in seconds using ffprobe."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)],
            capture_output=True, text=True, check=True
        )
        return float(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
        return 0


def split_audio(audio_path: Path, chunk_dir: Path, chunk_seconds: int = CHUNK_DURATION_SECONDS) -> list[Path]:
    """Split audio into chunks using ffmpeg."""
    duration = get_audio_duration(audio_path)
    if duration <= 0:
        return [audio_path]

    num_chunks = math.ceil(duration / chunk_seconds)
    if num_chunks <= 1:
        return [audio_path]

    chunks = []
    for i in range(num_chunks):
        start = i * chunk_seconds
        chunk_path = chunk_dir / f"chunk_{i:03d}.wav"
        subprocess.run([
            "ffmpeg", "-y", "-i", str(audio_path),
            "-ss", str(start), "-t", str(chunk_seconds),
            "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
            str(chunk_path)
        ], capture_output=True, check=True)
        if chunk_path.exists() and chunk_path.stat().st_size > 0:
            chunks.append(chunk_path)

    return chunks


def transcribe_file(client: OpenAI, audio_path: Path) -> str:
    """Transcribe a single audio file."""
    with open(audio_path, "rb") as f:
        result = client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            response_format="text"
        )
    return result


def main():
    parser = argparse.ArgumentParser(description="Transcribe audio via OpenAI Whisper API")
    parser.add_argument("audio", help="Path to audio file")
    parser.add_argument("--output", "-o", default=None, help="Output text file")
    args = parser.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable not set.", file=sys.stderr)
        print("Set it with: export OPENAI_API_KEY='your-key-here'", file=sys.stderr)
        sys.exit(1)

    audio_path = Path(args.audio)
    if not audio_path.exists():
        print(f"Error: File not found: {audio_path}", file=sys.stderr)
        sys.exit(1)

    client = OpenAI(api_key=api_key)
    file_size = audio_path.stat().st_size

    if file_size <= MAX_FILE_SIZE:
        print(f"Transcribing {audio_path.name} ({file_size / 1024 / 1024:.1f} MB)...")
        transcript = transcribe_file(client, audio_path)
    else:
        print(f"File is {file_size / 1024 / 1024:.1f} MB (>{MAX_FILE_SIZE / 1024 / 1024:.0f} MB). Splitting into chunks...")
        with tempfile.TemporaryDirectory() as tmpdir:
            chunks = split_audio(audio_path, Path(tmpdir))
            print(f"Split into {len(chunks)} chunks.")

            parts = []
            for i, chunk in enumerate(chunks):
                print(f"  Transcribing chunk {i + 1}/{len(chunks)}...")
                parts.append(transcribe_file(client, chunk))

            transcript = "\n\n".join(parts)

    # Output
    output_path = args.output or str(audio_path.with_suffix(".txt"))
    Path(output_path).write_text(transcript, encoding="utf-8")
    print(f"\nTranscript saved to: {output_path}")
    print(f"Length: {len(transcript)} characters, {len(transcript.split())} words")


if __name__ == "__main__":
    main()
