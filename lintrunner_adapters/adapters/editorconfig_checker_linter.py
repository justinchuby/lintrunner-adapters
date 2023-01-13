"""Adapter for editorconfig-checker."""

from __future__ import annotations

import argparse
import logging
import re
import sys
from typing import Pattern

import lintrunner_adapters
from lintrunner_adapters import LintMessage, LintSeverity, run_command

LINTER_CODE = "EDITORCONFIG-CHECKER"

RESULTS_RE: Pattern[str] = re.compile(
    r"""(?mx)
    ^
    [ \t]*  # Leading whitespace.
    (?:(?P<line>\d+):)?
    \s(?P<message>.*)
    $
    """
)


def _test_results_re() -> None:
    """
    >>> def t(s): return RESULTS_RE.search(s).groupdict()

    >>> t(r"\tNo final newline expected")
    ... # doctest: +NORMALIZE_WHITESPACE
    {'line': None, 'message': 'No final newline expected'}

    >>> t(r"\t6: Trailing whitespace")
    ... # doctest: +NORMALIZE_WHITESPACE
    {'line': '6', 'message': 'Trailing whitespace'}
    """  # noqa: D301
    pass


def check_files(
    filenames: list[str],
    *,
    retries: int,
) -> list[LintMessage]:
    try:
        proc = run_command(
            ["ec", "-no-color", *filenames],
            retries=retries,
        )
    except OSError as err:
        return [
            LintMessage(
                path=None,
                line=None,
                char=None,
                code=LINTER_CODE,
                severity=LintSeverity.ERROR,
                name="command-failed",
                original=None,
                replacement=None,
                description=(f"Failed due to {err.__class__.__name__}:\n{err}"),
            )
        ]
    stdout = str(proc.stdout, "utf-8").strip()
    lint_messages = []
    path = ""
    for line in stdout.splitlines():
        if not line.startswith("\t"):
            # Trim the trailing colon.
            path = line[:-1]
        else:
            match = RESULTS_RE.search(line)
            if match:
                lint_messages.append(
                    LintMessage(
                        path=path,
                        line=int(match.group("line")) if match.group("line") else None,
                        char=None,
                        code=LINTER_CODE,
                        severity=LintSeverity.WARNING,
                        name="editorconfig",
                        original=None,
                        replacement=None,
                        description=match.group("message"),
                    )
                )
    return lint_messages


def main() -> None:
    parser = argparse.ArgumentParser(
        description=f"editorconfig-checker wrapper linter. Linter code: {LINTER_CODE}",
        fromfile_prefix_chars="@",
    )
    lintrunner_adapters.add_default_options(parser)
    args = parser.parse_args()

    logging.basicConfig(
        format="<%(threadName)s:%(levelname)s> %(message)s",
        level=logging.NOTSET
        if args.verbose
        else logging.DEBUG
        if len(args.filenames) < 1000
        else logging.INFO,
        stream=sys.stderr,
    )

    lint_messages = check_files(
        list(args.filenames),
        retries=args.retries,
    )
    for lint_message in lint_messages:
        lint_message.display()


if __name__ == "__main__":
    main()
