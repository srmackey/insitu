"""One version number. Drift between the three old homes is what made releases a decision."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from insitu import __version__

ROOT = Path(__file__).resolve().parents[1]


def test_design_header_agrees_with_package_version() -> None:
    header = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    match = re.search(r"^\*\*Version (\d+\.\d+)", header, re.M)
    assert match, "DESIGN.md has no **Version X.Y header"
    assert __version__.startswith(match.group(1) + "."), (
        f"DESIGN.md says {match.group(1)}, package says {__version__}"
    )


def test_pyproject_derives_the_version_rather_than_repeating_it() -> None:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert "version" not in data["project"], "pyproject must not hardcode a second version"
    assert data["project"]["dynamic"] == ["version"]
    assert data["tool"]["hatch"]["version"]["path"] == "src/insitu/__init__.py"
