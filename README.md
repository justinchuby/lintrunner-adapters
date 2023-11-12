# lintrunner-adapters

[![CI](https://github.com/justinchuby/lintrunner-adapters/actions/workflows/ci.yml/badge.svg)](https://github.com/justinchuby/lintrunner-adapters/actions/workflows/ci.yml)
[![PyPI version](https://badge.fury.io/py/lintrunner-adapters.svg)](https://badge.fury.io/py/lintrunner-adapters)

Adapters and tools for [lintrunner](https://github.com/suo/lintrunner).

`lintrunner-adapters` currently supports popular Python / Rust / C++ linters and formatters like `flake8`, `pylint`, `mypy`, `black`, `ruff`(with auto-fix support), `rustfmt`, `clippy`, `clang-format` and many more - and the list is growing. Contribution is welcome!

To see the list of supported linters and formatters, run `lintrunner_adapters run`.

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

## GitHub action

https://github.com/justinchuby/lintrunner-action

## How to

### Use `lintrunner_adapters` with `lintrunner` in your project

Refer to the [`.lintrunner.toml`](https://github.com/justinchuby/lintrunner-adapters/blob/main/.lintrunner.toml) config file in this repo and example configs for each adapter under [`examples/adapters`](https://github.com/justinchuby/lintrunner-adapters/tree/main/examples/adapters).

### Write lint config in `.lintrunner.toml`

See https://docs.rs/lintrunner/latest/lintrunner/lint_config/struct.LintConfig.html.

### Create a new adapter

Use [`lintrunner_adapters/adapters/pylint_linter.py`](https://github.com/justinchuby/lintrunner-adapters/blob/main/lintrunner_adapters/adapters/pylint_linter.py) as an example.

### Run lintrunner in CI and get Github code scanning messages in your PRs

#### Option 1

Use a GitHub Action: [lintrunner-action](https://github.com/justinchuby/lintrunner-action)

#### Option 2

Run it directly in the workflow. See [`.github/workflows/ci.yml`](https://github.com/justinchuby/lintrunner-adapters/blob/main/.github/workflows/ci.yml).
