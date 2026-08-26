"""Vault root resolution. One vault per process."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path


def resolve_vault_root(
    *,
    env: Mapping[str, str] | None = None,
    cli_vault: str | Path | None = None,
    home: str | Path | None = None,
) -> Path:
    """Return the vault root: INSITU_HOME, else --vault, else ~/.insitu."""
    environ = os.environ if env is None else env
    insitu_home = str(environ.get("INSITU_HOME", "") or "").strip()
    if insitu_home:
        return Path(insitu_home).expanduser().resolve()
    if cli_vault is not None:
        return Path(cli_vault).expanduser().resolve()
    home_path = Path(home) if home is not None else Path.home()
    return (home_path / ".insitu").expanduser().resolve()
