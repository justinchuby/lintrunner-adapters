"""Adapter for https://github.com/charliermarsh/ruff."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import logging
import os
import subprocess
import sys

from lintrunner_adapters import (
    LintMessage,
    LintSeverity,
    add_default_options,
    as_posix,
    run_command,
)

LINTER_CODE = "RUFF-FIX"


def explain_rule(code: str) -> str:
    proc = run_command(
        [sys.executable, "-mruff", "rule", "--format=json", code],
        check=True,
    )
    rule = json.loads(str(proc.stdout, "utf-8").strip())
    return f"\n{rule['linter']}: {rule['summary']}"


def check_file(
    filename: str,
    severities: dict[str, LintSeverity],
    *,
    config: str | None,
    explain: bool,
    retries: int,
    timeout: int,
) -> list[LintMessage]:
    try:
        with open(filename, "rb") as f:
            original = f.read()
        with open(filename, "rb") as f:
            proc_fix = run_command(
                [
                    sys.executable,
                    "-mruff",
                    "--fix",
                    "-e",
                    "--stdin-filename",
                    filename,
                    "-",
                ]
                + ([f"--config={config}"] if config else []),
                stdin=f,
                retries=retries,
                timeout=timeout,
                check=True,
            )
        proc_lint = run_command(
            [
                sys.executable,
                "-mruff",
                "-e",
                "-q",
                "--format=json",
                "--stdin-filename",
                filename,
                "-",
            ]
            + ([f"--config={config}"] if config else []),
            input=proc_fix.stdout,
            retries=retries,
            timeout=timeout,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as err:
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
                description=(
                    f"Failed due to {err.__class__.__name__}:\n{err}"
                    if not isinstance(err, subprocess.CalledProcessError)
                    else (
                        f"COMMAND (exit code {err.returncode})\n"
                        f"{' '.join(as_posix(x) for x in err.cmd)}\n\n"
                        f"STDERR\n{err.stderr.decode('utf-8').strip() or '(empty)'}\n\n"
                        f"STDOUT\n{err.stdout.decode('utf-8').strip() or '(empty)'}"
                    )
                ),
            )
        ]

    replacement = proc_fix.stdout
    if original == replacement:
        return []
    vulnerabilities = json.loads(str(proc_lint.stdout, "utf-8").strip())
    rules = (
        {code: explain_rule(code) for code in {v["code"] for v in vulnerabilities}}
        if explain
        else None
    )

    return [
        LintMessage(
            path=filename,
            name="format",
            description="Run `lintrunner -a` to apply this patch.",
            line=None,
            char=None,
            code=LINTER_CODE,
            severity=LintSeverity.WARNING,
            original=original.decode("utf-8"),
            replacement=replacement.decode("utf-8"),
        ),
        *[
            LintMessage(
                path=vuln["filename"],
                name=vuln["code"],
                description=vuln["message"]
                if not rules
                else f"{vuln['message']}\n{rules[vuln['code']]}",
                line=int(vuln["location"]["row"]),
                char=int(vuln["location"]["column"]),
                code=LINTER_CODE,
                severity=severities.get(vuln["code"], LintSeverity.ADVICE),
                original=None,
                replacement=None,
            )
            for vuln in vulnerabilities
        ],
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description=f"ruff wrapper linter. Linter code: {LINTER_CODE}",
        fromfile_prefix_chars="@",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to the `pyproject.toml` "
        "or `ruff.toml` file to use for configuration",
    )
    parser.add_argument(
        "--explain",
        action="store_true",
        help="Explain a rule",
    )
    parser.add_argument(
        "--timeout",
        default=90,
        type=int,
        help="Seconds to wait for ruff",
    )
    parser.add_argument(
        "--severity",
        action="append",
        help="map code to severity (e.g. `F401:advice`). "
        "This option can be used multiple times.",
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

    severities: dict[str, LintSeverity] = {}
    if args.severity:
        for severity in args.severity:
            parts = severity.split(":", 1)
            assert len(parts) == 2, f"invalid severity `{severity}`"
            severities[parts[0]] = LintSeverity(parts[1])

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=os.cpu_count(),
        thread_name_prefix="Thread",
    ) as executor:
        futures = {
            executor.submit(
                check_file,
                x,
                severities,
                config=args.config,
                explain=args.explain,
                retries=args.retries,
                timeout=args.timeout,
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
