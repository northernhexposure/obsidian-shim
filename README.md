# obsidian-shim

MCP stdio server for surgical, table-safe editing of an Obsidian vault via the [Local REST API](https://github.com/coddingtonbear/obsidian-local-rest-api) plugin.

## Why

The plugin's heading-targeted PATCH appends content to the *end* of a heading's section — past any `---` divider — which detaches inserted table rows from their table. This server uses a Claude-Code-style `str_replace` (find a unique string, replace it) to place edits exactly where they belong.

## Tools (Increment 1)

| Tool | Description |
|------|-------------|
| `view` | Read a file; optionally return a line range |
| `str_replace` | Atomic find-and-replace of a unique string |
| `list_files` | List files/directories in the vault |

## Configuration

| Variable | Default | Notes |
|----------|---------|-------|
| `OBSIDIAN_API_KEY` | *(required)* | Bearer token for the Local REST API plugin |
| `OBSIDIAN_HOST` | `127.0.0.1` | Loopback only |
| `OBSIDIAN_PORT` | `27123` | HTTP (not HTTPS) |

## Run

```bash
uv run --directory ~/Projects/obsidian-shim obsidian-shim
```

## License

MIT — see [LICENSE](LICENSE).
