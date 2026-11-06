from pathlib import Path

FORBIDDEN = [
    "".join(["IP", "Quality", "Score"]),
    "".join(["IP", "QS"]),
    "upstream " + "key",
    "key " + "pool",
]
SKIP_DIRS = {
    ".git",
    ".venv",
    ".superpowers",
    "dist",
    "build",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}


def test_no_file_names_the_upstream_provider() -> None:
    root = Path(__file__).resolve().parent.parent
    needles = [word.lower() for word in FORBIDDEN]
    offenders: list[str] = []
    for path in root.rglob("*"):
        rel = path.relative_to(root)
        if not path.is_file() or SKIP_DIRS.intersection(rel.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        offenders.extend(f"{rel}: {n}" for n in needles if n in text)
    assert offenders == []
