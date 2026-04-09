"""Task construction, filename generation, and execution."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from dvdrip._errors import UserError
from dvdrip._models import Task, Title
from dvdrip._parsing import parse_duration

if TYPE_CHECKING:
    from dvdrip._dvd import DVD

_logger = logging.getLogger(__name__)


def find_main_feature(
    titles: list[Title],
    *,
    verbose: bool = False,
) -> Title:
    """Find the longest title on the disc (the main feature).

    Args:
        titles: List of titles to search.
        verbose: If True, print selection details.

    Returns:
        The Title with the longest duration.
    """
    if verbose:
        _logger.debug("Attempting to determine main feature of %d titles...", len(titles))
    main_feature = max(
        titles,
        key=lambda title: parse_duration(str(title.info.duration)),
    )
    if verbose:
        _logger.debug("Selected %r as main feature.", main_feature.number)
    return main_feature


def construct_tasks(
    titles: list[Title],
    *,
    chapter_split: bool,
) -> list[Task]:
    """Create ripping tasks from titles.

    Args:
        titles: List of titles to create tasks for.
        chapter_split: If True, create one task per chapter.

    Returns:
        List of Task models.
    """
    tasks: list[Task] = []
    for title in titles:
        num_chapters = len(title.info.chapters)
        if chapter_split and num_chapters > 1:
            tasks.extend(
                Task(title=title, chapter=chapter) for chapter in range(1, num_chapters + 1)
            )
        else:
            tasks.append(Task(title=title))
    return tasks


def task_filenames(
    tasks: list[Task],
    output: str,
    *,
    dry_run: bool = False,
) -> list[str]:
    """Generate output filenames for a list of tasks.

    Args:
        tasks: List of ripping tasks.
        output: Base output path.
        dry_run: If True, do not create directories.

    Raises:
        UserError: If multiple tasks would produce the same filename.

    Returns:
        List of output file paths.
    """
    if len(tasks) > 1:
        result = [_multi_filename(task, output) for task in tasks]
        if not dry_run:
            Path(output).mkdir(parents=True)
    else:
        result = [f"{output}.mp4" for _ in tasks]

    if len(set(result)) != len(result):
        msg = "multiple tasks use same filename"
        raise UserError(msg)
    return result


def _multi_filename(task: Task, output: str) -> str:
    """Compute filename for a task when ripping multiple titles."""
    if task.chapter is None:
        return str(Path(output) / f"Title{task.title.number:02d}.mp4")
    return str(
        Path(output) / f"Title{task.title.number:02d}_{task.chapter:02d}.mp4",
    )


def perform_tasks(  # noqa: PLR0913
    dvd: DVD,
    tasks: list[Task],
    filenames: list[str],
    *,
    preset: str,
    dry_run: bool = False,
    verbose: bool = False,
) -> None:
    """Execute all ripping tasks.

    Args:
        dvd: A DVD instance.
        tasks: List of ripping tasks.
        filenames: Output filenames for each task.
        preset: HandBrakeCLI preset name.
        dry_run: If True, do not actually rip.
        verbose: If True, print detailed progress.
    """
    title_count = len({t.title.number for t in tasks})
    for task, filename in zip(tasks, filenames, strict=True):
        if task.chapter is None:
            _logger.info(
                "Title %d / %d => %r",
                task.title.number,
                title_count,
                filename,
            )
        else:
            num_chapters = len(task.title.info.chapters)
            _logger.info(
                "Title %d / %d , Chapter %d / %d => %r",
                task.title.number,
                title_count,
                task.chapter,
                num_chapters,
                filename,
            )
        dvd.rip_title(task, filename, preset=preset, dry_run=dry_run, verbose=verbose)
