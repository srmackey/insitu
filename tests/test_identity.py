from __future__ import annotations

import pytest

from insitu.identity import (
    InvalidIdentity,
    validate_project_key,
    validate_role_id,
    validate_skill_id,
    validate_stanza_id,
)


def test_accepts_global_and_kebab_project_keys() -> None:
    assert validate_project_key("_global") == "_global"
    assert validate_project_key("river-ledger") == "river-ledger"
    assert validate_project_key("a1") == "a1"


def test_folds_project_key_case() -> None:
    assert validate_project_key("ProjectName") == "projectname"
    assert validate_project_key("River") == "river"


def test_rejects_project_keys_outside_charset() -> None:
    for key in ("has_underscore", "has space", "", ".", "..", "a/b"):
        with pytest.raises(InvalidIdentity):
            validate_project_key(key)


def test_rejects_absolute_and_drive_project_keys() -> None:
    with pytest.raises(InvalidIdentity):
        validate_project_key("/tmp/evil")
    with pytest.raises(InvalidIdentity):
        validate_project_key("C:\\windows")


def test_accepts_kebab_stanza_segments() -> None:
    assert validate_stanza_id("interaction/summary-first") == "interaction/summary-first"
    assert validate_stanza_id("one") == "one"


def test_rejects_stanza_escape_and_charset() -> None:
    for sid in (
        "../escape",
        "interaction/../methodology/x",
        "/absolute/path",
        "Foo/Bar",
        "_secret/foo",
        "interaction//foo",
        "interaction/./foo",
    ):
        with pytest.raises(InvalidIdentity):
            validate_stanza_id(sid)


def test_accepts_kebab_role_ids() -> None:
    assert validate_role_id("clerk") == "clerk"
    assert validate_role_id("ledger-clerk") == "ledger-clerk"
    assert validate_role_id("a1") == "a1"


def test_rejects_role_ids_outside_charset() -> None:
    for key in ("Clerk", "has_underscore", "has space", "", ".", "..", "a/b", "_global"):
        with pytest.raises(InvalidIdentity):
            validate_role_id(key)


def test_rejects_absolute_role_ids() -> None:
    with pytest.raises(InvalidIdentity):
        validate_role_id("/tmp/evil")
    with pytest.raises(InvalidIdentity):
        validate_role_id("C:\\windows")


def test_accepts_kebab_skill_ids() -> None:
    assert validate_skill_id("close-books") == "close-books"
    assert validate_skill_id("a1") == "a1"


def test_rejects_nested_or_bad_skill_ids() -> None:
    for key in (
        "methodology/land",
        "CloseBooks",
        "has_underscore",
        "has space",
        "",
        ".",
        "..",
        "_global",
    ):
        with pytest.raises(InvalidIdentity):
            validate_skill_id(key)


def test_rejects_absolute_skill_ids() -> None:
    with pytest.raises(InvalidIdentity):
        validate_skill_id("/tmp/evil")
    with pytest.raises(InvalidIdentity):
        validate_skill_id("C:\\windows")
