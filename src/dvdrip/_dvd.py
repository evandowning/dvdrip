"""DVD scanning, ripping, and ejection."""

import ctypes
import logging
import os
import re
import stat
import subprocess
import time
from pathlib import Path
from pprint import pformat
from typing import Final

from dvdrip._errors import UserError
from dvdrip._models import Task, Title, TitleInfo
from dvdrip._parsing import (
    extract_duration,
    extract_title_scan,
    find_title_count,
    only,
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
        dry_run: bool,
        verbose: bool,
    ) -> None:
        """Rip a single DVD title or chapter using HandBrakeCLI.

        Args:
            task: The ripping task containing title and chapter info.
            output: Output file path.
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
            "Production Standard",
            "--encoder",
            "x264",
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

    def scan_titles(
        self,
        title_numbers: list[int] | None,
        *,
        verbose: bool,
    ) -> list[Title]:
        """Scan multiple DVD titles and return parsed Title models.

        Args:
            title_numbers: List of title numbers to scan, or None for all.
            verbose: If True, print progress information.

        Returns:
            List of parsed Title models.
        """
        first = title_numbers[0] if title_numbers else 1
        raw_scan = tuple(self.scan_title(first))
        title_count = find_title_count(raw_scan, verbose=verbose)
        _logger.info("Disc claims to have %d titles.", title_count)
        title_name, title_info = only(
            parse_title_scan(extract_title_scan(raw_scan)).items(),
        )

        titles = [_make_title(title_name, first, title_info)]

        to_scan = [
            x
            for x in range(1, title_count + 1)
            if x != first and (not title_numbers or x in title_numbers)
        ]
        for i in to_scan:
            try:
                scan = extract_title_scan(self.scan_title(i))
            except subprocess.CalledProcessError:
                _logger.warning("Cannot scan title %d.", i)
            else:
                title_info_names = parse_title_scan(scan).items()
                if title_info_names:
                    title_name, title_info = only(title_info_names)
                    titles.append(
                        _make_title(title_name, i, title_info),
                    )
                else:
                    _logger.warning("Cannot parse scan of title %d.", i)
        return titles

    def eject(self) -> None:
        """Eject the DVD drive."""
        if os.name == "nt":
            self._eject_windows()
            return

        for _ in range(
            TOTAL_EJECT_SECONDS * EJECT_ATTEMPTS_PER_SECOND,
        ):
            if not subprocess.call(["eject", self.mountpoint]):  # noqa: S603, S607
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


def _make_title(name: str, number: int, info: dict) -> Title:
    """Create a Title model from raw parsed data.

    Args:
        name: Title name from scan (e.g. "title 1").
        number: Title number.
        info: Raw parsed info dictionary.

    Returns:
        A Title model.
    """
    assert f"title {number}" == name  # noqa: S101
    info["duration"] = extract_duration("duration " + info["duration"])
    return Title(number=number, info=TitleInfo(**info))
