"""Generic linter that greps for a pattern and optionally suggests replacements."""

# PyTorch LICENSE. See LICENSE file in the root directory of this source tree.

import argparse
import logging
import subprocess
import sys
from typing import Optional

from lintrunner_adapters import LintMessage, LintSeverity, as_posix, run_command


def lint_file(
    matching_line: str,
    allowlist_pattern: str,
    replace_pattern: str,
    linter_name: str,
    error_name: str,
    error_description: str,
) -> Optional[LintMessage]:
    # matching_line looks like:
    #   tools/linter/clangtidy_linter.py:13:import foo.bar.baz
    split = matching_line.split(":")
    filename = split[0]

    if allowlist_pattern:
        try:
            proc = run_command(["grep", "-nEHI", allowlist_pattern, filename])
        except Exception as err:
            return LintMessage(
                path=None,
                line=None,
                char=None,
                code=linter_name,
                severity=LintSeverity.ERROR,
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

        # allowlist pattern was found, abort lint
        if proc.returncode == 0:
            return None

    original = None
    replacement = None
    if replace_pattern:
        with open(filename, encoding="utf-8") as f:
            original = f.read()

        try:
            proc = run_command(["sed", "-r", replace_pattern, filename])
            replacement = proc.stdout.decode("utf-8")
        except Exception as err:
            return LintMessage(
                path=None,
                line=None,
                char=None,
                code=linter_name,
                severity=LintSeverity.ERROR,
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

    return LintMessage(
        path=split[0],
        line=int(split[1]) if len(split) > 1 else None,
        char=None,
        code=linter_name,
        severity=LintSeverity.ERROR,
        name=error_name,
        original=original,
        replacement=replacement,
        description=error_description,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="grep wrapper linter.",
        fromfile_prefix_chars="@",
    )
    parser.add_argument(
        "--pattern",
        required=True,
        help="pattern to grep for",
    )
    parser.add_argument(
        "--allowlist-pattern",
        help="if this pattern is true in the file, we don't grep for pattern",
    )
    parser.add_argument(
        "--linter-name",
        required=True,
        help="name of the linter",
    )
    parser.add_argument(
        "--match-first-only",
        action="store_true",
        help="only match the first hit in the file",
    )
    parser.add_argument(
        "--error-name",
        required=True,
        help="human-readable description of what the error is",
    )
    parser.add_argument(
        "--error-description",
        required=True,
        help="message to display when the pattern is found",
    )
    parser.add_argument(
        "--replace-pattern",
        help=(
            "the form of a pattern passed to `sed -r`. "
            "If specified, this will become proposed replacement text."
        ),
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="verbose logging",
    )
    parser.add_argument(
        "filenames",
        nargs="+",
        help="paths to lint",
    )
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

    files_with_matches = []
    if args.match_first_only:
        files_with_matches = ["--files-with-matches"]

    try:
        proc = run_command(
            ["grep", "-nEHI", *files_with_matches, args.pattern, *args.filenames]
        )
    except Exception as err:
        err_msg = LintMessage(
            path=None,
            line=None,
            char=None,
            code=args.linter_name,
            severity=LintSeverity.ERROR,
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
        err_msg.display()
        sys.exit(0)

    lines = proc.stdout.decode().splitlines()
    for line in lines:
        lint_message = lint_file(
            line,
            args.allowlist_pattern,
            args.replace_pattern,
            args.linter_name,
            args.error_name,
            args.error_description,
        )
        if lint_message is not None:
            lint_message.display()


if __name__ == "__main__":
    main()
