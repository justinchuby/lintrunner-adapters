# PyTorch LICENSE. See LICENSE file in the root directory of this source tree.

from __future__ import annotations

import argparse
import logging
import re
import subprocess
import sys
from typing import Dict, List, Optional, Pattern, Set

import lintrunner_adapters
from lintrunner_adapters import LintMessage, LintSeverity, as_posix, run_command

LINTER_CODE = "FLAKE8"

# fmt: off
# https://www.flake8rules.com/
DOCUMENTED_IN_FLAKE8RULES: Set[str] = {
    "E101", "E111", "E112", "E113", "E114", "E115", "E116", "E117",
    "E121", "E122", "E123", "E124", "E125", "E126", "E127", "E128", "E129",
    "E131", "E133",
    "E201", "E202", "E203",
    "E211",
    "E221", "E222", "E223", "E224", "E225", "E226", "E227", "E228",
    "E231",
    "E241", "E242",
    "E251",
    "E261", "E262", "E265", "E266",
    "E271", "E272", "E273", "E274", "E275",
    "E301", "E302", "E303", "E304", "E305", "E306",
    "E401", "E402",
    "E501", "E502",
    "E701", "E702", "E703", "E704",
    "E711", "E712", "E713", "E714",
    "E721", "E722",
    "E731",
    "E741", "E742", "E743",
    "E901", "E902", "E999",
    "W191",
    "W291", "W292", "W293",
    "W391",
    "W503", "W504",
    "W601", "W602", "W603", "W604", "W605",
    "F401", "F402", "F403", "F404", "F405",
    "F811", "F812",
    "F821", "F822", "F823",
    "F831",
    "F841",
    "F901",
    "C901",
}

# https://pypi.org/project/flake8-comprehensions/#rules
DOCUMENTED_IN_FLAKE8COMPREHENSIONS: Set[str] = {
    "C400", "C401", "C402", "C403", "C404", "C405", "C406", "C407", "C408", "C409",
    "C410",
    "C411", "C412", "C413", "C414", "C415", "C416",
}

# https://github.com/PyCQA/flake8-bugbear#list-of-warnings
DOCUMENTED_IN_BUGBEAR: Set[str] = {
    "B001", "B002", "B003", "B004", "B005", "B006", "B007", "B008", "B009", "B010",
    "B011", "B012", "B013", "B014", "B015",
    "B301", "B302", "B303", "B304", "B305", "B306",
    "B901", "B902", "B903", "B950",
}
# fmt: on


# https://github.com/dlint-py/dlint/tree/master/docs
def documented_in_dlint(code: str) -> bool:
    """Returns whether the given code is documented in dlint."""
    return code.startswith("DUO")


# https://www.pydocstyle.org/en/stable/error_codes.html
def documented_in_pydocstyle(code: str) -> bool:
    """Returns whether the given code is documented in pydocstyle."""
    return re.match(r"D[0-9]{3}", code) is not None


# stdin:2: W802 undefined name 'foo'
# stdin:3:6: T484 Name 'foo' is not defined
# stdin:3:-100: W605 invalid escape sequence '\/'
# stdin:3:1: E302 expected 2 blank lines, found 1
RESULTS_RE: Pattern[str] = re.compile(
    r"""(?mx)
    ^
    (?P<file>.*?):
    (?P<line>\d+):
    (?:(?P<column>-?\d+):)?
    \s(?P<code>\S+?):?
    \s(?P<message>.*)
    $
    """
)


def _test_results_re() -> None:
    """Doctests.

    >>> def t(s): return RESULTS_RE.search(s).groupdict()

    >>> t(r"file.py:80:1: E302 expected 2 blank lines, found 1")
    ... # doctest: +NORMALIZE_WHITESPACE
    {'file': 'file.py', 'line': '80', 'column': '1', 'code': 'E302',
     'message': 'expected 2 blank lines, found 1'}

    >>> t(r"file.py:7:1: P201: Resource `stdout` is acquired but not always released.")
    ... # doctest: +NORMALIZE_WHITESPACE
    {'file': 'file.py', 'line': '7', 'column': '1', 'code': 'P201',
     'message': 'Resource `stdout` is acquired but not always released.'}

    >>> t(r"file.py:8:-10: W605 invalid escape sequence '/'")
    ... # doctest: +NORMALIZE_WHITESPACE
    {'file': 'file.py', 'line': '8', 'column': '-10', 'code': 'W605',
     'message': "invalid escape sequence '/'"}
    """
    pass


def get_issue_severity(code: str) -> LintSeverity:
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
        for x in [
            "B9",
            "C4",
            "C9",
            "E2",
            "E3",
            "E5",
            "T400",
            "T49",
        ]
    ):
        return LintSeverity.ADVICE

    # "F821": Undefined name
    # "E999": syntax error
    if any(code.startswith(x) for x in ["F821", "E999"]):
        return LintSeverity.ERROR

    # "F": PyFlakes Error
    # "B": flake8-bugbear Error
    # "E": PEP8 "Error"
    # "W": PEP8 Warning
    # possibly other plugins...
    return LintSeverity.WARNING


def get_issue_documentation_url(code: str) -> str:
    if code in DOCUMENTED_IN_FLAKE8RULES:
        return f"https://www.flake8rules.com/rules/{code}.html"

    if code in DOCUMENTED_IN_FLAKE8COMPREHENSIONS:
        return "https://pypi.org/project/flake8-comprehensions/#rules"

    if code in DOCUMENTED_IN_BUGBEAR:
        return "https://github.com/PyCQA/flake8-bugbear#list-of-warnings"

    if documented_in_dlint(code):
        return f"https://github.com/dlint-py/dlint/blob/master/docs/linters/{code}.md"

    if documented_in_pydocstyle(code):
        return "https://www.pydocstyle.org/en/stable/error_codes.html"

    return ""


def format_lint_message(message: str, code: str, show_disable: bool) -> str:
    formatted = f"{message}\nSee {get_issue_documentation_url(code)}."
    if show_disable:
        formatted += f"\n\nTo disable, use `  # noqa: {code}`"
    return formatted


def check_files(
    filenames: List[str],
    severities: Dict[str, LintSeverity],
    *,
    retries: int,
    docstring_convention: Optional[str],
    show_disable: bool,
) -> List[LintMessage]:
    try:
        proc = run_command(
            [sys.executable, "-mflake8", "--exit-zero"]
            + (
                ["--docstring-convention", docstring_convention]
                if docstring_convention
                else []
            )
            + filenames,
            retries=retries,
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
                        "COMMAND (exit code {returncode})\n"
                        "{command}\n\n"
                        "STDERR\n{stderr}\n\n"
                        "STDOUT\n{stdout}"
                    ).format(
                        returncode=err.returncode,
                        command=" ".join(as_posix(x) for x in err.cmd),
                        stderr=err.stderr.strip() or "(empty)",
                        stdout=err.stdout.strip() or "(empty)",
                    )
                ),
            )
        ]

    return [
        LintMessage(
            path=match["file"],
            name=match["code"],
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
            severity=severities.get(match["code"]) or get_issue_severity(match["code"]),
            original=None,
            replacement=None,
        )
        for match in RESULTS_RE.finditer(proc.stdout.decode("utf-8"))
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description=f"Flake8 wrapper linter. Linter code: {LINTER_CODE}",
        fromfile_prefix_chars="@",
    )
    parser.add_argument(
        "--severity",
        action="append",
        help="map code to severity (e.g. `B950:advice`)",
    )
    parser.add_argument(
        "--docstring-convention",
        default=None,
        type=str,
        help="docstring convention to use. E.g. 'google', 'numpy'",
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

    severities: Dict[str, LintSeverity] = {}
    if args.severity:
        for severity in args.severity:
            parts = severity.split(":", 1)
            assert len(parts) == 2, f"invalid severity `{severity}`"
            severities[parts[0]] = LintSeverity(parts[1])

    lint_messages = check_files(
        args.filenames,
        severities,
        retries=args.retries,
        docstring_convention=args.docstring_convention,
        show_disable=args.show_disable,
    )
    for lint_message in lint_messages:
        lint_message.display()


if __name__ == "__main__":
    main()
