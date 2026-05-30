# Changelog

## 0.2.0 — 2026-05-30

### Increment 5 — Commands
- `list_commands` — list all available Obsidian commands
- `execute_command` — execute a command by ID (with destructive-action warning in docstring)
- Integration test verifying a bogus command ID surfaces the live API's 404 as the retryable "command not found" message (the guess-first/fall-back-to-`list_commands` contract)

### Test hardening (gap analysis follow-up)
- `patch_content` content-type detection now covered for all input shapes (array/object/quoted-string/bool/null/number → `application/json`; scalars/empty → `text/markdown`), plus heading/block targets and the `_is_number` helper
- `create_file` existence-probe now tested to reraise on non-404 errors instead of silently overwriting
- New `test_client.py` — unit coverage for `client.py` error translation (status, 300-char detail truncation, reason-phrase fallback) and JSON-key unwrapping (`files`/`commands`), runnable without a live vault
- `view` end-past-EOF clamping and non-404 reraise

### Increment 4 — Periodic notes
- `get_periodic_note` — current daily/weekly/monthly/quarterly/yearly note
- `get_recent_periodic_notes` — iterate backward through recent periodic notes
- Graceful handling when periodic notes plugin is not configured (error message, not crash)
- Improved tool docstrings for better MCP discoverability

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
