#!/usr/bin/env python3
"""
Split timestamped transcript segments into logical sections.

Input: timestamped_transcript.json (list of segments with start/end/text)
Output: List of sections with timestamps, titles, and merged text

Usage:
    python section_splitter.py timestamped_transcript.json [--output sections.json]
"""

import argparse
import json
import re
import sys
from pathlib import Path


# Topic transition signals (case-insensitive)
TRANSITION_PHRASES = [
    r"\bnow let'?s\b",
    r"\bmoving on\b",
    r"\bnext\b",
    r"\blet'?s talk about\b",
    r"\blet'?s look at\b",
    r"\blet'?s move\b",
    r"\bthe next\b",
    r"\bturning to\b",
    r"\banother\b.*\btopic\b",
    r"\bso\b.*\bwhat about\b",
    r"\bin this section\b",
    r"\b接下来\b",
    r"\b下面\b",
    r"\b我们来看\b",
    r"\b然后\b.*\b讲\b",
]

# Minimum pause (seconds) to consider as a topic break
PAUSE_THRESHOLD = 3.0

# Target words per section
MIN_WORDS_PER_SECTION = 300
MAX_WORDS_PER_SECTION = 600


def format_timestamp(seconds: float) -> str:
    """Convert seconds to HH:MM:SS display format."""
    seconds = max(0, int(seconds))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def _word_count(text: str) -> int:
    """Count words in text, handling both CJK and Latin scripts."""
    # Count CJK characters as individual "words"
    cjk_chars = len(re.findall(r"[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af]", text))
    # Count space-separated words for Latin text
    latin_text = re.sub(r"[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af]", " ", text)
    latin_words = len(latin_text.split())
    return cjk_chars + latin_words


def _has_transition_phrase(text: str) -> bool:
    """Check if text contains a topic transition phrase."""
    for pattern in TRANSITION_PHRASES:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def _is_sentence_boundary(text: str) -> bool:
    """Check if text ends at a sentence boundary."""
    return bool(re.search(r"[.!?。！？][\s\"'）)]*$", text.strip()))


def split_into_sections(
    segments: list[dict],
    min_words: int = MIN_WORDS_PER_SECTION,
    max_words: int = MAX_WORDS_PER_SECTION,
) -> list[dict]:
    """
    Split timestamped segments into logical sections.

    Args:
        segments: List of {"start": float, "end": float, "text": str}
        min_words: Minimum words per section before allowing a split
        max_words: Maximum words per section before forcing a split

    Returns:
        List of section dicts with section_number, start_time, end_time,
        text, timestamp_display, and a placeholder title.
    """
    if not segments:
        return []

    sections = []
    current_segments = []
    current_word_count = 0
    section_number = 0

    for i, seg in enumerate(segments):
        text = seg.get("text", "").strip()
        if not text:
            continue

        seg_words = _word_count(text)
        current_segments.append(seg)
        current_word_count += seg_words

        # Determine if we should split here
        should_split = False

        # Check for long pause before next segment (topic break)
        if i + 1 < len(segments):
            gap = segments[i + 1].get("start", 0) - seg.get("end", 0)
            if gap >= PAUSE_THRESHOLD and current_word_count >= min_words:
                should_split = True

        # Check for transition phrase at start of next segment
        if (
            i + 1 < len(segments)
            and current_word_count >= min_words
            and _has_transition_phrase(segments[i + 1].get("text", ""))
        ):
            should_split = True

        # Force split if we've exceeded max words at a sentence boundary
        if current_word_count >= max_words and _is_sentence_boundary(text):
            should_split = True

        # Hard split if well over max
        if current_word_count >= max_words * 1.5:
            should_split = True

        # Last segment — always finalize
        if i == len(segments) - 1:
            should_split = True

        if should_split and current_segments:
            section_number += 1
            start_time = current_segments[0].get("start", 0.0)
            end_time = current_segments[-1].get("end", start_time)
            merged_text = " ".join(s.get("text", "").strip() for s in current_segments)
            # Clean up double spaces
            merged_text = re.sub(r"  +", " ", merged_text).strip()

            sections.append({
                "section_number": section_number,
                "title": f"Section {section_number}",
                "start_time": start_time,
                "end_time": end_time,
                "text": merged_text,
                "timestamp_display": format_timestamp(start_time),
            })

            current_segments = []
            current_word_count = 0

    return sections


def main():
    parser = argparse.ArgumentParser(description="Split timestamped transcript into sections")
    parser.add_argument("input", help="Path to timestamped_transcript.json")
    parser.add_argument("--output", "-o", default=None, help="Output JSON file")
    parser.add_argument("--min-words", type=int, default=MIN_WORDS_PER_SECTION)
    parser.add_argument("--max-words", type=int, default=MAX_WORDS_PER_SECTION)
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: File not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    data = json.loads(input_path.read_text(encoding="utf-8"))
    segments = data.get("segments", data if isinstance(data, list) else [])

    sections = split_into_sections(segments, args.min_words, args.max_words)

    output_path = args.output or str(input_path.with_name("sections.json"))
    Path(output_path).write_text(
        json.dumps({"sections": sections}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Split into {len(sections)} sections → {output_path}")


if __name__ == "__main__":
    main()
