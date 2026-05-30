"""Unit and integration tests for obsidian-shim Increment 1."""

from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest

from obsidian_shim.client import ObsidianClient
from obsidian_shim.tools import _str_replace_impl


# =========================================================================
# Unit tests — mock the client, test str_replace logic
# =========================================================================

class TestStrReplaceUnit:
    """str_replace logic with a mocked ObsidianClient."""

    @staticmethod
    def _mock_client(content: str) -> MagicMock:
        client = MagicMock(spec=ObsidianClient)
        client.read_file.return_value = content
        return client

    def test_zero_matches_raises(self):
        client = self._mock_client("hello world")
        with pytest.raises(ValueError, match="old_str not found"):
            _str_replace_impl(client, "note.md", "missing", "x")
        client.write_file.assert_not_called()

    def test_multiple_matches_raises(self):
        client = self._mock_client("aaa bbb aaa")
        with pytest.raises(ValueError, match=r"not unique \(found 2 times\)"):
            _str_replace_impl(client, "note.md", "aaa", "x")
        client.write_file.assert_not_called()

    def test_exactly_one_match_succeeds(self):
        client = self._mock_client("hello world")
        result = _str_replace_impl(client, "note.md", "world", "there")
        client.write_file.assert_called_once_with("note.md", "hello there")
        assert "Replaced" in result

    def test_empty_new_str_deletes(self):
        client = self._mock_client("hello cruel world")
        result = _str_replace_impl(client, "note.md", "cruel ", "")
        client.write_file.assert_called_once_with("note.md", "hello world")
        assert "Deleted" in result

    def test_multiline_old_str(self):
        content = "line1\nline2\nline3\n"
        client = self._mock_client(content)
        _str_replace_impl(client, "note.md", "line1\nline2", "replaced")
        client.write_file.assert_called_once_with("note.md", "replaced\nline3\n")

    def test_unicode_roundtrip(self):
        content = "Em-dash — and emoji 🌿 and accented café\n"
        client = self._mock_client(content)
        _str_replace_impl(client, "note.md", "café", "naïve")
        expected = "Em-dash — and emoji 🌿 and accented naïve\n"
        client.write_file.assert_called_once_with("note.md", expected)

    def test_trailing_newline_preserved(self):
        # File WITH trailing newline
        content_with = "hello\n"
        client = self._mock_client(content_with)
        _str_replace_impl(client, "note.md", "hello", "goodbye")
        client.write_file.assert_called_once_with("note.md", "goodbye\n")

    def test_no_trailing_newline_preserved(self):
        # File WITHOUT trailing newline
        content_without = "hello"
        client = self._mock_client(content_without)
        _str_replace_impl(client, "note.md", "hello", "goodbye")
        client.write_file.assert_called_once_with("note.md", "goodbye")


# =========================================================================
# Integration tests — live Obsidian Local REST API on 127.0.0.1:27123
# =========================================================================

SCRATCH_NOTE = "_mcp-test.md"

pytestmark_integration = pytest.mark.integration


def _require_api_key():
    key = os.environ.get("OBSIDIAN_API_KEY")
    if not key:
        pytest.skip("OBSIDIAN_API_KEY not set")
    return key


@pytest.fixture()
def live_client():
    key = _require_api_key()
    return ObsidianClient(api_key=key)


@pytest.fixture(autouse=False)
def scratch_note(live_client: ObsidianClient):
    """Create and clean up the scratch note around each test."""
    yield live_client
    # Cleanup — ignore 404 if the test already deleted it
    try:
        live_client.delete_file(SCRATCH_NOTE)
    except Exception:
        pass


@pytest.mark.integration
class TestIntegration:

    # -- view ---------------------------------------------------------------

    def test_view_roundtrip(self, scratch_note: ObsidianClient):
        client = scratch_note
        content = "# Hello\n\nSome content with — em-dash and 🌿\n"
        client.write_file(SCRATCH_NOTE, content)

        from obsidian_shim.tools import _get_client
        import obsidian_shim.tools as tools_mod
        tools_mod._client = client  # inject live client

        from obsidian_shim.tools import view
        result = view(SCRATCH_NOTE)
        assert result == content

    def test_view_range(self, scratch_note: ObsidianClient):
        client = scratch_note
        content = "line1\nline2\nline3\nline4\nline5\n"
        client.write_file(SCRATCH_NOTE, content)

        import obsidian_shim.tools as tools_mod
        tools_mod._client = client

        from obsidian_shim.tools import view
        result = view(SCRATCH_NOTE, view_range=[2, 4])
        assert "2: line2" in result
        assert "3: line3" in result
        assert "4: line4" in result
        assert "1: line1" not in result
        assert "5: line5" not in result

    def test_view_file_not_found(self, scratch_note: ObsidianClient):
        client = scratch_note
        import obsidian_shim.tools as tools_mod
        tools_mod._client = client

        from obsidian_shim.tools import view
        result = view("_nonexistent-file-12345.md")
        assert "not found" in result.lower()

    # -- list_files ---------------------------------------------------------

    def test_list_files_root(self, scratch_note: ObsidianClient):
        client = scratch_note
        import obsidian_shim.tools as tools_mod
        tools_mod._client = client

        from obsidian_shim.tools import list_files
        result = list_files()
        assert isinstance(result, list)
        assert len(result) > 0

    # -- str_replace --------------------------------------------------------

    def test_str_replace_live(self, scratch_note: ObsidianClient):
        client = scratch_note
        content = "alpha beta gamma\n"
        client.write_file(SCRATCH_NOTE, content)

        import obsidian_shim.tools as tools_mod
        tools_mod._client = client

        from obsidian_shim.tools import str_replace
        result = str_replace(SCRATCH_NOTE, "beta", "BETA")
        assert "Error" not in result

        updated = client.read_file(SCRATCH_NOTE)
        assert updated == "alpha BETA gamma\n"

    # -- THE CRITICAL CASE: table above divider -----------------------------

    def test_table_above_divider(self, scratch_note: ObsidianClient):
        """str_replace inserts a new row inside the table, NOT below the --- divider.

        This is the exact failure from 2026-05-29 that this project exists to fix.
        """
        client = scratch_note

        original = (
            "# Tracker\n"
            "\n"
            "| Date | Status |\n"
            "| --- | --- |\n"
            "| 2026-05-28 | Done |\n"
            "| 2026-05-29 | Active |\n"
            "\n"
            "---\n"
            "\n"
            "## Next\n"
            "\n"
            "Future plans here.\n"
        )
        client.write_file(SCRATCH_NOTE, original)

        import obsidian_shim.tools as tools_mod
        tools_mod._client = client

        from obsidian_shim.tools import str_replace

        # Replace the last row with itself + a new row appended.
        old = "| 2026-05-29 | Active |"
        new = "| 2026-05-29 | Active |\n| 2026-05-30 | Planned |"

        result = str_replace(SCRATCH_NOTE, old, new)
        assert "Error" not in result, f"str_replace failed: {result}"

        updated = client.read_file(SCRATCH_NOTE)

        # The new row must be directly under the old last row, inside the table.
        lines = updated.splitlines()

        # Find the positions of key elements.
        new_row_idx = None
        divider_idx = None
        next_heading_idx = None
        for i, line in enumerate(lines):
            if "2026-05-30" in line:
                new_row_idx = i
            if line.strip() == "---" and i > 3:  # skip the table header separator
                divider_idx = i
            if line.strip() == "## Next":
                next_heading_idx = i

        assert new_row_idx is not None, "New row not found in output"
        assert divider_idx is not None, "Divider --- not found in output"
        assert next_heading_idx is not None, "## Next heading not found"

        # Critical assertions:
        assert new_row_idx < divider_idx, (
            f"New row (line {new_row_idx}) must be ABOVE divider (line {divider_idx}).\n"
            f"Full content:\n{updated}"
        )
        assert divider_idx < next_heading_idx, (
            f"Divider must be above ## Next heading.\nFull content:\n{updated}"
        )

        # The row directly before the new row should be the old last row.
        assert "2026-05-29" in lines[new_row_idx - 1], (
            "New row should be directly below the 2026-05-29 row"
        )

        # The structure after the table should be: blank, ---, blank, ## Next
        assert lines[new_row_idx + 1].strip() == "", "Blank line expected after table"
        assert lines[new_row_idx + 2].strip() == "---", "Divider expected after blank"
        assert lines[new_row_idx + 3].strip() == "", "Blank line expected after divider"
        assert lines[new_row_idx + 4].strip() == "## Next", "## Next expected after blank"
