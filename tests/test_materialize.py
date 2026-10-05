from __future__ import annotations

from pathlib import Path

import pytest
import yaml

import importlib

from helpers import write_article, write_platforms, write_project

from insitu.materialize import materialize

materialize_mod = importlib.import_module("insitu.materialize")


def _seed(vault: Path) -> None:
    write_article(vault, "interaction/summary-first", "GLOBAL-CORE-BODY")
    write_article(vault, "interaction/how-i-work-with-ai", "PROJECT-CORE-BODY")
    write_project(vault, "_global", core=["interaction/summary-first"])
    write_project(vault, "river-ledger", core=["interaction/how-i-work-with-ai"])


def test_materialize_writes_protocol_and_adapters(
    vault: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed(vault)
    write_platforms(monkeypatch, tmp_path, ["grok", "claude", "cursor"])
    work = tmp_path / "river-ledger"
    work.mkdir()
    agents = work / "AGENTS.md"
    claude_md = work / "CLAUDE.md"
    agents.write_bytes(b"keep-agents\n")
    claude_md.write_bytes(b"keep-claude\n")

    result = materialize(vault, work, project="river-ledger")
    assert result["ok"] is True

    protocol = (work / "PROTOCOL.md").read_text(encoding="utf-8")
    header, _, _rest = protocol.partition("-->")
    assert str(vault.resolve()) in header or str(vault) in header
    assert "river-ledger" in header
    assert "interaction/summary-first" in header
    assert "interaction/how-i-work-with-ai" in header
    assert "timestamp" in header.lower()
    assert "GLOBAL-CORE-BODY" in protocol
    assert "PROJECT-CORE-BODY" in protocol
    assert protocol.index("GLOBAL-CORE-BODY") < protocol.index("PROJECT-CORE-BODY")

    grok = work / ".grok" / "rules" / "insitu-protocol.md"
    claude = work / ".claude" / "rules" / "insitu-protocol.md"
    cursor = work / ".cursor" / "rules" / "insitu-protocol.mdc"
    assert grok.is_file()
    assert claude.is_file()
    assert cursor.is_file()
    assert "GLOBAL-CORE-BODY" in grok.read_text(encoding="utf-8")
    claude_text = claude.read_text(encoding="utf-8")
    assert "paths" not in claude_text
    cursor_text = cursor.read_text(encoding="utf-8")
    assert "alwaysApply: true" in cursor_text

    assert agents.read_bytes() == b"keep-agents\n"
    assert claude_md.read_bytes() == b"keep-claude\n"


def test_no_environment_file_writes_agents_and_leaves_a_constitution(
    vault: Path, tmp_path: Path
) -> None:
    _seed(vault)
    work = tmp_path / "river-ledger"
    work.mkdir()
    agents = work / "AGENTS.md"
    agents.write_bytes(b"keep-agents\n")
    result = materialize(vault, work, project="river-ledger")
    assert result["ok"] is True
    assert result["platform_source"] == "default"
    assert result["platform"] == "agents"
    assert result["unapplied"] == []
    assert result["adapters"] == []
    assert result["unchanged"] == [
        {
            "platform": "agents",
            "path": str(agents),
            "reason": "unstamped",
        }
    ]
    assert agents.read_bytes() == b"keep-agents\n"
    assert (work / "PROTOCOL.md").is_file()
    assert not (work / ".grok").exists()
    assert not (work / ".claude").exists()
    assert not (work / ".cursor").exists()


def test_no_environment_file_writes_a_missing_agents_file(
    vault: Path, tmp_path: Path
) -> None:
    _seed(vault)
    work = tmp_path / "river-ledger"
    work.mkdir()
    result = materialize(vault, work, project="river-ledger")
    assert result["ok"] is True
    assert result["platform_source"] == "default"
    agents = work / "AGENTS.md"
    assert agents.is_file()
    text = agents.read_text(encoding="utf-8")
    assert "insitu-generated:" in text
    assert "PROJECT-CORE-BODY" in text
    assert result["adapters"] == [{"surface": "agents", "path": str(agents)}]
    assert "unchanged" not in result


def test_a_stamped_agents_file_is_refreshed(vault: Path, tmp_path: Path) -> None:
    _seed(vault)
    work = tmp_path / "river-ledger"
    work.mkdir()
    agents = work / "AGENTS.md"
    # Built by the renderer so this source does not carry a generated-file marker.
    agents.write_text(
        materialize_mod.render_header(vault, "river-ledger", ["old"]) + "\n\nOLD-BODY\n",
        encoding="utf-8",
    )
    result = materialize(vault, work, project="river-ledger")
    assert result["ok"] is True
    text = agents.read_text(encoding="utf-8")
    assert "OLD-BODY" not in text
    assert "PROJECT-CORE-BODY" in text
    assert result["adapters"][0]["surface"] == "agents"


def test_a_name_without_a_definition_is_reported_and_the_rest_still_write(
    vault: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed(vault)
    write_platforms(monkeypatch, tmp_path, ["grok", "notepad"])
    work = tmp_path / "river-ledger"
    work.mkdir()
    result = materialize(vault, work, project="river-ledger")
    assert result["ok"] is True
    assert result["platform_source"] == "platforms"
    assert {"platform": "notepad", "reason": "no_definition"} in result["unapplied"]
    assert (work / "PROTOCOL.md").is_file()
    assert (work / ".grok" / "rules" / "insitu-protocol.md").is_file()
    assert not (work / "AGENTS.md").exists()


def test_generated_header_carries_no_git_ref(vault: Path, tmp_path: Path) -> None:
    """0.14 dropped the git: stamp. Staged-not-committed vaults made it reliably wrong."""
    _seed(vault)
    work = tmp_path / "river-ledger"
    work.mkdir()
    result = materialize(vault, work, project="river-ledger")
    assert result["ok"] is True
    header = (work / "PROTOCOL.md").read_text(encoding="utf-8")
    assert "git:" not in header
    assert "timestamp:" in header and "articles:" in header


def test_materialize_skips_locked_adapter_still_writes_protocol(
    vault: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed(vault)
    write_platforms(monkeypatch, tmp_path, ["grok"])
    work = tmp_path / "river-ledger"
    work.mkdir()
    original = Path.write_text

    def maybe_lock(self: Path, data, *args, **kwargs):
        if self.name == "insitu-protocol.md":
            raise PermissionError("locked")
        return original(self, data, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", maybe_lock)
    result = materialize(vault, work, project="river-ledger")
    assert result["ok"] is True
    assert (work / "PROTOCOL.md").is_file()
    assert "GLOBAL-CORE-BODY" in (work / "PROTOCOL.md").read_text(encoding="utf-8")
    assert not (work / ".grok" / "rules" / "insitu-protocol.md").exists()
    assert "adapter_locked" in result["warnings"] or any(
        w.startswith("adapter_") for w in result["warnings"]
    )
    assert result["adapters"] == []


def test_materialize_skips_hanging_adapter_write(
    vault: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import time

    _seed(vault)
    write_platforms(monkeypatch, tmp_path, ["grok"])
    work = tmp_path / "river-ledger"
    work.mkdir()
    original = Path.write_text

    def hang_adapter(self: Path, data, *args, **kwargs):
        if self.name == "insitu-protocol.md":
            time.sleep(1)
        return original(self, data, *args, **kwargs)

    monkeypatch.setattr(materialize_mod, "ADAPTER_WRITE_TIMEOUT_SECONDS", 0.2)
    monkeypatch.setattr(Path, "write_text", hang_adapter)
    result = materialize(vault, work, project="river-ledger")
    assert result["ok"] is True
    assert (work / "PROTOCOL.md").is_file()
    assert "adapter_locked" in result["warnings"]
    assert result["adapters"] == []


# --- the destination must be the named project's checkout ------------------
#
# Everywhere else working_folder identifies the calling chair. Here it is the
# folder that gets written, and the operator gate only compares the two for a
# bound chair. These cover the admin case the gate waves through.


def test_a_named_project_must_match_the_folder_it_is_written_into(
    vault: Path, tmp_path: Path
) -> None:
    _seed(vault)
    work = tmp_path / "harbor"

    result = materialize(vault, work, project="river-ledger")

    assert result["ok"] is False
    assert result["error"] == "folder_project_mismatch"
    assert result["project"] == "river-ledger"
    assert result["folder"] == "harbor"
    assert not work.exists(), "a refused call must not create the folder"


def test_a_missing_checkout_is_refused_not_created(
    vault: Path, tmp_path: Path
) -> None:
    _seed(vault)
    work = tmp_path / "river-ledger"

    result = materialize(vault, work, project="river-ledger")

    assert result["ok"] is False
    assert result["error"] == "working_folder_missing"
    assert result["project"] == "river-ledger"
    assert Path(result["path"]) == work
    assert "does not exist" in result["detail"]
    assert not work.exists(), "a missing checkout must not be created"


def test_a_file_path_is_not_a_checkout(vault: Path, tmp_path: Path) -> None:
    _seed(vault)
    work = tmp_path / "river-ledger"
    work.write_text("not a folder\n", encoding="utf-8")

    result = materialize(vault, work, project="river-ledger")

    assert result["ok"] is False
    assert result["error"] == "working_folder_not_directory"
    assert work.is_file()


def test_a_mismatch_leaves_an_existing_checkout_untouched(
    vault: Path, tmp_path: Path
) -> None:
    """The prune is the destructive half: it removes stamped skills the named
    project does not compose, which is every skill when that project has none."""
    _seed(vault)
    work = tmp_path / "harbor"
    work.mkdir()
    protocol = work / "PROTOCOL.md"
    protocol.write_text("HARBOR-PROTOCOL", encoding="utf-8")
    skill_dir = work / ".grok" / "skills" / "dock-tool"
    skill_dir.mkdir(parents=True)
    skill_md = skill_dir / "SKILL.md"
    # Stamped by the renderer rather than a literal, so the stamp stays real if
    # its format moves, and so this source carries no generated-file marker.
    skill_md.write_text(
        materialize_mod.render_skill_copy(
            "---\nname: dock-tool\n---\n\nDOCK-TOOL-BODY\n",
            vault,
            "harbor",
            "dock-tool",
        ),
        encoding="utf-8",
    )
    assert materialize_mod.has_insitu_skill_stamp(
        skill_md.read_text(encoding="utf-8")
    ), "the prune only reaches stamped skills, so the fixture must be stamped"

    result = materialize(vault, work, project="river-ledger")

    assert result["ok"] is False
    assert result["error"] == "folder_project_mismatch"
    assert protocol.read_text(encoding="utf-8") == "HARBOR-PROTOCOL"
    assert skill_md.is_file(), "a refused call must not prune the folder's skills"


def test_a_mixed_case_folder_still_matches_its_lowercase_key(
    vault: Path, tmp_path: Path
) -> None:
    """Folder basenames may be mixed-case; stored keys are lowercase."""
    _seed(vault)
    work = tmp_path / "River-Ledger"
    work.mkdir()

    result = materialize(vault, work, project="river-ledger")

    assert result["ok"] is True
    assert (work / "PROTOCOL.md").is_file()


def _environment(tmp_path: Path, text: str | None) -> Path:
    root = tmp_path / "install"
    root.mkdir()
    (root / "nexus.md").write_text("name: example\n", encoding="utf-8")
    if text is not None:
        (root / "platforms.yaml").write_text(text, encoding="utf-8")
    return root


def test_platforms_yaml_enabled_replaces_the_vault_list(
    vault: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed(vault)
    (vault / "config" / "surfaces.yaml").write_text(
        yaml.safe_dump({"surfaces": ["cursor"]}),
        encoding="utf-8",
    )
    write_platforms(monkeypatch, tmp_path, ["grok"])
    work = tmp_path / "river-ledger"
    work.mkdir()

    result = materialize(vault, work, project="river-ledger")

    assert result["ok"] is True
    assert result["platform_source"] == "platforms"
    assert (work / ".grok" / "rules" / "insitu-protocol.md").is_file()
    assert not (work / ".cursor").exists()
    assert not (work / ".claude").exists()
    assert not (work / "AGENTS.md").exists()


def test_an_empty_enabled_list_does_not_fall_through_to_surfaces(
    vault: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed(vault)
    (vault / "config" / "surfaces.yaml").write_text(
        yaml.safe_dump({"surfaces": ["cursor"]}),
        encoding="utf-8",
    )
    root = _environment(tmp_path, "enabled: []\n")
    monkeypatch.setenv("INSITU_ROOT", str(root))
    work = tmp_path / "river-ledger"
    work.mkdir()

    result = materialize(vault, work, project="river-ledger")

    assert result["ok"] is True
    assert result["platform_source"] == "platforms"
    assert "no_surfaces_configured" not in result["warnings"]
    assert (work / "PROTOCOL.md").is_file()
    assert not (work / "AGENTS.md").exists()
    assert not (work / ".cursor").exists()


def test_a_bad_platforms_file_is_not_the_vault_list(
    vault: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed(vault)
    (vault / "config" / "surfaces.yaml").write_text(
        yaml.safe_dump({"surfaces": ["grok"]}),
        encoding="utf-8",
    )
    root = _environment(tmp_path, "enabled: grok\n")
    monkeypatch.setenv("INSITU_ROOT", str(root))
    work = tmp_path / "river-ledger"
    work.mkdir()

    result = materialize(vault, work, project="river-ledger")

    assert result["ok"] is False
    assert result["error"] == "platforms_invalid"
    assert not (work / "PROTOCOL.md").exists()
    assert not (work / ".grok").exists()


def test_a_missing_platforms_file_does_not_read_surfaces(
    vault: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed(vault)
    (vault / "config" / "surfaces.yaml").write_text(
        yaml.safe_dump({"surfaces": ["grok"]}),
        encoding="utf-8",
    )
    root = _environment(tmp_path, None)
    monkeypatch.setenv("INSITU_ROOT", str(root))
    work = tmp_path / "river-ledger"
    work.mkdir()

    result = materialize(vault, work, project="river-ledger")

    assert result["ok"] is True
    assert result["platform_source"] == "default"
    assert result["platform"] == "agents"
    assert (work / "AGENTS.md").is_file()
    assert not (work / ".grok").exists()


def test_a_stored_path_is_what_gets_written(
    vault: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed(vault)
    write_platforms(
        monkeypatch,
        tmp_path,
        ["ledger"],
        extra={
            "ledger": {
                "instructions": [
                    {
                        "scope": "project",
                        "path": "notes/protocol.md",
                        "format": "markdown",
                    }
                ],
                "skills": [{"scope": "project", "path": "kit/skills"}],
            }
        },
    )
    work = tmp_path / "river-ledger"
    work.mkdir()
    result = materialize(vault, work, project="river-ledger")
    assert result["ok"] is True
    assert result["unapplied"] == []
    dest = work / "notes" / "protocol.md"
    assert dest.is_file()
    assert "PROJECT-CORE-BODY" in dest.read_text(encoding="utf-8")
    assert not (work / ".grok").exists()
    assert not (work / ".cursor").exists()


def test_an_unknown_format_is_reported_and_a_sibling_still_writes(
    vault: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed(vault)
    write_platforms(
        monkeypatch,
        tmp_path,
        ["grok", "odd"],
        extra={
            "odd": {
                "instructions": [
                    {
                        "scope": "project",
                        "path": "odd/protocol.toml",
                        "format": "toml",
                    }
                ]
            }
        },
    )
    work = tmp_path / "river-ledger"
    work.mkdir()
    result = materialize(vault, work, project="river-ledger")
    assert result["ok"] is True
    assert {
        "platform": "odd",
        "reason": "unknown_format",
        "path": "odd/protocol.toml",
    } in result["unapplied"]
    assert (work / ".grok" / "rules" / "insitu-protocol.md").is_file()
    assert not (work / "odd").exists()


def test_claude_md_is_never_written(
    vault: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed(vault)
    write_platforms(
        monkeypatch,
        tmp_path,
        ["page"],
        extra={
            "page": {
                "instructions": [
                    {
                        "scope": "project",
                        "path": "CLAUDE.md",
                        "format": "markdown",
                    }
                ]
            }
        },
    )
    work = tmp_path / "river-ledger"
    work.mkdir()
    result = materialize(vault, work, project="river-ledger")
    assert result["ok"] is True
    assert not (work / "CLAUDE.md").exists()
    assert {
        "platform": "page",
        "reason": "constitution",
        "path": "CLAUDE.md",
    } in result["unapplied"]
    assert (work / "PROTOCOL.md").is_file()


def test_a_path_that_escapes_the_checkout_is_not_written(
    vault: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed(vault)
    write_platforms(
        monkeypatch,
        tmp_path,
        ["out"],
        extra={
            "out": {
                "instructions": [
                    {
                        "scope": "project",
                        "path": "../outside.md",
                        "format": "markdown",
                    }
                ]
            }
        },
    )
    work = tmp_path / "river-ledger"
    work.mkdir()
    result = materialize(vault, work, project="river-ledger")
    assert result["ok"] is True
    assert not (tmp_path / "outside.md").exists()
    assert any(row["reason"] == "path_escapes" for row in result["unapplied"])


def test_a_user_scoped_instruction_is_not_a_project_write(
    vault: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed(vault)
    outside = tmp_path / "user-rules.md"
    write_platforms(
        monkeypatch,
        tmp_path,
        ["host"],
        extra={
            "host": {
                "instructions": [
                    {
                        "scope": "user",
                        "path": str(outside),
                        "format": "markdown",
                    }
                ]
            }
        },
    )
    work = tmp_path / "river-ledger"
    work.mkdir()
    result = materialize(vault, work, project="river-ledger")
    assert result["ok"] is True
    assert not outside.exists()
    assert {
        "platform": "host",
        "reason": "no_project_instruction",
    } in result["unapplied"]
