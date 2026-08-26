from __future__ import annotations

from pathlib import Path

from insitu.vault import resolve_vault_root


def test_insitu_home_wins_over_cli_and_default(tmp_path: Path) -> None:
    env_vault = tmp_path / "from-env"
    cli_vault = tmp_path / "from-cli"
    user_home = tmp_path / "userhome"
    env_vault.mkdir()
    result = resolve_vault_root(
        env={"INSITU_HOME": str(env_vault)},
        cli_vault=cli_vault,
        home=user_home,
    )
    assert result == env_vault.resolve()


def test_cli_vault_used_when_env_absent(tmp_path: Path) -> None:
    cli_vault = tmp_path / "from-cli"
    user_home = tmp_path / "userhome"
    result = resolve_vault_root(env={}, cli_vault=cli_vault, home=user_home)
    assert result == cli_vault.resolve()


def test_default_is_dot_insitu_under_home(tmp_path: Path) -> None:
    user_home = tmp_path / "userhome"
    result = resolve_vault_root(env={}, cli_vault=None, home=user_home)
    assert result == (user_home / ".insitu").resolve()


def test_empty_insitu_home_falls_through_to_cli(tmp_path: Path) -> None:
    cli_vault = tmp_path / "from-cli"
    result = resolve_vault_root(
        env={"INSITU_HOME": "  "},
        cli_vault=cli_vault,
        home=tmp_path / "userhome",
    )
    assert result == cli_vault.resolve()
