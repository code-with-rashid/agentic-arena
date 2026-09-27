"""Profile pages declare enough provenance to support a current decision.

The rendered summary is generated from this front matter. Keeping the contract
small and flat lets the core test suite validate it without adding a YAML runtime
dependency to the comparison harness.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PROFILE_DIRS = (ROOT / "docs" / "frameworks", ROOT / "docs" / "harnesses")
EXCLUDED = {"README.md", "comparison.md"}
REQUIRED = {
    "profile_type",
    "evidence_status",
    "evidence_level",
    "last_verified",
    "revalidate_after",
    "reviewed_version",
    "best_for",
    "owns",
    "important_limit",
    "evidence_summary",
}
STATUS_LEVEL = {
    "mock-tested": "mock",
    "diagnostic-only": "diagnostic",
    "protocol-mismatch": "none",
    "source-reviewed": "source-review",
    "native-live": "live",
    "independently-reproduced": "reproduced",
}


def _profiles() -> list[Path]:
    return sorted(
        page
        for directory in PROFILE_DIRS
        for page in directory.glob("*.md")
        if page.name not in EXCLUDED
    )


def _front_matter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path.relative_to(ROOT)} has no YAML front matter"
    block = text.split("---", 2)[1]
    values: dict[str, str] = {}
    for raw in block.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        key, separator, value = raw.partition(":")
        assert separator, f"{path.relative_to(ROOT)} has malformed metadata line: {raw!r}"
        values[key.strip()] = value.strip().strip('"')
    return values


PROFILES = _profiles()


@pytest.mark.parametrize("path", PROFILES, ids=lambda path: path.stem)
def test_profile_metadata_is_complete_and_current(path: Path) -> None:
    metadata = _front_matter(path)
    missing = sorted(REQUIRED - metadata.keys())
    assert not missing, f"{path.relative_to(ROOT)} is missing profile metadata: {missing}"
    assert all(metadata[key] for key in REQUIRED), (
        f"{path.relative_to(ROOT)} has empty profile metadata"
    )

    expected_type = "framework" if path.parent.name == "frameworks" else "coding-harness"
    assert metadata["profile_type"] == expected_type

    status = metadata["evidence_status"]
    assert status in STATUS_LEVEL, f"{path.relative_to(ROOT)} has unknown status {status!r}"
    assert metadata["evidence_level"] == STATUS_LEVEL[status]

    verified = date.fromisoformat(metadata["last_verified"])
    deadline = date.fromisoformat(metadata["revalidate_after"])
    assert verified <= date.today(), f"{path.relative_to(ROOT)} was verified in the future"
    assert verified < deadline, f"{path.relative_to(ROOT)} has no revalidation window"
    assert date.today() <= deadline, (
        f"{path.relative_to(ROOT)} became stale on {deadline}; review the pinned source or "
        "rerun its declared evidence before moving the date"
    )


def test_every_product_profile_is_under_the_metadata_contract() -> None:
    assert len(PROFILES) == 15, "Add every new framework or harness profile to this contract"
