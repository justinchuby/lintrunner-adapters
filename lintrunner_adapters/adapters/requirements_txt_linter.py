# https://github.com/pre-commit/pre-commit-hooks/blob/main/pre_commit_hooks/requirements_txt_fixer.py
# Copyright (c) 2014 pre-commit dev team: Anthony Sottile, Ken Struys

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

from __future__ import annotations

import argparse
import concurrent.futures
import logging
import os
import re
import sys
from typing import IO

from lintrunner_adapters import LintMessage, LintSeverity, add_default_options

LINTER_CODE = "REQUIREMENTS-TXT"


class Requirement:
    UNTIL_COMPARISON = re.compile(b"={2,3}|!=|~=|>=?|<=?")
    UNTIL_SEP = re.compile(rb"[^;\s]+")

    def __init__(self) -> None:
        self.value: bytes | None = None
        self.comments: list[bytes] = []

    @property
    def name(self) -> bytes:
        assert self.value is not None, self.value
        name = self.value.lower()
        for egg in (b"#egg=", b"&egg="):
            if egg in self.value:
                return name.partition(egg)[-1]

        m = self.UNTIL_SEP.match(name)
        assert m is not None

        name = m.group()
        m = self.UNTIL_COMPARISON.search(name)
        if not m:
            return name

        return name[: m.start()]

    def __lt__(self, requirement: Requirement) -> bool:
        # \n means top of file comment, so always return True,
        # otherwise just do a string comparison with value.
        assert self.value is not None, self.value
        if self.value == b"\n":
            return True
        if requirement.value == b"\n":
            return False
        return self.name < requirement.name

    def is_complete(self) -> bool:
        return self.value is not None and not self.value.rstrip(b"\r\n").endswith(b"\\")

    def append_value(self, value: bytes) -> None:
        if self.value is not None:
            self.value += value
        else:
            self.value = value


def fix_requirements(f: IO[bytes]) -> bytes:
    requirements: list[Requirement] = []
    before = list(f)
    after: list[bytes] = []

    before_string = b"".join(before)

    # adds new line in case one is missing
    # AND a change to the requirements file is needed regardless:
    if before and not before[-1].endswith(b"\n"):
        before[-1] += b"\n"

    # If the file is empty (i.e. only whitespace/newlines) exit early
    if before_string.strip() == b"":
        return before_string

    for line in before:
        # If the most recent requirement object has a value, then it's
        # time to start building the next requirement object.

        if not requirements or requirements[-1].is_complete():
            requirements.append(Requirement())

        requirement = requirements[-1]

        # If we see a newline before any requirements, then this is a
        # top of file comment.
        if len(requirements) == 1 and line.strip() == b"":
            if len(requirement.comments) and requirement.comments[0].startswith(b"#"):
                requirement.value = b"\n"
            else:
                requirement.comments.append(line)
        elif line.lstrip().startswith(b"#") or line.strip() == b"":
            requirement.comments.append(line)
        else:
            requirement.append_value(line)

    # if a file ends in a comment, preserve it at the end
    rest = requirements.pop().comments if requirements[-1].value is None else []

    # find and remove pkg-resources==0.0.0
    # which is automatically added by broken pip package under Debian
    requirements = [
        req for req in requirements if req.value != b"pkg-resources==0.0.0\n"
    ]

    for requirement in sorted(requirements):
        after.extend(requirement.comments)
        assert requirement.value, requirement.value
        after.append(requirement.value)
    after.extend(rest)

    after_string = b"".join(after)

    return after_string


def check_file(filename: str) -> list[LintMessage]:
    with open(filename, "rb") as f:
        original = f.read()
    with open(filename, "rb") as f:
        replacement = fix_requirements(f)

    if original == replacement:
        return []

    return [
        LintMessage(
            path=filename,
            line=None,
            char=None,
            code=LINTER_CODE,
            severity=LintSeverity.WARNING,
            name="format",
            original=original.decode("utf-8"),
            replacement=replacement.decode("utf-8"),
            description="Run `lintrunner -a` to apply this patch.",
        )
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description=f"Format Python requirements.txt files. Linter code: {LINTER_CODE}",
        fromfile_prefix_chars="@",
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

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=os.cpu_count(),
        thread_name_prefix="Thread",
    ) as executor:
        futures = {executor.submit(check_file, x): x for x in args.filenames}
        for future in concurrent.futures.as_completed(futures):
            try:
                for lint_message in future.result():
                    lint_message.display()
            except Exception:
                logging.critical('Failed at "%s".', futures[future])
                raise


if __name__ == "__main__":
    main()
