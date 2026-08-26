"""Size metadata. Token counts are chars / 4 and labeled an estimate."""

from __future__ import annotations

TOKEN_ESTIMATE_NOTE = "estimate (chars / 4)"


def estimate_tokens(text: str) -> int:
    return len(text) // 4


def size_fields(text: str) -> dict:
    return {
        "bytes": len(text.encode("utf-8")),
        "estimated_tokens": estimate_tokens(text),
        "token_estimate_note": TOKEN_ESTIMATE_NOTE,
    }


def total_size(texts: list[str]) -> dict:
    combined = "".join(texts)
    fields = size_fields(combined)
    fields["stanza_count"] = len(texts)
    # totals should be the sum of per-stanza sizes, not the concat of empties
    fields["bytes"] = sum(len(t.encode("utf-8")) for t in texts)
    fields["estimated_tokens"] = sum(estimate_tokens(t) for t in texts)
    return fields
