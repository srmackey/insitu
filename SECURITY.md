# Security

## Reporting

Report a vulnerability privately with a GitHub Security Advisory on this repository. Do not open a public issue for a vault leak, a path escape, or a bug that writes files outside the vault and the folder the caller named.

## Trust boundary

- Transport is stdio. The host starts a local process as the user who launched it.
- The process reads and writes the vault: `INSITU_HOME`, or `~/.insitu` when that is unset. That tree holds articles, skills, project maps, packs, provenance, and config.
- `materialize` also writes generated protocol files and skill copies into the working folder the caller names, and only when that folder already exists. It does not create a folder.
- It does not run git, it does not start a shell, and it does not use the network.
- It does not take a credential.
- Delete tools remove vault objects only after a preview is confirmed.
