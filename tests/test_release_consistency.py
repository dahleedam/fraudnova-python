import re
from pathlib import Path

import fraudnova


def test_version_matches_latest_changelog_release() -> None:
    changelog = Path(__file__).resolve().parent.parent / "CHANGELOG.md"
    match = re.search(r"^## \[(\d+\.\d+\.\d+)\]", changelog.read_text(encoding="utf-8"), re.M)
    assert match is not None
    assert match.group(1) == fraudnova.__version__
