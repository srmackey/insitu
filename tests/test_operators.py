from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from helpers import write_project, write_stanza

from insitu.cli import build_parser, main
from insitu.operators import (
    CLASS_ADMIN,
    CLASS_BOUND,
    PRE_INIT_WARNING,
    chair_key,
    check_map_write,
    grant,
    init_admin,
    load_operators,
    operator_status,
    revoke,
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


# --- the gate: bound chairs stay in their own map -------------------------
# The 2026-08-23 miss: a session sitting in one checkout mutated another
# project's map, because nothing checked the folder against the key.


def _chair(tmp_path: Path, name: str) -> Path:
    folder = tmp_path / "checkouts" / name
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def test_pre_init_vault_allows_a_cross_map_write_and_warns(
    vault: Path, tmp_path: Path
) -> None:
    refusal, warning = check_map_write(
        vault, project="other", working_folder=str(_chair(tmp_path, "alpha"))
    )
    assert refusal is None
    assert warning == PRE_INIT_WARNING


def test_bound_chair_cannot_write_another_map(vault: Path, tmp_path: Path) -> None:
    init_admin(vault, "river-ledger")
    refusal, warning = check_map_write(
        vault, project="beta", working_folder=str(_chair(tmp_path, "alpha"))
    )
    assert warning is None
    assert refusal is not None
    assert refusal["error"] == "chair_bound"
    assert refusal["chair"] == "alpha"
    assert refusal["project"] == "beta"


def test_bound_chair_can_write_its_own_map(vault: Path, tmp_path: Path) -> None:
    init_admin(vault, "river-ledger")
    refusal, _warning = check_map_write(
        vault, project="alpha", working_folder=str(_chair(tmp_path, "alpha"))
    )
    assert refusal is None


def test_the_basename_match_is_case_folded(vault: Path, tmp_path: Path) -> None:
    init_admin(vault, "river-ledger")
    refusal, _warning = check_map_write(
        vault, project="ALPHA", working_folder=str(_chair(tmp_path, "alpha"))
    )
    assert refusal is None


def test_a_trailing_separator_does_not_break_the_chair_key() -> None:
    assert chair_key("C:/x/River-Ledger/") == "river-ledger"
    assert chair_key("/srv/checkouts/harbor") == "harbor"


def test_admin_chair_may_name_another_map(vault: Path, tmp_path: Path) -> None:
    init_admin(vault, "river-ledger")
    refusal, warning = check_map_write(
        vault, project="beta", working_folder=str(_chair(tmp_path, "river-ledger"))
    )
    assert refusal is None
    assert warning is None


def test_admin_may_sweep_two_maps_and_two_checkouts(
    vault: Path, tmp_path: Path
) -> None:
    """The sweep in the operator-classes spec: several maps, one sitting."""
    init_admin(vault, "river-ledger")
    admin_chair = str(_chair(tmp_path, "river-ledger"))
    for key in ("alpha", "beta"):
        refusal, _warning = check_map_write(
            vault, project=key, working_folder=admin_chair
        )
        assert refusal is None
    for folder in ("alpha", "beta"):
        refusal, _warning = check_map_write(
            vault, project=folder, working_folder=str(_chair(tmp_path, folder))
        )
        assert refusal is None


def test_working_folder_is_required(vault: Path) -> None:
    init_admin(vault, "river-ledger")
    refusal, _warning = check_map_write(vault, project="alpha", working_folder="")
    assert refusal is not None
    assert refusal["error"] == "working_folder_required"


def test_working_folder_is_required_before_init_too(vault: Path) -> None:
    refusal, _warning = check_map_write(vault, project="alpha", working_folder="  ")
    assert refusal is not None
    assert refusal["error"] == "working_folder_required"


# --- grant and revoke -----------------------------------------------------


def test_grant_refuses_a_bound_caller(vault: Path, tmp_path: Path) -> None:
    init_admin(vault, "river-ledger")
    result = grant(
        vault,
        project="alpha",
        operator_class="admin",
        working_folder=str(_chair(tmp_path, "alpha")),
    )
    assert result["ok"] is False
    assert result["error"] == "admin_required"
    assert load_operators(vault).is_admin("alpha") is False


def test_grant_from_an_admin_chair_promotes_a_project(
    vault: Path, tmp_path: Path
) -> None:
    init_admin(vault, "river-ledger")
    result = grant(
        vault,
        project="alpha",
        operator_class="admin",
        working_folder=str(_chair(tmp_path, "river-ledger")),
    )
    assert result["ok"] is True
    assert load_operators(vault).is_admin("alpha") is True


def test_grant_rejects_an_unknown_class(vault: Path, tmp_path: Path) -> None:
    init_admin(vault, "river-ledger")
    result = grant(
        vault,
        project="alpha",
        operator_class="wizard",
        working_folder=str(_chair(tmp_path, "river-ledger")),
    )
    assert result["ok"] is False
    assert result["error"] == "unknown_class"


def test_grant_refuses_before_init(vault: Path, tmp_path: Path) -> None:
    result = grant(
        vault,
        project="alpha",
        operator_class="admin",
        working_folder=str(_chair(tmp_path, "alpha")),
    )
    assert result["ok"] is False
    assert result["error"] == "not_initialized"


def test_revoke_drops_a_project_to_the_default_class(
    vault: Path, tmp_path: Path
) -> None:
    init_admin(vault, "river-ledger")
    admin_chair = str(_chair(tmp_path, "river-ledger"))
    grant(vault, project="alpha", operator_class="admin", working_folder=admin_chair)
    result = revoke(vault, project="alpha", working_folder=admin_chair)
    assert result["ok"] is True
    assert load_operators(vault).is_admin("alpha") is False


def test_revoke_refuses_the_last_admin(vault: Path, tmp_path: Path) -> None:
    init_admin(vault, "river-ledger")
    result = revoke(
        vault,
        project="river-ledger",
        working_folder=str(_chair(tmp_path, "river-ledger")),
    )
    assert result["ok"] is False
    assert result["error"] == "last_admin"
    assert load_operators(vault).admins == ["river-ledger"]


def test_revoke_refuses_a_bound_caller(vault: Path, tmp_path: Path) -> None:
    init_admin(vault, "river-ledger")
    result = revoke(
        vault, project="river-ledger", working_folder=str(_chair(tmp_path, "alpha"))
    )
    assert result["ok"] is False
    assert result["error"] == "admin_required"


def test_revoke_of_an_unlisted_project_says_so(vault: Path, tmp_path: Path) -> None:
    init_admin(vault, "river-ledger")
    result = revoke(
        vault,
        project="never-subscribed",
        working_folder=str(_chair(tmp_path, "river-ledger")),
    )
    assert result["ok"] is False
    assert result["error"] == "not_listed"


# --- the gate through the live MCP tools ----------------------------------


@pytest.fixture
def served(vault: Path, monkeypatch):
    """Point the process vault at a fixture vault with two projects."""
    import insitu.server as server

    write_stanza(vault, "methodology/dock-rule", "Body.")
    write_project(vault, "alpha", core=[], include_global=False)
    write_project(vault, "beta", core=[], include_global=False)
    monkeypatch.setattr(server, "_process_vault", vault.resolve(), raising=False)
    return server


def test_tool_refuses_a_bound_chair_writing_another_map(
    served, vault: Path, tmp_path: Path
) -> None:
    init_admin(vault, "river-ledger")
    result = served.link_stanza(
        working_folder=str(_chair(tmp_path, "alpha")),
        project="beta",
        stanza_id="methodology/dock-rule",
    )
    assert result["ok"] is False
    assert result["error"] == "chair_bound"
    beta = yaml.safe_load((vault / "projects" / "beta" / "map.yaml").read_text("utf-8"))
    assert not (beta or {}).get("core")


def test_tool_allows_a_bound_chair_writing_its_own_map(
    served, vault: Path, tmp_path: Path
) -> None:
    init_admin(vault, "river-ledger")
    result = served.link_stanza(
        working_folder=str(_chair(tmp_path, "alpha")),
        project="alpha",
        stanza_id="methodology/dock-rule",
    )
    assert result["ok"] is True


def test_tool_allows_an_admin_chair_to_write_another_map(
    served, vault: Path, tmp_path: Path
) -> None:
    init_admin(vault, "river-ledger")
    result = served.link_stanza(
        working_folder=str(_chair(tmp_path, "river-ledger")),
        project="beta",
        stanza_id="methodology/dock-rule",
    )
    assert result["ok"] is True


def test_pre_init_tool_call_succeeds_and_carries_the_warning(
    served, tmp_path: Path
) -> None:
    result = served.link_stanza(
        working_folder=str(_chair(tmp_path, "alpha")),
        project="beta",
        stanza_id="methodology/dock-rule",
    )
    assert result["ok"] is True
    assert result["warning"] == PRE_INIT_WARNING


def test_materialize_of_another_project_is_admin_only(
    served, vault: Path, tmp_path: Path
) -> None:
    init_admin(vault, "river-ledger")
    bound = served.materialize(
        working_folder=str(_chair(tmp_path, "alpha")), project="beta"
    )
    assert bound["ok"] is False
    assert bound["error"] == "chair_bound"

    swept = served.materialize(
        working_folder=str(_chair(tmp_path, "beta")), project="beta"
    )
    assert swept["ok"] is True


def test_materialize_without_a_project_stays_folder_local(
    served, vault: Path, tmp_path: Path
) -> None:
    init_admin(vault, "river-ledger")
    result = served.materialize(working_folder=str(_chair(tmp_path, "alpha")))
    assert result["ok"] is True
