# Insitu (optional constitution hook)

This is insurance, not the injector. `materialize` never writes this file.

- Insitu holds standing "who you are here" guidance as stanzas and project-mapped skills, and composes a project protocol.
- Project key is this folder's basename.
- Treat generated `PROTOCOL.md` and host adapters (`.grok/rules/insitu-protocol.md`, `.claude/rules/insitu-protocol.md`, `.cursor/rules/insitu-protocol.mdc`) as binding. Do not edit them.
- If those files are missing or the header looks stale, call `materialize`. `materialize` never writes `AGENTS.md` or `CLAUDE.md`. Other missing host files are the router's job: retrieve the multi-platform pack and write them.
- If the user asks Insitu status of this folder, call `project_status`. Do not walk the other inspect tools for that. Do not call it at session start.
- Pull on-demand stanzas with `get_stanza` when the work needs one. Do not pull the on-demand list at session start. Use `list_stanzas` to see the catalog and sizes (what to include, what to trim). Do not call it at session start to load the core.
- Mapped skills are generated copies under `.grok/skills`, `.claude/skills`, and `.cursor/skills`. Treat them as binding for `/name`. Do not edit them. If a generated skill is missing or its stamp is stale, call `materialize`. Pull a skill body with `get_skill`. Use `list_skills` to see the catalog. Do not call `list_skills` at session start to load skills.
