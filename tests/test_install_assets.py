from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTERS = ROOT / "install" / "routers"
PACK_MARKERS = (
    "Named ledger decisions beat silent defaults.",
    "GLOBAL-CORE-BODY",
    "PROJECT-CORE-BODY",
)


def test_install_routers_and_examples_exist() -> None:
    cursor = ROUTERS / "cursor.mdc"
    claude = ROUTERS / "claude.md"
    grok = ROUTERS / "grok.md"
    assert cursor.is_file()
    assert claude.is_file()
    assert grok.is_file()
    assert (ROOT / "install" / "mcp.json.examples.md").is_file()
    assert (ROOT / "install" / "AGENTS.md").is_file()
    cursor_text = cursor.read_text(encoding="utf-8")
    claude_text = claude.read_text(encoding="utf-8")
    assert "alwaysApply: true" in cursor_text
    assert "paths:" not in claude_text
    for path in (cursor, claude, grok):
        text = path.read_text(encoding="utf-8")
        for marker in PACK_MARKERS:
            assert marker not in text


def test_routers_contain_rematerialize_and_do_not_delete() -> None:
    for name in ("cursor.mdc", "claude.md", "grok.md"):
        text = (ROUTERS / name).read_text(encoding="utf-8")
        assert "affects_projects" in text
        assert "start a new session" in text
        assert "materialize" in text
        assert "delete_article" in text
        assert "delete_role" in text
        assert "delete_project" in text
        assert "unless the user" in text.lower()
        assert "findings" in text


def test_routers_mention_generated_skill_dirs() -> None:
    for name in ("cursor.mdc", "claude.md", "grok.md"):
        text = (ROUTERS / name).read_text(encoding="utf-8")
        assert ".grok/skills" in text
        assert ".claude/skills" in text
        assert ".cursor/skills" in text
        assert "get_skill" in text
        assert "list_skills" in text
        assert "Do not call `list_skills` at" in text or "Do not call list_skills at" in text
        assert "session start to load skills" in text
        assert "\u2014" not in text
        assert "\u2013" not in text


def test_routers_two_layer_bootstrap() -> None:
    expected_host = {
        "cursor.mdc": "platform/cursor",
        "claude.md": "platform/claude-code",
        "grok.md": "platform/grok-build",
    }
    for name, host_id in expected_host.items():
        text = (ROUTERS / name).read_text(encoding="utf-8")
        assert "platform/router-vs-pack" in text
        assert host_id in text
        assert "never writes" in text
        assert "AGENTS.md" in text
        assert "pack is not installed" in text
        assert "Do not put pack bodies" in text


def test_readme_documents_install() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Python 3.11" in text
    assert "uv sync" in text
    assert "INSITU_HOME" in text
    assert "--vault" in text
    assert "mcp.json" in text
    assert "~/.cursor/rules/insitu-router.mdc" in text
    assert "~/.claude/rules/insitu-router.md" in text
    assert "~/.grok/rules/insitu-router.md" in text
