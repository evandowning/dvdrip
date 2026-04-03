"""Tests for dvdrip._dvd."""

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from dvdrip._dvd import DVD, _make_title, find_mount_point
from dvdrip._errors import UserError
from dvdrip._models import Duration, Task, Title, TitleInfo


def _make_title_info() -> TitleInfo:
    return TitleInfo(
        duration=Duration(hours=1, minutes=0, seconds=0),
        size=" 720x576, pixel aspect: 16/15, display aspect: 1.33, 25.0 fps",
        chapters={"1": "duration 00:30:00", "2": "duration 00:30:00"},
        audio_tracks={"1": "English (AC3) (5.1 ch) (iso639-2: eng), 48000Hz"},
        subtitle_tracks={"1": "English (Bitmap)(VOBSUB)"},
    )


class TestDVDInit:
    def test_directory_mountpoint(self, tmp_path: Path) -> None:
        dvd = DVD(str(tmp_path), verbose=False)
        assert dvd.mountpoint == str(tmp_path)

    def test_not_directory_raises(self, tmp_path: Path) -> None:
        filepath = tmp_path / "file.txt"
        filepath.write_text("test")
        with pytest.raises(UserError, match="not a directory"):
            DVD(str(filepath), verbose=False)

    def test_block_device_looks_up_mount(self, tmp_path: Path) -> None:
        with (
            patch("dvdrip._dvd.Path") as mock_path_cls,
            patch("dvdrip._dvd.stat") as mock_stat,
            patch("dvdrip._dvd.find_mount_point") as mock_find,
        ):
            mock_path_instance = MagicMock()
            mock_path_instance.stat.return_value.st_mode = 0o060000
            mock_path_instance.is_dir.return_value = True
            mock_path_cls.return_value = mock_path_instance
            mock_stat.S_ISBLK.return_value = True
            mock_find.return_value = str(tmp_path)

            dvd = DVD("/dev/sr0", verbose=False, mount_timeout=5)
            assert dvd.mountpoint == str(tmp_path)


class TestFindMountPoint:
    def test_finds_mount(self) -> None:
        with patch("dvdrip._dvd.check_output") as mock:
            mock.return_value = "/dev/sr0   1024  512  512  50% /media/dvd\n"
            with patch("dvdrip._dvd.os.path.realpath", return_value="/dev/sr0"):
                result = find_mount_point("/dev/sr0", timeout=1)
                assert result == "/media/dvd"

    def test_timeout_raises(self) -> None:
        with (
            patch("dvdrip._dvd.check_output") as mock,
            patch("dvdrip._dvd.os.path.realpath", return_value="/dev/sr0"),
            patch("dvdrip._dvd.time.sleep"),
            patch("dvdrip._dvd.time.time", side_effect=[0, 0, 100]),
        ):
            mock.return_value = "no matching device\n"
            with pytest.raises(UserError, match="not mounted"):
                find_mount_point("/dev/sr0", timeout=0.01)


class TestDVDRipTitle:
    def test_dry_run_does_not_call(self, tmp_path: Path) -> None:
        dvd = DVD(str(tmp_path), verbose=False)
        info = _make_title_info()
        title = Title(number=1, info=info)
        task = Task(title=title, chapter=None)

        with patch("dvdrip._dvd.subprocess.call") as mock_call:
            dvd.rip_title(task, "output.mp4", dry_run=True, verbose=False)
            mock_call.assert_not_called()

    def test_verbose_logs(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        dvd = DVD(str(tmp_path), verbose=False)
        info = _make_title_info()
        title = Title(number=1, info=info)
        task = Task(title=title, chapter=None)

        with caplog.at_level(logging.DEBUG):
            dvd.rip_title(task, "output.mp4", dry_run=True, verbose=True)
        assert "Title Scan:" in caplog.text

    def test_calls_handbrake(self, tmp_path: Path) -> None:
        dvd = DVD(str(tmp_path), verbose=False)
        info = _make_title_info()
        title = Title(number=1, info=info)
        task = Task(title=title, chapter=None)

        with patch("dvdrip._dvd.check_err") as mock:
            dvd.rip_title(task, "output.mp4", dry_run=False, verbose=False)
            mock.assert_called_once()
            args = mock.call_args[0][0]
            assert args[0] == "HandBrakeCLI"

    def test_verbose_calls_subprocess(self, tmp_path: Path) -> None:
        dvd = DVD(str(tmp_path), verbose=False)
        info = _make_title_info()
        title = Title(number=1, info=info)
        task = Task(title=title, chapter=None)

        with patch("dvdrip._dvd.subprocess.call") as mock_call:
            dvd.rip_title(task, "output.mp4", dry_run=False, verbose=True)
            mock_call.assert_called_once()

    def test_with_chapter(self, tmp_path: Path) -> None:
        dvd = DVD(str(tmp_path), verbose=False)
        info = _make_title_info()
        title = Title(number=1, info=info)
        task = Task(title=title, chapter=2)

        with patch("dvdrip._dvd.check_err") as mock:
            dvd.rip_title(task, "output.mp4", dry_run=False, verbose=False)
            args = mock.call_args[0][0]
            assert "--chapters" in args
            assert "2" in args

    def test_with_subtitles(self, tmp_path: Path) -> None:
        dvd = DVD(str(tmp_path), verbose=False)
        info = _make_title_info()
        title = Title(number=1, info=info)
        task = Task(title=title)

        with patch("dvdrip._dvd.check_err") as mock:
            dvd.rip_title(task, "output.mp4", dry_run=False, verbose=False)
            args = mock.call_args[0][0]
            assert "--subtitle" in args


class TestDVDScanTitle:
    def test_returns_lines(self, tmp_path: Path) -> None:
        dvd = DVD(str(tmp_path), verbose=False)
        with patch("dvdrip._dvd.check_err") as mock:
            mock.return_value = "line1\nline2\n"
            lines = dvd.scan_title(1)
            assert "line1" in lines

    def test_verbose_logs(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        dvd = DVD(str(tmp_path), verbose=True)
        with patch("dvdrip._dvd.check_err") as mock, caplog.at_level(logging.DEBUG):
            mock.return_value = "scan output\n"
            dvd.scan_title(1)
        assert "< scan output" in caplog.text


class TestDVDScanAll:
    def test_returns_lines(self, tmp_path: Path) -> None:
        dvd = DVD(str(tmp_path), verbose=False)
        with patch("dvdrip._dvd.check_err") as mock:
            mock.return_value = "line1\nline2\n"
            lines = dvd.scan_all()
            assert "line1" in lines
            args = mock.call_args[0][0]
            assert "--title" in args
            assert "0" in args

    def test_verbose_logs(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        dvd = DVD(str(tmp_path), verbose=True)
        with patch("dvdrip._dvd.check_err") as mock, caplog.at_level(logging.DEBUG):
            mock.return_value = "scan output\n"
            dvd.scan_all()
        assert "< scan output" in caplog.text


class TestDVDScanTitles:
    def test_single_title(self, tmp_path: Path) -> None:
        dvd = DVD(str(tmp_path), verbose=False)
        scan_output = [
            "Scanning title 1 of 1...",
            "+ title 1:",
            "  + duration: 01:30:00",
            "  + size: 720x480, pixel aspect: 8/9, display aspect: 1.33, 29.97 fps",
            "  + chapters:",
            "    + 1: duration 00:45:00",
            "  + audio tracks:",
            "    + 1, English (AC3) (5.1 ch) (iso639-2: eng), 48000Hz",
            "  + subtitle tracks:",
            "    + 1, English (Bitmap)(VOBSUB)",
        ]
        with patch.object(dvd, "scan_all", return_value=scan_output):
            titles = dvd.scan_titles(None)
            assert len(titles) == 1
            assert titles[0].number == 1

    def test_multiple_titles(self, tmp_path: Path) -> None:
        dvd = DVD(str(tmp_path), verbose=False)
        scan_output = [
            "Scanning title 1 of 2...",
            "+ title 1:",
            "  + duration: 01:00:00",
            "  + size: 720x480, pixel aspect: 8/9, display aspect: 1.33, 29.97 fps",
            "  + chapters:",
            "    + 1: duration 01:00:00",
            "  + audio tracks:",
            "    + 1, English (AC3) (5.1 ch) (iso639-2: eng), 48000Hz",
            "  + subtitle tracks:",
            "    + 1, English (Bitmap)(VOBSUB)",
            "+ title 2:",
            "  + duration: 00:30:00",
            "  + size: 720x480, pixel aspect: 8/9, display aspect: 1.33, 29.97 fps",
            "  + chapters:",
            "    + 1: duration 00:30:00",
            "  + audio tracks:",
            "    + 1, English (AC3) (5.1 ch) (iso639-2: eng), 48000Hz",
            "  + subtitle tracks:",
            "    + 1, English (Bitmap)(VOBSUB)",
        ]
        with patch.object(dvd, "scan_all", return_value=scan_output):
            titles = dvd.scan_titles(None)
            assert len(titles) == 2
            assert titles[0].number == 1
            assert titles[1].number == 2

    def test_skipped_title_numbers(self, tmp_path: Path) -> None:
        dvd = DVD(str(tmp_path), verbose=False)
        scan_output = [
            "Scanning title 2 of 8...",
            "+ title 2:",
            "  + duration: 03:00:18",
            "  + size: 720x480, pixel aspect: 8/9, display aspect: 1.33, 29.97 fps",
            "  + chapters:",
            "    + 1: duration 03:00:18",
            "  + audio tracks:",
            "    + 1, English (AC3) (5.1 ch) (iso639-2: eng), 48000Hz",
            "  + subtitle tracks:",
            "    + 1, English (Bitmap)(VOBSUB)",
            "+ title 3:",
            "  + duration: 00:30:00",
            "  + size: 720x480, pixel aspect: 8/9, display aspect: 1.33, 29.97 fps",
            "  + chapters:",
            "    + 1: duration 00:30:00",
            "  + audio tracks:",
            "    + 1, English (AC3) (5.1 ch) (iso639-2: eng), 48000Hz",
            "  + subtitle tracks:",
            "    + 1, English (Bitmap)(VOBSUB)",
        ]
        with patch.object(dvd, "scan_all", return_value=scan_output):
            titles = dvd.scan_titles(None)
            assert len(titles) == 2
            assert titles[0].number == 2
            assert titles[1].number == 3

    def test_filter_by_title_numbers(self, tmp_path: Path) -> None:
        dvd = DVD(str(tmp_path), verbose=False)
        scan_output = [
            "+ title 2:",
            "  + duration: 01:00:00",
            "  + size: 720x480, pixel aspect: 8/9, display aspect: 1.33, 29.97 fps",
            "  + chapters:",
            "    + 1: duration 01:00:00",
            "  + audio tracks:",
            "    + 1, English (AC3) (5.1 ch) (iso639-2: eng), 48000Hz",
            "  + subtitle tracks:",
            "    + 1, English (Bitmap)(VOBSUB)",
            "+ title 3:",
            "  + duration: 00:30:00",
            "  + size: 720x480, pixel aspect: 8/9, display aspect: 1.33, 29.97 fps",
            "  + chapters:",
            "    + 1: duration 00:30:00",
            "  + audio tracks:",
            "    + 1, English (AC3) (5.1 ch) (iso639-2: eng), 48000Hz",
            "  + subtitle tracks:",
            "    + 1, English (Bitmap)(VOBSUB)",
        ]
        with patch.object(dvd, "scan_all", return_value=scan_output):
            titles = dvd.scan_titles([3])
            assert len(titles) == 1
            assert titles[0].number == 3

    def test_extra_fields_ignored(self, tmp_path: Path) -> None:
        dvd = DVD(str(tmp_path), verbose=False)
        scan_output = [
            "+ title 2:",
            "  + Main Feature",
            "  + index 2",
            "  + duration: 03:00:18",
            "  + size: 720x480, pixel aspect: 8/9, display aspect: 1.33, 29.970 fps",
            "  + autocrop: 0/0/8/8",
            "  + chapters:",
            "    + 1: duration 03:00:18",
            "  + audio tracks:",
            "    + 1, English (AC3, 2.0 ch, 192 kbps) (iso639-2: eng), 48000Hz, 192000bps",
            "  + subtitle tracks:",
            "    + 1, English (4:3) [VOBSUB]",
        ]
        with patch.object(dvd, "scan_all", return_value=scan_output):
            titles = dvd.scan_titles(None)
            assert len(titles) == 1
            assert titles[0].number == 2


class TestDVDEject:
    def test_unix_eject(self, tmp_path: Path) -> None:
        dvd = DVD(str(tmp_path), verbose=False)
        with patch("dvdrip._dvd.subprocess.call", return_value=0) as mock:
            dvd.eject()
            mock.assert_called_once()

    def test_unix_eject_retries(self, tmp_path: Path) -> None:
        dvd = DVD(str(tmp_path), verbose=False)
        with (
            patch("dvdrip._dvd.subprocess.call", side_effect=[1, 0]) as mock,
            patch("dvdrip._dvd.time.sleep") as mock_sleep,
        ):
            dvd.eject()
            assert mock.call_count == 2
            mock_sleep.assert_called_once()

    def test_windows_eject_non_drive_letter(self, tmp_path: Path) -> None:
        dvd = DVD(str(tmp_path), verbose=False)
        dvd.mountpoint = "C:\\Users\\test"
        with patch("dvdrip._dvd.os.name", "nt"):
            dvd.eject()

    def test_windows_eject_drive_letter(self, tmp_path: Path) -> None:
        dvd = DVD(str(tmp_path), verbose=False)
        dvd.mountpoint = "F:"
        with (
            patch("dvdrip._dvd.os.name", "nt"),
            patch("dvdrip._dvd.ctypes") as mock_ctypes,
        ):
            dvd.eject()
            assert mock_ctypes.windll.WINMM.mciSendStringW.call_count == 2


class TestMakeTitle:
    def test_invalid_name_raises(self) -> None:
        with pytest.raises(ValueError, match="Unexpected title name"):
            _make_title("not a title", {})
