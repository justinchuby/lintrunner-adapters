# PyTorch LICENSE. See LICENSE file in the root directory of this source tree.

import argparse
import concurrent.futures
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List

from lintrunner_adapters import (
    IS_WINDOWS,
    LintMessage,
    LintSeverity,
    as_posix,
    run_command,
)

LINTER_CODE = "CLANGFORMAT"


def check_file(
    filename: str,
    binary: str,
    style: str,
    retries: int,
    timeout: int,
) -> List[LintMessage]:
    try:
        with open(filename, "rb") as f:
            original = f.read()
        proc = run_command(
            [binary, f"-style={style}", filename],
            retries=retries,
            timeout=timeout,
            check=True,
        )
    except subprocess.TimeoutExpired:
        return [
            LintMessage(
                path=filename,
                line=None,
                char=None,
                code=LINTER_CODE,
                severity=LintSeverity.ERROR,
                name="timeout",
                original=None,
                replacement=None,
                description=(
                    "clang-format timed out while trying to process a file. "
                    "Please report an issue in pytorch/pytorch with the "
                    "label 'module: lint'"
                ),
            )
        ]
    except (OSError, subprocess.CalledProcessError) as err:
        return [
            LintMessage(
                path=filename,
                line=None,
                char=None,
                code=LINTER_CODE,
                severity=LintSeverity.ADVICE,
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
        ]

    replacement = proc.stdout
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
            description="See https://clang.llvm.org/docs/ClangFormat.html.\nRun `lintrunner -a` to apply this patch.",
        )
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description=f"Format files with clang-format. Linter code: {LINTER_CODE}",
        fromfile_prefix_chars="@",
    )
    parser.add_argument(
        "--binary",
        required=True,
        help="clang-format binary path",
    )
    parser.add_argument(
        "--fallback",
        action="store_true",
        help="fallback to using clang-format from PATH",
    )
    parser.add_argument(
        "--style",
        default="file",
        help="clang-format style",
    )
    parser.add_argument(
        "--retries",
        default=3,
        type=int,
        help="times to retry timed out clang-format",
    )
    parser.add_argument(
        "--timeout",
        default=90,
        type=int,
        help="seconds to wait for clang-format",
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

    binary = os.path.normpath(args.binary) if IS_WINDOWS else args.binary
    if not Path(binary).exists():
        if args.fallback:
            # Find clang-format in PATH
            binary = shutil.which("clang-format")
            if binary is None:
                lint_message = LintMessage(
                    path=None,
                    line=None,
                    char=None,
                    code=LINTER_CODE,
                    severity=LintSeverity.ERROR,
                    name="init-error",
                    original=None,
                    replacement=None,
                    description=(
                        f"Could not find clang-format binary at {binary}, "
                        "and fallback to PATH failed."
                        "Run `lintrunner init` or make sure clang-format is "
                        "installed and in PATH."
                    ),
                )
                lint_message.display()
                sys.exit(0)
        else:
            lint_message = LintMessage(
                path=None,
                line=None,
                char=None,
                code=LINTER_CODE,
                severity=LintSeverity.ERROR,
                name="init-error",
                original=None,
                replacement=None,
                description=(
                    f"Could not find clang-format binary at {binary}. "
                    "did you forget to run `lintrunner init`?"
                ),
            )
            lint_message.display()
            sys.exit(0)

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=os.cpu_count(),
        thread_name_prefix="Thread",
    ) as executor:
        futures = {
            executor.submit(
                check_file, x, binary, args.style, args.retries, args.timeout
            ): x
            for x in args.filenames
        }
        for future in concurrent.futures.as_completed(futures):
            try:
                for lint_message in future.result():
                    lint_message.display()
            except Exception:
                logging.critical('Failed at "%s".', futures[future])
                raise


if __name__ == "__main__":
    main()
