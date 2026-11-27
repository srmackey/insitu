"""Address keys: nexus.md derives the key, and a slash stays one folder."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from insitu.address import derive_key, resolve, load_tree
from insitu.identity import project_dirname, project_key_from_dirname
from insitu.materialize import materialize
from insitu.operators import check_map_write, load_operators
from insitu.store import load_vault
from insitu.validate import validate


def _nexus(folder: Path, name: str, rows: list[str], parent: str | None = None) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    lines = [f"# nexus: {name}", ""]
    if parent:
        lines.extend([f"parent: {parent}", ""])
    lines.extend(
        [
            "| Node | Path | Kind | Status | Sensitive | Services | Triggers |",
            "|---|---|---|---|---|---|---|",
            *rows,
        ]
    )
    (folder / "nexus.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _coast(tmp_path: Path) -> Path:
    root = tmp_path / "coast"
    _nexus(
        root,
        "coast",
        [
            "| harbor | harbor/ | nexus | active | no | status | the inner harbor |",
            "| pier | pier/ | nexus | active | yes | status | the far pier |",
            "| quay | quay/ | nexus | active | no | status | the quay |",
            "| ledger | ledger/ | node | active | no | status | the tide ledger |",
        ],
    )
    _nexus(
        root / "harbor",
        "harbor",
        ["| dock | dock/ | node | active | no | status | the harbor dock |"],
        parent="coast",
    )
    _nexus(
        root / "pier",
        "pier",
        [
            "| dock | dock/ | node | active | no | status | the pier dock |",
            "| skiff | skiff/ | node | active | no | status | the skiff |",
        ],
        parent="coast",
    )
    _nexus(
        root / "quay",
        "quay",
        ["| buoy | buoy/ | node | active | no | status | the buoy |"],
        parent="coast",
    )
    return root


def _map(vault: Path, key: str) -> None:
    folder = vault / "projects" / project_dirname(key)
    folder.mkdir(parents=True)
    (folder / "map.yaml").write_text(
        yaml.safe_dump({"include_global": False, "core": []}, sort_keys=False),
        encoding="utf-8",
    )


def test_dirname_encodes_one_slash() -> None:
    assert project_dirname("pier/skiff") == "pier~skiff"
    assert project_key_from_dirname("pier~skiff") == "pier/skiff"
    assert project_dirname("coast") == "coast"


def test_derive_key_follows_nexus_md(tmp_path: Path) -> None:
    root = _coast(tmp_path)
    assert derive_key(root, root / "pier" / "skiff") == "pier/skiff"
    assert derive_key(root, root / "pier") == "pier"
    assert derive_key(root, root / "ledger") == "coast/ledger"
    assert derive_key(root, root / "pier" / "loose") is None

    tree = load_tree(root)
    assert tree is not None
    assert resolve(tree, "coast/pier") is None
    skiff = resolve(tree, "pier/skiff")
    bare = resolve(tree, "skiff")
    assert skiff is not None and skiff.address == "pier/skiff"
    assert bare is not None and bare.address == "pier/skiff"
    assert resolve(tree, "dock") is None


def test_materialize_reads_the_encoded_project_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _coast(tmp_path)
    monkeypatch.setenv("INSITU_ROOT", str(root))
    vault = tmp_path / "shelf"
    (vault / "articles").mkdir(parents=True)
    (vault / "projects").mkdir()
    _map(vault, "pier/skiff")
    work = root / "pier" / "skiff"
    work.mkdir()

    result = materialize(vault, work)
    assert result["ok"] is True
    assert (work / "AGENTS.md").is_file()
    assert not (work / "PROTOCOL.md").exists()
    assert (vault / "projects" / "pier~skiff" / "map.yaml").is_file()
    assert not (vault / "projects" / "pier" / "skiff").exists()


def test_project_map_aliases_a_unique_bare_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _coast(tmp_path)
    monkeypatch.setenv("INSITU_ROOT", str(root))
    vault = tmp_path / "shelf"
    (vault / "articles").mkdir(parents=True)
    (vault / "projects").mkdir()
    _map(vault, "pier/skiff")
    _map(vault, "pier/dock")
    _map(vault, "harbor/dock")

    projects = load_vault(vault).projects
    assert projects["pier/skiff"].key == "pier/skiff"
    assert "skiff" in projects
    assert projects["skiff"].key == "pier/skiff"
    assert "dock" not in projects
    assert set(projects) == {"pier/skiff", "pier/dock", "harbor/dock"}


def test_admin_scope_follows_the_nexus(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _coast(tmp_path)
    monkeypatch.setenv("INSITU_ROOT", str(root))
    vault = tmp_path / "shelf"
    (vault / "config").mkdir(parents=True)
    (vault / "config" / "operators.yaml").write_text(
        yaml.safe_dump(
            {
                "default_class": "bound",
                "projects": {"coast": "admin", "pier": "admin", "quay": "admin"},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    covered, _ = check_map_write(vault, project="pier/skiff", working_folder=root / "pier")
    assert covered is None
    sibling, _ = check_map_write(vault, project="pier/skiff", working_folder=root / "quay")
    assert sibling is not None
    assert sibling["error"] == "admin_scope"
    top, _ = check_map_write(vault, project="quay/buoy", working_folder=root)
    assert top is None

    classes = load_operators(vault)
    assert classes.classes_for("pier/skiff") == ["bound"]
    assert classes.classes_for("harbor/dock") == ["bound"]
    assert classes.is_admin("pier") is True
    assert classes.is_admin("pier/skiff") is False


def test_a_chair_takes_only_its_own_row(tmp_path: Path) -> None:
    root = _coast(tmp_path)
    _nexus(
        root / "harbor",
        "harbor",
        [
            "| dock | dock/ | node | active | no | status | the harbor dock |",
            "| crane | crane/ | node | active | yes | status | the crane |",
        ],
        parent="coast",
    )
    tree = load_tree(root)
    assert tree is not None

    pier = resolve(tree, "pier")
    skiff = resolve(tree, "pier/skiff")
    assert pier is not None and pier.sensitive is True
    assert skiff is not None and skiff.sensitive is False

    harbor = resolve(tree, "harbor")
    crane = resolve(tree, "harbor/crane")
    assert harbor is not None and harbor.sensitive is False
    assert crane is not None and crane.sensitive is True


def test_a_sensitive_nexus_imposes_no_class(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _coast(tmp_path)
    monkeypatch.setenv("INSITU_ROOT", str(root))
    vault = tmp_path / "shelf"
    (vault / "config").mkdir(parents=True)
    (vault / "config" / "operators.yaml").write_text(
        yaml.safe_dump({"default_class": "bound", "projects": {"coast": "admin"}}),
        encoding="utf-8",
    )

    classes = load_operators(vault)
    assert classes.classes_for("pier/skiff") == ["bound"]
    assert classes.classes_for("pier") == ["bound"]


def _empty_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "shelf"
    (vault / "articles").mkdir(parents=True)
    (vault / "projects").mkdir()
    return vault


def test_validate_flags_a_row_that_does_not_say_yes_or_no(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _coast(tmp_path)
    _nexus(
        root / "quay",
        "quay",
        [
            "| buoy | buoy/ | node | active | no | status | the buoy |",
            "| net | net/ | node | active |  | status | the net |",
            "| oar | oar/ | node | active | maybe | status | the oar |",
        ],
        parent="coast",
    )
    monkeypatch.setenv("INSITU_ROOT", str(root))

    result = validate(_empty_vault(tmp_path))
    flagged = [i for i in result["issues"] if i["kind"] == "registry_sensitive_unset"]
    assert flagged == [
        {"kind": "registry_sensitive_unset", "nexus": "quay", "node": "net", "cell": ""},
        {"kind": "registry_sensitive_unset", "nexus": "quay", "node": "oar", "cell": "maybe"},
    ]
    assert result["ok"] is False


def test_validate_flags_every_row_when_the_column_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "cove"
    root.mkdir()
    (root / "nexus.md").write_text(
        "# nexus: cove\n\n| Node | Path | Kind |\n|---|---|---|\n| reef | reef/ | node |\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("INSITU_ROOT", str(root))

    result = validate(_empty_vault(tmp_path))
    assert [i["node"] for i in result["issues"] if i["kind"] == "registry_sensitive_unset"] == [
        "reef"
    ]


def test_validate_is_quiet_on_a_complete_registry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("INSITU_ROOT", str(_coast(tmp_path)))
    result = validate(_empty_vault(tmp_path))
    assert not [i for i in result["issues"] if i["kind"] == "registry_sensitive_unset"]
