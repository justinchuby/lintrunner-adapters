"""Initializer script that installs stuff to pip."""

# PyTorch LICENSE. See LICENSE file in the root directory of this source tree.

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import time


def run_command(args: list[str]) -> subprocess.CompletedProcess[bytes]:
    logging.debug("$ %s", " ".join(args))
    start_time = time.monotonic()
    try:
        return subprocess.run(args, check=True)
    finally:
        end_time = time.monotonic()
        logging.debug("took %dms", (end_time - start_time) * 1000)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="pip initializer")
    parser.add_argument(
        "packages",
        nargs="*",
        help="pip packages to install",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="verbose logging",
    )
    parser.add_argument(
        "--dry-run", help="do not install anything, just print what would be done."
    )
    parser.add_argument(
        "--no-black-binary",
        help="do not use pre-compiled binaries from pip for black.",
        action="store_true",
    )
    parser.add_argument(
        "--user",
        help="use the --user option for pip install",
        action="store_true",
    )
    parser.add_argument(
        "--force-venv",
        help="do not install anything without activated venv",
        action="store_true",
    )
    parser.add_argument(
        "--requirement",
        help="install packages from a requirements file",
    )

    args = parser.parse_args()

    logging.basicConfig(
        format="<%(threadName)s:%(levelname)s> %(message)s",
        level=logging.NOTSET if args.verbose else logging.DEBUG,
        stream=sys.stderr,
    )

    pip_args = [sys.executable, "-m", "pip", "install"]

    # If we are in a global install and `--user` is specified,
    # use `--user` to install so that you do not
    # need root access in order to initialize linters.
    #
    # However, `pip install --user` interacts poorly with virtualenvs (see:
    # https://bit.ly/3vD4kvl) and conda (see: https://bit.ly/3KG7ZfU). So in
    # these cases perform a regular installation.
    in_conda = os.environ.get("CONDA_PREFIX") is not None
    in_virtualenv = os.environ.get("VIRTUAL_ENV") is not None
    if args.force_venv and not in_virtualenv and not in_conda:
        raise RuntimeError(
            "Fails to init because no virtualenv is found with 'force_venv=True'. "
            "Activate virtualenv to install packages."
        )
    if args.user and not in_conda and not in_virtualenv:
        pip_args.append("--user")

    if args.requirement:
        pip_args.extend(["-r", args.requirement])

    pip_args.extend(args.packages)

    for package in args.packages:
        package_name, _, version = package.partition("=")
        if not version:
            raise RuntimeError(
                f"Package '{package_name}' did not have a version specified. "
                "Please specify a version to produce a consistent linting experience."
            )
        if args.no_black_binary and "black" in package_name:
            pip_args.append(f"--no-binary={package_name}")

    dry_run = args.dry_run == "1"
    if dry_run:
        print(f"Would have run: '{pip_args}'")
        sys.exit(0)

    run_command(pip_args)
