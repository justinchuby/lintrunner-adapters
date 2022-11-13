"""cli for running lintrunner adapters.

Usage:

    python -m lintrunner_adapters <adapter_name> <args>

Use

    python -m lintrunner_adapters

to list available adapters.
"""

import json
import pathlib
import subprocess
import sys
from typing import List

import click

import lintrunner_adapters
from lintrunner_adapters.tools import convert_to_sarif


@click.group()
def cli():
    pass


@cli.command(
    context_settings=dict(
        ignore_unknown_options=True,
        allow_extra_args=True,
    ),
)
def run():
    """Run an adapter."""
    run_adapter(sys.argv[2:])


@cli.command()
@click.argument("input", type=click.File("r"))
@click.argument("output", type=click.File("w"))
def to_sarif(input, output):
    """Convert the output of lintrunner json (INPUT) to SARIF (OUTPUT)."""

    lintrunner_jsons = [json.loads(line) for line in input]

    sarif = convert_to_sarif.produce_sarif(lintrunner_jsons)

    json.dump(sarif, output)


def run_adapter(args: List[str]) -> None:

    module_path = pathlib.Path(lintrunner_adapters.__file__).parent
    adapter_paths = (module_path / "adapters").glob("*.py")
    adapters = {path.stem: path for path in adapter_paths}

    if not len(args):
        print("Usage: python -m lintrunner_adapters <adapter_name> <args>")
        print(f"Available adapters: {sorted(adapters.keys())}")
        sys.exit(1)

    adapter_name = args[0]
    if adapter_name not in adapters:
        print(f"Unknown executable name: {adapter_name}")
        print(f"Available adapters: {sorted(adapters.keys())}")
        sys.exit(1)

    try:
        subprocess.run(
            [
                sys.executable,
                adapters[adapter_name],
                *args[1:],
            ],
            check=True,
        )
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)


if __name__ == "__main__":
    cli()
