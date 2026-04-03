"""Tests for dvdrip._subprocess."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from dvdrip._subprocess import check_err, check_output


class TestCheckErr:
    def test_returns_decoded_stderr(self) -> None:
        with patch("dvdrip._subprocess.subprocess.Popen") as mock_popen:
            process = MagicMock()
            process.communicate.return_value = (None, b"stderr output")
            process.poll.return_value = 0
            mock_popen.return_value = process

            result = check_err(["echo", "test"])
            assert result == "stderr output"

    def test_raises_on_nonzero_exit(self) -> None:
        with patch("dvdrip._subprocess.subprocess.Popen") as mock_popen:
            process = MagicMock()
            process.communicate.return_value = (None, b"error")
            process.poll.return_value = 1
            mock_popen.return_value = process

            with pytest.raises(subprocess.CalledProcessError) as exc_info:
                check_err(["bad", "cmd"])
            assert exc_info.value.returncode == 1

    def test_passes_stdout_kwarg(self) -> None:
        with patch("dvdrip._subprocess.subprocess.Popen") as mock_popen:
            process = MagicMock()
            process.communicate.return_value = (None, b"")
            process.poll.return_value = 0
            mock_popen.return_value = process

            check_err(["cmd"], stdout=subprocess.PIPE)
            mock_popen.assert_called_once_with(
                ["cmd"],
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE,
            )


class TestCheckOutput:
    def test_returns_decoded_stdout(self) -> None:
        with patch("dvdrip._subprocess.subprocess.check_output") as mock:
            mock.return_value = b"hello world"
            result = check_output(["echo", "hello"])
            assert result == "hello world"
