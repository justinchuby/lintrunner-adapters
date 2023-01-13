"""Add trailing commas to calls and literals."""

from __future__ import annotations

import argparse
import concurrent.futures
import logging
import os
import sys

from add_trailing_comma._main import _fix_src

from lintrunner_adapters import LintMessage, LintSeverity, add_default_options

LINTER_CODE = "ADD-TRAILING-COMMA"


def format_error_message(filename: str, err: Exception) -> LintMessage:
    return LintMessage(
        path=filename,
        line=None,
        char=None,
        code=LINTER_CODE,
        severity=LintSeverity.ADVICE,
        name="command-failed",
        original=None,
        replacement=None,
        description=(f"Failed due to {err.__class__.__name__}:\n{err}"),
    )


def check_file(filename: str) -> list[LintMessage]:
    with open(filename, "rb") as fb:
        contents_bytes = fb.read()

    try:
        original = contents_text = contents_bytes.decode("utf-8")
        replacement = _fix_src(contents_text, (3, 6))

        if original == replacement:
            return []

        return [
            LintMessage(
                path=filename,
                line=None,
                char=None,
                code=LINTER_CODE,
                severity=LintSeverity.WARNING,
                name="format",
                original=original,
                replacement=replacement,
                description="Run `lintrunner -a` to apply this patch.",
            )
        ]
    except Exception as err:
        return [format_error_message(filename, err)]


def main() -> None:
    parser = argparse.ArgumentParser(
        description=f"add-trailing-comma wrapper linter. Linter code: {LINTER_CODE}",
        fromfile_prefix_chars="@",
    )
    add_default_options(parser)
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

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=os.cpu_count(),
        thread_name_prefix="Thread",
    ) as executor:
        futures = {executor.submit(check_file, x): x for x in args.filenames}
        for future in concurrent.futures.as_completed(futures):
            try:
                for lint_message in future.result():
                    lint_message.display()
            except Exception:
                logging.critical('Failed at "%s".', futures[future])
                raise


if __name__ == "__main__":
    main()
