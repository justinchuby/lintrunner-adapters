"""cli for running lintrunner adapters.
Usage:

    python -m lintrunner_adapters <adapter_name> <args>

Use

    python -m lintrunner_adapters

to list available adapters.
"""

import pathlib
import subprocess
import sys

import lintrunner_adapters


def main():

    module_path = pathlib.Path(lintrunner_adapters.__file__).parent
    adapter_paths = (module_path / "adapters").glob("*.py")
    adapters = {path.stem: path for path in adapter_paths}

    if len(sys.argv) < 2:
        print("Usage: python -m lintrunner_adapters <adapter_name> <args>")
        print(f"Available adapters: {sorted(adapters.keys())}")
        sys.exit(1)

    executable_name = sys.argv[1]
    if executable_name not in adapters:
        print(f"Unknown executable name: {executable_name}")
        print(f"Available adapters: {sorted(adapters.keys())}")
        sys.exit(1)

    try:
        subprocess.run(
            [
                sys.executable,
                adapters[executable_name],
                *sys.argv[2:],
            ],
            check=True,
        )
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)


if __name__ == "__main__":
    main()
