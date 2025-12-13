# SPDX-FileCopyrightText: Copyright 2025 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: MIT
"""Adapter for https://github.com/PyCQA/docformatter"""
from __future__ import annotations

import argparse
import concurrent.futures
import logging
import os
import subprocess
import sys
from pathlib import Path

from lintrunner_adapters import (
    LintMessage,
    LintSeverity,
    add_default_options,
    run_command,
)

LINTER_CODE = "DOCFORMATTER"


def check_file(
    filename: str,
    retries: int,
    config: str | None,
) -> list[LintMessage]:
    try:
        path = Path(filename)
        original = path.read_text(encoding="utf-8")

        args = ["docformatter"]
        if config is not None:
            args += ["--config", config]
        args += ["--diff", str(path)]

        proc = run_command(args, retries=retries, check=False)
        # 0 means no change, 3 means there was reformatting.
        if proc.returncode not in (0, 3):
            raise subprocess.CalledProcessError(
                proc.returncode,
                proc.args,
                output=proc.stdout,
                stderr=proc.stderr,
            )

        patch_proc = run_command(
            ["patch", filename, "-o", "-"], input=proc.stdout, check=True
        )

        replacement = patch_proc.stdout.decode("utf-8")
    except Exception as err:
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

    if original == replacement:
        return []

    return [
        LintMessage(
            path=filename,
            line=None,
            char=None,
            code=LINTER_CODE,
            name="format",
            original=original,
            replacement=replacement,
            severity=LintSeverity.WARNING,
            description="Run `lintrunner -a` to apply this patch.",
        )
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description=f"Docstring formatter. Linter code: {LINTER_CODE}.",
        fromfile_prefix_chars="@",
    )
    parser.add_argument(
        "--config",
        required=False,
        help="location of docformatter config",
    )
    add_default_options(parser)
    args = parser.parse_args()

    logging.basicConfig(
        format="<%(threadName)s:%(levelname)s> %(message)s",
        level=(
            logging.NOTSET
            if args.verbose
            else logging.DEBUG
            if len(args.filenames) < 1000
            else logging.INFO
        ),
        stream=sys.stderr,
    )

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=os.cpu_count(),
        thread_name_prefix="Thread",
    ) as executor:
        futures = {
            executor.submit(check_file, x, args.retries, args.config): x
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
