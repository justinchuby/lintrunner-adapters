"""Upgrade syntax for newer versions of the language."""

from __future__ import annotations

import argparse
import concurrent.futures
import logging
import os
import sys

from pyupgrade._data import Settings
from pyupgrade._main import _fix_plugins, _fix_tokens

from lintrunner_adapters import LintMessage, LintSeverity, add_default_options

LINTER_CODE = "PYUPGRADE"


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


def check_file(
    filename: str,
    *,
    min_version: tuple[int, ...],
    keep_percent_format: bool,
    keep_mock: bool,
    keep_runtime_typing: bool,
) -> list[LintMessage]:
    with open(filename, "rb") as fb:
        contents_bytes = fb.read()

    try:
        original = replacement = contents_bytes.decode("utf-8")
        replacement = _fix_plugins(
            replacement,
            settings=Settings(
                min_version=min_version,
                keep_percent_format=keep_percent_format,
                keep_mock=keep_mock,
                keep_runtime_typing=keep_runtime_typing,
            ),
        )
        replacement = _fix_tokens(replacement)

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
        description=f"pyupgrade wrapper linter. Linter code: {LINTER_CODE}",
        fromfile_prefix_chars="@",
    )
    parser.add_argument("--keep-percent-format", action="store_true")
    parser.add_argument("--keep-mock", action="store_true")
    parser.add_argument("--keep-runtime-typing", action="store_true")
    parser.add_argument(
        "--py3-plus",
        "--py3-only",
        action="store_const",
        dest="min_version",
        default=(3,),
        const=(3,),
    )
    parser.add_argument(
        "--py36-plus",
        action="store_const",
        dest="min_version",
        const=(3, 6),
    )
    parser.add_argument(
        "--py37-plus",
        action="store_const",
        dest="min_version",
        const=(3, 7),
    )
    parser.add_argument(
        "--py38-plus",
        action="store_const",
        dest="min_version",
        const=(3, 8),
    )
    parser.add_argument(
        "--py39-plus",
        action="store_const",
        dest="min_version",
        const=(3, 9),
    )
    parser.add_argument(
        "--py310-plus",
        action="store_const",
        dest="min_version",
        const=(3, 10),
    )
    parser.add_argument(
        "--py311-plus",
        action="store_const",
        dest="min_version",
        const=(3, 11),
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
        futures = {
            executor.submit(
                check_file,
                x,
                min_version=args.min_version,
                keep_percent_format=args.keep_percent_format,
                keep_mock=args.keep_mock,
                keep_runtime_typing=args.keep_runtime_typing,
            ): x
            for x in args.filenames
        }
        for future in concurrent.futures.as_completed(futures):
            try:
                for lint_message in future.result():
                    lint_message.display()
            except Exception:
                logging.critical('Failed at "%s".', futures[future])
                raise


if __name__ == "__main__":
    main()
