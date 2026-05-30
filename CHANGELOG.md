# Changelog

## 0.1.0 — 2026-05-30

Initial release. Ten MCP tools replacing `mcp-obsidian` as the stdio server
behind the supergateway → cloudflared → claude.ai bridge.

### Increment 1 — Core edit tools
- `view` — read a file with optional line-range selection
- `str_replace` — atomic find-and-replace with uniqueness guard (the reason this project exists: places edits exactly where they belong, avoiding the plugin's heading-targeted PATCH which appends past `---` dividers)
- `list_files` — list vault files and directories

### Increment 2 — Read + search
- `get_file_contents` — full raw file content (distinct from `view`'s line-numbered output)
- `batch_get_file_contents` — multi-file read, resilient to per-file 404s
- `simple_search` — full-text vault search via `POST /search/simple/`

### Increment 3 — Write surface
- `create_file` — safe create (refuses to overwrite)
- `append_content` — append to end of file (creates if absent)
- `patch_content` — frontmatter-focused insert via `PATCH` (heading/block targets supported but documented as footgun-prone)
- `delete_file` — hard delete with `confirm=true` safety guard

### Housekeeping
- Shared test fixtures in `conftest.py`
- GitHub Actions CI (unit tests on Python 3.10 + 3.12)
- Connector cutover completed: LaunchAgent plist updated, supergateway serving on `:8765/mcp`
