# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: MIT
from __future__ import annotations

import argparse
import logging
import shutil
import subprocess
import sys
from xml.etree.ElementTree import Element

from defusedxml import ElementTree

from lintrunner_adapters import (
    LintMessage,
    LintSeverity,
    add_default_options,
    as_posix,
    run_command,
)

LINTER_CODE = "CPPCHECK"

SEVERITIES = {
    "error": LintSeverity.ERROR,
    "warning": LintSeverity.WARNING,
    "style": LintSeverity.ADVICE,
    "performance": LintSeverity.ADVICE,
    "portability": LintSeverity.ADVICE,
    "information": LintSeverity.ADVICE,
}


def extract_xml_report(output: str) -> str | None:
    xml_start = output.find("<?xml")
    if xml_start == -1:
        xml_start = output.find("<results")
    if xml_start == -1:
        return None
    return output[xml_start:].strip()


def _test_extract_xml_report() -> None:
    r"""Doctests.

    >>> output = '''Checking src/test.cc ...
    ... <?xml version="1.0" encoding="UTF-8"?>
    ... <results version="2">
    ...   <errors />
    ... </results>
    ... '''
    >>> extract_xml_report(output) == '''<?xml version="1.0" encoding="UTF-8"?>
    ... <results version="2">
    ...   <errors />
    ... </results>'''
    True
    """
    pass


def format_description(
    error: Element,
    locations: list[Element],
) -> str:
    description = error.attrib.get("verbose") or error.attrib.get("msg") or ""

    if error.attrib.get("inconclusive") == "true":
        description += "\n\nInconclusive analysis result."

    if "cwe" in error.attrib:
        description += f"\nCWE: CWE-{error.attrib['cwe']}"

    if "remark" in error.attrib:
        description += f"\nRemark: {error.attrib['remark']}"

    related_locations = []
    for location in locations[1:]:
        file_name = location.attrib.get("file")
        line = location.attrib.get("line")
        info = location.attrib.get("info")
        if file_name is None:
            continue
        location_text = file_name
        if line is not None:
            location_text += f":{line}"
        if info:
            location_text += f" ({info})"
        related_locations.append(location_text)

    if related_locations:
        description += "\nRelated locations:\n" + "\n".join(related_locations)

    return description


def parse_cppcheck_xml(report: str) -> list[LintMessage]:
    root = ElementTree.fromstring(
        report,
        forbid_dtd=True,
        forbid_entities=True,
        forbid_external=True,
    )
    lint_messages = []

    for error in root.findall("./errors/error"):
        locations = error.findall("location")
        primary = locations[0] if locations else None
        path = primary.attrib.get("file") if primary is not None else None
        line = primary.attrib.get("line") if primary is not None else None

        lint_messages.append(
            LintMessage(
                path=path,
                line=int(line) if line is not None else None,
                char=None,
                code=LINTER_CODE,
                severity=SEVERITIES.get(
                    error.attrib.get("severity", ""),
                    LintSeverity.WARNING,
                ),
                name=error.attrib.get("id", "cppcheck"),
                original=None,
                replacement=None,
                description=format_description(error, locations),
            )
        )

    return lint_messages


def _test_parse_cppcheck_xml() -> None:
    r"""Doctests.

    >>> report = '''<?xml version="1.0" encoding="UTF-8"?>
    ... <results version="2">
    ...   <errors>
    ...     <error id="arrayIndexOutOfBounds" severity="error" msg="Short message"
    ...         verbose="Array index is out of bounds" cwe="788" inconclusive="true"
    ...         remark="Documented false positive context">
    ...       <location file="src/test.cc" line="12" />
    ...       <location file="include/test.h" line="7" info="declaration" />
    ...     </error>
    ...     <error id="unusedFunction" severity="style" msg="The function is never used">
    ...       <location file="src/test.cc" line="3" />
    ...     </error>
    ...   </errors>
    ... </results>
    ... '''
    >>> parse_cppcheck_xml(report) == [
    ...     LintMessage(
    ...         path="src/test.cc",
    ...         line=12,
    ...         char=None,
    ...         code="CPPCHECK",
    ...         severity=LintSeverity.ERROR,
    ...         name="arrayIndexOutOfBounds",
    ...         original=None,
    ...         replacement=None,
    ...         description=(
    ...             "Array index is out of bounds\n\n"
    ...             "Inconclusive analysis result.\n"
    ...             "CWE: CWE-788\n"
    ...             "Remark: Documented false positive context\n"
    ...             "Related locations:\n"
    ...             "include/test.h:7 (declaration)"
    ...         ),
    ...     ),
    ...     LintMessage(
    ...         path="src/test.cc",
    ...         line=3,
    ...         char=None,
    ...         code="CPPCHECK",
    ...         severity=LintSeverity.ADVICE,
    ...         name="unusedFunction",
    ...         original=None,
    ...         replacement=None,
    ...         description="The function is never used",
    ...     ),
    ... ]
    True
    """
    pass


def build_command(
    binary: str,
    filenames: list[str],
    *,
    enable: list[str] | None,
    extra_args: list[str] | None,
) -> list[str]:
    return [
        binary,
        "--xml",
        "--xml-version=2",
        *(f"--enable={value}" for value in enable or []),
        *(extra_args or []),
        *filenames,
    ]


def _test_build_command() -> None:
    """Doctests.

    >>> build_command(
    ...     "cppcheck",
    ...     ["src/test.cc"],
    ...     enable=["warning,style", "performance"],
    ...     extra_args=["--inline-suppr", "--std=c++20", "-Iinclude"],
    ... )
    ... # doctest: +NORMALIZE_WHITESPACE
    ['cppcheck', '--xml', '--xml-version=2', '--enable=warning,style',
     '--enable=performance', '--inline-suppr', '--std=c++20', '-Iinclude',
     'src/test.cc']
    """
    pass


def check_files(
    filenames: list[str],
    *,
    binary: str,
    enable: list[str] | None,
    extra_args: list[str] | None,
    retries: int,
    timeout: int,
) -> list[LintMessage]:
    command = build_command(
        binary,
        filenames,
        enable=enable,
        extra_args=extra_args,
    )
    try:
        proc = run_command(
            command,
            retries=retries,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return [
            LintMessage(
                path=None,
                line=None,
                char=None,
                code=LINTER_CODE,
                severity=LintSeverity.ERROR,
                name="timeout",
                original=None,
                replacement=None,
                description=(
                    "cppcheck timed out while processing files. "
                    "Try increasing `--timeout` or reducing the number of files."
                ),
            )
        ]
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
                description=f"Failed due to {err.__class__.__name__}:\n{err}",
            )
        ]

    stderr = proc.stderr.decode("utf-8", errors="replace").strip()
    stdout = proc.stdout.decode("utf-8", errors="replace").strip()
    report = extract_xml_report(stderr) or extract_xml_report(stdout)

    if report is None:
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
                    "COMMAND (exit code {returncode})\n"
                    "{command}\n\n"
                    "STDERR\n{stderr}\n\n"
                    "STDOUT\n{stdout}"
                ).format(
                    returncode=proc.returncode,
                    command=" ".join(as_posix(x) for x in command),
                    stderr=stderr or "(empty)",
                    stdout=stdout or "(empty)",
                ),
            )
        ]

    try:
        return parse_cppcheck_xml(report)
    except ElementTree.ParseError as err:
        return [
            LintMessage(
                path=None,
                line=None,
                char=None,
                code=LINTER_CODE,
                severity=LintSeverity.ERROR,
                name="invalid-xml",
                original=None,
                replacement=None,
                description=(
                    f"Failed to parse cppcheck XML output: {err}\n\n"
                    f"STDERR\n{stderr or '(empty)'}\n\n"
                    f"STDOUT\n{stdout or '(empty)'}"
                ),
            )
        ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description=f"cppcheck wrapper linter. Linter code: {LINTER_CODE}",
        fromfile_prefix_chars="@",
    )
    parser.add_argument(
        "--binary",
        default="cppcheck",
        help="cppcheck binary path",
    )
    parser.add_argument(
        "--enable",
        action="append",
        help="value passed to --enable. Can be used multiple times.",
    )
    parser.add_argument(
        "--extra-arg",
        action="append",
        help=(
            "extra argument passed through to cppcheck. "
            "Can be used multiple times, for example "
            "`--extra-arg=-Iinclude --extra-arg=--std=c++20`."
        ),
    )
    parser.add_argument(
        "--timeout",
        default=300,
        type=int,
        help="seconds to wait for cppcheck",
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

    if shutil.which(args.binary) is None:
        LintMessage(
            path=None,
            line=None,
            char=None,
            code=LINTER_CODE,
            severity=LintSeverity.ERROR,
            name="init-error",
            original=None,
            replacement=None,
            description=(
                f"Could not find cppcheck binary `{args.binary}`. "
                "Install cppcheck or pass `--binary` with the executable path."
            ),
        ).display()
        sys.exit(0)

    lint_messages = check_files(
        list(args.filenames),
        binary=args.binary,
        enable=args.enable,
        extra_args=args.extra_arg,
        retries=args.retries,
        timeout=args.timeout,
    )
    for lint_message in lint_messages:
        lint_message.display()


if __name__ == "__main__":
    main()
