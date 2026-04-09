"""Tests for dvdrip._display."""

import logging

import pytest

from dvdrip._display import display_scan, render_bar
from dvdrip._models import Duration, Title, TitleInfo


class TestRenderBar:
    def test_full_bar(self) -> None:
        bar = render_bar(0, 100, 100, 10)
        assert "\u25a0" in bar
        assert len(bar) == 10

    def test_partial_bar(self) -> None:
        bar = render_bar(0, 50, 100, 10)
        assert "\u25a0" in bar
        assert "\u2025" in bar

    def test_end_segment(self) -> None:
        bar = render_bar(50, 50, 100, 10)
        assert "\u25a0" in bar


class TestDisplayScan:
    def test_basic_output(self, caplog: pytest.LogCaptureFixture) -> None:
        title = Title(
            number=1,
            info=TitleInfo(
                duration=Duration(hours=1, minutes=30, seconds=0),
                size=" 720x576, pixel aspect: 16/15, display aspect: 1.33, 25.0 fps",
                chapters={"1": "duration 00:45:00", "2": "duration 00:45:00"},
                audio_tracks={
                    "1": "English (AC3) (5.1 ch) (iso639-2: eng), 48000Hz, 448000bps",
                },
                subtitle_tracks={"1": "English (Bitmap)(VOBSUB)"},
            ),
        )
        with caplog.at_level(logging.INFO):
            display_scan([title])
        assert "Title" in caplog.text
        assert "720" in caplog.text
        assert "audio" in caplog.text
        assert "chapter" in caplog.text
        assert "\u25d6" in caplog.text
