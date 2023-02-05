"""Linter wrapper for rust clippy.

https://doc.rust-lang.org/clippy
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from typing import Pattern

import lintrunner_adapters
from lintrunner_adapters import LintMessage, LintSeverity, run_command

LINTER_CODE = "CLIPPY"

# Severity can be "I", "C", "R", "W", "E", "F"
# https://pylint.pycqa.org/en/latest/user_guide/usage/output.html
SEVERITIES = {
    "I": LintSeverity.ADVICE,
    "C": LintSeverity.ADVICE,
    "R": LintSeverity.ADVICE,
    "W": LintSeverity.WARNING,
    "E": LintSeverity.ERROR,
    "F": LintSeverity.ERROR,
}



def format_lint_messages(
    message: str, code: str, string_code: str, show_disable: bool
) -> str:
    formatted = (
        f"{message} ({string_code})\n"
        f"See [{string_code}]({pylint_doc_url(code, string_code)})."
    )
    if show_disable:
        formatted += f"\n\nTo disable, use `  # pylint: disable={string_code}`"
    return formatted


def check_files(
    filenames: list[str],
    *,
    retries: int,
) -> list[LintMessage]:
    try:
        # FIXME: Lint the file list
        proc = run_command(
            ["cargo", "clippy", "--message-format=json", "--", *filenames],
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
    return [
        LintMessage(
            path=match["file"],
            name=match["code"],
            description=format_lint_messages(
                match["message"], match["code"], match["string_code"], show_disable
            ),
            line=int(match["line"]),
            char=int(match["column"])
            if match["column"] is not None and not match["column"].startswith("-")
            else None,
            code=LINTER_CODE,
            severity=SEVERITIES.get(match["code"][0], LintSeverity.ERROR),
            original=None,
            replacement=None,
        )
        for match in RESULTS_RE.finditer(stdout)
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description=f"pylint wrapper linter. Linter code: {LINTER_CODE}",
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
        rcfile=args.rcfile,
        jobs=args.jobs,
        retries=args.retries,
        show_disable=args.show_disable,
    )
    for lint_message in lint_messages:
        lint_message.display()


if __name__ == "__main__":
    main()
