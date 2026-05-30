"""MCP tool definitions: view, str_replace, list_files."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from obsidian_shim.client import ObsidianClient, ObsidianAPIError

mcp_server = FastMCP("obsidian-shim")

# Lazily initialised on first tool call so env vars are read at runtime.
_client: ObsidianClient | None = None


def _get_client() -> ObsidianClient:
    global _client
    if _client is None:
        _client = ObsidianClient()
    return _client


# ---------------------------------------------------------------------------
# view
# ---------------------------------------------------------------------------

@mcp_server.tool()
def view(filepath: str, view_range: list[int] | None = None) -> str:
    """Read a file from the vault. Optionally return only a range of lines (1-indexed, inclusive)."""
    client = _get_client()
    try:
        content = client.read_file(filepath)
    except ObsidianAPIError as exc:
        if exc.status_code == 404:
            return f"Error: file not found: {filepath}"
        raise

    if view_range is None:
        return content

    if len(view_range) != 2:
        return "Error: view_range must be [start_line, end_line] (1-indexed, inclusive)"

    start, end = view_range
    lines = content.splitlines(keepends=True)
    total = len(lines)

    if start < 1 or end < start or start > total:
        return f"Error: invalid view_range [{start}, {end}] for file with {total} lines"

    end = min(end, total)
    selected = lines[start - 1 : end]
    numbered = "".join(f"{i}: {line}" for i, line in enumerate(selected, start=start))
    return numbered


# ---------------------------------------------------------------------------
# str_replace
# ---------------------------------------------------------------------------

def _str_replace_impl(
    client: ObsidianClient, filepath: str, old_str: str, new_str: str
) -> str:
    """Core str_replace logic, separated for testability."""
    content = client.read_file(filepath)

    count = content.count(old_str)
    if count == 0:
        raise ValueError("old_str not found")
    if count > 1:
        raise ValueError(f"old_str is not unique (found {count} times)")

    new_content = content.replace(old_str, new_str, 1)
    client.write_file(filepath, new_content)

    # Build a short confirmation showing context around the change.
    idx = new_content.find(new_str) if new_str else new_content.find(old_str)
    if idx == -1:
        # Deletion case: show a few chars around the removal point.
        idx = content.find(old_str)
        before = content[max(0, idx - 40) : idx]
        after = content[idx + len(old_str) : idx + len(old_str) + 40]
        return f"Deleted old_str. Context: ...{before}⏐{after}..."

    before = new_content[max(0, idx - 40) : idx]
    after_end = idx + len(new_str)
    after = new_content[after_end : after_end + 40]
    return f"Replaced. Context: ...{before}{new_str}{after}..."


@mcp_server.tool()
def str_replace(filepath: str, old_str: str, new_str: str) -> str:
    """Atomic find-and-replace of a unique string in a vault file.

    Reads the file, verifies old_str appears exactly once, replaces it with
    new_str, and writes the file back — all in one call. old_str may be
    multiline; new_str may be empty (deletion). The file's encoding and
    trailing-newline state are preserved byte-for-byte.
    """
    client = _get_client()
    try:
        return _str_replace_impl(client, filepath, old_str, new_str)
    except ObsidianAPIError as exc:
        if exc.status_code == 404:
            return f"Error: file not found: {filepath}"
        raise
    except ValueError as exc:
        return f"Error: {exc}"


# ---------------------------------------------------------------------------
# list_files
# ---------------------------------------------------------------------------

@mcp_server.tool()
def list_files(dirpath: str | None = None) -> list[str]:
    """List files and directories in the vault root or a subdirectory."""
    client = _get_client()
    return client.list_files(dirpath or "")
