import re
from pathlib import Path

from fraudnova import Client

README = Path(__file__).resolve().parent.parent / "README.md"


def test_readme_only_calls_methods_that_exist() -> None:
    names = set(re.findall(r"client\.(\w+)\(", README.read_text(encoding="utf-8")))
    assert names, "README shows no client.<method>() calls"
    missing = sorted(name for name in names if not hasattr(Client, name))
    assert missing == []


def test_readme_mentions_install_and_every_method() -> None:
    text = README.read_text(encoding="utf-8")
    assert "pip install fraudnova" in text
    for term in (
        "check_ip",
        "check_email",
        "check_phone",
        "check_ips",
        "check_emails",
        "check_phones",
        "balance",
        "my_ip",
        "flagged",
        "RetryPolicy",
    ):
        assert term in text, term
