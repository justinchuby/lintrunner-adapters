"""cli for running lintrunner adapters.

Usage:

    python -m lintrunner_adapters <adapter_name> <args>

Use

    python -m lintrunner_adapters

to list available adapters.
"""
from __future__ import annotations

import json
import subprocess
import sys
from typing import Any

import click

import lintrunner_adapters
from lintrunner_adapters.tools import convert_to_sarif


@click.group()
def cli() -> None:
    pass


@cli.command(
    context_settings=dict(
        ignore_unknown_options=True,
        allow_extra_args=True,
    ),
)
@click.argument(
    "adapter", type=click.Choice(list(lintrunner_adapters.available_adapters().keys()))
)
def run(adapter: str) -> None:
    """Run an adapter."""
    adapters = lintrunner_adapters.available_adapters()
    try:
        subprocess.run(
            [
                sys.executable,
                adapters[adapter],
                *sys.argv[3:],
            ],
            check=True,
        )
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)


@cli.command()
@click.argument("input", type=click.File("r", encoding="utf-8"))
@click.argument("output", type=click.File("w", encoding="utf-8"))
def to_sarif(input: Any, output: Any) -> None:
    """Convert the output of lintrunner json (INPUT) to SARIF (OUTPUT)."""
    lintrunner_jsons = [json.loads(line) for line in input]
    sarif = convert_to_sarif.produce_sarif(lintrunner_jsons)
    json.dump(sarif, output)


if __name__ == "__main__":
    cli()
