from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from insitu.cli import build_parser, main
from insitu.operators import (
    CLASS_ADMIN,
    CLASS_BOUND,
    init_admin,
    load_operators,
    operator_status,
)


@pytest.fixture(autouse=True)
def _no_ambient_vault(monkeypatch) -> None:
    """INSITU_HOME outranks --vault, so a set one would redirect these tests."""
    monkeypatch.delenv("INSITU_HOME", raising=False)


def _write_operators(vault: Path, data: dict) -> Path:
    path = vault / "config" / "operators.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


# --- loader: a vault with no config is pre-init, not an error -------------


def test_missing_config_is_pre_init_and_permissive(vault: Path) -> None:
    config = load_operators(vault)
    assert config.initialized is False
    assert config.default_class == CLASS_BOUND
    assert config.admins == []


def test_pre_init_status_carries_a_warning(vault: Path) -> None:
    status = operator_status(vault)
    assert status["ok"] is True
    assert status["initialized"] is False
    assert "insitu init --admin" in status["warning"]


def test_initialized_status_has_no_warning(vault: Path) -> None:
    init_admin(vault, "river-ledger")
    status = operator_status(vault)
    assert status["initialized"] is True
    assert "warning" not in status


# --- loader: classes, defaults, and junk ---------------------------------


def test_listed_project_takes_its_class(vault: Path) -> None:
    _write_operators(
        vault,
        {"default_class": "bound", "projects": {"river-ledger": "admin", "harbor": "bound"}},
    )
    config = load_operators(vault)
    assert config.is_admin("river-ledger") is True
    assert config.is_admin("harbor") is False
    assert config.class_for("harbor") == CLASS_BOUND


def test_unlisted_project_takes_the_default_class(vault: Path) -> None:
    _write_operators(vault, {"default_class": "bound", "projects": {"dp": "admin"}})
    config = load_operators(vault)
    assert config.class_for("never-subscribed") == CLASS_BOUND


def test_project_keys_are_case_folded(vault: Path) -> None:
    _write_operators(vault, {"projects": {"River-Ledger": "admin"}})
    config = load_operators(vault)
    assert config.is_admin("river-ledger") is True
    assert config.is_admin("RIVER-LEDGER") is True


def test_unknown_class_names_are_dropped_not_honored(vault: Path) -> None:
    _write_operators(
        vault, {"default_class": "wizard", "projects": {"dp": "superuser"}}
    )
    config = load_operators(vault)
    assert config.default_class == CLASS_BOUND
    assert config.class_for("dp") == CLASS_BOUND
    assert config.admins == []


def test_unparseable_config_falls_back_to_bound_but_stays_initialized(
    vault: Path,
) -> None:
    path = vault / "config" / "operators.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("just a string, not a mapping\n", encoding="utf-8")
    config = load_operators(vault)
    assert config.initialized is True
    assert config.default_class == CLASS_BOUND
    assert config.admins == []


# --- init: registers once, then refuses ----------------------------------


def test_init_registers_the_first_admin(vault: Path) -> None:
    result = init_admin(vault, "river-ledger")
    assert result["ok"] is True
    assert result["class"] == CLASS_ADMIN
    assert load_operators(vault).admins == ["river-ledger"]


def test_init_writes_a_config_with_the_shipped_default(vault: Path) -> None:
    init_admin(vault, "river-ledger")
    data = yaml.safe_load((vault / "config" / "operators.yaml").read_text("utf-8"))
    assert data["default_class"] == CLASS_BOUND
    assert data["projects"] == {"river-ledger": CLASS_ADMIN}


def test_init_refuses_when_an_admin_already_exists(vault: Path) -> None:
    init_admin(vault, "river-ledger")
    result = init_admin(vault, "someone-else")
    assert result["ok"] is False
    assert result["error"] == "already_initialized"
    assert result["admins"] == ["river-ledger"]
    assert load_operators(vault).is_admin("someone-else") is False


def test_init_refuses_an_empty_key(vault: Path) -> None:
    result = init_admin(vault, "   ")
    assert result["ok"] is False
    assert result["error"] == "empty_key"
    assert not (vault / "config" / "operators.yaml").exists()


def test_init_on_a_bound_only_config_still_registers(vault: Path) -> None:
    _write_operators(vault, {"default_class": "bound", "projects": {"harbor": "bound"}})
    result = init_admin(vault, "river-ledger")
    assert result["ok"] is True
    config = load_operators(vault)
    assert config.is_admin("river-ledger") is True
    assert config.class_for("harbor") == CLASS_BOUND


# --- CLI surface: the bare invocation must keep serving -------------------


def test_bare_invocation_is_serve() -> None:
    args = build_parser().parse_args([])
    assert (getattr(args, "command", None) or "serve") == "serve"


def test_bare_invocation_with_vault_is_serve() -> None:
    args = build_parser().parse_args(["--vault", "/somewhere"])
    assert (getattr(args, "command", None) or "serve") == "serve"
    assert args.vault == "/somewhere"


def test_vault_is_accepted_before_or_after_the_subcommand() -> None:
    parser = build_parser()
    before = parser.parse_args(["--vault", "/v", "init", "--admin", "dp"])
    after = parser.parse_args(["init", "--admin", "dp", "--vault", "/v"])
    assert (before.sub_vault or before.vault) == "/v"
    assert (after.sub_vault or after.vault) == "/v"


def test_named_vault_wins_over_the_top_level_one() -> None:
    args = build_parser().parse_args(["--vault", "/a", "operators", "--vault", "/b"])
    assert (args.sub_vault or args.vault) == "/b"


def test_cli_init_then_refuse_round_trip(vault: Path, capsys) -> None:
    assert main(["init", "--admin", "river-ledger", "--vault", str(vault)]) == 0
    assert main(["init", "--admin", "other", "--vault", str(vault)]) == 1
    out = capsys.readouterr().out
    assert "already_initialized" in out


def test_cli_operators_reports_the_registered_admin(vault: Path, capsys) -> None:
    main(["init", "--admin", "river-ledger", "--vault", str(vault)])
    capsys.readouterr()
    assert main(["operators", "--vault", str(vault)]) == 0
    assert "river-ledger" in capsys.readouterr().out
