from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    root = tmp_path / "vault"
    (root / "stanzas").mkdir(parents=True)
    (root / "projects").mkdir()
    (root / "config").mkdir()
    return root
