"""Tests for dvdrip._tasks."""

import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from dvdrip._errors import UserError
from dvdrip._models import Duration, Task, Title, TitleInfo
from dvdrip._tasks import construct_tasks, find_main_feature, perform_tasks, task_filenames


def _make_title(number: int, duration_seconds: int, num_chapters: int = 1) -> Title:
    hours = duration_seconds // 3600
    minutes = (duration_seconds % 3600) // 60
    seconds = duration_seconds % 60
    chapters = {str(i): f"duration 00:10:0{i}" for i in range(1, num_chapters + 1)}
    return Title(
        number=number,
        info=TitleInfo(
            duration=Duration(hours=hours, minutes=minutes, seconds=seconds),
            size=" 720x576, pixel aspect: 16/15, display aspect: 1.33, 25.0 fps",
            chapters=chapters,
            audio_tracks={"1": "English"},
            subtitle_tracks={},
        ),
    )


class TestFindMainFeature:
    def test_selects_longest(self) -> None:
        titles = [_make_title(1, 3600), _make_title(2, 7200), _make_title(3, 1800)]
        result = find_main_feature(titles)
        assert result.number == 2

    def test_verbose(self, caplog: pytest.LogCaptureFixture) -> None:
        titles = [_make_title(1, 3600)]
        with caplog.at_level(logging.DEBUG):
            find_main_feature(titles, verbose=True)
        assert "main feature" in caplog.text.lower()


class TestConstructTasks:
    def test_no_split(self) -> None:
        titles = [_make_title(1, 3600, 3)]
        tasks = construct_tasks(titles, chapter_split=False)
        assert len(tasks) == 1
        assert tasks[0].chapter is None

    def test_chapter_split(self) -> None:
        titles = [_make_title(1, 3600, 3)]
        tasks = construct_tasks(titles, chapter_split=True)
        assert len(tasks) == 3
        assert tasks[0].chapter == 1
        assert tasks[2].chapter == 3

    def test_single_chapter_no_split(self) -> None:
        titles = [_make_title(1, 3600, 1)]
        tasks = construct_tasks(titles, chapter_split=True)
        assert len(tasks) == 1
        assert tasks[0].chapter is None


class TestTaskFilenames:
    def test_single_task(self) -> None:
        title = _make_title(1, 3600)
        tasks = [Task(title=title)]
        filenames = task_filenames(tasks, "output/test", dry_run=True)
        assert filenames == ["output/test.mp4"]

    def test_multiple_tasks(self) -> None:
        t1 = _make_title(1, 3600)
        t2 = _make_title(2, 1800)
        tasks = [Task(title=t1), Task(title=t2)]
        filenames = task_filenames(tasks, "output/test", dry_run=True)
        assert "output/test/Title01.mp4" in filenames[0]
        assert "output/test/Title02.mp4" in filenames[1]

    def test_chapter_filenames(self) -> None:
        title = _make_title(1, 3600)
        tasks = [Task(title=title, chapter=1), Task(title=title, chapter=2)]
        filenames = task_filenames(tasks, "output/test", dry_run=True)
        assert "Title01_01.mp4" in filenames[0]
        assert "Title01_02.mp4" in filenames[1]

    def test_duplicate_filenames_raises(self) -> None:
        title = _make_title(1, 3600)
        tasks = [Task(title=title), Task(title=title)]
        with pytest.raises(UserError, match="same filename"):
            task_filenames(tasks, "output/test", dry_run=True)

    def test_creates_directory(self, tmp_path: Path) -> None:
        out = tmp_path / "dvd_out"
        t1 = _make_title(1, 3600)
        t2 = _make_title(2, 1800)
        tasks = [Task(title=t1), Task(title=t2)]
        task_filenames(tasks, str(out), dry_run=False)
        assert out.is_dir()


class TestPerformTasks:
    def test_calls_rip_title(self, caplog: pytest.LogCaptureFixture) -> None:
        dvd = MagicMock()
        title = _make_title(1, 3600, 2)
        tasks = [Task(title=title, chapter=1), Task(title=title, chapter=2)]
        filenames = ["out_01.mp4", "out_02.mp4"]

        with caplog.at_level(logging.INFO):
            perform_tasks(dvd, tasks, filenames, dry_run=False, verbose=False)

        assert dvd.rip_title.call_count == 2
        assert "Title 1" in caplog.text
        assert "Chapter" in caplog.text

    def test_no_chapter(self, caplog: pytest.LogCaptureFixture) -> None:
        dvd = MagicMock()
        title = _make_title(1, 3600)
        tasks = [Task(title=title)]
        filenames = ["out.mp4"]

        with caplog.at_level(logging.INFO):
            perform_tasks(dvd, tasks, filenames, dry_run=True, verbose=False)
        assert "Title 1" in caplog.text
