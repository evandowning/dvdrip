"""Tests for dvdrip._parsing."""

import logging

import pytest

from dvdrip._models import Duration, Size
from dvdrip._parsing import (
    compute_aspect_ratio,
    extract_duration,
    extract_title_scan,
    find_title_count,
    only,
    parse_audio_tracks,
    parse_chapters,
    parse_duration,
    parse_size,
    parse_subtitle_tracks,
    parse_title_scan,
)


class TestOnly:
    def test_single_element(self) -> None:
        assert only([42]) == 42

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="not enough"):
            only([])

    def test_multiple_raises(self) -> None:
        with pytest.raises(ValueError, match="too many"):
            only([1, 2])


class TestFindTitleCount:
    def test_scanning_format(self) -> None:
        scan = ("Scanning title 1 of 5...",)
        assert find_title_count(scan, verbose=False) == 5

    def test_dvd_has_format(self) -> None:
        scan = ("[12:34:56] scan: DVD has 3 title(s)",)
        assert find_title_count(scan, verbose=False) == 3

    def test_not_found_raises(self) -> None:
        with pytest.raises(AssertionError, match="TITLE_COUNT"):
            find_title_count(("no match here",), verbose=False)

    def test_not_found_verbose_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.DEBUG), pytest.raises(AssertionError):
            find_title_count(("some line",), verbose=True)
        assert "some line" in caplog.text


class TestExtractTitleScan:
    def test_basic(self) -> None:
        scan = [
            "some preamble",
            "+ title 1:",
            "  + duration: 01:30:00",
            "end of scan",
        ]
        result = extract_title_scan(scan)
        assert result == ("+ title 1:", "  + duration: 01:30:00")

    def test_empty(self) -> None:
        assert extract_title_scan([]) == ()


class TestParseTitleScan:
    def test_basic_title(self) -> None:
        scan = (
            "+ title 1:",
            "  + duration: 01:30:00",
            "  + size: 720x480, pixel aspect: 8/9, display aspect: 1.33, 29.97 fps",
            "  + chapters:",
            "    + 1: duration 00:45:00",
            "    + 2: duration 00:45:00",
            "  + audio tracks:",
            "    + 1, English (AC3) (5.1 ch) (iso639-2: eng)",
            "  + subtitle tracks:",
            "    + 1, English (Bitmap)(VOBSUB)",
        )
        result = parse_title_scan(scan)
        assert "title 1" in result
        info = result["title 1"]
        assert info["duration"] == " 01:30:00"
        assert "1" in info["audio tracks"]
        assert "1" in info["subtitle tracks"]


class TestParseSize:
    def test_standard(self) -> None:
        s = " 720x576, pixel aspect: 16/15, display aspect: 1.33, 25.0 fps"
        size = parse_size(s)
        assert size == Size(
            width=720,
            height=576,
            pix_aspect_width=16,
            pix_aspect_height=15,
            fps=25.0,
        )


class TestComputeAspectRatio:
    def test_4_3(self) -> None:
        size = Size(width=720, height=576, pix_aspect_width=16, pix_aspect_height=15, fps=25.0)
        assert compute_aspect_ratio(size) == (4, 3)

    def test_16_9(self) -> None:
        size = Size(width=1920, height=1080, pix_aspect_width=1, pix_aspect_height=1, fps=24.0)
        assert compute_aspect_ratio(size) == (16, 9)


class TestParseDuration:
    def test_hhmmss(self) -> None:
        assert parse_duration("02:25:33") == 8733

    def test_mmss(self) -> None:
        assert parse_duration("25:33") == 1533

    def test_zero(self) -> None:
        assert parse_duration("00:00:00") == 0


class TestExtractDuration:
    def test_basic(self) -> None:
        d = extract_duration("duration 01:30:15")
        assert d == Duration(hours=1, minutes=30, seconds=15)

    def test_with_surrounding(self) -> None:
        d = extract_duration("cells 0->0, duration 00:24:15, something")
        assert d == Duration(hours=0, minutes=24, seconds=15)


class TestParseChapters:
    def test_basic(self) -> None:
        d = {"2": "duration 00:10:00", "1": "duration 00:20:00"}
        chapters = parse_chapters(d)
        assert len(chapters) == 2
        assert chapters[0].number == 1
        assert chapters[0].duration.in_seconds() == 1200
        assert chapters[1].number == 2


class TestParseAudioTracks:
    def test_basic(self) -> None:
        d = {"1": "English (AC3) (5.1 ch) (iso639-2: eng), 48000Hz, 448000bps"}
        tracks = parse_audio_tracks(d)
        assert len(tracks) == 1
        assert tracks[0].lang == "English"
        assert tracks[0].channels == "5.1"
        assert tracks[0].iso639_2 == "eng"

    def test_combined_format(self) -> None:
        d = {"1": "English (AC3, 2.0 ch, 192 kbps) (iso639-2: eng), 48000Hz, 192000bps"}
        tracks = parse_audio_tracks(d)
        assert len(tracks) == 1
        assert tracks[0].lang == "English"
        assert tracks[0].codec == "AC3"
        assert tracks[0].channels == "2.0"
        assert tracks[0].iso639_2 == "eng"

    def test_with_more_extras(self) -> None:
        d = {"1": "English (AC3) (5.1 ch) (extra info) (iso639-2: eng), 48000Hz"}
        tracks = parse_audio_tracks(d)
        assert len(tracks) == 1
        assert "(extra info)" in tracks[0].extras

    def test_unparseable_info_warns(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.WARNING):
            d = {"1": ""}
            tracks = parse_audio_tracks(d)
            assert len(tracks) == 0
        assert "Cannot parse audio track info" in caplog.text

    def test_unparseable_fields_warns(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.WARNING):
            d = {"1": "English (bad fields format)"}
            tracks = parse_audio_tracks(d)
            assert len(tracks) == 0
        assert "Cannot parse audio track fields" in caplog.text


class TestParseSubtitleTracks:
    def test_basic(self) -> None:
        d = {"2": "French (VOBSUB)", "1": "English (VOBSUB)"}
        tracks = parse_subtitle_tracks(d)
        assert len(tracks) == 2
        assert tracks[0].number == 1
        assert tracks[0].info == "English (VOBSUB)"
        assert tracks[1].number == 2
