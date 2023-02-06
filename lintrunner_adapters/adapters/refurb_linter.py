"""Refurbish and modernize Python code"""

from __future__ import annotations

import argparse
import logging
import re
import sys
import textwrap

from lintrunner_adapters import LintMessage, LintSeverity, add_default_options
from lintrunner_adapters._common.lintrunner_common import run_command

LINTER_CODE = "REFURB"

RESULTS_RE = re.compile(
    r"""(?mx)
        ^
        (?P<file>.*?):
        (?P<line>\d+):
        (?:(?P<column>-?\d+))?
        (?:\s\[(?P<code>.*)\]:)?
        \s(?P<message>.*)
        $
        """
)


def _test_results_re() -> None:
    """Doctests.

    >>> def t(s): return RESULTS_RE.search(s).groupdict()

    >>> t(r"main.py:3:17 [FURB109]: Use `in (x, y, z)` instead of `in [x, y, z]`")
    ... # doctest: +NORMALIZE_WHITESPACE
    {'file': 'main.py', 'line': '3', 'column': '17', 'code': 'FURB109',
     'message': 'Use `in (x, y, z)` instead of `in [x, y, z]`'}

    >>> t(r"main.py:4:5 [FURB101]: Use `y = Path(x).read_text()` instead of `with open(x, ...) as f: y = f.read()`")
    ... # doctest: +NORMALIZE_WHITESPACE
    {'file': 'main.py', 'line': '4', 'column': '5', 'code': 'FURB101',
     'message': 'Use `y = Path(x).read_text()` instead of `with open(x, ...) as f: y = f.read()`'}
    """
    pass


def format_lint_message(message: str, code: str, show_disable: bool) -> str:
    formatted = f"{message}"
    if show_disable:
        formatted += textwrap.dedent(
            f"""

            To disable, use
            [tool.refurb]
            ignore = [{code}]
            or
            disable = [{code}]
            """
        )
    return formatted


def check_files(
    filenames: list[str],
    severities: dict[str, LintSeverity],
    *,
    config_file: str,
    retries: int,
    show_disable: bool,
) -> list[LintMessage]:
    try:
        proc = run_command(
            [sys.executable, "-mrefurb", "--config-file", config_file, *filenames],
            retries=retries,
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
    return [
        LintMessage(
            path=match["file"],
            name=match["code"] or "note",
            description=format_lint_message(
                match["message"],
                match["code"],
                show_disable,
            ),
            line=int(match["line"]),
            char=int(match["column"])
            if match["column"] is not None and not match["column"].startswith("-")
            else None,
            code=LINTER_CODE,
            severity=severities.get(match["code"], LintSeverity.ADVICE),
            original=None,
            replacement=None,
        )
        for match in RESULTS_RE.finditer(stdout)
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description=f"refurb wrapper linter. Linter code: {LINTER_CODE}. "
        f"Use pyproject.toml to configure any refurb settings.",
        fromfile_prefix_chars="@",
    )
    parser.add_argument(
        "--config-file",
        default="pyproject.toml",
        help="path to pyproject.toml config file",
    )
    parser.add_argument(
        "--severity",
        action="append",
        help="map code to severity (e.g. `FURB109:advice`). "
        "This option can be used multiple times.",
    )
    parser.add_argument(
        "--show-disable",
        action="store_true",
        help="show how to disable a lint message",
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
        severities,
        config_file=args.config_file,
        retries=args.retries,
        show_disable=args.show_disable,
    )
    for lint_message in lint_messages:
        lint_message.display()


if __name__ == "__main__":
    main()
