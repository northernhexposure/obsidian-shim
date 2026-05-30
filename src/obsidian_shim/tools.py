"""MCP tool definitions for obsidian-shim (Increments 1–3)."""

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
    """Read a vault file with optional line-range selection.

    Use this to inspect a specific section of a file (e.g. lines 10–25) or to
    get line-numbered output for orientation. For the full raw content without
    line numbers, use ``get_file_contents`` instead.

    Args:
        filepath: Vault-relative path (e.g. "Projects/todo.md").
        view_range: Optional two-element list ``[start, end]`` (1-indexed,
            inclusive). Omit to return the entire file as-is.
    """
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
    """Surgically replace one unique string in a vault file.

    This is the primary editing tool. It reads the file, verifies ``old_str``
    appears exactly once, replaces it with ``new_str``, and writes back
    atomically. Use this instead of ``patch_content`` for any body-text edit —
    it places content exactly where it belongs, even inside tables or above
    ``---`` dividers.

    - ``old_str`` may span multiple lines; include enough context to be unique.
    - ``new_str`` may be empty to delete ``old_str``.
    - Fails if ``old_str`` is not found or matches more than once.

    Args:
        filepath: Vault-relative path (e.g. "Projects/todo.md").
        old_str: The exact text to find (must appear exactly once).
        new_str: The replacement text (empty string = deletion).
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
    """List files and directories under a vault path.

    Use this to discover vault structure or find files by browsing. Returns a
    flat list of vault-relative paths. Pass no argument for the vault root, or
    a directory path to list its children.

    Args:
        dirpath: Vault-relative directory (e.g. "Projects"). Omit or pass
            empty string for the vault root.
    """
    client = _get_client()
    return client.list_files(dirpath or "")


# ---------------------------------------------------------------------------
# get_file_contents
# ---------------------------------------------------------------------------

@mcp_server.tool()
def get_file_contents(filepath: str) -> str:
    """Return the full raw content of a vault file.

    Use this when you need the complete file text for processing or analysis.
    Unlike ``view``, this returns raw content without line numbers, making it
    suitable for feeding into ``str_replace`` or other transformations.

    Args:
        filepath: Vault-relative path (e.g. "Projects/todo.md").
    """
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
    """Read multiple vault files in one call, concatenated with headers.

    Use this when you need content from several files at once (e.g. comparing
    notes or gathering context). Each file appears under a ``# filepath``
    header separated by ``---``. Missing files get an inline error marker
    without aborting the batch.

    Args:
        filepaths: List of vault-relative paths.
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
    """Full-text search across all vault files.

    Use this to find notes containing a word or phrase. Returns a list of
    matches, each with ``filename``, ``score``, and ``matches`` (context
    snippets around each hit). Use ``context_length`` to control how many
    characters of surrounding text are returned per match.

    Args:
        query: The text to search for (plain text, not regex).
        context_length: Characters of context around each match (default 100).
    """
    client = _get_client()
    return client.search(query, context_length=context_length)


# ---------------------------------------------------------------------------
# create_file
# ---------------------------------------------------------------------------

@mcp_server.tool()
def create_file(filepath: str, content: str) -> str:
    """Create a new file in the vault (will not overwrite existing files).

    Use this to write a brand-new note. If a file already exists at the path,
    this returns an error — use ``str_replace`` or ``patch_content`` to modify
    existing files, or ``append_content`` to add to the end.

    Args:
        filepath: Vault-relative path for the new file (e.g. "Projects/new.md").
        content: The full text content to write.
    """
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
    """Append content to the end of a vault file.

    Adds text after the file's existing content. Creates the file if it does
    not exist. Use this for journal-style additions or appending new sections.
    For inserting content at a specific location, use ``str_replace`` instead.

    Args:
        filepath: Vault-relative path (e.g. "Projects/log.md").
        content: Text to append (include leading newline if you want a blank
            line before the new content).
    """
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
    """Permanently delete a file from the vault.

    This is irreversible — the file is removed, not trashed. You must pass
    ``confirm=True`` or the call is rejected.

    Args:
        filepath: Vault-relative path of the file to delete.
        confirm: Must be True to proceed. Defaults to False as a safety guard.
    """
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
