"""Classes impose and forbid content, and every derived surface says so."""

from __future__ import annotations

from pathlib import Path

import yaml

from helpers import write_article, write_project, write_role

from insitu.affects import composed_id_sets
from insitu.materialize import materialize
from insitu.mutate import link_article
from insitu.operators import grant, init_admin, load_operators, operator_status
from insitu.resolve import resolve_protocol
from insitu.status import project_status
from insitu.store import load_vault
from insitu.validate import validate


def _vault(tmp_path: Path) -> Path:
    root = tmp_path / "vault"
    (root / "articles").mkdir(parents=True)
    (root / "projects").mkdir()
    (root / "config").mkdir()
    return root


def _operators(vault: Path, data: dict) -> None:
    (vault / "config" / "operators.yaml").write_text(
        yaml.safe_dump(data, sort_keys=False), encoding="utf-8"
    )


def _core_ids(resolved: dict) -> list[str]:
    return [item["id"] for item in resolved["core"]]


def _sensitive(vault: Path) -> None:
    """The motivating case: a class that imposes the discreet variant."""
    write_article(vault, "methodology/discreet", "Summaries and pointers only.")
    write_article(vault, "methodology/loud", "Publish the whole digest.")
    _operators(
        vault,
        {
            "default_class": "bound",
            "classes": {
                "sensitive": {
                    "obligations": {"core": ["methodology/discreet"]},
                    "prohibitions": ["methodology/loud"],
                }
            },
            "projects": {"gno": ["bound", "sensitive"], "admin-chair": "admin"},
        },
    )


# --- config shape -----------------------------------------------------------


def test_an_existing_file_still_loads_unchanged(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _operators(vault, {"default_class": "bound", "projects": {"alpha": "admin"}})
    config = load_operators(vault)
    assert config.classes_for("alpha") == ["admin"]
    assert config.is_admin("alpha") is True
    assert config.class_for("alpha") == "admin"
    assert config.obligations_for("alpha") == ([], [])


def test_rights_are_the_union_over_the_held_set(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _operators(
        vault,
        {
            "default_class": "bound",
            "classes": {"auditor": {"rights": "admin"}},
            "projects": {"alpha": ["bound", "auditor"]},
        },
    )
    config = load_operators(vault)
    assert config.classes_for("alpha") == ["bound", "auditor"]
    # One admin rung anywhere in the set carries the whole set.
    assert config.is_admin("alpha") is True


def test_a_file_cannot_redefine_the_two_rights_classes(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _operators(
        vault,
        {
            "default_class": "bound",
            "classes": {"bound": {"rights": "admin"}},
            "projects": {"alpha": "bound"},
        },
    )
    # Otherwise `bound` would mean something different per vault.
    assert load_operators(vault).is_admin("alpha") is False


def test_grant_replaces_the_set_and_round_trips(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    init_admin(vault, "admin-chair")
    _operators(
        vault,
        {
            "default_class": "bound",
            "classes": {"sensitive": {"prohibitions": ["methodology/loud"]}},
            "projects": {"admin-chair": "admin"},
        },
    )
    out = grant(
        vault,
        project="gno",
        operator_class=["bound", "sensitive"],
        working_folder=str(tmp_path / "admin-chair"),
    )
    assert out["ok"] is True
    assert out["classes"] == ["bound", "sensitive"]
    reloaded = load_operators(vault)
    assert reloaded.classes_for("gno") == ["bound", "sensitive"]
    # The class definition survives the rewrite rather than being dropped.
    assert reloaded.classes["sensitive"].prohibitions == ["methodology/loud"]


def test_grant_refuses_a_class_that_is_not_defined(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    init_admin(vault, "admin-chair")
    out = grant(
        vault,
        project="gno",
        operator_class="invented",
        working_folder=str(tmp_path / "admin-chair"),
    )
    assert out["ok"] is False
    assert out["error"] == "unknown_class"


# --- composition ------------------------------------------------------------


def test_an_obligation_composes_without_the_map_listing_it(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _sensitive(vault)
    write_article(vault, "methodology/own", "This chair's own rule.")
    write_project(vault, "gno", core=["methodology/own"], include_global=False)
    resolved = resolve_protocol(vault, "gno")
    assert resolved["ok"] is True
    assert _core_ids(resolved) == ["methodology/discreet", "methodology/own"]


def test_an_obligation_composes_ahead_of_what_the_map_chose(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _sensitive(vault)
    write_article(vault, "methodology/own", "This chair's own rule.")
    write_role(vault, "clerk", core=["methodology/own"])
    write_project(vault, "gno", core=[], roles=["clerk"], include_global=False)
    # Imposed before chosen: the role's member follows the obligation.
    assert _core_ids(resolve_protocol(vault, "gno")) == [
        "methodology/discreet",
        "methodology/own",
    ]


def test_an_obligation_survives_include_global_false(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _sensitive(vault)
    write_project(vault, "_global", core=[])
    write_project(vault, "gno", core=[], include_global=False)
    # Opting out of _global is a choice. An obligation is not opt-out-able.
    assert _core_ids(resolve_protocol(vault, "gno")) == ["methodology/discreet"]


def test_a_chair_without_the_class_composes_nothing_extra(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _sensitive(vault)
    write_article(vault, "methodology/own", "This chair's own rule.")
    write_project(vault, "alpha", core=["methodology/own"], include_global=False)
    resolved = resolve_protocol(vault, "alpha")
    assert _core_ids(resolved) == ["methodology/own"]
    assert "imposed" not in resolved


def test_a_prohibited_article_is_excluded_and_named_not_fatal(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _sensitive(vault)
    # The map lists it; the class forbids it. The chair still gets a protocol.
    write_project(vault, "gno", core=["methodology/loud"], include_global=False)
    resolved = resolve_protocol(vault, "gno")
    assert resolved["ok"] is True
    assert "methodology/loud" not in _core_ids(resolved)
    assert resolved["excluded"] == [
        {"id": "methodology/loud", "list": "core", "prohibited_by": "sensitive"}
    ]


def test_resolve_reports_what_was_imposed_and_by_which_class(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _sensitive(vault)
    write_project(vault, "gno", core=[], include_global=False)
    resolved = resolve_protocol(vault, "gno")
    assert resolved["classes"] == ["bound", "sensitive"]
    assert resolved["imposed"] == [
        {"id": "methodology/discreet", "list": "core", "imposed_by": "sensitive"}
    ]


# --- derived surfaces -------------------------------------------------------


def test_composed_id_sets_sees_obligations_and_drops_prohibitions(
    tmp_path: Path,
) -> None:
    vault = _vault(tmp_path)
    _sensitive(vault)
    write_project(vault, "gno", core=["methodology/loud"], include_global=False)
    core, _on_demand = composed_id_sets(load_vault(vault), "gno")
    assert "methodology/discreet" in core
    assert "methodology/loud" not in core


def test_validate_does_not_call_an_imposed_article_unreferenced(
    tmp_path: Path,
) -> None:
    vault = _vault(tmp_path)
    _sensitive(vault)
    write_project(vault, "gno", core=[], include_global=False)
    findings = validate(vault)["findings"]
    unreferenced = [row["id"] for row in findings["unreferenced"]]
    assert "methodology/discreet" not in unreferenced


def test_validate_flags_an_obligation_naming_nothing(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _operators(
        vault,
        {
            "default_class": "bound",
            "classes": {"sensitive": {"obligations": {"core": ["methodology/ghost"]}}},
            "projects": {"gno": "sensitive"},
        },
    )
    write_project(vault, "gno", core=[], include_global=False)
    kinds = [issue["kind"] for issue in validate(vault)["issues"]]
    # Sharper than a stale conflict: this one fails resolution for the class.
    assert "missing_obligation" in kinds


def test_validate_flags_a_class_set_that_contradicts_itself(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    write_article(vault, "methodology/x", "A rule.")
    _operators(
        vault,
        {
            "default_class": "bound",
            "classes": {
                "gives": {"obligations": {"core": ["methodology/x"]}},
                "takes": {"prohibitions": ["methodology/x"]},
            },
            "projects": {"gno": ["gives", "takes"]},
        },
    )
    write_project(vault, "gno", core=[], include_global=False)
    issues = [i for i in validate(vault)["issues"] if i["kind"] == "obligation_prohibited"]
    assert issues and issues[0]["prohibited_by"] == "takes"
    # The prohibition wins in composition; the config is still contradictory.
    assert _core_ids(resolve_protocol(vault, "gno")) == []


def test_project_status_card_names_the_class_and_what_it_did(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _sensitive(vault)
    folder = tmp_path / "gno"
    folder.mkdir()
    write_project(vault, "gno", core=["methodology/loud"], include_global=False)
    card = project_status(vault, working_folder=str(folder))["card"]
    assert "Class: bound, sensitive" in card
    assert "Imposed by sensitive: methodology/discreet" in card
    assert "Forbidden by sensitive: methodology/loud" in card


def test_the_generated_header_carries_the_classes(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _sensitive(vault)
    (vault / "config" / "surfaces.yaml").write_text("surfaces: []\n", encoding="utf-8")
    folder = tmp_path / "gno"
    folder.mkdir()
    write_project(vault, "gno", core=[], include_global=False)
    materialize(vault, working_folder=str(folder), project="gno")
    text = (folder / "PROTOCOL.md").read_text(encoding="utf-8")
    # Two chairs on the same map.yaml can compose differently; the header has
    # to carry what accounts for that.
    assert "classes: bound, sensitive" in text
    assert "methodology/discreet" in text


def test_operator_status_reports_sets_and_definitions(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _sensitive(vault)
    out = operator_status(vault)
    assert out["projects"]["gno"] == {
        "classes": ["bound", "sensitive"],
        "rights": "bound",
    }
    assert out["classes"]["sensitive"]["prohibitions"] == ["methodology/loud"]
    assert out["admins"] == ["admin-chair"]


# --- write-time refusal -----------------------------------------------------


def test_linking_a_prohibited_article_is_refused(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _sensitive(vault)
    write_project(vault, "gno", core=[], include_global=False)
    before = (vault / "projects" / "gno" / "map.yaml").read_text(encoding="utf-8")
    refused = link_article(vault, "gno", "methodology/loud")
    assert refused["ok"] is False
    assert refused["error"] == "prohibited_by_class"
    assert refused["prohibited_by"] == "sensitive"
    assert (vault / "projects" / "gno" / "map.yaml").read_text(encoding="utf-8") == before


def test_linking_an_unprohibited_article_still_works(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _sensitive(vault)
    write_article(vault, "methodology/fine", "Nothing forbids this.")
    write_project(vault, "gno", core=[], include_global=False)
    assert link_article(vault, "gno", "methodology/fine")["ok"] is True
