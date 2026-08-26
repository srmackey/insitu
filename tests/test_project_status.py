from __future__ import annotations

from pathlib import Path

import yaml

from helpers import (
    seed_pack_repo,
    write_pack_repos,
    write_project,
    write_role,
    write_stanza,
)

from insitu.library import install_capability
from insitu.materialize import materialize
from insitu.status import project_status


def _seed(vault: Path) -> None:
    write_stanza(vault, "interaction/digest-then-drill", "GLOBAL-CORE-BODY")
    write_stanza(vault, "interaction/how-i-work-with-ai", "PROJECT-CORE-BODY")
    write_stanza(vault, "methodology/small-diffs", "ON-DEMAND-BODY")
    write_stanza(vault, "methodology/ledger-clerk", "ROLE-CORE-BODY")
    write_project(vault, "_global", core=["interaction/digest-then-drill"])
    write_role(vault, "clerk", core=["methodology/ledger-clerk"])
    write_project(
        vault,
        "river-ledger",
        core=["interaction/how-i-work-with-ai"],
        on_demand=["methodology/small-diffs"],
        roles=["clerk"],
        repo="river-ledger",
        name="River Ledger",
        notes="Fictional ledger notes.\n",
    )


def _dump(result: dict) -> str:
    return str(result)


def test_missing_working_folder_is_structured_error(vault: Path, tmp_path: Path) -> None:
    _seed(vault)
    missing = tmp_path / "no-such-folder"
    result = project_status(vault, missing)
    assert result["ok"] is False
    assert result["error"] == "working_folder_missing"


def test_working_folder_file_is_not_a_directory(vault: Path, tmp_path: Path) -> None:
    _seed(vault)
    path = tmp_path / "a-file"
    path.write_text("nope\n", encoding="utf-8")
    result = project_status(vault, path)
    assert result["ok"] is False
    assert result["error"] == "working_folder_not_directory"


def test_project_missing_is_structured_miss(vault: Path, tmp_path: Path) -> None:
    _seed(vault)
    work = tmp_path / "unknown-node"
    work.mkdir()
    result = project_status(vault, work)
    assert result["ok"] is False
    assert result["error"] == "project_missing"
    assert result["project"] == "unknown-node"


def test_happy_path_map_sources_size_card_no_bodies(
    vault: Path, tmp_path: Path
) -> None:
    _seed(vault)
    work = tmp_path / "river-ledger"
    work.mkdir()
    result = project_status(vault, work)
    assert result["ok"] is True
    assert result["project"] == "river-ledger"
    assert result["name"] == "River Ledger"
    assert result["repo"] == "river-ledger"
    assert result["roles"] == ["clerk"]
    assert result["include_global"] is True
    assert result["core"] == ["interaction/how-i-work-with-ai"]
    assert result["on_demand"] == ["methodology/small-diffs"]
    assert result["notes"] is True
    assert result["size"]["stanza_count"] == 3
    assert "card" in result
    dumped = _dump(result)
    assert "GLOBAL-CORE-BODY" not in dumped
    assert "PROJECT-CORE-BODY" not in dumped
    assert "ROLE-CORE-BODY" not in dumped
    assert "ON-DEMAND-BODY" not in dumped
    assert "content" not in result
    kinds = [row["kind"] for row in result["sources"]]
    assert kinds == ["_global", "role", "project"]
    by_kind = {row["kind"]: row for row in result["sources"]}
    assert by_kind["_global"]["stanzas"] == ["interaction/digest-then-drill"]
    assert by_kind["role"]["id"] == "clerk"
    assert by_kind["role"]["stanzas"] == ["methodology/ledger-clerk"]
    assert by_kind["project"]["stanzas"] == ["interaction/how-i-work-with-ai"]
    assert "interaction/digest-then-drill" in result["card"]
    assert result["disk"]["protocol"]["present"] is False
    assert result["disk"]["current"] is False


def test_first_wins_attributes_duplicate_to_earlier_source(
    vault: Path, tmp_path: Path
) -> None:
    write_stanza(vault, "interaction/digest-then-drill", "GLOBAL-CORE-BODY")
    write_project(vault, "_global", core=["interaction/digest-then-drill"])
    write_project(
        vault,
        "river-ledger",
        core=["interaction/digest-then-drill"],
        include_global=True,
    )
    work = tmp_path / "river-ledger"
    work.mkdir()
    result = project_status(vault, work)
    assert result["ok"] is True
    assert result["core"] == ["interaction/digest-then-drill"]
    kinds = [row["kind"] for row in result["sources"]]
    assert kinds == ["_global"]
    assert result["sources"][0]["stanzas"] == ["interaction/digest-then-drill"]
    assert result["size"]["stanza_count"] == 1


def test_disk_current_when_header_matches_live_compose(
    vault: Path, tmp_path: Path
) -> None:
    _seed(vault)
    (vault / "config" / "surfaces.yaml").write_text(
        yaml.safe_dump({"surfaces": ["grok", "claude"]}),
        encoding="utf-8",
    )
    work = tmp_path / "river-ledger"
    work.mkdir()
    assert materialize(vault, work)["ok"] is True
    result = project_status(vault, work)
    assert result["ok"] is True
    assert result["disk"]["current"] is True
    assert result["disk"]["protocol"]["present"] is True
    assert result["disk"]["protocol"]["matches"] is True
    assert result["disk"]["protocol"]["project"] == "river-ledger"
    assert result["disk"]["protocol"]["timestamp"]
    adapters = {row["surface"]: row for row in result["disk"]["adapters"]}
    assert adapters["grok"]["present"] is True
    assert adapters["claude"]["present"] is True
    assert "Pack looks current" in result["card"]


def test_disk_stale_when_header_stanza_list_differs(
    vault: Path, tmp_path: Path
) -> None:
    _seed(vault)
    work = tmp_path / "river-ledger"
    work.mkdir()
    assert materialize(vault, work)["ok"] is True
    write_stanza(vault, "interaction/extra", "EXTRA-BODY")
    write_project(
        vault,
        "river-ledger",
        core=["interaction/how-i-work-with-ai", "interaction/extra"],
        on_demand=["methodology/small-diffs"],
        roles=["clerk"],
        repo="river-ledger",
        name="River Ledger",
        notes="Fictional ledger notes.\n",
    )
    result = project_status(vault, work)
    assert result["ok"] is True
    assert result["disk"]["protocol"]["present"] is True
    assert result["disk"]["protocol"]["matches"] is False
    assert result["disk"]["current"] is False
    assert "EXTRA-BODY" not in _dump(result)


def test_missing_adapter_does_not_clear_current_if_protocol_matches(
    vault: Path, tmp_path: Path
) -> None:
    _seed(vault)
    (vault / "config" / "surfaces.yaml").write_text(
        yaml.safe_dump({"surfaces": ["grok", "claude"]}),
        encoding="utf-8",
    )
    work = tmp_path / "river-ledger"
    work.mkdir()
    assert materialize(vault, work)["ok"] is True
    (work / ".claude" / "rules" / "insitu-protocol.md").unlink()
    result = project_status(vault, work)
    assert result["ok"] is True
    assert result["disk"]["current"] is True
    adapters = {row["surface"]: row for row in result["disk"]["adapters"]}
    assert adapters["grok"]["present"] is True
    assert adapters["claude"]["present"] is False
    assert "missing" in result["card"].lower()


def test_project_override_uses_named_map(vault: Path, tmp_path: Path) -> None:
    _seed(vault)
    work = tmp_path / "some-checkout"
    work.mkdir()
    result = project_status(vault, work, project="river-ledger")
    assert result["ok"] is True
    assert result["project"] == "river-ledger"


def test_import_source_group(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    (vault / "stanzas").mkdir(parents=True)
    (vault / "projects").mkdir()
    (vault / "config").mkdir()
    repo = tmp_path / "repo"
    seed_pack_repo(repo, "harbor-kit", "0.1.0")
    write_pack_repos(vault, [{"name": "fixture", "path": str(repo)}])
    write_project(vault, "alpha", core=[], include_global=False)
    assert install_capability(vault, "alpha", "harbor-kit", "0.1.0")["ok"] is True
    work = tmp_path / "alpha"
    work.mkdir()
    result = project_status(vault, work)
    assert result["ok"] is True
    assert result["sources"][0]["kind"] == "import"
    assert result["sources"][0]["pack"] == "harbor-kit"
    assert result["sources"][0]["version"] == "0.1.0"
    assert "methodology/dock-rule" in result["sources"][0]["stanzas"]
    assert "DOCK" not in _dump(result) and "content" not in result
