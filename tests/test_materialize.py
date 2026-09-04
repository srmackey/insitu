from __future__ import annotations

from pathlib import Path

import pytest
import yaml

import importlib

from helpers import write_project, write_article

from insitu.materialize import materialize

materialize_mod = importlib.import_module("insitu.materialize")


def _seed(vault: Path) -> None:
    write_article(vault, "interaction/summary-first", "GLOBAL-CORE-BODY")
    write_article(vault, "interaction/how-i-work-with-ai", "PROJECT-CORE-BODY")
    write_project(vault, "_global", core=["interaction/summary-first"])
    write_project(vault, "river-ledger", core=["interaction/how-i-work-with-ai"])


def test_materialize_writes_protocol_and_adapters(vault: Path, tmp_path: Path) -> None:
    _seed(vault)
    (vault / "config" / "surfaces.yaml").write_text(
        yaml.safe_dump({"surfaces": ["grok", "claude", "cursor"]}),
        encoding="utf-8",
    )
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


def test_missing_surfaces_warns_and_writes_protocol_only(
    vault: Path, tmp_path: Path
) -> None:
    _seed(vault)
    work = tmp_path / "river-ledger"
    work.mkdir()
    result = materialize(vault, work, project="river-ledger")
    assert result["ok"] is True
    assert "no_surfaces_configured" in result["warnings"]
    assert (work / "PROTOCOL.md").is_file()
    assert not (work / ".grok").exists()
    assert not (work / ".claude").exists()
    assert not (work / ".cursor").exists()


def test_unknown_surface_is_hard_error(vault: Path, tmp_path: Path) -> None:
    _seed(vault)
    (vault / "config" / "surfaces.yaml").write_text(
        yaml.safe_dump({"surfaces": ["grok", "notepad"]}),
        encoding="utf-8",
    )
    work = tmp_path / "river-ledger"
    work.mkdir()
    result = materialize(vault, work, project="river-ledger")
    assert result["ok"] is False
    assert result["error"] == "unknown_surface"
    assert result["surface"] == "notepad"
    assert not (work / "PROTOCOL.md").exists()


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
    (vault / "config" / "surfaces.yaml").write_text(
        yaml.safe_dump({"surfaces": ["grok"]}),
        encoding="utf-8",
    )
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
    (vault / "config" / "surfaces.yaml").write_text(
        yaml.safe_dump({"surfaces": ["grok"]}),
        encoding="utf-8",
    )
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


def test_a_mismatch_leaves_an_existing_checkout_untouched(
    vault: Path, tmp_path: Path
) -> None:
    """The prune is the destructive half: it removes stamped skills the named
    project does not compose, which is every skill when that project has none."""
    _seed(vault)
    (vault / "config" / "surfaces.yaml").write_text(
        yaml.safe_dump({"surfaces": ["grok"]}),
        encoding="utf-8",
    )
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
