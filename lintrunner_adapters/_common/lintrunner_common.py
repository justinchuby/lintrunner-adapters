from __future__ import annotations

import argparse
import dataclasses
import enum
import json
import logging
import os
import subprocess
import sys
import time
from typing import Any, BinaryIO, Optional

IS_WINDOWS: bool = os.name == "nt"


def eprint(*args: Any, **kwargs: Any) -> None:
    """Print to stderr."""
    print(*args, file=sys.stderr, flush=True, **kwargs)


class LintSeverity(str, enum.Enum):
    """Severity of a lint message."""

    ERROR = "error"
    WARNING = "warning"
    ADVICE = "advice"
    DISABLED = "disabled"


@dataclasses.dataclass(frozen=True)
class LintMessage:
    """A lint message defined by https://docs.rs/lintrunner/latest/lintrunner/lint_message/struct.LintMessage.html."""

    path: Optional[str]
    line: Optional[int]
    char: Optional[int]
    code: str
    severity: LintSeverity
    name: str
    original: Optional[str]
    replacement: Optional[str]
    description: Optional[str]

    def asdict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    def display(self) -> None:
        """Print to stdout for lintrunner to consume."""
        print(json.dumps(self.asdict()), flush=True)


def as_posix(name: str) -> str:
    return name.replace("\\", "/") if IS_WINDOWS else name


def _run_command(
    args: list[str],
    *,
    timeout: Optional[int],
    stdin: Optional[BinaryIO],
    input: Optional[bytes],
    check: bool,
) -> "subprocess.CompletedProcess[bytes]":
    logging.debug("$ %s", " ".join(args))
    start_time = time.monotonic()
    try:
        if input is not None:
            return subprocess.run(  # noqa: DUO116
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=IS_WINDOWS,  # So batch scripts are found.
                input=input,
                timeout=timeout,
                check=check,
            )

        return subprocess.run(  # noqa: DUO116
            args,
            stdin=stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=IS_WINDOWS,  # So batch scripts are found.
            timeout=timeout,
            check=check,
        )
    finally:
        end_time = time.monotonic()
        logging.debug("took %dms", (end_time - start_time) * 1000)


def run_command(
    args: list[str],
    *,
    retries: int = 0,
    timeout: Optional[int] = None,
    stdin: Optional[BinaryIO] = None,
    input: Optional[bytes] = None,
    check: bool = False,
) -> "subprocess.CompletedProcess[bytes]":
    remaining_retries = retries
    while True:
        try:
            return _run_command(
                args, timeout=timeout, stdin=stdin, input=input, check=check
            )
        except subprocess.TimeoutExpired as err:
            if remaining_retries == 0:
                raise err
            remaining_retries -= 1
            logging.warning(
                "(%s/%s) Retrying because command failed with: %r",
                retries - remaining_retries,
                retries,
                err,
            )
            time.sleep(1)


def add_default_options(parser: argparse.ArgumentParser) -> None:
    """Add default options to a parser.

    This should be called the last in the chain of add_argument calls.
    """
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="number of times to retry if the linter times out.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="verbose logging",
    )
    parser.add_argument(
        "filenames",
        nargs="+",
        help="paths to lint",
    )
