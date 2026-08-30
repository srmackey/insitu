from __future__ import annotations

from pathlib import Path

import pytest

from insitu.store import VaultReadError, load_vault

from helpers import write_skill, write_stanza

BAD_DESCRIPTION = (
    "---\n"
    "name: maintain\n"
    "description: Generic pass: changeset, two gates, eval log.\n"
    "---\n\n"
    "# Maintain\n"
)


def test_pack_skill_with_unquoted_colon_names_its_file(vault: Path) -> None:
    skill_md = vault / "library" / "system-development" / "0.9.0" / "skills" / "maintain" / "SKILL.md"
    skill_md.parent.mkdir(parents=True)
    skill_md.write_text(BAD_DESCRIPTION, encoding="utf-8")

    with pytest.raises(VaultReadError) as excinfo:
        load_vault(vault)

    assert excinfo.value.path == skill_md
    assert str(skill_md) in str(excinfo.value)
    assert "line 3" in str(excinfo.value)


def test_vault_skill_with_unquoted_colon_names_its_file(vault: Path) -> None:
    skill_md = vault / "skills" / "maintain" / "SKILL.md"
    skill_md.parent.mkdir(parents=True)
    skill_md.write_text(BAD_DESCRIPTION, encoding="utf-8")

    with pytest.raises(VaultReadError) as excinfo:
        load_vault(vault)

    assert excinfo.value.path == skill_md


def test_malformed_stanza_names_its_file(vault: Path) -> None:
    path = vault / "stanzas" / "methodology" / "broken.md"
    path.parent.mkdir(parents=True)
    path.write_text(BAD_DESCRIPTION, encoding="utf-8")

    with pytest.raises(VaultReadError) as excinfo:
        load_vault(vault)

    assert excinfo.value.path == path


def test_malformed_role_names_its_file(vault: Path) -> None:
    path = vault / "roles" / "repo.yaml"
    path.parent.mkdir(parents=True)
    path.write_text("core: [a]\nname: bad: value\n", encoding="utf-8")

    with pytest.raises(VaultReadError) as excinfo:
        load_vault(vault)

    assert excinfo.value.path == path


def test_malformed_project_map_names_its_file(vault: Path) -> None:
    path = vault / "projects" / "insitu" / "map.yaml"
    path.parent.mkdir(parents=True)
    path.write_text("core: [a]\nname: bad: value\n", encoding="utf-8")

    with pytest.raises(VaultReadError) as excinfo:
        load_vault(vault)

    assert excinfo.value.path == path


def test_well_formed_vault_still_loads(vault: Path) -> None:
    write_stanza(vault, "methodology/ok", "Body.")
    write_skill(vault, "closeout", "Body.")

    loaded = load_vault(vault)

    assert "methodology/ok" in loaded.stanzas
    assert "closeout" in loaded.skills


BAD_YAML = "default: review: strict\n"


def test_malformed_surfaces_names_its_file(vault: Path) -> None:
    path = vault / "config" / "surfaces.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(BAD_YAML, encoding="utf-8")

    from insitu.materialize import _read_surfaces

    with pytest.raises(VaultReadError) as excinfo:
        _read_surfaces(vault)

    assert excinfo.value.path == path
