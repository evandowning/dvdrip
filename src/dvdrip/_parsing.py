"""Parsing functions for HandBrakeCLI scan output."""

import logging
import re
from collections.abc import Iterable
from math import gcd
from typing import Any

from dvdrip._models import (
    AudioTrack,
    Chapter,
    Duration,
    Size,
    SubtitleTrack,
)

_TITLE_COUNT_REGEXES = [
    re.compile(r"^Scanning title \d+ of (\d+)\.\.\.$"),
    re.compile(r"^\[\d\d:\d\d:\d\d] scan: DVD has (\d+) title\(s\)$"),
]

_STRUCTURED_LINE_RE = re.compile(r"( *)\+ (([a-z0-9 ]+):)?(.*)")

_TRACK_VALUE_RE = re.compile(r"(\d+), (.*)")

_SIZE_REGEX = re.compile(
    r"^\s*(\d+)x(\d+),\s*"
    r"pixel aspect: (\d+)/(\d+),\s*"
    r"display aspect: (?:\d+(?:\.\d+)),\s*"
    r"(\d+(?:\.\d+)) fps\s*$",
)

_DURATION_REGEX = re.compile(
    r"^(?:.*,)?\s*duration\s+(\d\d):(\d\d):(\d\d)\s*(?:,.*)?$",
)

_AUDIO_TRACK_REGEX = re.compile(
    r"^(\S+)\s*((?:\([^)]*\)\s*)*)(?:,\s*(.*))?$",
)

_AUDIO_TRACK_FIELD_REGEX = re.compile(
    r"^\(([^)]*)\)\s*\(([^)]*?)\s*ch\)\s*"
    r"((?:\([^()]*\)\s*)*)\(iso639-2:\s*([^)]+)\)$",
)

_logger = logging.getLogger(__name__)


def only[T](iterable: Iterable[T]) -> T:
    """Return the one and only element in an iterable.

    Raises:
        ValueError: If iterable does not have exactly one item.
    """
    (result,) = iterable
    return result


def find_title_count(
    scan: tuple[str, ...],
    *,
    verbose: bool,
) -> int:
    """Find the total number of titles on a DVD from scan output.

    Args:
        scan: Lines of HandBrakeCLI scan output.
        verbose: If True, print scan lines on failure.

    Raises:
        AssertionError: If title count cannot be found.
    """
    for regex in _TITLE_COUNT_REGEXES:
        m = None
        for line in scan:
            m = regex.match(line)
            if m:
                break
        if m:
            return int(m.group(1))
    if verbose:
        for line in scan:
            _logger.debug(line)
    msg = "Can't find TITLE_COUNT_REGEX in scan"
    raise AssertionError(msg)


def extract_title_scan(scan: Iterable[str]) -> tuple[str, ...]:
    """Extract structured title scan lines from raw scan output.

    Args:
        scan: Iterable of scan output lines.

    Returns:
        Tuple of structured lines from the title scan section.
    """
    result: list[str] = []
    in_title_scan = False
    for line in scan:
        if not in_title_scan and line.startswith("+"):
            in_title_scan = True
        if in_title_scan:
            m = _STRUCTURED_LINE_RE.match(line)
            if m:
                result.append(line)
            else:
                break
    return tuple(result)


def _massage_track_data(node: dict[str, Any], key: str) -> None:
    """Normalize track data from list format to dict format."""
    if key in node:
        track_data = node[key]
        if isinstance(track_data, list):
            new_track_data = {}
            for track in track_data:
                m = _TRACK_VALUE_RE.match(track)
                assert m is not None  # noqa: S101
                k, v = m.groups()
                new_track_data[k] = v
            node[key] = new_track_data


def parse_title_scan(scan: tuple[str, ...]) -> dict[str, Any]:
    """Parse structured title scan lines into a nested dictionary.

    Args:
        scan: Tuple of structured scan lines.

    Returns:
        Dictionary mapping title names to their parsed info.
    """
    _pos, result = _parse_title_scan_helper(scan, pos=0, indent=0)

    for value in result.values():
        _massage_track_data(value, "audio tracks")
        _massage_track_data(value, "subtitle tracks")
    return result


def _parse_title_scan_helper(
    scan: tuple[str, ...],
    pos: int,
    indent: int,
) -> tuple[int, Any]:
    """Recursively parse scan lines at a given indentation level."""
    result: dict[str | None, Any] = {}
    cruft: list[str] = []
    while True:
        pos, node = _parse_node(scan, pos=pos, indent=indent)
        if node:
            if isinstance(node, tuple):
                k, v = node
                result[k] = v
            else:
                cruft.append(node)
                result[None] = cruft
        else:
            break
    if len(result) == 1 and None in result:
        return pos, result[None]
    return pos, result


def _parse_node(
    scan: tuple[str, ...],
    pos: int,
    indent: int,
) -> tuple[int, Any]:
    """Parse a single node from scan lines."""
    if pos >= len(scan):
        return pos, None
    line = scan[pos]
    m = _STRUCTURED_LINE_RE.match(line)
    assert m is not None  # noqa: S101
    spaces_str, colon, name, value = m.groups()
    spaces = len(spaces_str) / 2
    if spaces < indent:
        return pos, None
    assert spaces == indent, f"{indent} <> {line!r}"  # noqa: S101
    pos += 1
    if colon:
        if value:
            node = (name, value)
        else:
            pos, children = _parse_title_scan_helper(scan, pos, indent + 1)
            node = (name, children)
    else:
        node = value
    return pos, node


def parse_size(s: str) -> Size:
    """Parse a size string from HandBrakeCLI into a Size model.

    Args:
        s: Size string like "720x576, pixel aspect: 16/15, ...".

    Returns:
        A Size model with parsed dimensions.
    """
    match = _SIZE_REGEX.match(s)
    assert match is not None  # noqa: S101
    w, h, paw, pah, fps_str = match.groups()
    return Size(
        width=int(w),
        height=int(h),
        pix_aspect_width=int(paw),
        pix_aspect_height=int(pah),
        fps=float(fps_str),
    )


def compute_aspect_ratio(size: Size) -> tuple[int, int]:
    """Compute the display aspect ratio from a Size model.

    Args:
        size: A Size model with pixel aspect information.

    Returns:
        Tuple of (width_ratio, height_ratio).
    """
    w = size.width * size.pix_aspect_width
    h = size.height * size.pix_aspect_height
    d = gcd(w, h)
    return (w // d, h // d)


def parse_duration(s: str) -> int:
    """Parse a colon-separated duration string into total seconds.

    Args:
        s: Duration string like "02:25:33".

    Returns:
        Total number of seconds.
    """
    result = 0
    for field in s.strip().split(":"):
        result *= 60
        result += int(field)
    return result


def extract_duration(s: str) -> Duration:
    """Extract a Duration model from a HandBrakeCLI duration string.

    Args:
        s: String containing "duration HH:MM:SS".

    Returns:
        A Duration model.
    """
    match = _DURATION_REGEX.match(s)
    assert match is not None  # noqa: S101
    hours, minutes, seconds = (int(x) for x in match.groups())
    return Duration(hours=hours, minutes=minutes, seconds=seconds)


def parse_chapters(d: dict[str, str]) -> list[Chapter]:
    """Parse a dictionary of chapter data into Chapter models.

    Args:
        d: Dictionary mapping chapter number strings to info strings.

    Returns:
        List of Chapter models sorted by number.
    """
    chapters = []
    for number, info in sorted(
        ((int(n), info) for n, info in d.items()),
    ):
        chapters.append(
            Chapter(number=number, duration=extract_duration(info)),
        )
    return chapters


def parse_audio_tracks(d: dict[str, str]) -> list[AudioTrack]:
    """Parse a dictionary of audio track data into AudioTrack models.

    Args:
        d: Dictionary mapping track number strings to info strings.

    Returns:
        List of AudioTrack models sorted by number.
    """
    tracks = []
    for number, info in sorted(
        ((int(n), info) for n, info in d.items()),
    ):
        m = _AUDIO_TRACK_REGEX.match(info)
        if m:
            lang, field_string, extras = m.groups()
            m2 = _AUDIO_TRACK_FIELD_REGEX.match(field_string)
            if m2:
                codec, channels, more_extras, iso639_2 = m2.groups()
                if more_extras:
                    extras = more_extras + extras
                tracks.append(
                    AudioTrack(
                        number=number,
                        lang=lang,
                        codec=codec,
                        channels=channels,
                        iso639_2=iso639_2,
                        extras=extras if extras else "",
                    ),
                )
            else:
                _logger.warning("Cannot parse audio track fields %r", field_string)
        else:
            _logger.warning("Cannot parse audio track info %r", info)
    return tracks


def parse_subtitle_tracks(d: dict[str, str]) -> list[SubtitleTrack]:
    """Parse a dictionary of subtitle track data into SubtitleTrack models.

    Args:
        d: Dictionary mapping track number strings to info strings.

    Returns:
        List of SubtitleTrack models sorted by number.
    """
    return [
        SubtitleTrack(number=int(n), info=info)
        for n, info in sorted(((int(n), info) for n, info in d.items()))
    ]
