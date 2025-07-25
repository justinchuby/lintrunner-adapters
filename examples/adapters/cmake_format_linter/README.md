# cmake-format linter

This example demonstrates how to use cmake-format with lintrunner-adapters.

## Usage

```bash
lintrunner init && lintrunner
```

## Configuration file

You can optionally provide a cmake-format configuration file using the `--config-file` argument:

```toml
command = [
    'python',
    '-m',
    'lintrunner_adapters',
    'run',
    'cmake_format_linter',
    '--config-file=.cmake-format.yaml',
    '--',
    '@{{PATHSFILE}}',
]
```
