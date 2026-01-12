# SPDX-FileCopyrightText: Copyright 2025-2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
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
    as_posix,
    run_command,
)

LINTER_CODE = "DOCFORMATTER"


def check_file(
    filename: str,
    retries: int,
    timeout: int,
    config: str | None,
) -> list[LintMessage]:
    try:
        path = Path(filename)
        original = path.read_bytes()

        args = ["docformatter"]
        if config is not None:
            args += ["--config", config]
        args.append("-")

        proc = run_command(
            args,
            retries=retries,
            timeout=timeout,
            input=original,
            check=False,
        )

        replacement = proc.stdout
        if not replacement:
            raise subprocess.CalledProcessError(
                proc.returncode,
                proc.args,
                output=proc.stdout,
                stderr=proc.stderr,
            )
    except subprocess.TimeoutExpired:
        return [
            LintMessage(
                path=filename,
                line=None,
                char=None,
                code=LINTER_CODE,
                severity=LintSeverity.ERROR,
                name="timeout",
                original=None,
                replacement=None,
                description=f"docformatter timed out while processing {filename}.",
            )
        ]
    except (OSError, subprocess.CalledProcessError) as err:
        return [
            LintMessage(
                path=filename,
                line=None,
                char=None,
                code=LINTER_CODE,
                severity=LintSeverity.ADVICE,
                name="command-failed",
                original=None,
                replacement=None,
                description=(
                    f"Failed due to {err.__class__.__name__}:\n{err}"
                    if not isinstance(err, subprocess.CalledProcessError)
                    else (
                        "COMMAND (exit code {returncode})\n"
                        "{command}\n\n"
                        "STDERR\n{stderr}\n\n"
                        "STDOUT\n{stdout}"
                    ).format(
                        returncode=err.returncode,
                        command=" ".join(as_posix(x) for x in err.cmd),
                        stderr=err.stderr.decode("utf-8").strip() or "(empty)",
                        stdout=err.stdout.decode("utf-8").strip() or "(empty)",
                    )
                ),
            )
        ]

    try:
        original_decoded = original.decode("utf-8")
        replacement_decoded = replacement.decode("utf-8")
    except UnicodeDecodeError as err:
        return [
            LintMessage(
                path=filename,
                line=None,
                char=None,
                code=LINTER_CODE,
                severity=LintSeverity.ERROR,
                name="decode-failed",
                original=None,
                replacement=None,
                description=f"utf-8 decoding failed due to {err.__class__.__name__}:\n{err}",
            )
        ]

    if original_decoded == replacement_decoded:
        return []

    return [
        LintMessage(
            path=filename,
            line=None,
            char=None,
            code=LINTER_CODE,
            name="format",
            original=original_decoded,
            replacement=replacement_decoded,
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
    parser.add_argument(
        "--timeout",
        default=90,
        type=int,
        help="seconds to wait for docformatter",
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
            executor.submit(check_file, x, args.retries, args.timeout, args.config): x
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
