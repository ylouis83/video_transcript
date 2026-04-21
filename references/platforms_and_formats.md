# Video Transcript Skill — Reference Guide

## Supported Platforms

yt-dlp supports 1000+ sites. The most commonly used for transcript extraction:

| Platform | Subtitle Support | Notes |
|---|---|---|
| YouTube | Excellent — manual + auto-generated | Best subtitle coverage |
| Bilibili (B站) | Good — CC subtitles | Use `--cookies` for members-only content |
| Vimeo | Good — manual subtitles | Less auto-caption coverage |
| TikTok/Douyin | Limited | Usually no subtitles; rely on Whisper |
| Twitter/X | Limited | Auto-captions sometimes available |
| Coursera | Good | Lecture subtitles usually available |
| TED | Excellent | Multi-language manual subtitles |

## yt-dlp Subtitle Language Codes

| Language | Code | Auto-caption | Manual common |
|---|---|---|---|
| English | `en` | Yes | Yes |
| Chinese (Simplified) | `zh-Hans` | Yes | Yes |
| Chinese (Traditional) | `zh-Hant` | Yes | Yes |
| Japanese | `ja` | Yes | Yes |
| Korean | `ko` | Yes | Yes |
| French | `fr` | Yes | Yes |
| German | `de` | Yes | Yes |
| Spanish | `es` | Yes | Yes |
| Russian | `ru` | Yes | Less common |
| Portuguese | `pt` | Yes | Less common |
| Arabic | `ar` | Yes | Less common |

## Whisper Model Comparison

| Model | Size | VRAM | Speed | Quality | Best For |
|---|---|---|---|---|---|
| `tiny` | 39M | ~1GB | Very fast | Low | Quick draft, noisy audio |
| `base` | 74M | ~1GB | Fast | OK | Long videos, speed priority |
| `small` | 244M | ~2GB | Moderate | Good | General use |
| `medium` | 769M | ~5GB | Slow | Very good | Default recommendation |
| `large-v3` | 1550M | ~10GB | Very slow | Best | High accuracy needed |

**Recommendation**: Start with `medium`. Use `small` for videos >1 hour. Use `large-v3` only when accuracy is critical (e.g., technical talks with specialized terminology).

## Subtitle Format Reference

### VTT (WebVTT)
```
WEBVTT
Kind: captions
Language: en

00:00:01.000 --> 00:00:04.000
Hello and welcome to today's talk.

00:00:04.500 --> 00:00:08.000
Today we'll be discussing neural networks.
```

### SRT (SubRip)
```
1
00:00:01,000 --> 00:00:04,000
Hello and welcome to today's talk.

2
00:00:04,500 --> 00:00:08,000
Today we'll be discussing neural networks.
```

## Timestamp Display Format

Timestamps in the output documents use **HH:MM:SS** format (pure text, no links):

| Seconds | Display |
|---|---|
| 0 | `00:00:00` |
| 83 | `00:01:23` |
| 347 | `00:05:47` |
| 3723 | `01:02:03` |

Used in:
- Table of Contents entries: `- [Section Title](#anchor) \`[00:01:23]\``
- Section headings: `## Section Title \`[00:01:23]\``
- Metadata block: `> **Duration**: 01:23:45`

## Visual Summary Sources

| Source | Method | Quality | Requirements |
|---|---|---|---|
| Video frame (ffmpeg) | Extract JPEG at section start + 5s | Best — actual content | `ffmpeg`, downloadable video |
| AI-generated (DALL-E) | Generate concept image from text | Good — thematic | `openai` package, `OPENAI_API_KEY` |
| None (--no-images) | Skip images entirely | N/A | No extra dependencies |

Frame capture command:
```bash
ffmpeg -ss <timestamp> -i video.mp4 -vframes 1 -q:v 2 section_01.jpg
```

Video download for screenshots (lowest quality to save bandwidth):
```bash
yt-dlp -f "worst[ext=mp4]/worst" -o video.mp4 "<url>"
```

## Translation Quality Guidelines

### Technical Terms — Keep Original with Translation
- Transformer 架构 (Transformer Architecture)
- 反向传播 (Backpropagation)
- 卷积神经网络 (Convolutional Neural Network, CNN)
- 注意力机制 (Attention Mechanism)

### Idiomatic Translation Patterns
| English | Bad (literal) | Good (natural) |
|---|---|---|
| "Let's dive into..." | "让我们潜入..." | "让我们深入了解..." |
| "The takeaway here is..." | "这里的外卖是..." | "这里的要点是..." |
| "It turns out that..." | "它变成了..." | "结果表明..." |
| "Under the hood" | "在引擎盖下" | "在底层/内部" |

## Document Formatting Standards

### Chinese Document (GB/T Standard Reference)
- Title: 小二号 (18pt) 黑体/微软雅黑, bold
- Section heading: 三号 (16pt) 黑体, bold
- Subsection heading: 四号 (14pt) 黑体, bold
- Body text: 小四号 (12pt) 宋体
- Line spacing: 1.5x
- Paragraph indent: 2 Chinese characters (约2em)
- Margins: 2.54cm all sides (A4 standard)

### English Document
- Title: 22pt Calibri, bold
- Section heading: 16pt Calibri, bold
- Subsection heading: 13pt Calibri, bold
- Body text: 12pt Calibri
- Line spacing: 1.5x
- Margins: 1 inch (2.54cm) all sides
