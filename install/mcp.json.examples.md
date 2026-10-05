# Server block

Insitu is one process and one vault. Set the vault with `INSITU_HOME`, or pass `--vault`. If neither is set, the server uses `~/.insitu`.

Set `INSITU_ROOT` to an install that has `nexus.md` when the project key should be the address from that file (`nexus` or `nexus/node`). The vault stays the one above. Leave `INSITU_ROOT` unset and the key stays the working-folder basename.

`INSITU_HOME` wins over `--vault` when both are set. Point demos at `examples/vault` in this repo.

Where this block is written is `install/README.md`. The host file, the format, and the key come from `platforms.yaml`. This page does not name them.

Replace the checkout path with this repo.

```yaml
command: uv
args:
  - run
  - --directory
  - /path/to/insitu
  - insitu
env:
  INSITU_HOME: /path/to/your/vault
```

When `format` is `json`, write that as an object under the definition's `key`. When `format` is `toml`, write it as a table under that key.

On Windows, write a normal absolute path. Do not leave a tilde in a host file that will not expand it.
