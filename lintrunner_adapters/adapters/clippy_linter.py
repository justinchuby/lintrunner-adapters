"""Linter wrapper for rust clippy.

https://doc.rust-lang.org/clippy
"""

from __future__ import annotations

import argparse
import json
import logging
import pathlib
import subprocess
import sys
from typing import Any, Collection

import lintrunner_adapters
from lintrunner_adapters import LintMessage, LintSeverity, as_posix, run_command

LINTER_CODE = "CLIPPY"

# https://rustc-dev-guide.rust-lang.org/diagnostics.html#diagnostic-levels
SEVERITIES = {
    "error": LintSeverity.ERROR,
    "warning": LintSeverity.WARNING,
    "note": LintSeverity.ADVICE,
    "help": LintSeverity.ADVICE,
    None: LintSeverity.ADVICE,
}


def format_lint_messages(clippy_message: dict[str, Any]) -> str:
    message = f"```\n{clippy_message['rendered']}```"
    return message


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


def find_cargo_toml_files(filenames: Collection[pathlib.Path]) -> set[pathlib.Path]:
    """Recursively look up to find all the Cargo.toml files in the files to be linted."""
    all_cargo_tomls: set[pathlib.Path] = set()
    for filename in filenames:
        if any(
            is_relative_to(filename, cargo_toml.parent)
            for cargo_toml in all_cargo_tomls
        ):
            logging.debug(
                f"Skipping finding Cargo.toml from '{filename}' because it is in a known "
                "Cargo.toml directory"
            )
            continue
        cargo_toml = find_cargo_root(filename)
        if cargo_toml is None:
            logging.debug(f"No Cargo.toml found in parents of {filename}")
            continue
        all_cargo_tomls.add(cargo_toml)

    if not all_cargo_tomls:
        logging.warning("No Cargo.toml found in parents of files to be linted")

    return all_cargo_tomls


def check_cargo_toml(  # pylint: disable=too-many-branches
    cargo_toml: pathlib.Path, filenames: set[str], retries: int
) -> list[LintMessage]:
    try:
        proc = run_command(
            ["cargo", "clippy", "--message-format=json"],
            retries=retries,
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
    except subprocess.CalledProcessError as err:
        return [
            LintMessage(
                path=str(cargo_toml),
                line=None,
                char=None,
                code="RUSTFMT",
                severity=LintSeverity.ERROR,
                name="command-failed",
                original=None,
                replacement=None,
                description=(
                    (
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

    stdout = str(proc.stdout, "utf-8").strip()

    lint_messages: list[LintMessage] = []
    for line in stdout.splitlines():
        try:
            data = json.loads(line)
        except json.JSONDecodeError as err:
            logging.warning("Failed to parse JSON: %s", err)
            continue

        if data.get("reason") != "compiler-message":
            continue

        if "target" not in data:
            logging.debug("No target in data: %s", data)
            continue

        if "src_path" not in data["target"]:
            logging.debug("No src_path in target: %s", data["target"])
            continue

        if "message" not in data:
            logging.debug("No message in data: %s", data)
            continue

        if data["message"].get("code") is None:
            logging.debug("No code in message: %s", data["message"])
            continue

        if "spans" not in data["message"] or not data["message"]["spans"]:
            logging.debug("No spans in message: %s", data["message"])
            continue

        first_span = data["message"]["spans"][0]
        line_num = first_span.get("line_start")
        char = first_span.get("column_start")

        # The src_path is relative to the Cargo.toml file
        src_path: str = str((cargo_toml.parent / first_span["file_name"]).resolve())
        # Filter the lint messages to only include the files that are in filenames
        if src_path not in filenames:
            logging.debug(
                "Skipping '%s' because it is not in the list of files to be linted",
                src_path,
            )
            continue

        lint_messages.append(
            LintMessage(
                path=src_path,
                line=line_num,
                char=char,
                code=LINTER_CODE,
                severity=SEVERITIES[data["message"].get("level")],
                name=data["message"]["code"]["code"],
                original=None,
                replacement=None,
                description=format_lint_messages(data["message"]),
            )
        )

    return lint_messages


def check_files(filenames: list[str], retries: int) -> list[LintMessage]:
    """Run clippy on the files."""
    # Convert filenames to a set of absolute paths
    absolute_paths = [pathlib.Path(filename).resolve() for filename in filenames]
    absolute_filenames = {str(path) for path in absolute_paths}
    # Recursively look up to find all the Cargo.toml files in the files to be linted
    all_cargo_tomls = find_cargo_toml_files(absolute_paths)
    logging.info("Found Cargo.toml files: %s", all_cargo_tomls)
    # Run clippy on each Cargo.toml file
    lint_messages: list[LintMessage] = []
    for cargo_toml in all_cargo_tomls:
        logging.debug(f"Running clippy on {cargo_toml}")
        lint_messages.extend(
            check_cargo_toml(cargo_toml, absolute_filenames, retries=retries)
        )

    return lint_messages


def main() -> None:
    parser = argparse.ArgumentParser(
        description=f"Rust clippy wrapper linter. Linter code: {LINTER_CODE}",
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

    lint_messages = check_files(args.filenames, retries=args.retries)
    for lint_message in lint_messages:
        lint_message.display()


if __name__ == "__main__":
    main()
