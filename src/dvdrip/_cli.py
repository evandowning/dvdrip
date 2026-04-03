"""The ``dvdrip`` CLI entrypoint."""

import logging
import re
import sys
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, CliImplicitFlag

from dvdrip._display import display_scan
from dvdrip._dvd import DVD
from dvdrip._errors import UserError
from dvdrip._tasks import (
    construct_tasks,
    find_main_feature,
    perform_tasks,
    task_filenames,
)

_NUM_RANGE_REGEX = re.compile(r"^(\d*)-(\d+)|(\d+)$")

_logger = logging.getLogger(__name__)


class Settings(BaseSettings, cli_parse_args=True, cli_exit_on_error=True):
    """Rip DVDs quickly and easily from the command line."""

    verbose: CliImplicitFlag[bool] = Field(
        default=False,
        validation_alias=AliasChoices("v", "verbose"),
        description="Increase verbosity.",
    )
    chapter_split: CliImplicitFlag[bool] = Field(
        default=False,
        validation_alias=AliasChoices("c", "chapter-split", "chapter_split"),
        description="Split each chapter out into a separate file.",
    )
    dry_run: CliImplicitFlag[bool] = Field(
        default=False,
        validation_alias=AliasChoices("n", "dry-run", "dry_run"),
        description="Don't actually write anything.",
    )
    scan: CliImplicitFlag[bool] = Field(
        default=False,
        validation_alias=AliasChoices("scan"),
        description="Display scan of disc; do not rip.",
    )
    main_feature: CliImplicitFlag[bool] = Field(
        default=False,
        validation_alias=AliasChoices("main-feature", "main_feature"),
        description="Rip only the main feature title.",
    )
    titles: str = Field(
        default="*",
        validation_alias=AliasChoices("t", "titles"),
        description=(
            "Comma-separated list of title numbers to consider (starting at 1) or * for all titles."
        ),
    )
    input: str = Field(
        validation_alias=AliasChoices("i", "input"),
        description="Volume to rip (must be a directory).",
    )
    output: str | None = Field(
        default=None,
        validation_alias=AliasChoices("o", "output"),
        description=(
            "Output location. Extension is added if only one title "
            "being ripped, otherwise, a directory will be created "
            "to contain ripped titles."
        ),
    )
    mount_timeout: float = Field(
        default=15,
        validation_alias=AliasChoices("mount-timeout", "mount_timeout"),
        description="Amount of time to wait for a mountpoint to be mounted.",
    )


def _parse_titles_arg(titles_arg: str) -> list[int] | None:
    """Parse the --titles argument into a list of title numbers.

    Args:
        titles_arg: A string like "*", "1,3-5,7", or "2".

    Raises:
        UserError: If the format is invalid.

    Returns:
        List of title numbers, or None for all titles.
    """
    if titles_arg == "*":
        return None

    result: set[int] = set()
    for s in titles_arg.split(","):
        m = _NUM_RANGE_REGEX.match(s)
        if not m:
            msg = f"--titles must be * or list of integer ranges, found {titles_arg!r}"
            raise UserError(msg)
        start, end, only_val = m.groups()
        if only_val is not None:
            result.add(int(only_val))
        else:
            start_int = int(start) if start else 1
            result.update(range(start_int, int(end) + 1))
    return sorted(result)


def _run(settings: Settings) -> None:
    """Execute the main dvdrip workflow.

    Args:
        settings: Parsed CLI settings.
    """
    if not settings.scan and settings.output is None:
        msg = "output argument is required"
        raise UserError(msg)

    dvd = DVD(
        settings.input,
        verbose=settings.verbose,
        mount_timeout=settings.mount_timeout,
    )
    _logger.info("Reading from %r", dvd.mountpoint)
    title_numbers = _parse_titles_arg(settings.titles)
    titles = dvd.scan_titles(title_numbers, verbose=settings.verbose)

    if settings.scan:
        display_scan(titles)
        return

    _rip(settings, dvd, titles)


def _rip(settings: Settings, dvd: DVD, titles: list) -> None:
    """Rip titles from a DVD based on settings.

    Args:
        settings: Parsed CLI settings.
        dvd: The DVD to rip from.
        titles: List of scanned titles.
    """
    if settings.main_feature and len(titles) > 1:
        titles = [find_main_feature(titles, verbose=settings.verbose)]

    if not titles:
        msg = "No titles to rip"
        raise UserError(msg)

    if not settings.output:
        msg = "No output specified"
        raise UserError(msg)

    _logger.info("Writing to %r", settings.output)
    tasks = construct_tasks(titles, chapter_split=settings.chapter_split)

    filenames = task_filenames(
        tasks,
        settings.output,
        dry_run=settings.dry_run,
    )
    for filename in filenames:
        if Path(filename).exists():
            msg = f"{filename!r} already exists"
            raise UserError(msg)

    perform_tasks(
        dvd,
        tasks,
        filenames,
        dry_run=settings.dry_run,
        verbose=settings.verbose,
    )

    if not settings.dry_run:
        dvd.eject()


def main() -> None:
    """CLI entrypoint for dvdrip."""
    settings = Settings()  # type: ignore[call-arg]  # ty: ignore[missing-argument]

    logging.basicConfig(
        level=logging.DEBUG if settings.verbose else logging.INFO,
        format="%(message)s",
        stream=sys.stdout,
    )

    try:
        _run(settings)
    except FileExistsError as exc:
        _logger.error("%s: %r", exc.strerror, exc.filename)
        sys.exit(1)
    except UserError as exc:
        _logger.error("%s", exc.message)
        sys.exit(1)
