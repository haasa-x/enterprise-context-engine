"""Doc-link check: every relative Markdown link must resolve to a real file.

Runs without Neo4j. Scans README.md, CONTRIBUTING.md, CHANGELOG.md and every
file under docs/, and fails if any relative link (or image) points at a path
that does not exist. External (http/https/mailto) and pure-anchor links are
ignored.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

_LINK_PATTERN = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
_EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "#", "tel:")


def _markdown_files() -> list[Path]:
    top_level = [
        REPO_ROOT / name for name in ("README.md", "CONTRIBUTING.md", "CHANGELOG.md")
    ]
    docs = sorted((REPO_ROOT / "docs").rglob("*.md"))
    return [path for path in [*top_level, *docs] if path.exists()]


def _link_targets(markdown: str) -> list[str]:
    targets = []
    for raw in _LINK_PATTERN.findall(markdown):
        target = raw.strip().split(" ", 1)[0].split("#", 1)[0]
        if target and not target.startswith(_EXTERNAL_PREFIXES):
            targets.append(target)
    return targets


def test_all_relative_doc_links_resolve() -> None:
    broken: list[str] = []
    for path in _markdown_files():
        for target in _link_targets(path.read_text()):
            resolved = (path.parent / target).resolve()
            if not resolved.exists():
                broken.append(f"{path.relative_to(REPO_ROOT)} -> {target}")
    assert not broken, "Broken relative doc links: " + "; ".join(broken)
