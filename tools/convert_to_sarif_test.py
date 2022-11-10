import unittest
import convert_to_sarif


class TestConvertToSarif(unittest.TestCase):
    def test_produce_sarif_returns_correct_sarif_result(self):
        lintrunner_results = [
            {
                "path": "test.py",
                "line": 1,
                "char": 2,
                "code": "FLAKE8",
                "severity": "error",
                "description": "test description",
                "name": "test-code",
            },
            {
                "path": "test.py",
                "line": 1,
                "char": 2,
                "code": "FLAKE8",
                "severity": "error",
                "description": "test description",
                "name": "test-code-2",
            },
        ]
        actual = convert_to_sarif.produce_sarif(lintrunner_results)
        expected = {
            "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "lintrunner",
                            "rules": [
                                {
                                    "id": "FLAKE8/test-code",
                                    "name": "FLAKE8/test-code",
                                    "shortDescription": {
                                        "text": "FLAKE8/test-code: test description"
                                    },
                                    "fullDescription": {
                                        "text": "FLAKE8/test-code\ntest description"
                                    },
                                    "defaultConfiguration": {"level": "error"},
                                },
                                {
                                    "id": "FLAKE8/test-code-2",
                                    "name": "FLAKE8/test-code-2",
                                    "shortDescription": {
                                        "text": "FLAKE8/test-code-2: test description"
                                    },
                                    "fullDescription": {
                                        "text": "FLAKE8/test-code-2\ntest description"
                                    },
                                    "defaultConfiguration": {"level": "error"},
                                },
                            ],
                        }
                    },
                    "results": [
                        {
                            "ruleId": "FLAKE8/test-code",
                            "level": "error",
                            "message": {"text": "FLAKE8/test-code\ntest description"},
                            "locations": [
                                {
                                    "physicalLocation": {
                                        "artifactLocation": {"uri": "file://test.py"},
                                        "region": {"startLine": 1, "startColumn": 2},
                                    }
                                }
                            ],
                        },
                        {
                            "ruleId": "FLAKE8/test-code-2",
                            "level": "error",
                            "message": {"text": "FLAKE8/test-code-2\ntest description"},
                            "locations": [
                                {
                                    "physicalLocation": {
                                        "artifactLocation": {"uri": "file://test.py"},
                                        "region": {"startLine": 1, "startColumn": 2},
                                    }
                                }
                            ],
                        },
                    ],
                }
            ],
        }

        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
