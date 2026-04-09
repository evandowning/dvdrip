"""Subprocess wrappers for running external commands."""

import os
import subprocess
from typing import Final

CHAR_ENCODING: Final[str] = "UTF-8"


def check_err(
    args: list[str],
    *,
    stdout: int | None = None,
) -> str:
    """Run a subprocess and return its decoded stderr output.

    Args:
        args: Command and arguments to run.
        stdout: How to handle stdout (e.g. subprocess.PIPE).

    Raises:
        subprocess.CalledProcessError: If the process exits with a non-zero code.
    """
    process = subprocess.Popen(  # noqa: S603
        args,
        stderr=subprocess.PIPE,
        stdout=stdout,
    )
    _, stderr = process.communicate()
    retcode = process.poll()
    if retcode:
        raise subprocess.CalledProcessError(retcode, args, output=stderr)
    assert stderr is not None  # noqa: S101
    return stderr.decode(CHAR_ENCODING, "replace")


def check_output(args: list[str]) -> str:
    """Run a subprocess and return its decoded stdout output.

    Args:
        args: Command and arguments to run.
    """
    raw = subprocess.check_output(args)  # noqa: S603
    s = raw.decode(CHAR_ENCODING)
    return s.replace(os.linesep, "\n")
