"""MCP tool definitions for obsidian-shim (Increments 1–3)."""

from __future__ import annotations

import json

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


# ---------------------------------------------------------------------------
# get_file_contents
# ---------------------------------------------------------------------------

@mcp_server.tool()
def get_file_contents(filepath: str) -> str:
    """Read the full raw content of a vault file (no line numbers, no range)."""
    client = _get_client()
    try:
        return client.read_file(filepath)
    except ObsidianAPIError as exc:
        if exc.status_code == 404:
            return f"Error: file not found: {filepath}"
        raise


# ---------------------------------------------------------------------------
# batch_get_file_contents
# ---------------------------------------------------------------------------

@mcp_server.tool()
def batch_get_file_contents(filepaths: list[str]) -> str:
    """Read multiple vault files, concatenated with per-file headers.

    If a file is missing or errors, an inline error marker is included
    for that file and the rest continue normally.
    """
    client = _get_client()
    parts: list[str] = []
    for fp in filepaths:
        parts.append(f"# {fp}\n")
        try:
            content = client.read_file(fp)
            parts.append(content)
        except ObsidianAPIError as exc:
            if exc.status_code == 404:
                parts.append(f"[Error: file not found: {fp}]\n")
            else:
                parts.append(f"[Error: HTTP {exc.status_code}: {exc}]\n")
        parts.append("\n---\n")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# simple_search
# ---------------------------------------------------------------------------

@mcp_server.tool()
def simple_search(query: str, context_length: int = 100) -> list[dict]:
    """Search the vault for a text query. Returns filename, score, and match contexts."""
    client = _get_client()
    return client.search(query, context_length=context_length)


# ---------------------------------------------------------------------------
# create_file
# ---------------------------------------------------------------------------

@mcp_server.tool()
def create_file(filepath: str, content: str) -> str:
    """Create a new file in the vault. Refuses to overwrite an existing file."""
    client = _get_client()
    # Check existence first — safe in single-writer environment.
    try:
        client.read_file(filepath)
        return f"Error: file already exists: {filepath}"
    except ObsidianAPIError as exc:
        if exc.status_code != 404:
            raise
    # File does not exist — create it.
    client.write_file(filepath, content)
    return f"Created {filepath}"


# ---------------------------------------------------------------------------
# append_content
# ---------------------------------------------------------------------------

@mcp_server.tool()
def append_content(filepath: str, content: str) -> str:
    """Append content to the end of a vault file (creates the file if absent)."""
    client = _get_client()
    client.append_content(filepath, content)
    return f"Appended to {filepath}"


# ---------------------------------------------------------------------------
# patch_content
# ---------------------------------------------------------------------------

@mcp_server.tool()
def patch_content(
    filepath: str,
    content: str,
    operation: str,
    target_type: str,
    target: str,
    create_if_missing: bool = False,
) -> str:
    """Insert content into a vault file relative to a heading, block, or frontmatter field.

    This tool is primarily intended for **frontmatter** edits (e.g. setting a
    field value or appending tags). For frontmatter list fields like ``tags``,
    pass a JSON array string (e.g. ``'["new-tag"]'``) as ``content``.

    WARNING: For heading/block targets, append lands at the END of the section
    — past any ``---`` divider — which can misplace content. Use ``str_replace``
    for precise body edits instead.

    Args:
        filepath: Vault-relative path to the file.
        content: The content to insert. For frontmatter list fields, use a
            JSON array string (e.g. '["value"]').
        operation: "append", "prepend", or "replace".
        target_type: "frontmatter", "heading", or "block".
        target: The frontmatter field name, heading path, or block reference.
        create_if_missing: If True, create the target if it doesn't exist.
    """
    client = _get_client()

    # Determine content type: use application/json for frontmatter when the
    # content looks like a JSON value (array, object, number, bool, null).
    content_type = "text/markdown"
    if target_type == "frontmatter":
        stripped = content.strip()
        if stripped and stripped[0] in ('[', '{', '"') or stripped in ('true', 'false', 'null') or _is_number(stripped):
            content_type = "application/json"

    try:
        client.patch_content(
            filepath,
            content,
            operation,
            target_type,
            target,
            create_if_missing=create_if_missing,
            content_type=content_type,
        )
    except ObsidianAPIError as exc:
        if exc.status_code == 404:
            return f"Error: file or target not found: {filepath} / {target}"
        raise
    return f"Patched {target_type} '{target}' in {filepath} ({operation})"


def _is_number(s: str) -> bool:
    """Check if string looks like a JSON number."""
    try:
        float(s)
        return True
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# delete_file
# ---------------------------------------------------------------------------

@mcp_server.tool()
def delete_file(filepath: str, confirm: bool = False) -> str:
    """Delete a file from the vault. Requires confirm=True as a safety guard."""
    if not confirm:
        return "Error: deletion requires confirm=true"
    client = _get_client()
    try:
        client.delete_file(filepath)
    except ObsidianAPIError as exc:
        if exc.status_code == 404:
            return f"Error: file not found: {filepath}"
        raise
    return f"Deleted {filepath}"
