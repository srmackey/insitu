"""Facts about a provision's own text (DESIGN.md §6.5, §12).

Two of these compare the text to a composition. The third compares it to the
vault's own two-file shape. All three are scans of authored prose, which is why
they live together.

The composition pair are opposite strengths, deliberately kept apart.

A **conflict** is declared. `conflicts:` on an article names another article that
must not be composed beside it. It is symmetric on read, so one side declaring is
enough, and it refuses: at write time a link or install that would put both in one
protocol is rejected. It has to be a declaration precisely because it has teeth.
A text scan can see that one article names another but not whether that is a
mirror, a variant, or an incompatibility, and refusing on a guess is worse than
not refusing.

A **mention** is not declared. Composition scans an article's text for other
article ids and reports the ones this project does not compose, so the agent can
offer them at the moment of an install. That is an offer, not a finding, which is
why a guess is affordable here: a contrast mention costs one declined suggestion.
Classification of the same signal into prerequisite versus contrast belongs to the
audit half, which a human reads.

Only article ids are scanned. They carry a `/` and are unambiguous in prose. Skill
ids are a single segment and would match ordinary words.

**Provenance in the body** is the third, and it measures the text against nothing
but this vault's structure: a why-log already has a home outside the composed body,
so a block headed `Provenance` is that content sitting in the one place every chair
pays for it. Like a mention it warns and never refuses, because it is the author's
own prose and only they can say whether the word is the heading or the subject.
"""

from __future__ import annotations

import re
from typing import Iterable

from .identity import InvalidIdentity, validate_article_id
from .models import Article, PackVersion, Vault

# An article id as it appears in prose: two or more `a-z0-9-` segments joined by
# `/`. Backticks, quotes and sentence punctuation fall outside the class, so a
# fenced `methodology/x` and a bare one both match, and a trailing period does
# not become part of the id.
_ID_IN_TEXT = re.compile(r"(?<![A-Za-z0-9_/-])([a-z0-9][a-z0-9-]*(?:/[a-z0-9][a-z0-9-]*)+)")

# A block opening with the word, optionally as a markdown heading. Anchored at the
# start of a block so an article that discusses provenance in a sentence, or names
# `provenance/<id>.md` mid-paragraph, does not trip it.
_PROVENANCE_OPENER = re.compile(r"\s{0,3}#{0,6}\s*provenance\b", re.IGNORECASE)


def provenance_in_body(content: str) -> dict | None:
    """A why-log entry written into the body, where every chair pays for it.

    The vault gives provenance a home already: `provenance/<id>.md` for an article
    and `provenance/skills/<id>.md` for a skill, both written by the same call that
    writes the provision, from `why`. A block in the body headed `Provenance` is
    that content in the one place it composes into every chair holding the
    provision, and the author is standing right here when it happens.

    Warns rather than refuses. The scan cannot tell a why-log entry from an article
    whose subject is provenance, and the cost of being wrong is one ignored key
    against a body silently rejected.
    """
    hits: list[int] = []
    at_block_start = True
    for number, line in enumerate((content or "").splitlines(), start=1):
        if not line.strip():
            at_block_start = True
            continue
        if at_block_start and _PROVENANCE_OPENER.match(line):
            hits.append(number)
        at_block_start = False
    if not hits:
        return None
    where = "line " + ", ".join(str(number) for number in hits)
    return {
        "code": "provenance_in_body",
        "lines": hits,
        "detail": (
            f"the body opens a block with 'Provenance' at {where}. The body composes "
            "into every chair holding this provision; the why-log composes into none "
            "and is where a dated entry belongs. See `why_log` for the file this call "
            "already wrote."
        ),
    }


def declared_conflicts(article: Article) -> list[str]:
    """The article ids this article declares itself incompatible with."""
    out: list[str] = []
    for raw in article.conflicts:
        try:
            out.append(validate_article_id(str(raw)))
        except InvalidIdentity:
            continue
    return out


def conflicts_between(
    candidate: Article, composed: Iterable[Article]
) -> list[dict[str, str]]:
    """Pairs where `candidate` and a composed article declare against each other.

    Symmetric: either side declaring is the whole relation, so an author states it
    once and both directions hold.
    """
    declared = set(declared_conflicts(candidate))
    found: list[dict[str, str]] = []
    for other in composed:
        if other.id == candidate.id:
            continue
        if other.id in declared:
            found.append({"id": other.id, "declared_by": candidate.id})
        elif candidate.id in set(declared_conflicts(other)):
            found.append({"id": other.id, "declared_by": other.id})
    return found


def conflicts_within(articles: Iterable[Article]) -> list[dict[str, str]]:
    """Every conflicting pair inside one set, each pair reported once."""
    items = list(articles)
    seen: set[tuple[str, str]] = set()
    found: list[dict[str, str]] = []
    for index, article in enumerate(items):
        for other in items[index + 1 :]:
            pair = tuple(sorted((article.id, other.id)))
            if pair in seen:
                continue
            hit = conflicts_between(article, [other])
            if hit:
                seen.add(pair)
                found.append(
                    {"a": pair[0], "b": pair[1], "declared_by": hit[0]["declared_by"]}
                )
    return found


def resolve_article(vault: Vault, article_id: str) -> Article | None:
    """An article by id, native first, then any pack version on the shelf."""
    article = vault.articles.get(article_id)
    if article is not None:
        return article
    for versions in vault.library.values():
        for pack_version in versions.values():
            found = pack_version.articles.get(article_id)
            if found is not None:
                return found
    return None


def composed_articles(vault: Vault, project: str) -> list[Article]:
    """Every article this project composes, core and on-demand, native or packed.

    On-demand counts. It is not injected, but a chair that pulls it mid-session
    ends up holding both, which is the state a conflict exists to prevent.
    """
    # Imported here rather than at module scope: `affects` reaches `resolve`, and
    # `resolve` reaches this module for the resolve-time warning. Keeping the
    # declaration and scan helpers free of vault-composition imports is what lets
    # both directions work without a cycle.
    from .affects import composed_id_sets

    if project not in vault.projects:
        return []
    core, on_demand = composed_id_sets(vault, project)
    out: list[Article] = []
    for article_id in sorted(core | on_demand):
        found = resolve_article(vault, article_id)
        if found is not None:
            out.append(found)
    return out


def composed_ids(vault: Vault, project: str) -> set[str]:
    """Ids this project composes, core and on-demand together."""
    from .affects import composed_id_sets

    if project not in vault.projects:
        return set()
    core, on_demand = composed_id_sets(vault, project)
    return core | on_demand


def prohibition_refusal(vault: Vault, project: str, article_id: str) -> dict | None:
    """The write-time half of a prohibition: refuse to put it on the map at all.

    Resolution excludes a prohibited article rather than failing, because a map
    can acquire a prohibition without its occupant touching anything. A write is
    the opposite case: someone is asking for it right now, so the honest answer
    is no rather than a silent drop they discover later.
    """
    from .operators import load_operators

    operators = load_operators(vault.root)
    by = operators.prohibiting_class(project, article_id)
    if by is None:
        return None
    return {
        "ok": False,
        "error": "prohibited_by_class",
        "id": article_id,
        "project": project,
        "prohibited_by": by,
        "classes": operators.classes_for(project),
        "detail": (
            f"class {by!r} forbids {article_id!r} on this chair. An admin chair "
            "changes that in the vault's operator config, not on this map."
        ),
    }


def conflict_refusal(vault: Vault, project: str, candidate: Article) -> dict | None:
    """The write-time half: refuse a link or install that would compose a conflict.

    Write is where the deliberate case happens, and where the person who can undo
    it is standing. Resolution only warns (`methodology` note in DESIGN §6.5),
    because every map may pin `latest` and a refusal there would let one upstream
    declaration make untouched checkouts unresolvable.
    """
    clash = conflicts_between(candidate, composed_articles(vault, project))
    if not clash:
        return None
    return {
        "ok": False,
        "error": "conflicts_with_composed",
        "id": candidate.id,
        "project": project,
        "conflicts": clash,
    }


def _known_article_ids(vault: Vault, pack: PackVersion | None = None) -> set[str]:
    known = set(vault.articles)
    if pack is not None:
        known |= set(pack.articles)
    return known


def mentions_not_composed(
    vault: Vault,
    texts: Iterable[str],
    composed: Iterable[str],
    pack: PackVersion | None = None,
) -> list[str]:
    """Article ids named in `texts` that resolve somewhere but not in this project.

    An id nothing can resolve is not reported here. That is the audit half's
    finding, and repeating it at install would put a broken reference in front of
    someone who cannot fix it from where they are standing.
    """
    known = _known_article_ids(vault, pack)
    have = set(composed)
    found: list[str] = []
    for text in texts:
        for match in _ID_IN_TEXT.finditer(text or ""):
            article_id = match.group(1)
            if article_id in known and article_id not in have and article_id not in found:
                found.append(article_id)
    return sorted(found)
