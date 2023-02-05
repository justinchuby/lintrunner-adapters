"""Linter wrapper for rust clippy.

https://doc.rust-lang.org/clippy
"""

from __future__ import annotations

import argparse
import json
import logging
import pathlib
import re
import sys
from typing import Collection, Pattern

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


def format_lint_messages(message: str, code: str, string_code: str) -> str:
    formatted = (
        f"{message} ({string_code})\n"
        f"See [{string_code}]({pylint_doc_url(code, string_code)})."
    )
    return formatted


def is_relative_to(path: pathlib.Path, parent: pathlib.Path) -> bool:
    """Check if path is relative to parent."""
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def find_cargo_root(path: pathlib.Path) -> pathlib.Path | None:
    """Find the Cargo.toml file in parent directories of the path."""
    for parent in path.parents:
        potential_cargo_toml = parent / "Cargo.toml"
        if (potential_cargo_toml).exists():
            return potential_cargo_toml
    return None


def find_cargo_toml_files(filenames: Collection[str]) -> set[pathlib.Path]:
    # Recursively look up to find all the Cargo.toml files in the files to be linted
    all_cargo_tomls: set[pathlib.Path] = set()
    for filename in filenames:
        path = pathlib.Path(filename)
        if any(
            is_relative_to(path, cargo_toml.parent) for cargo_toml in all_cargo_tomls
        ):
            logging.debug(
                f"Skipping {path} because it is in a known Cargo.toml directory"
            )
            continue
        cargo_toml = find_cargo_root(path)
        if cargo_toml is None:
            logging.debug(f"No Cargo.toml found in parents of {path}")
            continue
        all_cargo_tomls.add(cargo_toml)

    if not all_cargo_tomls:
        logging.warning("No Cargo.toml found in parents of files to be linted")

    return all_cargo_tomls


def check_cargo_toml(
    cargo_toml: pathlib.Path,
    filenames: set[str],
) -> list[LintMessage]:

    try:
        proc = run_command(
            ["cargo", "clippy", "--message-format=json"],
            cwd=cargo_toml.parent,
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

    lint_messages: list[LintMessage] = []
    for line in stdout.splitlines():
        try:
            data = json.loads(line)
        except json.JSONDecodeError as err:
            logging.warning("Failed to parse JSON: %s", err)
            continue

        if "message" not in data:
            logging.debug("No message in data: %s", data)
            continue

        # Filter the lint messages to only include the files that are in filenames
        if data["filename"] not in filenames:
            logging.debug(
                "Skipping %s because it is not in the list of files to be linted",
                data["filename"],
            )
            continue

        message = data["message"]
        if "children" in data:
            for child in data["children"]:
                if "message" not in child:
                    logging.debug("No message in child: %s", child)
                    continue
                message += "\n" + child["message"]

        lint_messages.append(
            LintMessage(
                path=data["filename"],
                line=data["line_start"],
                char=data["column_start"],
                code=LINTER_CODE,
                severity=SEVERITIES[data["level"]],
                name=data["code"],
                original=None,
                replacement=None,
                description=message,
            )
        )

    return lint_messages


def check_files(
    filenames: Collection[str],
) -> list[LintMessage]:
    paths = set(filenames)
    # Recursively look up to find all the Cargo.toml files in the files to be linted
    all_cargo_tomls = find_cargo_toml_files(filenames)
    # Run clippy on each Cargo.toml file
    lint_messages: list[LintMessage] = []
    for cargo_toml in all_cargo_tomls:
        logging.debug(f"Running clippy on {cargo_toml}")
        lint_messages.extend(check_cargo_toml(cargo_toml, paths))

    return lint_messages


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

    lint_messages = check_files(args.filenames)
    for lint_message in lint_messages:
        lint_message.display()


if __name__ == "__main__":
    main()
