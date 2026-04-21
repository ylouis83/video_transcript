---
name: video-transcript
description: >
  Extract transcripts from video URLs and produce publication-ready bilingual lecture scripts.
  Use this skill whenever a user provides a video link (YouTube, Bilibili, TikTok/Douyin, Vimeo,
  or any platform supported by yt-dlp) and wants: a text transcript, lecture notes, subtitles
  extraction, speech-to-text from video, a written version of a talk, translated lecture scripts,
  or bilingual transcripts. Also trigger when the user pastes a video URL and asks to "write out
  what they said", "get the transcript", "turn this video into a document", or similar requests
  even if they don't explicitly mention "transcript".
---

# Video Transcript Skill

Extract spoken content from any video URL and produce beautifully formatted, publication-ready
lecture scripts. When the source language is not Chinese, automatically produce both the original
language version and a Chinese translation.

## Workflow Overview

```
Video URL
  |
  v
1. Download subtitles/captions (yt-dlp) — preserve timestamps
  |-- Found?  --> Parse with timestamps
  |-- Not found? --> Download audio --> Whisper transcription (with timestamps)
  |
  v
2. Structure the raw transcript
  |-- Detect language
  |-- Split into logical sections (by topic/timestamps)
  |-- Map each section to its starting timestamp
  |-- Add headings and paragraph breaks
  |
  v
2.5. Capture Visual Summaries
  |-- Try: download video → ffmpeg frame capture at each section timestamp
  |-- Fallback: generate concept images via DALL-E (requires OPENAI_API_KEY)
  |-- Skip with --no-images flag
  |
  v
3. If non-Chinese source:
  |-- Produce original language document
  |-- Produce Chinese translation document
  |
  v
4. Format and export
  |-- Markdown (.md) with timestamps in TOC and section headings, embedded images
  |-- Word (.docx) with professional layout, embedded images, timestamp annotations
```

## Step 1: Extract Raw Transcript (with Timestamps)

### 1a. Try subtitle extraction first (preferred)

Use the bundled script to extract subtitles with timestamps:

```bash
python3 "<skill-path>/scripts/extract_transcript.py" "<video-url>"
```

The script tries in order:
1. Manual/human-written subtitles (highest quality) — parses VTT/SRT timestamps
2. Auto-generated captions — parses VTT/SRT timestamps
3. Falls back to audio download + Whisper (outputs JSON with segment timestamps)

New flags:
- `--no-images`: Skip visual summary capture
- `--no-timestamps`: Use legacy behavior without timestamp preservation

If running manually with yt-dlp:

```bash
# List available subtitles
yt-dlp --list-subs "<video-url>"

# Download best available subtitle
yt-dlp --write-sub --write-auto-sub --sub-lang "en,zh-Hans,zh,ja,ko,fr,de,es" \
  --skip-download --sub-format "vtt/srt/best" -o "transcript" "<video-url>"
```

### 1b. Audio download + Whisper fallback

When no subtitles are available:

```bash
# Download audio only
yt-dlp -x --audio-format wav --audio-quality 0 -o "audio.%(ext)s" "<video-url>"

# Transcribe with Whisper (local)
whisper audio.wav --model medium --output_format txt --language auto

# OR via OpenAI API (if OPENAI_API_KEY is set)
python3 "<skill-path>/scripts/whisper_api.py" audio.wav
```

**Model selection guidance:**
- Short videos (<15 min): `medium` model for good balance of speed and accuracy
- Long videos (>15 min): `base` or `small` model to save time
- High accuracy needed: `large-v3` model
- OpenAI API: always uses the latest Whisper model, best for quality

### 1c. Subtitle cleaning and timestamp extraction

Raw subtitles contain timestamps, duplicates, and formatting artifacts. The script produces:

1. **`timestamped_transcript.json`**: Structured segments with start/end times
   ```json
   {
     "segments": [
       {"start": 0.0, "end": 5.2, "text": "Hello everyone..."},
       {"start": 5.2, "end": 12.1, "text": "Today we'll talk about..."}
     ]
   }
   ```
2. **`raw_transcript.txt`**: Cleaned plain text (timestamps removed, duplicates merged, tags stripped)
3. **`sections.json`**: Segments grouped into sections with timestamp mapping

Cleaning rules:
- Remove formatting tags (`<font>`, `<i>`, position markers)
- Merge duplicate lines from overlapping subtitle segments
- Join broken sentences across subtitle blocks
- Preserve paragraph breaks at natural pause points (>2 seconds gap)

## Step 2: Structure the Transcript

Transform raw text into a structured document:

### Language detection
Detect the source language from the first 500 characters. If the video title or metadata
contains language hints, use those as confirmation.

### Section splitting
- **If timestamps are available**: Group by natural topic shifts (look for long pauses >3s,
  topic transition phrases like "now let's talk about", "moving on to", "next")
- **If no timestamps**: Split by semantic coherence — each section should cover one main idea
- Target section length: 300-600 words per section

### Heading generation
- Create a descriptive title from the video title/content
- Generate section headings that summarize each section's main point
- Use H2 (`##`) for major sections, H3 (`###`) for subsections

### Text refinement
The raw transcript is spoken language. Refine for readability while preserving the speaker's
voice and intent:
- Remove filler words ("um", "uh", "you know", "like" when used as filler)
- Fix grammatical artifacts of speech (incomplete restarts, self-corrections)
- Keep the speaker's unique expressions, idioms, and speaking style
- Do NOT rewrite content or add information not present in the original
- Preserve technical terms and proper nouns exactly as spoken

## Step 3: Bilingual Output (when source is not Chinese)

When the source language is not Chinese, produce TWO documents:

### Original language document
- Clean, structured transcript in the source language
- All formatting and sections applied

### Chinese translation document
- Professional, natural Chinese translation (not machine-translation style)
- Adapt idioms and cultural references for Chinese readers
- Keep technical terms with both Chinese translation and original in parentheses
  - Example: "Transformer 架构 (Transformer Architecture)"
- Maintain the same section structure as the original
- Translation style: 信达雅 (faithful, expressive, elegant)

### When source IS Chinese
- Produce only one document (the Chinese version)
- Apply the same structuring and refinement

## Step 4: Format and Export

Produce BOTH formats for every document:

### Markdown (.md) format

Use this structure (timestamps and images are included when available):

```markdown
# [Document Title]

> **Source**: [Video title and URL]
> **Speaker**: [Speaker name if identifiable]
> **Date**: [Video publish date if available]
> **Duration**: HH:MM:SS

---

## Table of Contents

- [Section 1 Title](#section-1-title) `[00:01:23]`
- [Section 2 Title](#section-2-title) `[00:05:47]`
- [Section 3 Title](#section-3-title) `[00:12:00]`

---

## Section 1 Title `[00:01:23]`

![Section 1 Summary](images/section_01.jpg)

[Section content with proper paragraphs]

## Section 2 Title `[00:05:47]`

![Section 2 Summary](images/section_02.jpg)

[Section content]

---

*Transcript extracted and formatted by Video Transcript Skill*
```

Timestamp format: `HH:MM:SS` (pure text, not clickable links).
Images: either ffmpeg-captured video frames or AI-generated concept illustrations.

### Word (.docx) format

Use the bundled script to generate professionally formatted Word documents:

```bash
python3 "<skill-path>/scripts/generate_docx.py" \
  --input transcript.md \
  --output transcript.docx \
  --title "Document Title" \
  --author "Speaker Name" \
  --base-dir ./output
```

The script applies these formatting standards:
- **Font**: Title in 小二号 Microsoft YaHei (微软雅黑) bold; body in 小四号 SimSun (宋体) for
  Chinese, Calibri for English
- **Line spacing**: 1.5x for body text
- **Margins**: 2.54cm (1 inch) all around — standard A4
- **Header**: Document title + page number
- **Footer**: Source URL
- **Title page**: Title, speaker, date, source URL
- **Table of Contents**: Auto-generated with page numbers
- **Section headings**: Styled with 三号 bold, automatic numbering, timestamp annotation in grey
- **Images**: Embedded from `![alt](path)` Markdown syntax, 5.5 inches wide with centered captions
- **Paragraph spacing**: 0.5 line before, 0.5 line after

## File Naming Convention

Output files follow this pattern:

```
[video-title]_[language]_transcript.md
[video-title]_[language]_transcript.docx
```

Examples:
- `attention_is_all_you_need_en_transcript.md`
- `attention_is_all_you_need_zh_transcript.md`
- `attention_is_all_you_need_en_transcript.docx`
- `attention_is_all_you_need_zh_transcript.docx`

For Chinese-only sources:
- `[video-title]_transcript.md`
- `[video-title]_transcript.docx`

## Dependencies

Install these if not already available (prefer `uv`, fallback to `pip`):

```bash
# Core (required)
uv pip install yt-dlp python-docx

# Whisper - local (optional, for videos without subtitles)
uv pip install openai-whisper

# Whisper - API (optional, alternative to local Whisper)
# Also used for DALL-E image generation fallback
# Requires OPENAI_API_KEY environment variable
uv pip install openai
```

System tools:
```bash
# ffmpeg — required for audio extraction and video frame capture
# Install via: brew install ffmpeg (macOS), apt install ffmpeg (Linux)
ffmpeg -version

# yt-dlp
yt-dlp --version
```

**Note**: `ffmpeg` is needed for both Whisper audio extraction and video frame capture for visual summaries. DALL-E fallback image generation requires `OPENAI_API_KEY`.

## Optional Pixelle-Video Installation

`Pixelle-Video` is optional. It is not bundled inside this skill directory and will not be installed automatically when someone copies or installs `video-transcript`.

You only need `Pixelle-Video` if you plan to run:

```bash
python3 "<skill-path>/scripts/pixelle_end_to_end.py" ...
```

Recommended local layout:

```text
workspace/
├── video-transcript/
└── Pixelle-Video/
```

Suggested setup steps:

```bash
# 1. Create a workspace directory
mkdir -p workspace
cd workspace

# 2. Place this skill repo in your workspace
git clone https://github.com/ylouis83/video_transcript.git

# 3. Clone or copy Pixelle-Video beside it
#    Replace this with the actual Pixelle-Video source you use
git clone <pixelle-video-repo> Pixelle-Video

# 4. Install Pixelle-Video with its own setup instructions
cd Pixelle-Video
# ...follow Pixelle-Video installation steps...
```

Default behavior:
- `pixelle_end_to_end.py` looks for a sibling folder named `Pixelle-Video`
- If Pixelle lives elsewhere, pass `--pixelle-repo /absolute/path/to/Pixelle-Video`
- If you do not need video rendering, ignore Pixelle and use the transcript / Markdown / docx pipeline directly

## Error Handling

| Scenario | Action |
|---|---|
| Video is private/unavailable | Tell the user, suggest checking the URL or permissions |
| No subtitles AND Whisper not installed | Ask user to install Whisper or set OPENAI_API_KEY |
| Video is very long (>2 hours) | Warn about processing time, suggest processing in chunks |
| Unsupported platform | Try yt-dlp anyway (it supports 1000+ sites), report if it fails |
| Network error during download | Retry once, then report the error |
| Audio extraction fails | Try alternative format (`-x --audio-format mp3`), then report |

## Quality Checklist

Before delivering the final documents, verify:

- [ ] No subtitle artifacts (timestamps, tags, position markers) remain in body text
- [ ] Sections have meaningful headings (not just "Section 1")
- [ ] Paragraphs are properly broken (not one giant wall of text)
- [ ] Technical terms are preserved accurately
- [ ] Translation (if applicable) reads naturally, not machine-translated
- [ ] Both .md and .docx files are generated
- [ ] File names follow the naming convention
- [ ] Metadata block (source, speaker, date) is filled in
- [ ] Table of contents matches actual sections
- [ ] Timestamps in TOC and headings are accurate and in HH:MM:SS format
- [ ] Section images are present (or --no-images was used)
- [ ] Images are properly embedded in .docx (not just text references)
