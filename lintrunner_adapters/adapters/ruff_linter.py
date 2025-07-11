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

LINTER_CODE = "RUFF"


logger = logging.getLogger(__name__)


def explain_rule(code: str) -> str:
    proc = run_command(
        ["ruff", "rule", "--format=json", code],
        check=True,
    )
    rule = json.loads(str(proc.stdout, "utf-8").strip())
    text = f"\n{rule['linter']}: {rule['summary']}"
    if "explanation" in rule:
        text += f"\n\n{rule['explanation']}"
    return text


def get_issue_severity(code: str | None) -> LintSeverity:
    if not code:
        # Handle rare cases of empty / None code
        return LintSeverity.ERROR

    # "B901": `return x` inside a generator
    # "B902": Invalid first argument to a method
    # "B903": __slots__ efficiency
    # "B950": Line too long
    # "C4": Flake8 Comprehensions
    # "C9": Cyclomatic complexity
    # "E2": PEP8 horizontal whitespace "errors"
    # "E3": PEP8 blank line "errors"
    # "E5": PEP8 line length "errors"
    # "T400": type checking Notes
    # "T49": internal type checker errors or unmatched messages
    if any(
        code.startswith(x)
        for x in (
            "B9",
            "C4",
            "C9",
            "E2",
            "E3",
            "E5",
            "T400",
            "T49",
            "PLC",
            "PLR",
        )
    ):
        return LintSeverity.ADVICE

    # "F821": Undefined name
    # "E999": syntax error
    if any(code.startswith(x) for x in ("F821", "E999", "PLE")):
        return LintSeverity.ERROR

    # "F": PyFlakes Error
    # "B": flake8-bugbear Error
    # "E": PEP8 "Error"
    # "W": PEP8 Warning
    # possibly other plugins...
    return LintSeverity.WARNING


def format_lint_message(
    message: str,
    code: str | None,
    rules: dict[str | None, str],
    show_disable: bool,
    url: str | None,
) -> str:
    if url is not None:
        message += f".\nSee {url}"
    if show_disable and code:
        message += f".\n\nTo disable, use `  # noqa: {code}`"
    if rules:
        message += f".\n{rules.get(code) or ''}"
    return message


def check_files(
    filenames: list[str],
    severities: dict[str, LintSeverity],
    *,
    config: str | None,
    retries: int,
    timeout: int,
    explain: bool,
    show_disable: bool,
) -> list[LintMessage]:
    try:
        proc = run_command(
            [
                sys.executable,
                "-m",
                "ruff",
                "check",
                "--exit-zero",
                "--quiet",
                "--output-format=json",
                *([f"--config={config}"] if config else []),
                *filenames,
            ],
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

    stdout = str(proc.stdout, "utf-8").strip()
    vulnerabilities = json.loads(stdout)

    if explain:
        all_codes = {v["code"] for v in vulnerabilities}
        rules = {code: explain_rule(code) for code in all_codes}
    else:
        rules = {}

    return [
        LintMessage(
            path=vuln["filename"],
            name=vuln["code"] or "ERROR",
            description=(
                format_lint_message(
                    vuln["message"],
                    vuln["code"],
                    rules,
                    show_disable,
                    vuln.get("url"),
                )
            ),
            line=int(vuln["location"]["row"]),
            char=int(vuln["location"]["column"]),
            code=LINTER_CODE,
            severity=severities.get(vuln["code"], get_issue_severity(vuln["code"])),
            original=None,
            replacement=None,
        )
        for vuln in vulnerabilities
    ]


def check_file_for_fixes(
    filename: str,
    *,
    config: str | None,
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
                    "-m",
                    "ruff",
                    "check",
                    "--fix-only",
                    "--exit-zero",
                    *([f"--config={config}"] if config else []),
                    "--stdin-filename",
                    filename,
                    "-",
                ],
                stdin=f,
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
        )
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description=f"Ruff linter with auto-fix support. Linter code: {LINTER_CODE}.",
        fromfile_prefix_chars="@",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to the `pyproject.toml` or `ruff.toml` file to use for configuration",
    )
    parser.add_argument(
        "--explain",
        action="store_true",
        help="Explain a rule",
    )
    parser.add_argument(
        "--show-disable",
        action="store_true",
        help="Show how to disable a lint message",
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
        help="map code to severity (e.g. `F401:advice`). This option can be used multiple times.",
    )
    parser.add_argument(
        "--no-fix",
        action="store_true",
        help="Do not suggest fixes",
    )
    add_default_options(parser, retries=1)
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

    severities: dict[str, LintSeverity] = {}
    if args.severity:
        for severity in args.severity:
            parts = severity.split(":", 1)
            assert len(parts) == 2, f"invalid severity `{severity}`"
            severities[parts[0]] = LintSeverity(parts[1])

    lint_messages = check_files(
        args.filenames,
        severities=severities,
        config=args.config,
        retries=args.retries,
        timeout=args.timeout,
        explain=args.explain,
        show_disable=args.show_disable,
    )
    for lint_message in lint_messages:
        lint_message.display()

    if args.no_fix or not lint_messages:
        # If we're not fixing, we can exit early
        return

    files_with_lints = {lint.path for lint in lint_messages if lint.path is not None}
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=os.cpu_count(),
        thread_name_prefix="Thread",
    ) as executor:
        futures = {
            executor.submit(
                check_file_for_fixes,
                path,
                config=args.config,
                retries=args.retries,
                timeout=args.timeout,
            ): path
            for path in files_with_lints
        }
        for future in concurrent.futures.as_completed(futures):
            try:
                for lint_message in future.result():
                    lint_message.display()
            except Exception:
                logger.critical('Failed at "%s".', futures[future])
                raise


if __name__ == "__main__":
    main()
