"""Adapters and tools for lintrunner."""

import pathlib
from typing import Dict

from ._common.lintrunner_common import (  # noqa: F401
    IS_WINDOWS,
    LintMessage,
    LintSeverity,
    as_posix,
    run_command,
)


def available_adapters() -> Dict[str, pathlib.Path]:
    """Return a mapping of available adapters and their paths."""
    module_path = pathlib.Path(__file__).parent
    adapter_paths = (module_path / "adapters").glob("*.py")
    adapters = {path.stem: path for path in adapter_paths}
    return adapters
