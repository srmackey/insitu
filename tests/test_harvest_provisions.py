"""Harvest a product public contract from provisions/pack.yaml."""

from __future__ import annotations

from pathlib import Path

import yaml

from helpers import write_project

from insitu.harvest import harvest_provisions
from insitu.store import load_vault


def _vault(tmp_path: Path) -> Path:
    root = tmp_path / "vault"
    (root / "articles").mkdir(parents=True)
    (root / "projects").mkdir()
    (root / "config").mkdir()
    return root


def _product(tmp_path: Path, *, version: str = "0.1.0") -> Path:
    root = tmp_path / "product"
    article = root / "home" / "articles" / "methodology" / "idea-capture.md"
    article.parent.mkdir(parents=True)
    article.write_text("# idea capture\n", encoding="utf-8")
    skill = root / "home" / "skills" / "capture-idea" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("# capture-idea\n", encoding="utf-8")
    manifest = {
        "id": "lantern-kit",
        "name": "Lantern Kit",
        "kind": "theme",
        "version": version,
        "articles": [
            {
                "id": "methodology/idea-capture",
                "path": "home/articles/methodology/idea-capture.md",
            }
        ],
        "skills": [
            {"id": "capture-idea", "path": "home/skills/capture-idea/SKILL.md"}
        ],
    }
    pack = root / "provisions"
    pack.mkdir()
    (pack / "pack.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return root


def test_no_manifest_is_not_an_error(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    product = tmp_path / "empty-product"
    product.mkdir()
    out = harvest_provisions(vault, product)
    assert out["ok"] is True
    assert out["harvested"] is False
    assert out["reason"] == "no_manifest"


def test_harvest_seeds_shelf_without_map_change(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    write_project(vault, "alpha", core=[])
    before = (vault / "projects" / "alpha" / "map.yaml").read_text(encoding="utf-8")
    product = _product(tmp_path)
    out = harvest_provisions(vault, product)
    assert out["ok"] is True
    assert out["harvested"] is True
    assert out["first_harvest"] is True
    assert out["used_by"] == []
    dest = vault / "library" / "lantern-kit" / "0.1.0"
    assert (dest / "articles" / "methodology" / "idea-capture.md").is_file()
    assert (dest / "skills" / "capture-idea" / "SKILL.md").is_file()
    assert (dest / "VERSION").read_text(encoding="utf-8").strip() == "0.1.0"
    shelf = yaml.safe_load((dest / "pack.yaml").read_text(encoding="utf-8"))
    assert shelf["articles"] == ["methodology/idea-capture"]
    assert shelf["skills"] == ["capture-idea"]
    assert "path" not in str(shelf["articles"])
    assert (vault / "projects" / "alpha" / "map.yaml").read_text(encoding="utf-8") == before


def test_same_version_unchanged_skips(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    product = _product(tmp_path)
    first = harvest_provisions(vault, product)
    assert first["harvested"] is True
    again = harvest_provisions(vault, product)
    assert again["ok"] is True
    assert again["harvested"] is False
    assert again["reason"] == "already_present"


def test_same_version_changed_bytes_asks_confirm(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    product = _product(tmp_path)
    harvest_provisions(vault, product)
    article = product / "home" / "articles" / "methodology" / "idea-capture.md"
    article.write_text("# idea capture changed\n", encoding="utf-8")
    plan = harvest_provisions(vault, product)
    assert plan["ok"] is True
    assert plan["written"] is False
    assert plan["expected"]["refresh"] is True
    done = harvest_provisions(
        vault, product, confirm=True, expected=plan["expected"]
    )
    assert done["ok"] is True
    assert done["harvested"] is True
    dest = vault / "library" / "lantern-kit" / "0.1.0"
    assert "changed" in (dest / "articles" / "methodology" / "idea-capture.md").read_text(
        encoding="utf-8"
    )


def test_bare_id_is_refused(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    product = _product(tmp_path)
    (product / "provisions" / "pack.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "lantern-kit",
                "version": "0.1.0",
                "articles": ["methodology/idea-capture"],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    out = harvest_provisions(vault, product)
    assert out["ok"] is False
    assert out["error"] == "extract_list_needs_path"


def test_missing_member_file(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    product = _product(tmp_path)
    (product / "home" / "articles" / "methodology" / "idea-capture.md").unlink()
    out = harvest_provisions(vault, product)
    assert out["ok"] is False
    assert out["error"] == "member_missing"


def test_new_version_drops_unreferenced_sibling(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    product = _product(tmp_path, version="0.1.0")
    harvest_provisions(vault, product)
    manifest = yaml.safe_load(
        (product / "provisions" / "pack.yaml").read_text(encoding="utf-8")
    )
    manifest["version"] = "0.2.0"
    (product / "provisions" / "pack.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    out = harvest_provisions(vault, product)
    assert out["ok"] is True
    assert out["version"] == "0.2.0"
    assert "0.1.0" in out["removed"]
    assert not (vault / "library" / "lantern-kit" / "0.1.0").exists()
    assert (vault / "library" / "lantern-kit" / "0.2.0").is_dir()
    load_vault(vault)
