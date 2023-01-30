"""Adapter for https://github.com/charliermarsh/ruff."""

from __future__ import annotations

import argparse
import json
import logging
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


def explain_rule(code: str) -> str:
    proc = run_command(
        [sys.executable, "-mruff", "rule", "--format=json", code],
        check=True,
    )
    rule = json.loads(str(proc.stdout, "utf-8").strip())
    return f"\n{rule['linter']}: {rule['summary']}"


def check_files(
    filenames: list[str],
    severities: dict[str, LintSeverity],
    *,
    config: str | None,
    retries: int,
    timeout: int,
    explain: bool,
) -> list[LintMessage]:
    try:
        proc = run_command(
            [sys.executable, "-mruff", "-e", "-q", "--format=json"]
            + ([f"--config={config}"] if config else [])
            + filenames,
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
    rules = (
        {code: explain_rule(code) for code in {v["code"] for v in vulnerabilities}}
        if explain
        else None
    )
    return [
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

    lint_messages = check_files(
        args.filenames,
        severities=severities,
        config=args.config,
        retries=args.retries,
        timeout=args.timeout,
        explain=args.explain,
    )
    for lint_message in lint_messages:
        lint_message.display()


if __name__ == "__main__":
    main()
