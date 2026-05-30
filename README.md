# obsidian-shim

MCP stdio server for surgical, table-safe editing of an Obsidian vault via the [Local REST API](https://github.com/coddingtonbear/obsidian-local-rest-api) plugin.

## Why

The plugin's heading-targeted PATCH appends content to the *end* of a heading's section — past any `---` divider — which detaches inserted table rows from their table. This server uses a Claude-Code-style `str_replace` (find a unique string, replace it) to place edits exactly where they belong.

## Tools

| Tool | Description |
|------|-------------|
| `view` | Read a file; optionally return a 1-indexed line range with line numbers |
| `str_replace` | Atomic find-and-replace of a unique string (the core edit primitive) |
| `list_files` | List files and directories in the vault root or a subdirectory |
| `get_file_contents` | Read the full raw content of a file |
| `batch_get_file_contents` | Read multiple files, concatenated with per-file headers (resilient to 404s) |
| `simple_search` | Full-text search across the vault; returns filename, score, and match contexts |
| `create_file` | Create a new file (refuses to overwrite existing files) |
| `append_content` | Append content to the end of a file (creates the file if absent) |
| `patch_content` | Insert content relative to a heading, block, or frontmatter field |
| `delete_file` | Delete a file (requires `confirm=true` as a safety guard) |
| `get_periodic_note` | Get the current daily/weekly/monthly/quarterly/yearly note |
| `get_recent_periodic_notes` | Walk backward through recent periodic notes (optionally with content) |
| `list_commands` | List all available Obsidian command IDs and names |
| `execute_command` | Execute an Obsidian command by ID (with a destructive-action warning) |

## Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/)
- [Obsidian](https://obsidian.md/) with the [Local REST API](https://github.com/coddingtonbear/obsidian-local-rest-api) plugin running on loopback

## Configuration

Set these environment variables:

| Variable | Default | Notes |
|----------|---------|-------|
| `OBSIDIAN_API_KEY` | *(required)* | Bearer token from the Local REST API plugin settings |
| `OBSIDIAN_HOST` | `127.0.0.1` | Loopback only |
| `OBSIDIAN_PORT` | `27123` | HTTP (not HTTPS) |

## Run

```bash
export OBSIDIAN_API_KEY="your-api-key-here"
uv run --directory ~/Projects/obsidian-shim obsidian-shim
```

The server communicates over stdio using the [Model Context Protocol](https://modelcontextprotocol.io/).

## Testing

```bash
# Unit tests (no live Obsidian needed)
uv run --with pytest pytest tests/ -k "not integration"

# Integration tests (requires a running Local REST API plugin)
export OBSIDIAN_API_KEY="your-api-key-here"
uv run --with pytest pytest tests/ -m integration
```

## License

MIT — see [LICENSE](LICENSE).
