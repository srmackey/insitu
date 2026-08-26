from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from insitu.review import apply_review


def test_apply_review_git_add_timeout_returns_git_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".git").mkdir()
    path = tmp_path / "stanzas" / "x.md"
    path.parent.mkdir()
    path.write_text("x\n", encoding="utf-8")

    def fake_run(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd="git", timeout=_kwargs.get("timeout") or 15)

    monkeypatch.setattr("insitu.review.subprocess.run", fake_run)
    result = apply_review(tmp_path, [path], "insitu: test")
    assert result["ok"] is False
    assert result["error"] == "git_timeout"
    assert result.get("staged") is not True


def test_apply_review_git_commit_timeout_returns_git_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".git").mkdir()
    path = tmp_path / "stanzas" / "x.md"
    path.parent.mkdir()
    path.write_text("x\n", encoding="utf-8")
    calls: list[str] = []

    def fake_run(args, **kwargs):
        calls.append(args[1] if len(args) > 1 else args[0])
        if "commit" in args:
            raise subprocess.TimeoutExpired(cmd=args, timeout=kwargs.get("timeout") or 15)
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("insitu.review.subprocess.run", fake_run)
    (tmp_path / "config").mkdir(exist_ok=True)
    (tmp_path / "config" / "review-policy.yaml").write_text(
        "default: auto\n", encoding="utf-8"
    )
    result = apply_review(tmp_path, [path], "insitu: test")
    assert result["ok"] is False
    assert result["error"] == "git_timeout"
    assert result.get("staged") is True
    assert "commit" in calls
