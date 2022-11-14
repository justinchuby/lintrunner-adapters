# lintrunner-adapters

[![CI](https://github.com/justinchuby/lintrunner-adapters/actions/workflows/ci.yml/badge.svg)](https://github.com/justinchuby/lintrunner-adapters/actions/workflows/ci.yml)
[![PyPI version](https://badge.fury.io/py/lintrunner-adapters.svg)](https://badge.fury.io/py/lintrunner-adapters)

Adapters for [lintrunner](https://github.com/suo/lintrunner)

## Install

```sh
pip install lintrunner-adapters
```

## Usage

```text
Usage: python -m lintrunner_adapters [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  run       Run an adapter.
  to-sarif  Convert the output of lintrunner json (INPUT) to SARIF (OUTPUT).
```

Use `lintrunner_adapters run` to see a list of adapters available.

## How to

### Write lint config in `.lintrunner.toml`

https://docs.rs/lintrunner/latest/lintrunner/lint_message/struct.LintMessage.html

### Create a new adapter

Use [`lintrunner_adapters/adapters/pylint_linter.py`](https://github.com/justinchuby/lintrunner-adapters/blob/main/lintrunner_adapters/adapters/pylint_linter.py) as an example.
