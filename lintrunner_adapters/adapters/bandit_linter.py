# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: MIT
"""Adapter for https://bandit.readthedocs.io/en/latest/"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import logging
import os
import sys
from typing import Any

from lintrunner_adapters import (
    LintMessage,
    LintSeverity,
    add_default_options,
    run_command,
)

LINTER_CODE = "BANDIT"

SEVERITIES = {
    "LOW": LintSeverity.ADVICE,
    "MEDIUM": LintSeverity.WARNING,
    "HIGH": LintSeverity.ERROR,
}


def format_lint_messages(
    message: str,
    code: str,
    string_code: str | None,
) -> str:
    suffix = string_code or code
    formatted = f"{message} ({suffix})" if suffix else message
    return formatted


def decode_failed_message(filename: str, err: UnicodeDecodeError) -> LintMessage:
    return LintMessage(
        path=filename,
        line=None,
        char=None,
        code=LINTER_CODE,
        severity=LintSeverity.ERROR,
        name="decode-failed",
        original=None,
        replacement=None,
        description=(f"utf-8 decoding failed due to {err.__class__.__name__}:\n{err}"),
    )


def command_failed_message(filename: str, err: Exception) -> LintMessage:
    return LintMessage(
        path=filename,
        line=None,
        char=None,
        code=LINTER_CODE,
        severity=LintSeverity.ERROR,
        name="command-failed",
        original=None,
        replacement=None,
        description=(f"Failed due to {err.__class__.__name__}:\n{err}"),
    )


def run_bandit(
    filename: str,
    configfile: str | None,
    timeout: int,
) -> bytes | None:
    return run_command(
        [
            "bandit",
            "--format",
            "json",
            "--quiet",
            "--exit-zero",
            *([f"--configfile={configfile}"] if configfile else []),
            filename,
        ],
        check=True,
        timeout=timeout,
    ).stdout


def parse_payload(
    stdout_bytes: bytes | None,
    filename: str,
) -> tuple[dict[str, Any] | None, list[LintMessage]]:
    if not stdout_bytes:
        return None, []
    try:
        stdout = stdout_bytes.decode("utf-8").strip()
    except UnicodeDecodeError as err:
        return None, [decode_failed_message(filename, err)]
    if not stdout:
        return None, []
    return json.loads(stdout), []


def coerce_optional_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def errors_from_payload(payload: dict[str, Any], filename: str) -> list[LintMessage]:
    return [
        LintMessage(
            path=error.get("filename") or filename,
            line=None,
            char=None,
            code=LINTER_CODE,
            severity=LintSeverity.ERROR,
            name="bandit-error",
            original=None,
            replacement=None,
            description=error.get("reason") or "Bandit reported an error.",
        )
        for error in payload.get("errors", [])
    ]


def issue_to_message(issue: dict[str, Any], filename: str) -> LintMessage:
    code = issue.get("test_id") or LINTER_CODE
    issue_text = issue.get("issue_text") or "Bandit reported an issue."
    severity = SEVERITIES.get(
        (issue.get("issue_severity") or "").upper(),
        LintSeverity.WARNING,
    )
    return LintMessage(
        path=issue.get("filename") or filename,
        name=code,
        description=format_lint_messages(
            issue_text,
            code,
            issue.get("test_name"),
        ),
        line=coerce_optional_int(issue.get("line_number")),
        char=coerce_optional_int(issue.get("col_offset")),
        code=LINTER_CODE,
        severity=severity,
        original=None,
        replacement=None,
    )


def issues_from_payload(payload: dict[str, Any], filename: str) -> list[LintMessage]:
    return [issue_to_message(issue, filename) for issue in payload.get("results", [])]


def check_file(
    filename: str,
    *,
    configfile: str | None,
    timeout: int,
) -> list[LintMessage]:
    try:
        stdout_bytes = run_bandit(
            filename=filename,
            configfile=configfile,
            timeout=timeout,
        )
    except Exception as err:
        return [command_failed_message(filename, err)]

    payload, decode_messages = parse_payload(stdout_bytes, filename)
    if decode_messages:
        return decode_messages
    if payload is None:
        return []

    return [
        *errors_from_payload(payload, filename),
        *issues_from_payload(payload, filename),
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description=f"bandit wrapper linter. Linter code: {LINTER_CODE}",
        fromfile_prefix_chars="@",
    )
    parser.add_argument(
        "--configfile",
        default=None,
        type=str,
        help="bandit config file",
    )
    parser.add_argument(
        "--timeout",
        default=90,
        type=int,
        help="seconds to wait for bandit",
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
            executor.submit(
                check_file,
                filename,
                configfile=args.configfile,
                timeout=args.timeout,
            ): filename
            for filename in args.filenames
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
