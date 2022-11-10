"""Convert the output of lintrunner json to SARIF."""

import argparse
import json
import os
import sarif_om as om
import attrs
import hashlib


def hash_rule_id(rule_id: str):
    """Hash the rule id to make it opaque (SARIF1001)."""""
    return hashlib.sha1(rule_id.encode("utf-8")).hexdigest()


def format_rule_name(lintrunner_result: dict):
    return f"{lintrunner_result['code']}/{lintrunner_result['name']}"


def severity_to_github_level(severity: str):
    if severity == "advice" or severity == "disabled":
        return "warning"
    return severity


def parse_single_lintrunner_result(lintrunner_result: dict):
    """Parse a single lintrunner result.

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
    result = om.Result(
        rule_id=hash_rule_id(format_rule_name(lintrunner_result)),
        level=severity_to_github_level(lintrunner_result["severity"]),
        message=om.Message(
            text=lintrunner_result["description"],
        ),
        locations=[
            om.Location(
                physical_location=om.PhysicalLocation(
                    artifact_location=om.ArtifactLocation(
                        uri=lintrunner_result["path"],
                    ),
                    region=om.Region(
                        start_line=lintrunner_result["line"] or 1,
                        start_column=lintrunner_result["char"] or 1,
                    ),
                ),
            ),
        ],
    )

    rule = {
        "id": format_rule_name(lintrunner_result),
        "rule": om.ReportingDescriptor(
            id=hash_rule_id(format_rule_name(lintrunner_result)),
            name=format_rule_name(lintrunner_result),
            short_description=om.MultiformatMessageString(
                text=lintrunner_result["description"],
            ),
            full_description=om.MultiformatMessageString(
                text=lintrunner_result["description"],
            ),
            # help=om.MultiformatMessageString(
            #     text=lintrunner_result["description"],
            # ),
            default_configuration=om.ReportingConfiguration(
                level=lintrunner_result["severity"],
            ),
        ),
    }

    return result, rule


def delete_default(dict_: dict):
    """Delete default (None, -1) values recursively from all of the dictionaries.

    https://stackoverflow.com/questions/33797126/proper-way-to-remove-keys-in-dictionary-with-none-values-in-python
    """
    for key, value in list(dict_.items()):
        if isinstance(value, dict):
            delete_default(value)
        elif value is None or value == -1 or (key=="kind" and value=="fail"):
            del dict_[key]
        elif isinstance(value, list):
            for v_i in value:
                if isinstance(v_i, dict):
                    delete_default(v_i)

    return dict_


def main(args):
    """Convert the output of lintrunner json to SARIF."""

    rules = {}
    results = []
    with open(args.input, "r") as f:
        for line in f:
            lintrunner_json = json.loads(line)
            result, rule = parse_single_lintrunner_result(lintrunner_json)
            results.append(result)
            rules[rule["id"]] = rule["rule"]

    sarif = om.SarifLog(
        version="2.1.0",
        schema_uri="https://json.schemastore.org/sarif-2.1.0.json",
        runs=[
            om.Run(
                tool=om.Tool(
                    driver=om.ToolComponent(
                        name="lintrunner",
                        rules=list(rules.values()),
                    )
                ),
                results=results,
            ),
        ],
    )

    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    with open(args.output, "w") as f:
        sarif = attrs.asdict(sarif)
        sarif = delete_default(sarif)
        f.write(json.dumps(sarif))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, required=True)
    parser.add_argument("--output", type=str, required=True)
    args = parser.parse_args()
    main(args)
