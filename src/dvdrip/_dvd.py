"""DVD scanning, ripping, and ejection."""

import ctypes
import logging
import os
import re
import stat
import subprocess
import sys
import time
from pathlib import Path
from pprint import pformat
from typing import Final

from dvdrip._errors import UserError
from dvdrip._models import Task, Title, TitleInfo
from dvdrip._parsing import (
    extract_duration,
    extract_title_scan,
    parse_title_scan,
)
from dvdrip._subprocess import check_err, check_output

_logger = logging.getLogger(__name__)

HANDBRAKE: Final[str] = "HandBrakeCLI"
TOTAL_EJECT_SECONDS: Final[int] = 5
EJECT_ATTEMPTS_PER_SECOND: Final[int] = 10


def find_mount_point(dev: str, timeout: float) -> str:
    """Find the mount point for a block device.

    Args:
        dev: Path to the block device.
        timeout: Maximum seconds to wait for the device to be mounted.

    Raises:
        UserError: If the device is not mounted within the timeout.
    """
    regex = re.compile(r"^" + re.escape(os.path.realpath(dev)) + r"\b")

    now = time.time()
    end_time = now + timeout
    while end_time >= now:
        for line in check_output(["df", "-P"]).split("\n"):
            m = regex.match(line)
            if m:
                parts = line.split(None, 5)
                if len(parts) > 1:
                    return parts[-1]
        time.sleep(0.1)
        now = time.time()
    msg = f"{dev!r} not mounted."
    raise UserError(msg)


class DVD:
    """Represents a DVD volume for scanning and ripping."""

    def __init__(
        self,
        mountpoint: str,
        *,
        verbose: bool,
        mount_timeout: float = 0,
    ) -> None:
        """Initialize a DVD from a mountpoint or block device.

        Args:
            mountpoint: Path to the DVD mount or block device.
            verbose: If True, print scan output.
            mount_timeout: Seconds to wait for device mount.
        """
        if stat.S_ISBLK(Path(mountpoint).stat().st_mode):
            mountpoint = find_mount_point(mountpoint, mount_timeout)
        if not Path(mountpoint).is_dir():
            msg = f"{mountpoint!r} is not a directory"
            raise UserError(msg)
        self.mountpoint = mountpoint
        self.verbose = verbose

    def rip_title(
        self,
        task: Task,
        output: str,
        *,
        preset: str,
        dry_run: bool,
        verbose: bool,
    ) -> None:
        """Rip a single DVD title or chapter using HandBrakeCLI.

        Args:
            task: The ripping task containing title and chapter info.
            output: Output file path.
            preset: HandBrakeCLI preset name.
            dry_run: If True, do not actually write files.
            verbose: If True, print detailed progress.
        """
        if verbose:
            _logger.debug("Title Scan:\n%s", pformat(task.title.info.model_dump()))

        audio_tracks = list(task.title.info.audio_tracks.keys())
        audio_encoders = ["faac"] * len(audio_tracks)
        subtitles = list(task.title.info.subtitle_tracks.keys())

        args = [
            HANDBRAKE,
            "--title",
            str(task.title.number),
            "--preset",
            preset,
            "--audio",
            ",".join(audio_tracks),
            "--aencoder",
            ",".join(audio_encoders),
        ]
        if task.chapter is not None:
            args += ["--chapters", str(task.chapter)]
        if subtitles:
            args += ["--subtitle", ",".join(subtitles)]
        args += [
            "--markers",
            "--optimize",
            "--input",
            self.mountpoint,
            "--output",
            output,
        ]
        if verbose:
            _logger.debug(
                "HandBrakeCLI args:\n%s",
                " ".join(("\n  " + a) if a.startswith("-") else a for a in args),
            )
        if not dry_run:
            if verbose:
                subprocess.call(args)  # noqa: S603
            else:
                check_err(args)

    def scan_title(self, i: int) -> list[str]:
        """Scan a single DVD title and return output lines.

        Args:
            i: Title number to scan.

        Returns:
            List of scan output lines.
        """
        lines = []
        for line in check_err(
            [
                HANDBRAKE,
                "--scan",
                "--title",
                str(i),
                "-i",
                self.mountpoint,
            ],
            stdout=subprocess.PIPE,
        ).split(os.linesep):
            if self.verbose:
                _logger.debug("< %s", line.rstrip())
            lines.append(line)
        return lines

    def scan_all(self) -> list[str]:
        """Scan all DVD titles at once and return output lines.

        Returns:
            List of scan output lines.
        """
        lines = []
        for line in check_err(
            [
                HANDBRAKE,
                "--scan",
                "--title",
                "0",
                "-i",
                self.mountpoint,
            ],
            stdout=subprocess.PIPE,
        ).split(os.linesep):
            if self.verbose:
                _logger.debug("< %s", line.rstrip())
            lines.append(line)
        return lines

    def scan_titles(
        self,
        title_numbers: list[int] | None,
    ) -> list[Title]:
        """Scan multiple DVD titles and return parsed Title models.

        Args:
            title_numbers: List of title numbers to scan, or None for all.

        Returns:
            List of parsed Title models.
        """
        raw_scan = self.scan_all()
        scan_lines = extract_title_scan(raw_scan)
        parsed = parse_title_scan(scan_lines)
        _logger.info("Disc has %d title(s).", len(parsed))

        titles = []
        for title_name, title_info in parsed.items():
            title = _make_title(title_name, title_info)
            if title_numbers and title.number not in title_numbers:
                continue
            titles.append(title)
        return titles

    def eject(self) -> None:
        """Eject the DVD drive."""
        if os.name == "nt":
            self._eject_windows()
            return

        cmd = (
            ["diskutil", "eject", self.mountpoint]
            if sys.platform == "darwin"
            else ["eject", self.mountpoint]
        )
        for _ in range(
            TOTAL_EJECT_SECONDS * EJECT_ATTEMPTS_PER_SECOND,
        ):
            if not subprocess.call(cmd):  # noqa: S603
                return
            time.sleep(1.0 / EJECT_ATTEMPTS_PER_SECOND)

    def _eject_windows(self) -> None:
        """Eject DVD drive on Windows using MCI commands."""
        mp = self.mountpoint
        if len(mp) < 4 and mp[1] == ":":  # noqa: PLR2004
            letter = mp[0]
            ctypes.windll.WINMM.mciSendStringW(  # type: ignore[attr-defined]  # ty: ignore[unresolved-attribute]
                f"open {letter}: type CDAudio alias {letter}_drive",
                None,
                0,
                None,
            )
            ctypes.windll.WINMM.mciSendStringW(  # type: ignore[attr-defined]  # ty: ignore[unresolved-attribute]
                f"set {letter}_drive door open",
                None,
                0,
                None,
            )


_TITLE_NAME_RE = re.compile(r"^title (\d+)$")


def _make_title(name: str, info: dict) -> Title:
    """Create a Title model from raw parsed data.

    Args:
        name: Title name from scan (e.g. "title 2").
        info: Raw parsed info dictionary.

    Raises:
        ValueError: If the title name format is unexpected.

    Returns:
        A Title model.
    """
    m = _TITLE_NAME_RE.match(name)
    if not m:
        msg = f"Unexpected title name format: {name!r}"
        raise ValueError(msg)
    number = int(m.group(1))
    info = {k: v for k, v in info.items() if k is not None}
    info["duration"] = extract_duration("duration " + info["duration"])
    return Title(number=number, info=TitleInfo(**info))
