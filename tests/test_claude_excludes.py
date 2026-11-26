"""Ancestor Claude rule excludes. Fictional trees only."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from helpers import PLATFORM_DEFS, write_article, write_role
from insitu.claude_excludes import merge_excludes, rule_globs
from insitu.identity import project_dirname
from insitu.materialize import materialize


def _spellings(path: Path) -> list[Path]:
    text = str(path)
    other = Path(text.replace("Ada Lovelace", "ADALOV~1"))
    if other == path:
        return [path]
    return [path, other]


def _tree(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "Ada Lovelace" / "coast"
    dock = root / "harbor" / "dock"
    (root / ".claude" / "rules").mkdir(parents=True)
    (root / "harbor" / ".claude" / "rules").mkdir(parents=True)
    (dock / ".claude" / "rules").mkdir(parents=True)
    return root, dock


def test_globs_name_ancestors_in_each_spelling_and_not_the_chair(tmp_path: Path) -> None:
    root, dock = _tree(tmp_path)
    globs = rule_globs(dock, root, _spellings)
    assert globs == [
        "**/Ada Lovelace/coast/.claude/rules/**",
        "**/ADALOV~1/coast/.claude/rules/**",
        "**/Ada Lovelace/coast/harbor/.claude/rules/**",
        "**/ADALOV~1/coast/harbor/.claude/rules/**",
    ]


def test_second_spelling_shortens_the_profile_and_leaves_the_rest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "Ada Lovelace"
    root = home / "coast"
    dock = root / "harbor" / "dock"
    (root / ".claude" / "rules").mkdir(parents=True)
    (dock / ".claude" / "rules").mkdir(parents=True)

    def win_path(path: Path, kind: str) -> Path | None:
        if kind == "short" and path == home.resolve():
            return tmp_path / "ADALOV~1"
        return None

    monkeypatch.setattr("insitu.claude_excludes._win_path", win_path)
    monkeypatch.setattr("insitu.claude_excludes.Path.home", staticmethod(lambda: home))
    globs = rule_globs(dock, root)
    assert globs == [
        "**/Ada Lovelace/coast/.claude/rules/**",
        "**/ADALOV~1/coast/.claude/rules/**",
    ]
    assert not any("harbor" in item for item in globs)


def test_a_nested_name_does_not_collide_with_the_install_root(tmp_path: Path) -> None:
    root = tmp_path / "people" / "DomainPrime"
    nested = root / "dev" / "domainprime"
    (root / ".claude" / "rules").mkdir(parents=True)
    (nested / ".claude" / "rules").mkdir(parents=True)
    globs = rule_globs(nested, root, lambda path: [path])
    assert "**/DomainPrime/.claude/rules/**" not in globs
    assert globs == ["**/people/DomainPrime/.claude/rules/**"]


def test_merge_keeps_other_keys_and_skips_a_matching_list(tmp_path: Path) -> None:
    work = tmp_path / "dock"
    settings = work / ".claude" / "settings.local.json"
    settings.parent.mkdir(parents=True)
    settings.write_text(
        json.dumps({"permissions": {"allow": ["Bash(echo hi)"]}}, indent=2) + "\n",
        encoding="utf-8",
    )
    globs = ["**/people/coast/.claude/rules/**"]
    path, error = merge_excludes(work, globs)
    assert error is None
    assert path == settings
    loaded = json.loads(settings.read_text(encoding="utf-8"))
    assert loaded["permissions"]["allow"] == ["Bash(echo hi)"]
    assert loaded["claudeMdExcludes"] == globs
    before = settings.read_bytes()
    again, again_error = merge_excludes(work, globs)
    assert again_error is None
    assert again == settings
    assert settings.read_bytes() == before


def test_merge_refuses_a_file_that_is_not_an_object(tmp_path: Path) -> None:
    work = tmp_path / "dock"
    settings = work / ".claude" / "settings.local.json"
    settings.parent.mkdir(parents=True)
    settings.write_text("[]\n", encoding="utf-8")
    path, error = merge_excludes(work, ["**/people/coast/.claude/rules/**"])
    assert path is None
    assert error == "claude_excludes_invalid"
    assert settings.read_text(encoding="utf-8") == "[]\n"


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


def _install(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "coast"
    _nexus(
        root,
        "coast",
        ["| harbor | harbor/ | nexus | active | no |  | the inner harbor |"],
    )
    _nexus(
        root / "harbor",
        "harbor",
        ["| dock | dock/ | node | active | no |  | the harbor dock |"],
        parent="coast",
    )
    (root / ".claude" / "rules").mkdir(parents=True)
    (root / "harbor" / ".claude" / "rules").mkdir(parents=True)
    (root / "platforms.yaml").write_text(
        yaml.safe_dump(
            {"enabled": ["claude"], "platforms": {"claude": PLATFORM_DEFS["claude"]}},
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("INSITU_ROOT", str(root))
    return root


def _map(vault: Path, key: str, *, roles: list[str] | None) -> None:
    folder = vault / "projects" / project_dirname(key)
    folder.mkdir(parents=True)
    data: dict = {"include_global": False, "core": ["interaction/dock-rule"]}
    if roles is not None:
        data["roles"] = roles
    (folder / "map.yaml").write_text(
        yaml.safe_dump(data, sort_keys=False),
        encoding="utf-8",
    )


def test_materialize_merges_excludes_for_a_chair_with_a_role(
    vault: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _install(tmp_path, monkeypatch)
    write_article(vault, "interaction/dock-rule", "DOCK-RULE")
    write_role(vault, "keeper")
    _map(vault, "harbor/dock", roles=["keeper"])
    work = root / "harbor" / "dock"
    work.mkdir(parents=True)
    settings = work / ".claude" / "settings.local.json"
    settings.parent.mkdir(parents=True)
    settings.write_text(
        json.dumps({"permissions": {"allow": ["Bash(echo hi)"]}}) + "\n",
        encoding="utf-8",
    )

    result = materialize(vault, work)
    assert result["ok"] is True
    assert result["claude_excludes"] == str(settings)
    loaded = json.loads(settings.read_text(encoding="utf-8"))
    assert loaded["permissions"]["allow"] == ["Bash(echo hi)"]
    assert loaded["claudeMdExcludes"] == rule_globs(work, root)
    assert any(item.endswith("/coast/.claude/rules/**") for item in loaded["claudeMdExcludes"])
    assert any(
        item.endswith("/coast/harbor/.claude/rules/**") for item in loaded["claudeMdExcludes"]
    )
    assert not any("/dock/" in item for item in loaded["claudeMdExcludes"])
    assert (work / "CLAUDE.md").exists() is False


def test_materialize_skips_a_map_with_no_role(
    vault: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _install(tmp_path, monkeypatch)
    write_article(vault, "interaction/dock-rule", "DOCK-RULE")
    _map(vault, "harbor/dock", roles=None)
    work = root / "harbor" / "dock"
    work.mkdir(parents=True)

    result = materialize(vault, work)
    assert result["ok"] is True
    assert result["claude_excludes_skipped"] == "no_role"
    assert "claude_excludes" not in result
    assert not (work / ".claude" / "settings.local.json").exists()


def test_materialize_skips_the_install_root(
    vault: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _install(tmp_path, monkeypatch)
    write_article(vault, "interaction/dock-rule", "DOCK-RULE")
    write_role(vault, "keeper")
    _map(vault, "coast", roles=["keeper"])

    result = materialize(vault, root)
    assert result["ok"] is True
    assert result["claude_excludes_skipped"] == "no_ancestor"
    assert "claude_excludes" not in result
    assert not (root / ".claude" / "settings.local.json").exists()


def test_materialize_warns_and_leaves_a_non_object(
    vault: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _install(tmp_path, monkeypatch)
    write_article(vault, "interaction/dock-rule", "DOCK-RULE")
    write_role(vault, "keeper")
    _map(vault, "harbor/dock", roles=["keeper"])
    work = root / "harbor" / "dock"
    settings = work / ".claude" / "settings.local.json"
    settings.parent.mkdir(parents=True)
    settings.write_text("[]\n", encoding="utf-8")

    result = materialize(vault, work)
    assert result["ok"] is True
    assert "claude_excludes" not in result
    assert "claude_excludes_invalid" in result["warnings"]
    assert settings.read_text(encoding="utf-8") == "[]\n"
