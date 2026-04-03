"""Tests for dvdrip._models."""

import pytest
from pydantic import ValidationError

from dvdrip._models import (
    AudioTrack,
    Chapter,
    Duration,
    Size,
    SubtitleTrack,
    Task,
    Title,
    TitleInfo,
)


class TestDuration:
    def test_str(self) -> None:
        d = Duration(hours=2, minutes=5, seconds=3)
        assert str(d) == "02:05:03"

    def test_in_seconds(self) -> None:
        d = Duration(hours=1, minutes=30, seconds=15)
        assert d.in_seconds() == 5415

    def test_zero(self) -> None:
        d = Duration(hours=0, minutes=0, seconds=0)
        assert d.in_seconds() == 0
        assert str(d) == "00:00:00"

    def test_frozen(self) -> None:
        d = Duration(hours=1, minutes=2, seconds=3)
        with pytest.raises(ValidationError):
            d.hours = 5


class TestSize:
    def test_fields(self) -> None:
        s = Size(width=720, height=576, pix_aspect_width=16, pix_aspect_height=15, fps=25.0)
        assert s.width == 720
        assert s.height == 576
        assert s.fps == 25.0

    def test_frozen(self) -> None:
        s = Size(width=720, height=576, pix_aspect_width=16, pix_aspect_height=15, fps=25.0)
        with pytest.raises(ValidationError):
            s.width = 1920


class TestChapter:
    def test_fields(self) -> None:
        d = Duration(hours=0, minutes=24, seconds=15)
        c = Chapter(number=1, duration=d)
        assert c.number == 1
        assert c.duration.in_seconds() == 1455


class TestAudioTrack:
    def test_fields(self) -> None:
        at = AudioTrack(
            number=1,
            lang="English",
            codec="AC3",
            channels="5.1",
            iso639_2="eng",
            extras="48000Hz, 448000bps",
        )
        assert at.lang == "English"
        assert at.channels == "5.1"


class TestSubtitleTrack:
    def test_fields(self) -> None:
        st = SubtitleTrack(number=1, info="English (Bitmap)(VOBSUB)")
        assert st.number == 1


class TestTitleInfo:
    def test_with_aliases(self) -> None:
        info = TitleInfo(
            duration=Duration(hours=1, minutes=0, seconds=0),
            size=" 720x576, pixel aspect: 16/15, display aspect: 1.33, 25 fps",
            chapters={"1": "duration 00:30:00"},
            **{"audio tracks": {"1": "track info"}, "subtitle tracks": {"1": "sub info"}},
        )
        assert info.audio_tracks == {"1": "track info"}
        assert info.subtitle_tracks == {"1": "sub info"}

    def test_populate_by_name(self) -> None:
        info = TitleInfo(
            duration=Duration(hours=1, minutes=0, seconds=0),
            size="test",
            chapters={"1": "ch"},
            audio_tracks={"1": "at"},
            subtitle_tracks={"1": "st"},
        )
        assert info.chapters == {"1": "ch"}


class TestTitle:
    def test_fields(self) -> None:
        info = TitleInfo(
            duration=Duration(hours=1, minutes=0, seconds=0),
            size="test",
            chapters={},
            audio_tracks={},
            subtitle_tracks={},
        )
        title = Title(number=1, info=info)
        assert title.number == 1


class TestTask:
    def test_default_chapter(self) -> None:
        info = TitleInfo(
            duration=Duration(hours=1, minutes=0, seconds=0),
            size="test",
            chapters={},
            audio_tracks={},
            subtitle_tracks={},
        )
        task = Task(title=Title(number=1, info=info))
        assert task.chapter is None

    def test_with_chapter(self) -> None:
        info = TitleInfo(
            duration=Duration(hours=1, minutes=0, seconds=0),
            size="test",
            chapters={},
            audio_tracks={},
            subtitle_tracks={},
        )
        task = Task(title=Title(number=1, info=info), chapter=3)
        assert task.chapter == 3
