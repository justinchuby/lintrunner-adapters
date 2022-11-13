"""EXEC: Ensure that source files are not executable."""

# PyTorch LICENSE. See LICENSE file in the root directory of this source tree.

import argparse
import logging
import os
import sys
from typing import Optional

from lintrunner_adapters import LintMessage, LintSeverity

LINTER_CODE = "EXEC"


def check_file(filename: str) -> Optional[LintMessage]:
    is_executable = os.access(filename, os.X_OK)
    if is_executable:
        return LintMessage(
            path=filename,
            line=None,
            char=None,
            code=LINTER_CODE,
            severity=LintSeverity.ERROR,
            name="executable-permissions",
            original=None,
            replacement=None,
            description="This file has executable permission; please remove it by using `chmod -x`.",
        )
    return None


def main():
    parser = argparse.ArgumentParser(
        description=f"exec linter. Linter code: {LINTER_CODE}",
        fromfile_prefix_chars="@",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
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

    lint_messages = []
    for filename in args.filenames:
        lint_message = check_file(filename)
        if lint_message is not None:
            lint_messages.append(lint_message)

    for lint_message in lint_messages:
        lint_message.display()


if __name__ == "__main__":
    main()
