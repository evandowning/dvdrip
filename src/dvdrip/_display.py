"""Display functions for DVD scan results."""

import logging
from typing import Final

from dvdrip._models import Title
from dvdrip._parsing import (
    compute_aspect_ratio,
    parse_audio_tracks,
    parse_chapters,
    parse_size,
    parse_subtitle_tracks,
)

MAX_BAR_WIDTH: Final[int] = 50

_logger = logging.getLogger(__name__)


def render_bar(
    start: int,
    length: int,
    total: int,
    width: int,
) -> str:
    """Render a Unicode progress bar segment.

    Args:
        start: Start position in the total range.
        length: Length of this segment.
        total: Total range.
        width: Character width of the bar.

    Returns:
        A string of Unicode block and dot characters.
    """
    end = start + length
    bar_start = round(start * (width - 1) / total)
    bar_length = round(end * (width - 1) / total) - bar_start + 1
    return (
        "\u2025" * bar_start + "\u25a0" * bar_length + "\u2025" * (width - bar_start - bar_length)
    )


def display_scan(titles: list[Title]) -> None:
    """Display a formatted scan of DVD titles.

    Args:
        titles: List of Title models to display.
    """
    max_title_seconds = max(title.info.duration.in_seconds() for title in titles)

    for title in titles:
        info = title.info
        size = parse_size(info.size)
        xaspect, yaspect = compute_aspect_ratio(size)
        duration = info.duration
        title_seconds = duration.in_seconds()
        _logger.info(
            "Title %3d/%3d: %s  %d\u00d7%d  %d:%d  %3g fps",
            title.number,
            len(titles),
            duration,
            size.width,
            size.height,
            xaspect,
            yaspect,
            size.fps,
        )
        for at in parse_audio_tracks(info.audio_tracks):
            _logger.info(
                "  audio %3d: %s (%sch)  [%s]",
                at.number,
                at.lang,
                at.channels,
                at.extras,
            )
        for sub in parse_subtitle_tracks(info.subtitle_tracks):
            _logger.info("  sub %3d: %s", sub.number, sub.info)
        position = 0
        if title_seconds > 0:
            for chapter in parse_chapters(info.chapters):
                seconds = chapter.duration.in_seconds()
                bar_width = round(
                    MAX_BAR_WIDTH * title_seconds / max_title_seconds,
                )
                bar = render_bar(
                    position,
                    seconds,
                    title_seconds,
                    bar_width,
                )
                _logger.info(
                    "  chapter %3d: %s \u25d6%s\u25d7",
                    chapter.number,
                    chapter.duration,
                    bar,
                )
                position += seconds
