"""Adapters and tools for lintrunner."""
from __future__ import annotations

__all__ = [
    "add_default_options",
    "as_posix",
    "available_adapters",
    "IS_WINDOWS",
    "LintMessage",
    "LintSeverity",
    "run_command",
]

import pathlib

from ._common.lintrunner_common import (
    IS_WINDOWS,
    LintMessage,
    LintSeverity,
    add_default_options,
    as_posix,
    run_command,
)


def available_adapters() -> dict[str, pathlib.Path]:
    """Return a mapping of available adapters and their paths."""
    module_path = pathlib.Path(__file__).parent
    adapter_paths = (module_path / "adapters").glob("*.py")
    adapters = {path.stem: path for path in adapter_paths}
    return adapters
