# MCP host snippets

Insitu is one process and one vault. Set the vault with `INSITU_HOME`, or pass `--vault`. If neither is set, the server uses `~/.insitu`.

Replace the repo path with your checkout.

## Cursor (`~/.cursor/mcp.json` or project `.cursor/mcp.json`)

```json
{
  "mcpServers": {
    "insitu": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/path/to/insitu",
        "insitu"
      ],
      "env": {
        "INSITU_HOME": "/path/to/your/vault"
      }
    }
  }
}
```

## Claude Code (`~/.claude.json` mcpServers, or a project `.mcp.json`)

```json
{
  "mcpServers": {
    "insitu": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/path/to/insitu",
        "insitu",
        "--vault",
        "/path/to/your/vault"
      ]
    }
  }
}
```

## Grok (`~/.grok/config.toml`)

```toml
[mcp_servers.insitu]
command = "uv"
args = ["run", "--directory", "/path/to/insitu", "insitu"]

[mcp_servers.insitu.env]
INSITU_HOME = "/path/to/your/vault"
```

`INSITU_HOME` wins over `--vault` when both are set. Point demos at `examples/vault` in this repo.

Windows: use a normal path such as `C:\\Users\\you\\Documents\\workspace\\insitu` and a vault such as `C:\\Users\\you\\.insitu`.
