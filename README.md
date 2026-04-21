# video-transcript

`video-transcript` turns public video URLs into structured transcript bundles, bilingual lecture notes, visual summaries, and optional short-form newsroom-style video assets.

It is built around a simple priority order:

1. Reuse the best available subtitles first.
2. Fall back to Whisper only when subtitles are missing.
3. Preserve timestamps so the transcript stays referenceable.
4. Split the transcript into sections and export publishable artifacts.
5. Optionally hand the result to Pixelle for short-video rendering.

## What it does

- Extracts transcripts from public video URLs supported by `yt-dlp`
- Prefers human subtitles, then auto subtitles, then audio transcription
- Preserves timestamps and emits structured transcript JSON
- Splits long transcripts into logical sections
- Captures section images from the source video with `ffmpeg`
- Falls back to OpenAI image generation when frames are unavailable
- Exports clean Markdown and Word `.docx` documents
- Supports bilingual output when the source is not Chinese
- Builds newsroom-style frame payloads for downstream Pixelle rendering

## Supported sources

Anything supported by `yt-dlp`, including common workflows for:

- YouTube
- Bilibili
- TikTok / Douyin
- Vimeo
- TED
- Coursera

## Repository layout

```text
.
├── README.md
├── SKILL.md
├── references/
│   └── platforms_and_formats.md
├── scripts/
│   ├── capture_frames.py
│   ├── extract_transcript.py
│   ├── generate_docx.py
│   ├── newsroom_story_builder.py
│   ├── pixelle_end_to_end.py
│   ├── section_splitter.py
│   └── whisper_api.py
└── tests/
    ├── conftest.py
    ├── test_newsroom_story_builder.py
    └── test_pixelle_end_to_end.py
```

## Core pipeline

### 1. Transcript extraction

[`scripts/extract_transcript.py`](./scripts/extract_transcript.py) tries, in order:

1. Manual subtitles
2. Auto-generated subtitles
3. Audio download + Whisper transcription

Typical outputs include:

- `metadata.json`
- `raw_transcript.txt`
- `timestamped_transcript.json`
- `sections.json`
- `transcript_enhanced.md`

### 2. Section splitting

[`scripts/section_splitter.py`](./scripts/section_splitter.py) groups transcript segments into topic-level sections using pauses, transitions, and size heuristics.

### 3. Visual summaries

[`scripts/capture_frames.py`](./scripts/capture_frames.py) captures frames near section timestamps with `ffmpeg`. If frame extraction is not possible and `OPENAI_API_KEY` is available, it can fall back to AI-generated concept images.

### 4. Word export

[`scripts/generate_docx.py`](./scripts/generate_docx.py) converts the enhanced Markdown output into a professionally formatted `.docx` document with headings, metadata, and embedded images.

### 5. Newsroom / Pixelle integration

[`scripts/newsroom_story_builder.py`](./scripts/newsroom_story_builder.py) converts transcript content into newsroom-style cards.

[`scripts/pixelle_end_to_end.py`](./scripts/pixelle_end_to_end.py) reuses the transcript bundle, prepares story frames, and can pass the result to a sibling `Pixelle-Video` repo for rendering.

## Requirements

Python 3.11+ is recommended.

Install Python dependencies:

```bash
python3 -m pip install yt-dlp python-docx openai
python3 -m pip install openai-whisper
```

System dependencies:

```bash
brew install ffmpeg
yt-dlp --version
ffmpeg -version
```

Notes:

- `openai-whisper` is only needed when subtitles are unavailable and you want local transcription.
- `openai` is needed for Whisper API usage and image-generation fallback.
- Keep credentials out of the repository. Use environment variables only.

## Quick start

Extract a transcript bundle:

```bash
python3 scripts/extract_transcript.py "https://www.youtube.com/watch?v=VIDEO_ID" \
  --output-dir ./output/example \
  --no-images
```

Generate a Word document from an enhanced Markdown transcript:

```bash
python3 scripts/generate_docx.py \
  --input ./output/example/transcript_enhanced.md \
  --output ./output/example/transcript.docx \
  --title "Transcript" \
  --base-dir ./output/example
```

Run the Pixelle-oriented end-to-end flow:

```bash
python3 scripts/pixelle_end_to_end.py \
  "https://www.youtube.com/watch?v=VIDEO_ID" \
  --output-dir ./output/pixelle_demo \
  --story-mode newsroom
```

If `Pixelle-Video` lives beside this repository, the default path works automatically. Otherwise pass `--pixelle-repo /path/to/Pixelle-Video`.

## Output conventions

The pipeline is designed to produce reusable transcript bundles rather than a single text file. Depending on the flags and source quality, the output directory may include:

- `metadata.json`
- `raw_transcript.txt`
- `timestamped_transcript.json`
- `sections.json`
- `transcript_enhanced.md`
- `images/`
- `.docx` exports
- Pixelle payload and final rendered video artifacts

## Testing

The repository includes focused tests for the newsroom formatter and Pixelle helper logic:

```bash
python3 -m pytest tests
```

If `pytest` is not installed in your current environment:

```bash
python3 -m pip install pytest
```

## Security and publishing notes

- Do not commit API keys, tokens, or generated deliverables.
- Keep local virtual environments and caches ignored.
- `OPENAI_API_KEY` should be provided via the shell environment, not hardcoded.
- Public uploads should include only source files, references, tests, and docs.

## License

No license file is included yet. Add one before wider third-party reuse.
