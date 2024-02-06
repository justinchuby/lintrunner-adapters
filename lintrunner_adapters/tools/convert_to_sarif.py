"""Convert the output of lintrunner json to SARIF."""

from __future__ import annotations

import argparse
import json
import os
from typing import Any, Iterable


def format_rule_name(lintrunner_result: dict[str, Any]) -> str:
    return f"{lintrunner_result['code']}/{lintrunner_result['name']}"


def severity_to_github_level(severity: str) -> str:
    if severity in {"advice", "disabled"}:
        return "note"
    return severity


def parse_single_lintrunner_result(
    lintrunner_result: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    r"""Parse a single lintrunner result.

    A result looks like this:
    {
        "path":"/adapters/pytorch/grep_linter.py",
        "line":227,
        "char":80,
        "code":"FLAKE8",
        "severity":"advice",
        "name":"E501",
        "description":"line too long (81 > 79 characters)\nSee https://www.flake8rules.com/rules/E501.html"
    }
    """
    if lintrunner_result["path"] is None:
        artifact_uri = None
    else:
        artifact_uri = (
            ("file://" + lintrunner_result["path"])
            if lintrunner_result["path"].startswith("/")
            else lintrunner_result["path"]
        )
    result = {
        "ruleId": format_rule_name(lintrunner_result),
        "level": severity_to_github_level(lintrunner_result["severity"]),
        "message": {
            "text": lintrunner_result["description"],
        },
        "locations": [
            {
                "physicalLocation": {
                    "artifactLocation": {
                        "uri": artifact_uri,
                    },
                    "region": {
                        "startLine": lintrunner_result["line"] or 1,
                        "startColumn": lintrunner_result["char"] or 1,
                    },
                },
            },
        ],
    }

    rule = {
        "id": format_rule_name(lintrunner_result),
        "rule": {
            "id": format_rule_name(lintrunner_result),
            "name": format_rule_name(lintrunner_result),
            "shortDescription": {"text": format_rule_name(lintrunner_result)},
            "fullDescription": {
                "text": format_rule_name(lintrunner_result)
                + "\n"
                + lintrunner_result["description"],
            },
            "defaultConfiguration": {
                "level": severity_to_github_level(lintrunner_result["severity"]),
            },
        },
    }

    return result, rule


def produce_sarif(lintrunner_results: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Convert the output of lintrunner json to SARIF."""

    rules = {}
    results = []
    for lintrunner_json in lintrunner_results:
        result, rule = parse_single_lintrunner_result(lintrunner_json)
        results.append(result)
        rules[rule["id"]] = rule["rule"]

    sarif = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "lintrunner",
                        "rules": list(rules.values()),
                    },
                },
                "results": results,
            },
        ],
    }

    return sarif


def main(args: Any) -> None:
    """Convert the output of lintrunner json to SARIF."""
    with open(args.input, encoding="utf-8") as f:
        lintrunner_jsons = [json.loads(line) for line in f]

    sarif = produce_sarif(lintrunner_jsons)

    output_dir = os.path.dirname(args.output)
    if output_dir:
        os.makedirs(os.path.dirname(args.output), exist_ok=True)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(sarif, f)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input", type=str, required=True, help="json file generated by lintrunner"
    )
    parser.add_argument("--output", type=str, required=True, help="output sarif file")
    args = parser.parse_args()
    main(args)
