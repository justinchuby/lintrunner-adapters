# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: MIT
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, Iterator, Sequence

from lintrunner_adapters import LintMessage, LintSeverity, add_default_options

LINTER_CODE = "BANNED_FUNCTIONS"
ERROR_NAME = "banned-function"
ERROR_DESCRIPTION = "Scans for banned functions and errors when one is encountered."


_NOISE_RE = re.compile(  # noqa: DUO138, RUF100
    r"""//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'""",
    re.DOTALL,
)
_NOLINT_RE = re.compile(r"//\s*NOLINT\(([^)]+)\)")


def _blank(match: re.Match[str]) -> str:
    return re.sub(r"[^\n]", " ", match.group())


def _expect_string_list(group: dict[str, Any], key: str) -> list[str]:
    value = group.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"`{key}` must be a list of strings")
    return value


def parse_config(config: object) -> dict[str, list[str]]:
    """Parse banned function config.

    The config must be a dictionary with a ``banned_functions`` list. Each
    group must contain ``names`` and may contain ``replacements``.
    """
    if not isinstance(config, dict):
        raise ValueError("config must be a JSON object with a `banned_functions` list")

    groups = config.get("banned_functions")

    if not isinstance(groups, list):
        raise ValueError("config must contain a `banned_functions` list")

    banned_functions: dict[str, list[str]] = {}
    for group in groups:
        if not isinstance(group, dict):
            raise ValueError("each banned function group must be an object")

        names = _expect_string_list(group, "names")
        replacements = _expect_string_list(group, "replacements")
        if not names:
            raise ValueError("`names` must contain at least one function name")

        for name in names:
            if name in banned_functions:
                raise ValueError(f"duplicate banned function `{name}`")
            banned_functions[name] = replacements

    return banned_functions


def _test_parse_config() -> None:
    r"""Doctests.

    >>> parse_config({"banned_functions": [
    ...     {"names": ["memcpy"], "replacements": ["memcpy_s"]},
    ...     {"names": ["printf"], "replacements": ["ET_LOG"]},
    ... ]}) == {
    ...     "memcpy": ["memcpy_s"],
    ...     "printf": ["ET_LOG"],
    ... }
    True
    >>> parse_config({"banned_functions": [{"names": ["gets"]}]})
    {'gets': []}
    >>> parse_config({"banned_functions": [{"names": ["memcpy"]}, {"names": ["memcpy"]}]})
    Traceback (most recent call last):
    ...
    ValueError: duplicate banned function `memcpy`
    >>> parse_config([{"names": ["memcpy"]}])
    Traceback (most recent call last):
    ...
    ValueError: config must be a JSON object with a `banned_functions` list
    """
    pass


def build_pattern(
    banned_functions: dict[str, list[str]],
) -> re.Pattern[str] | None:
    if not banned_functions:
        return None
    names = sorted(banned_functions, key=len, reverse=True)
    return re.compile(r"\b(" + "|".join(re.escape(name) for name in names) + r")\s*\(")


def _is_suppressed(original_line: str, function_name: str) -> bool:
    return any(
        function_name in {name.strip() for name in match.group(1).split(",")}
        for match in _NOLINT_RE.finditer(original_line)
    )


def format_replacements(replacements: list[str]) -> str:
    """Format suggested replacement text."""
    if not replacements:
        return ""

    replacement_text = ", ".join(f"`{name}()`" for name in replacements)
    if len(replacements) == 1:
        return f" Suggested replacement: {replacement_text}."
    return f" Suggested replacements: {replacement_text}."


def _test_format_replacements() -> None:
    r"""Doctests.

    >>> format_replacements(["memcpy_s"])
    ' Suggested replacement: `memcpy_s()`.'
    >>> format_replacements(["strcpy_s", "strncpy_s"])
    ' Suggested replacements: `strcpy_s()`, `strncpy_s()`.'
    >>> format_replacements([])
    ''
    """
    pass


def lint_file(
    path: Path,
    pattern: re.Pattern[str],
    banned_functions: dict[str, list[str]],
) -> Iterator[LintMessage]:
    text = path.read_text(encoding="utf-8")
    scrubbed = _NOISE_RE.sub(_blank, text)
    original_lines = text.splitlines()

    for line_number, line in enumerate(scrubbed.splitlines(), 1):
        for match in pattern.finditer(line):
            function_name = match.group(1)
            if _is_suppressed(original_lines[line_number - 1], function_name):
                continue

            replacements = format_replacements(banned_functions[function_name])
            yield LintMessage(
                path=str(path),
                line=line_number,
                char=match.start(1) + 1,
                code=LINTER_CODE,
                severity=LintSeverity.ERROR,
                name=ERROR_NAME,
                original=None,
                replacement=None,
                description=(
                    f"{ERROR_DESCRIPTION} Found `{function_name}()` in {path.name}."
                    f"{replacements}"
                ),
            )


def lint_banned_functions_in_files(
    filenames: Sequence[str],
    banned_functions: dict[str, list[str]],
) -> list[LintMessage]:
    """Lint files for banned function calls."""
    pattern = build_pattern(banned_functions)
    if pattern is None:
        return []

    messages: list[LintMessage] = []
    for filename in filenames:
        path = Path(filename)
        if not path.is_file():
            continue
        messages.extend(lint_file(path, pattern, banned_functions))
    return messages


def _test_lint_banned_functions_in_files() -> None:
    r"""Doctests.

    >>> from tempfile import TemporaryDirectory
    >>> with TemporaryDirectory() as directory:
    ...     path = Path(directory) / "runtime.cpp"
    ...     source = '''void f() {
    ...   memcpy(dst, src, 4);
    ...   printf("hi");
    ... }
    ... '''
    ...     _ = path.write_text(source, encoding="utf-8")
    ...     config = parse_config({"banned_functions": [
    ...         {"names": ["memcpy"], "replacements": ["memcpy_s"]},
    ...         {"names": ["printf"], "replacements": ["ET_LOG"]},
    ...     ]})
    ...     messages = lint_banned_functions_in_files([str(path)], config)
    ...     [(m.line, m.char, f"Found `{name}()`" in (m.description or ""))
    ...      for m, name in zip(messages, ["memcpy", "printf"])]
    [(2, 3, True), (3, 3, True)]
    >>> with TemporaryDirectory() as directory:
    ...     path = Path(directory) / "runtime.cpp"
    ...     source = '''void f() {
    ...   // memcpy(dst, src, 4);
    ...   const char* text = "printf(hi)";
    ...   memcpy(dst, src, 4); // NOLINT(memcpy)
    ... }
    ... '''
    ...     _ = path.write_text(source, encoding="utf-8")
    ...     config = parse_config({"banned_functions": [{"names": ["memcpy", "printf"]}]})
    ...     lint_banned_functions_in_files([str(path)], config)
    []
    """
    pass


def main() -> None:
    parser = argparse.ArgumentParser(
        description=f"{ERROR_DESCRIPTION} Linter code: {LINTER_CODE}",
        fromfile_prefix_chars="@",
    )
    parser.add_argument(
        "--config",
        required=True,
        help=(
            "Path to a JSON config file. The file must be an object with a "
            "`banned_functions` list. Each group contains `names` and optional "
            "`replacements` lists."
        ),
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

    try:
        with open(args.config, encoding="utf-8") as config_file:
            banned_functions = parse_config(json.load(config_file))
    except (OSError, ValueError, json.JSONDecodeError) as err:
        LintMessage(
            path=args.config,
            line=None,
            char=None,
            code=LINTER_CODE,
            severity=LintSeverity.ERROR,
            name="init-error",
            original=None,
            replacement=None,
            description=f"Failed to load banned functions config: {err}",
        ).display()
        sys.exit(0)

    lint_messages = lint_banned_functions_in_files(args.filenames, banned_functions)
    for lint_message in lint_messages:
        lint_message.display()


if __name__ == "__main__":
    main()
