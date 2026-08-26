from __future__ import annotations

from pathlib import Path

import frontmatter
import yaml

from helpers import seed_pack_repo, write_pack_repos, write_project, write_skill

from insitu.catalog import get_skill
from insitu.library import (
    fetch_pack,
    install_capability,
    install_skill,
    uninstall_skill,
)
from insitu.materialize import materialize
from insitu.resolve import resolve_protocol


def _vault(tmp_path: Path) -> Path:
    root = tmp_path / "vault"
    (root / "stanzas").mkdir(parents=True)
    (root / "projects").mkdir()
    (root / "config").mkdir()
    return root


def _with_repo(tmp_path: Path) -> Path:
    vault = _vault(tmp_path)
    repo = tmp_path / "repo"
    seed_pack_repo(repo, "harbor-kit", "0.1.0")
    write_pack_repos(vault, [{"name": "fixture", "path": str(repo)}])
    write_project(vault, "alpha", core=[], include_global=False)
    return vault


def test_install_skill_maps_pack_skill_without_native_copy(tmp_path: Path) -> None:
    vault = _with_repo(tmp_path)
    result = install_skill(vault, "alpha", "close-hatch", version="0.1.0")
    assert result["ok"] is True
    assert result["skill"] == "close-hatch"
    assert result["pack"] == "harbor-kit"
    data = yaml.safe_load(
        (vault / "projects" / "alpha" / "map.yaml").read_text(encoding="utf-8")
    )
    assert data["imports"] == [
        {
            "pack": "harbor-kit",
            "version": "0.1.0",
            "skills": ["close-hatch"],
        }
    ]
    assert not (vault / "skills" / "close-hatch").exists()
    resolved = resolve_protocol(vault, "alpha")
    assert resolved["ok"] is True
    assert [row["id"] for row in resolved["skills"]] == ["close-hatch"]
    found = get_skill(vault, "close-hatch", project="alpha")
    assert found["ok"] is True
    assert "CLOSE-0.1.0" in found["content"]
    assert found["origin"] == "library/harbor-kit@0.1.0"


def test_install_capability_does_not_attach_pack_skills(tmp_path: Path) -> None:
    vault = _with_repo(tmp_path)
    assert install_capability(vault, "alpha", "harbor-kit", "0.1.0")["ok"] is True
    resolved = resolve_protocol(vault, "alpha")
    assert resolved["ok"] is True
    assert resolved["skills"] == []
    assert [row["id"] for row in resolved["core"]] == ["methodology/dock-rule"]


def test_install_skill_after_capability_is_a_second_record(tmp_path: Path) -> None:
    vault = _with_repo(tmp_path)
    assert install_capability(vault, "alpha", "harbor-kit", "0.1.0")["ok"] is True
    assert install_skill(vault, "alpha", "close-hatch", version="0.1.0")["ok"] is True
    data = yaml.safe_load(
        (vault / "projects" / "alpha" / "map.yaml").read_text(encoding="utf-8")
    )
    assert data["imports"] == [
        {"pack": "harbor-kit", "version": "0.1.0"},
        {
            "pack": "harbor-kit",
            "version": "0.1.0",
            "skills": ["close-hatch"],
        },
    ]
    resolved = resolve_protocol(vault, "alpha")
    assert [row["id"] for row in resolved["skills"]] == ["close-hatch"]


def test_materialize_writes_pack_skill_from_shelf(tmp_path: Path) -> None:
    vault = _with_repo(tmp_path)
    assert install_skill(vault, "alpha", "close-hatch", version="0.1.0")["ok"] is True
    (vault / "config" / "surfaces.yaml").write_text(
        yaml.safe_dump({"surfaces": ["grok", "claude"]}),
        encoding="utf-8",
    )
    work = tmp_path / "alpha"
    work.mkdir()
    result = materialize(vault, work, project="alpha")
    assert result["ok"] is True
    grok = work / ".grok" / "skills" / "close-hatch" / "SKILL.md"
    claude = work / ".claude" / "skills" / "close-hatch" / "SKILL.md"
    assert grok.is_file()
    assert claude.is_file()
    text = grok.read_text(encoding="utf-8")
    post = frontmatter.loads(text)
    assert post.metadata["name"] == "close-hatch"
    body = post.content.lstrip()
    assert body.startswith("<!--")
    assert "insitu-generated: true" in body
    assert "skill: close-hatch" in body
    assert "CLOSE-0.1.0" in body
    assert (work / ".grok" / "skills" / "close-hatch" / "scripts" / "seal.py").is_file()
    protocol = (work / "PROTOCOL.md").read_text(encoding="utf-8")
    assert "Seal the hatch" not in protocol


def test_uninstall_skill_drops_map_member(tmp_path: Path) -> None:
    vault = _with_repo(tmp_path)
    assert install_skill(vault, "alpha", "close-hatch", version="0.1.0")["ok"] is True
    result = uninstall_skill(
        vault, "alpha", "close-hatch", pack="harbor-kit", version="0.1.0"
    )
    assert result["ok"] is True
    data = yaml.safe_load(
        (vault / "projects" / "alpha" / "map.yaml").read_text(encoding="utf-8")
    )
    assert not data.get("imports")
    resolved = resolve_protocol(vault, "alpha")
    assert resolved["skills"] == []


def test_missing_pack_skill_is_missing_skill(tmp_path: Path) -> None:
    vault = _with_repo(tmp_path)
    result = install_skill(vault, "alpha", "no-such-skill", version="0.1.0", pack="harbor-kit")
    assert result["ok"] is False
    assert result["error"] == "missing_skill"
    assert result["id"] == "no-such-skill"


def test_native_and_pack_same_skill_id_is_hard_error(tmp_path: Path) -> None:
    vault = _with_repo(tmp_path)
    assert fetch_pack(vault, "harbor-kit", "0.1.0", repo="fixture")["ok"] is True
    write_skill(vault, "close-hatch", "Native hatch.\n")
    write_project(
        vault,
        "alpha",
        core=[],
        include_global=False,
        skills=["close-hatch"],
        imports=[
            {
                "pack": "harbor-kit",
                "version": "0.1.0",
                "skills": ["close-hatch"],
            }
        ],
    )
    resolved = resolve_protocol(vault, "alpha")
    assert resolved["ok"] is False
    assert resolved["error"] == "duplicate_import_skill"
    assert resolved["id"] == "close-hatch"
