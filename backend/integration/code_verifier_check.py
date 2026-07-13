from __future__ import annotations

from backend.app.services.code_verifier import HttpCodeVerifier


def main() -> None:
    verifier = HttpCodeVerifier("http://code-verifier:8090", timeout_seconds=40)
    cases = (
        ("print(6 * 7)", "42", True, "passed"),
        ("print('actual')", "expected", False, "output_mismatch"),
        ("open('/tmp/result.txt', 'w')", "", False, "policy_rejected"),
        ("print(getattr(object, '__subclasses__')())", "", False, "policy_rejected"),
        ("import urllib.request\nprint('network')", "network", False, "policy_rejected"),
        ("while True:\n    pass", "", False, "timeout"),
    )
    for code, expected, expected_ok, expected_code in cases:
        result = verifier.verify(code, expected)
        assert result.ok is expected_ok, result.safe_summary()
        assert result.code == expected_code, result.safe_summary()
    print("code verifier isolation and quality checks passed")


if __name__ == "__main__":
    main()
