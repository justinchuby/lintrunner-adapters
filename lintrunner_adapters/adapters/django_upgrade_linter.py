"""Upgrade your Django project code."""

from __future__ import annotations

import argparse
import concurrent.futures
import logging
import os
import sys
from typing import Tuple, cast

from django_upgrade.data import Settings
from django_upgrade.main import apply_fixers

from lintrunner_adapters import LintMessage, LintSeverity, add_default_options

LINTER_CODE = "DJANGO_UPGRADE"


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


def check_file(filename: str, settings: Settings) -> list[LintMessage]:
    with open(filename, "rb") as fb:
        contents_bytes = fb.read()

    try:
        original = replacement = contents_bytes.decode("utf-8")
        replacement = apply_fixers(replacement, settings, filename)

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
        description=f"django-upgrade wrapper linter. Linter code: {LINTER_CODE}",
        fromfile_prefix_chars="@",
    )
    parser.add_argument(
        "--target-version",
        default="2.2",
        choices=[
            "1.7",
            "1.8",
            "1.9",
            "1.10",
            "1.11",
            "2.0",
            "2.1",
            "2.2",
            "3.0",
            "3.1",
            "3.2",
            "4.0",
            "4.1",
        ],
    )
    add_default_options(parser)
    args = parser.parse_args()

    target_version: tuple[int, int] = cast(
        Tuple[int, int],
        tuple(int(x) for x in args.target_version.split(".", 1)),
    )
    settings = Settings(target_version=target_version)

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
                settings,
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
