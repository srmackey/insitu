from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _no_install_root(monkeypatch: pytest.MonkeyPatch) -> None:
    """Address mode is opt-in. A machine INSITU_ROOT must not leak into tests."""
    monkeypatch.delenv("INSITU_ROOT", raising=False)


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    root = tmp_path / "vault"
    (root / "articles").mkdir(parents=True)
    (root / "projects").mkdir()
    (root / "config").mkdir()
    return root
