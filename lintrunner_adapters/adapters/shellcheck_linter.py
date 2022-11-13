# PyTorch LICENSE. See LICENSE file in the root directory of this source tree.

import argparse
import json
import shutil
import sys
from typing import List

from lintrunner_adapters import LintMessage, LintSeverity, run_command

LINTER_CODE = "SHELLCHECK"


def check_files(
    files: List[str],
) -> List[LintMessage]:
    try:
        proc = run_command(
            ["shellcheck", "--external-sources", "--format=json1"] + files
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
    results = json.loads(stdout)["comments"]
    return [
        LintMessage(
            path=result["file"],
            name=f"SC{result['code']}",
            description=result["message"],
            line=result["line"],
            char=result["column"],
            code=LINTER_CODE,
            severity=LintSeverity.ERROR,
            original=None,
            replacement=None,
        )
        for result in results
    ]


def main():
    parser = argparse.ArgumentParser(
        description=f"shellcheck runner. Linter code: {LINTER_CODE}",
        fromfile_prefix_chars="@",
    )
    parser.add_argument(
        "filenames",
        nargs="+",
        help="paths to lint",
    )

    if shutil.which("shellcheck") is None:
        err_msg = LintMessage(
            path="<none>",
            line=None,
            char=None,
            code=LINTER_CODE,
            severity=LintSeverity.ERROR,
            name="command-failed",
            original=None,
            replacement=None,
            description="shellcheck is not installed, did you forget to run `lintrunner init`?",
        )
        err_msg.display()
        sys.exit(0)

    args = parser.parse_args()

    lint_messages = check_files(args.filenames)
    for lint_message in lint_messages:
        lint_message.display()


if __name__ == "__main__":
    main()
