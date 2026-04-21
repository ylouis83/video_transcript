from pathlib import Path

from pixelle_end_to_end import (
    PIXELLE_ROOT,
    VIDEO_TRANSCRIPT_ROOT,
    build_pip_url_pool,
    extract_youtube_video_id,
    parse_args,
    resolve_pip_support_files,
    select_story_pip_sources,
)


def test_build_pip_url_pool_keeps_primary_first_and_dedupes() -> None:
    pool = build_pip_url_pool(
        "https://www.youtube.com/watch?v=primary123",
        [
            "https://www.youtube.com/watch?v=extra456",
            "https://www.youtube.com/watch?v=primary123",
            "  https://www.youtube.com/watch?v=extra789  ",
        ],
    )

    assert pool == [
        "https://www.youtube.com/watch?v=primary123",
        "https://www.youtube.com/watch?v=extra456",
        "https://www.youtube.com/watch?v=extra789",
    ]


def test_extract_youtube_video_id_supports_watch_and_shorts_urls() -> None:
    assert extract_youtube_video_id("https://www.youtube.com/watch?v=hZVOzk1MJCo") == "hZVOzk1MJCo"
    assert extract_youtube_video_id("https://www.youtube.com/shorts/MU-CCbQ0fw0") == "MU-CCbQ0fw0"


def test_parse_args_accepts_newsroom_longform(monkeypatch) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "pixelle_end_to_end.py",
            "https://www.youtube.com/watch?v=f3AXHn1P2sA",
            "--output-dir",
            "/tmp/newsroom-longform",
            "--story-mode",
            "newsroom-longform",
        ],
    )

    args = parse_args()

    assert args.story_mode == "newsroom-longform"


def test_repo_roots_are_workspace_relative() -> None:
    assert VIDEO_TRANSCRIPT_ROOT == Path(__file__).resolve().parents[1]
    assert PIXELLE_ROOT == VIDEO_TRANSCRIPT_ROOT.parent / "Pixelle-Video"


def test_parse_args_accepts_local_pip_files(monkeypatch) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "pixelle_end_to_end.py",
            "https://www.youtube.com/watch?v=f3AXHn1P2sA",
            "--output-dir",
            "/tmp/newsroom-longform",
            "--story-mode",
            "newsroom-longform",
            "--pip-file",
            "/tmp/clip-one.mp4",
            "--pip-file",
            "/tmp/clip-two.mp4",
        ],
    )

    args = parse_args()

    assert args.pip_file == ["/tmp/clip-one.mp4", "/tmp/clip-two.mp4"]


def test_resolve_pip_support_files_dedupes_existing_files(tmp_path: Path) -> None:
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"video")

    resolved = resolve_pip_support_files([str(clip), str(clip)])

    assert resolved == [clip.resolve()]


def test_select_story_pip_sources_prefers_support_videos(tmp_path: Path) -> None:
    source_video = tmp_path / "source.mp4"
    source_video.write_bytes(b"source")
    support_one = tmp_path / "support-one.mp4"
    support_two = tmp_path / "support-two.mp4"
    support_one.write_bytes(b"support-1")
    support_two.write_bytes(b"support-2")

    selected = select_story_pip_sources(source_video, [support_one, support_two])

    assert selected == [support_one, support_two]


def test_select_story_pip_sources_falls_back_to_source_video(tmp_path: Path) -> None:
    source_video = tmp_path / "source.mp4"
    source_video.write_bytes(b"source")

    selected = select_story_pip_sources(source_video, [])

    assert selected == [source_video]
