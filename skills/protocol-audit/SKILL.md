---
name: protocol-audit
description: "Audit a chair's composed Insitu protocol for contradictions, unresolved references, stale doctrine, unneeded weight, and shape. Use when asked to audit, review, or trim a protocol, when a chair's core feels heavy or wrong, or when two loaded rules seem to disagree. Produces a proposal and never edits. Not for structural validation, which is validate, and not for a size report, which is list_articles."
argument-hint: "[this chair | <project key> | sweep <keys>]"
---

# Protocol audit

Read what a chair actually loads and judge whether it still holds together. Output is a proposal. This skill never edits a protocol, a map, an article, or a pack.

The job is reading comprehension, not computation. No tool finds these problems for you. The tools hand you the text and the facts; the finding is yours.

## Scope

| Ask | You do |
|---|---|
| No argument, or "this chair" | Audit the working folder you are in. |
| A project key that is not this folder | Read it freely. Holding the report is admin only, so confirm the class with `operators`. If this chair is `bound`, the finding leaves as an export instead of becoming a report here. |
| `sweep` plus keys | Admin only, and only on a charter the principal named. One report per chair, then the roll-up in §7. |

**The cross-chair rule is about ownership, not permission.** Inspect is free to every class, so nothing stops a bound chair from reading another project's composition, and you may well end up doing that to check whether a finding is local or systemic. What a bound chair must not do is hold a report about a chair it cannot act on. Findings about another chair are not closable where you are sitting, and parking them in this chair's records is the mistake `methodology/status-contract` exists to prevent. If you are bound and you find something about a sibling, it leaves as an export under `methodology/envoy-mail`. It does not become your open loop.

A sweep is not a license to roam. If the principal did not name which maps are in scope, ask before reading them.

## 1. Load the picture

Before judging anything, get the whole composed text in front of you, plus the facts about where it came from.

- `project_status` for the map, the roles, the imports, the sizes, and whether the disk copy matches.
- `resolve_protocol` for the composed text. Read it. All of it. An audit of a summary is worthless.
- `list_articles` for the catalog with origins, so you know which members are native to the vault and which arrived in a pack.
- `where_used` on anything you suspect, because a finding that touches one map is local and one that touches five is a pack problem.
- The chair's own constitution and native files. The protocol is only half of what the agent loads, and half the contradictions are between the two.

Then read the node's `STATUS.md` and its `inbox/`. A finding already recorded there is not news, and one recorded there and since resolved tells you the record is drifting.

## 2. Contradictions

Two rules that tell the agent opposite things, or a rule that contradicts the node's own constitution or a native file.

**Do not compare article against article in the abstract.** That is the method that finds nothing, because doctrine written months apart rarely collides in the prose. It collides at an object.

Work from the objects instead. List the concrete things the protocol governs: specific files and paths, specific actions (commit, publish, deliver, materialize, write status), specific surfaces. For each one, gather every rule that touches it and ask which rule wins. A contradiction is a governed object with two answers and no tiebreaker.

That is how the sharpest known example was found. One article says host overlay stays untracked and not gitignored, and a few lines later says generated files carrying a vault path, the composed protocol included, should be gitignored. Neither sentence is wrong. A materialized adapter is both things at once, and nothing says which rule governs it. Read as prose it is invisible. Read from the file, it is obvious.

Check the node's constitution against the protocol the same way. Those two were written by different hands for different reasons and nothing composes them together.

## 3. Stale

Doctrine that was true and is not any more.

Start with what is mechanically checkable, because it is cheap and it is where the rot shows first:

- **Every named object still exists.** An article id, role, pack, skill, tool, path, or config key named in the protocol should resolve. `list_articles` and `get_article` settle article references, and the filesystem settles paths. A rule that points at something deleted is stale by definition, and this is the single highest-yield check in the whole audit. Doctrine gets split and renamed far more often than anyone updates the things that pointed at it.
- **Dates that have passed.** Provenance lines, phase references, "until X lands," "ships before Y."
- **Conditions written as pending that have since landed.** "Until the server refuses" is stale the day it refuses. Check, do not assume.

Then the part that needs judgment: an article whose provenance points at a decision that has since been recut. Read the provenance line, find the decision it names, and ask whether that decision still stands. This is where an article survives its own reason.

## 4. Unresolved references

An article that names another article this composition does not include. §3 asks whether a named object still exists in the vault. This asks whether it resolves *here*, in the protocol the chair actually loads.

The rule underneath it is Insitu's composable obligation: an article must be complete and actionable when composed alone. It may name another to contrast with it, or to point at the variant a different kind of chair takes. What it may not do is leave the reader following a rule they cannot finish without something they were not given.

**How to run it.** Read the composed text for article ids, and subtract the ids this protocol composes, core and on-demand together. What is left is the candidate list. Insitu returns `mentions_not_composed` on an install, which is the same scan at the moment someone chooses a member; this is the same scan over a composition that already exists, so it catches what predates that check and what someone was offered and declined.

**Classification is by hand, and it is most of the value.** The scan cannot tell why one article names another, so it hands you three cases that look identical:

- **Contrast.** "Mirror of X", "the opposite direction from X". Fine. The reader needs nothing more.
- **Delegation.** "A privacy-sensitive chair takes X instead." Fine, and often the point: the sentence exists so a chair knows the rule it is *not* under.
- **Prerequisite.** The rule cannot be completed without the other article. That is the finding. The fix is one of two things, and the choice is a real one: link the other article on that map, or rewrite the sentence so it stands alone. Adding weight to a protocol to satisfy a cross-reference is not automatically right.

**Evidence this is worth running.** Measured across a 35-article vault: 20 articles name another by id, in 46 pairs, and in 18 of those pairs some chair composes the referring article without the referenced one. One is live and is a prerequisite rather than a contrast: the nexus composes `methodology/insitu-vault-steward`, which says the Insitu vault's posture is `methodology/repo-provenance`, and does not compose that article.

Do not report a name that resolves nowhere as this finding. An id that exists in no vault and no pack is §3's existence check, and it is a different fix.

## 5. Unneeded

Weight that buys nothing for this chair.

Three tests, in order of how often they hit:

1. **Duplicated by a native file.** The node's constitution already says what a loaded article says. Two copies of a rule diverge, and the composed one is the copy nobody edits.

   **Check for local scope before calling it a duplicate.** A native line that repeats an article and then narrows it, extends it, or applies it to this chair's specific objects is not duplication. It is the local half of the rule, and deleting it silently drops a constraint. The test is whether the line tells the agent anything the loaded article does not. Read both in full before deciding, because the added scope is usually one clause inside an otherwise familiar sentence, and it is easy to skim past.

   **When it is a true duplicate, delete it rather than leaving a pointer.** Both files load into the same context, so a line whose whole content is "see that article" is still a line the agent reads to learn what it already knows. A bare pointer earns its place in one case: a public repo where the composed protocol is untracked and the constitution is the only governing file a reader can see. Otherwise cut it.
2. **Installed for a phase that closed.** Doctrine taken on for a piece of work that is finished.
3. **Never fires.** Ask concretely: name a sitting in this chair where this rule changed what happened. Not where it could have. Where it did. If you cannot name one, and the chair has been working, say so as a finding rather than deleting anything.

That third test is judgment and it is meant to be. There is no usage data, Insitu does not collect any, and it should not start. The person sitting in the chair knows what fires.

Be careful in the other direction too. A long article that fires every sitting earns its weight, and a short one that never fires does not. Size is a gauge, never a verdict.

## 6. Shape

What to group, split, extract, or trim so the core stays worth carrying.

- **One idea per article.** An article carrying two ideas should split, and the tell is a description with an "and" joining unrelated halves.
- **Repetition across members** wants extracting into one article the others point at.
- **A rarely-fired member** wants moving to on-demand rather than deleting. It stays in the map and gets pulled with `get_article` when the work needs it. This works at the article grain as well as the whole-capability grain.
- **A member for a host this checkout never runs, or a tool this chair does not have,** is carried weight. Check what the chair actually uses before assuming it needs the host profile.
- **Vocabulary collisions.** Pick the load-bearing nouns and search them across the protocol and the adjacent docs. One word doing three jobs is a shape finding, and it bites hardest in a pack whose job is teaching precise vocabulary.

## 7. Evidence, and the report

**Check every claim against the world.** An article that asserts a fact (a path exists, a host behaves a certain way, a tool writes this file, a config lists that surface) is a claim you can verify, and verifying it is where the second-best findings come from. One known example is an article saying in bold not to generate a directory that the product generates anyway, because the vault's surface config lists it. Doctrine against product behavior, invisible until someone looked at both.

An audit that reads doctrine and never checks it against the filesystem is half an audit.

Each finding carries:

- The category.
- What it is, in one sentence.
- The evidence by name: article ids, file paths, line numbers, config keys, command output.
- Whether the fix is local to this chair or goes up the product loop.
- The recommended action.
- The date the finding was made.
- A mark if it needs the principal's decision rather than being yours to call.

Order by attention needed, not by category. A live hazard does not sit below a trim suggestion because of where it happened to land in the list.

**On a sweep,** each chair gets its own report, and then one roll-up whose only content is what repeats. That is the whole point of sweeping: a finding in one chair is a local fix, and the same finding in three is a pack bump. The roll-up is not a summary of the reports. Do not restate them.

**This output is a proposal.** Wrap-versus-not is `interaction/digest-then-drill`; that form fires here even when the article is off. A short report is the findings, each carrying what this section already names. A tree that would be a work session is wrapped. Either way, wait. Nothing is applied. The principal replies accept, reject, or hold per finding, or a number to expand. The fix is a different sitting.

## 8. Where a finding goes

- **Local to the chair.** Fix it in that chair, under that chair's constitution, in a separate sitting.
- **The pack's fault.** It goes up as a pack bump in the workbench that authors it. A subscriber chair does not fix a pack member by editing the installed copy, per `methodology/one-way-import`.
- **The product's fault.** An Insitu increment with its own spec.

Say which of the three each finding is. That routing is most of the value.

## 9. Re-reading an old finding

A finding is dated because doctrine moves. When you pick up a finding recorded earlier, check first whether it still says what it said. Both known cases moved between being written and being read: one named an article that no longer existed, and one had quietly acquired a guard that changed how serious it was.

Re-reading starts with verification, not with the fix.

## Do not

- Do not edit anything. Not an article, not a map, not a pack, not a protocol, not a gitignore. The output is a proposal and the fix is a different sitting.
- Do not mutate another chair's map, even as admin, even mid-sweep, without the named charter.
- Do not treat this as `validate`. That checks structure. This checks sense.
- Do not report size as a finding. `list_articles` already prints weight, and weight alone is not a problem.
- Do not manufacture findings to fill a category. Four empty categories is a valid result and a useful one.
