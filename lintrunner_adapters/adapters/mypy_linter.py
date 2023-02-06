# PyTorch LICENSE. See LICENSE file in the root directory of this source tree.

from __future__ import annotations

import argparse
import logging
import pathlib
import re
import sys
from pathlib import Path
from typing import Pattern

import lintrunner_adapters
from lintrunner_adapters import LintMessage, LintSeverity, run_command

LINTER_CODE = "MYPY"

# tools/linter/flake8_linter.py:15:13: error: Incompatibl...int")  [assignment]
RESULTS_RE: Pattern[str] = re.compile(
    r"""(?mx)
    ^
    (?P<file>.*?):
    (?P<line>\d+):
    (?:(?P<column>-?\d+):)?
    \s(?P<severity>\S+?):?
    \s(?P<message>.*?)
    (?:\s\[(?P<code>.*)\])?
    $
    """
)


def _test_results_re() -> None:
    """Doctests.

    >>> def t(s): return RESULTS_RE.search(s).groupdict()

    >>> t(r'prog.py:1: error: "str" has no attribute "trim"  [attr-defined]')
    ... # doctest: +NORMALIZE_WHITESPACE
    {'file': 'prog.py', 'line': '1', 'column': None, 'severity': 'error',
     'message': '"str" has no attribute "trim" ', 'code': 'attr-defined'}

    >>> t(r'flake8_linter.py:15:13: error: Incompatibl...int")  [assignment]')
    ... # doctest: +NORMALIZE_WHITESPACE
    {'file': 'flake8_linter.py', 'line': '15', 'column': '13', 'severity': 'error',
     'message': 'Incompatibl...int") ', 'code': 'assignment'}

    >>> t(r'mypy_linter.py:106: note: Use "-> None" if function does not return a value')
    ... # doctest: +NORMALIZE_WHITESPACE
    {'file': 'mypy_linter.py', 'line': '106', 'column': None, 'severity': 'note',
     'message': 'Use "-> None" if function does not return a value', 'code': None}
    """
    pass


# Severity is either "error" or "note":
# https://github.com/python/mypy/blob/8b47a032e1317fb8e3f9a818005a6b63e9bf0311/mypy/errors.py#L46-L47
SEVERITIES = {
    "error": LintSeverity.ERROR,
    "note": LintSeverity.ADVICE,
}


def disable_message(code: str) -> str:
    if code is None:
        return ""
    return f"\n\nTo disable, use `  # type: ignore[{code}]`"


def check_files(
    filenames: list[str],
    *,
    config: str,
    retries: int,
    show_disable: bool,
) -> list[LintMessage]:
    try:
        proc = run_command(
            [sys.executable, "-mmypy", f"--config={config}", *filenames],
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
            description=match["message"]
            + (disable_message(match["code"]) if show_disable else ""),
            line=int(match["line"]),
            char=int(match["column"])
            if match["column"] is not None and not match["column"].startswith("-")
            else None,
            code=LINTER_CODE,
            severity=SEVERITIES.get(match["severity"], LintSeverity.ERROR),
            original=None,
            replacement=None,
        )
        for match in RESULTS_RE.finditer(stdout)
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description=f"mypy wrapper linter. Linter code: {LINTER_CODE}",
        fromfile_prefix_chars="@",
    )
    parser.add_argument(
        "--config",
        required=True,
        help="path to an mypy .ini config file",
    )
    parser.add_argument(
        "--show-notes",
        action="store_true",
        help="show notes in addition to errors",
    )
    parser.add_argument(
        "--show-disable",
        action="store_true",
        help="show how to disable a lint message",
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

    # Use a dictionary here to preserve order. mypy cares about order,
    # tragically, e.g. https://github.com/python/mypy/issues/2015
    filenames: dict[str, bool] = {}

    # If a stub file exists, have mypy check it instead of the original file, in
    # accordance with PEP-484 (see https://www.python.org/dev/peps/pep-0484/#stub-files)
    for filename in args.filenames:
        if filename.endswith(".pyi"):
            filenames[filename] = True
            continue

        stub_filename = filename.replace(".py", ".pyi")
        if Path(stub_filename).exists():
            filenames[stub_filename] = True
        else:
            filenames[filename] = True

    lint_messages = check_files(
        list(filenames),
        config=args.config,
        retries=args.retries,
        show_disable=args.show_disable,
    )

    all_files = {str(pathlib.Path(path).resolve()) for path in filenames}
    for lint_message in lint_messages:
        if lint_message.severity == LintSeverity.ADVICE and not args.show_notes:
            continue

        # Filter out messages for files not being linted because mypy sometimes
        # picks up files imported by the files being linted.
        if lint_message.path is not None:
            path = str(pathlib.Path(lint_message.path).resolve())
            if path not in all_files:
                logging.warning(
                    "Lint message %s is for a file '%s' not being linted",
                    lint_message,
                    lint_message.path,
                )
                continue
        lint_message.display()


if __name__ == "__main__":
    main()
