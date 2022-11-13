# PyTorch LICENSE. See LICENSE file in the root directory of this source tree.

import argparse
import concurrent.futures
import json
import logging
import os
import re
import subprocess
import time
from enum import Enum
from typing import List, NamedTuple, Optional, Pattern

from lintrunner_adapters import LintMessage, LintSeverity, run_command, as_posix, IS_WINDOWS


LINTER_CODE = "CMAKE"


# CMakeLists.txt:901: Lines should be <= 80 characters long [linelength]
RESULTS_RE: Pattern[str] = re.compile(
    r"""(?mx)
    ^
    (?P<file>.*?):
    (?P<line>\d+):
    \s(?P<message>.*)
    \s(?P<code>\[.*\])
    $
    """
)

def check_file(
    filename: str,
    config: str,
) -> List[LintMessage]:
    try:
        proc = run_command(
            ["cmakelint", f"--config={config}", filename],
            reties=0, timeout=90
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
            name=match["code"],
            description=match["message"],
            line=int(match["line"]),
            char=None,
            code=LINTER_CODE,
            severity=LintSeverity.ERROR,
            original=None,
            replacement=None,
        )
        for match in RESULTS_RE.finditer(stdout)
    ]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="cmakelint runner",
        fromfile_prefix_chars="@",
    )
    parser.add_argument(
        "--config",
        required=True,
        help="location of cmakelint config",
    )
    parser.add_argument(
        "filenames",
        nargs="+",
        help="paths to lint",
    )

    args = parser.parse_args()

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=os.cpu_count(),
        thread_name_prefix="Thread",
    ) as executor:
        futures = {
            executor.submit(
                check_file,
                filename,
                args.config,
            ): filename
            for filename in args.filenames
        }
        for future in concurrent.futures.as_completed(futures):
            try:
                for lint_message in future.result():
                    print(json.dumps(lint_message._asdict()), flush=True)
            except Exception:
                logging.critical('Failed at "%s".', futures[future])
                raise
