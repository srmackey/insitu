from __future__ import annotations

from pathlib import Path

from insitu.catalog import get_role, list_roles
from insitu.resolve import resolve_protocol
from insitu.validate import validate

EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "vault"

# The shipped example vault is fictional. Assert that by allowlist rather than by
# listing real project names, which would put them back in the tree.
FICTIONAL_PROJECT_KEYS = {"_global", "harbor-notes", "river-ledger"}
FICTIONAL_ROLE_IDS = {"clerk"}
FORBIDDEN = ("about-me",)


def test_examples_vault_is_fictional() -> None:
    assert EXAMPLES.is_dir()
    keys = {d.name for d in (EXAMPLES / "projects").iterdir() if d.is_dir()}
    assert keys == FICTIONAL_PROJECT_KEYS
    roles = {r.stem for r in (EXAMPLES / "roles").glob("*.yaml")}
    assert roles == FICTIONAL_ROLE_IDS
    for path in EXAMPLES.rglob("*"):
        text = str(path)
        if path.is_file():
            text += "\n" + path.read_text(encoding="utf-8")
        lowered = text.lower()
        for token in FORBIDDEN:
            assert token.lower() not in lowered


def test_examples_vault_composes_river_ledger() -> None:
    result = resolve_protocol(EXAMPLES, "river-ledger")
    assert result["ok"] is True
    assert result["roles"] == ["clerk"]
    ids = [item["id"] for item in result["core"]]
    assert ids == [
        "interaction/digest-then-drill",
        "methodology/ledger-clerk",
        "interaction/how-i-work-with-ai",
    ]
    joined = "\n".join(item["content"] for item in result["core"])
    assert "Named ledger decisions beat silent defaults." in joined
    assert "name the account, the amount, and the reason" in joined
    assert all("content" not in row for row in result["on_demand"])
    assert [row["id"] for row in result["skills"]] == ["close-books"]
    assert all("content" not in row for row in result["skills"])


def test_examples_vault_role_and_validate_are_clean() -> None:
    report = validate(EXAMPLES)
    assert report["ok"] is True, report
    listed = list_roles(EXAMPLES)
    assert listed["ok"] is True
    assert any(row["id"] == "clerk" for row in listed["roles"])
    got = get_role(EXAMPLES, "clerk")
    assert got["ok"] is True
    assert "river-ledger" in got["projects"]
    assert [item["id"] for item in got["core"]] == ["methodology/ledger-clerk"]
