"""Unit and integration tests for obsidian-shim Increment 1."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from obsidian_shim.client import ObsidianClient, ObsidianAPIError
from obsidian_shim.tools import _str_replace_impl, view, str_replace, list_files
from conftest import SCRATCH_NOTE, inject_client, mock_client


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
        with pytest.raises(ValueError, match="search text not found"):
            _str_replace_impl(client, "note.md", "missing", "x")
        client.write_file.assert_not_called()

    def test_multiple_matches_raises(self):
        client = self._mock_client("aaa bbb aaa")
        with pytest.raises(ValueError, match=r"not unique \(2 matches\)"):
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
        content_with = "hello\n"
        client = self._mock_client(content_with)
        _str_replace_impl(client, "note.md", "hello", "goodbye")
        client.write_file.assert_called_once_with("note.md", "goodbye\n")

    def test_no_trailing_newline_preserved(self):
        content_without = "hello"
        client = self._mock_client(content_without)
        _str_replace_impl(client, "note.md", "hello", "goodbye")
        client.write_file.assert_called_once_with("note.md", "goodbye")


# =========================================================================
# Unit tests — str_replace tool-level error handling
# =========================================================================

class TestStrReplaceTool:

    def test_404_returns_error(self):
        client = mock_client()
        client.read_file.side_effect = ObsidianAPIError(404, "Not Found")
        inject_client(client)
        result = str_replace("missing.md", "old", "new")
        assert "Error" in result
        assert "not found" in result.lower()

    def test_unexpected_status_reraises(self):
        client = mock_client()
        client.read_file.side_effect = ObsidianAPIError(503, "Service Unavailable")
        inject_client(client)
        with pytest.raises(ObsidianAPIError):
            str_replace("note.md", "old", "new")


# =========================================================================
# Unit tests — view validation
# =========================================================================

class TestViewUnit:

    def test_view_range_wrong_length(self):
        client = mock_client()
        client.read_file.return_value = "line1\nline2\nline3\n"
        inject_client(client)
        result = view("note.md", view_range=[1])
        assert "Error" in result
        assert "view_range" in result

    def test_view_range_invalid_bounds(self):
        client = mock_client()
        client.read_file.return_value = "line1\nline2\nline3\n"
        inject_client(client)
        result = view("note.md", view_range=[5, 10])
        assert "Error" in result
        assert "invalid view_range" in result

    def test_view_range_end_before_start(self):
        client = mock_client()
        client.read_file.return_value = "line1\nline2\nline3\n"
        inject_client(client)
        result = view("note.md", view_range=[3, 1])
        assert "Error" in result
        assert "invalid view_range" in result

    def test_view_range_end_past_eof_clamps(self):
        # end beyond the last line is clamped, not an error.
        client = mock_client()
        client.read_file.return_value = "line1\nline2\nline3\n"
        inject_client(client)
        result = view("note.md", view_range=[2, 99])
        assert "Error" not in result
        assert "2: line2" in result
        assert "3: line3" in result
        assert "1: line1" not in result

    def test_non_404_error_reraises(self):
        client = mock_client()
        client.read_file.side_effect = ObsidianAPIError(503, "Service Unavailable")
        inject_client(client)
        with pytest.raises(ObsidianAPIError):
            view("note.md")


# =========================================================================
# Unit tests — list_files error handling
# =========================================================================

class TestListFilesUnit:

    def test_404_returns_error(self):
        client = mock_client()
        client.list_files.side_effect = ObsidianAPIError(404, "Not Found")
        inject_client(client)
        result = list_files("nonexistent/dir")
        assert "Error" in result
        assert "not found" in result.lower()

    def test_unexpected_status_reraises(self):
        client = mock_client()
        client.list_files.side_effect = ObsidianAPIError(503, "Service Unavailable")
        inject_client(client)
        with pytest.raises(ObsidianAPIError):
            list_files("some/dir")


# =========================================================================
# Integration tests — live Obsidian Local REST API on 127.0.0.1:27123
# =========================================================================

@pytest.mark.integration
class TestIntegration:

    def test_view_roundtrip(self, scratch):
        content = "# Hello\n\nSome content with — em-dash and 🌿\n"
        scratch.write_file(SCRATCH_NOTE, content)
        inject_client(scratch)
        result = view(SCRATCH_NOTE)
        assert result == content

    def test_view_range(self, scratch):
        content = "line1\nline2\nline3\nline4\nline5\n"
        scratch.write_file(SCRATCH_NOTE, content)
        inject_client(scratch)
        result = view(SCRATCH_NOTE, view_range=[2, 4])
        assert "2: line2" in result
        assert "3: line3" in result
        assert "4: line4" in result
        assert "1: line1" not in result
        assert "5: line5" not in result

    def test_view_file_not_found(self, scratch):
        inject_client(scratch)
        result = view("_nonexistent-file-12345.md")
        assert "not found" in result.lower()

    def test_list_files_root(self, scratch):
        inject_client(scratch)
        result = list_files()
        assert isinstance(result, list)
        assert len(result) > 0

    def test_str_replace_live(self, scratch):
        content = "alpha beta gamma\n"
        scratch.write_file(SCRATCH_NOTE, content)
        inject_client(scratch)
        result = str_replace(SCRATCH_NOTE, "beta", "BETA")
        assert "Error" not in result
        updated = scratch.read_file(SCRATCH_NOTE)
        assert updated == "alpha BETA gamma\n"

    def test_table_above_divider(self, scratch):
        """str_replace inserts a new row inside the table, NOT below the --- divider.

        This is the exact failure from 2026-05-29 that this project exists to fix.
        """
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
        scratch.write_file(SCRATCH_NOTE, original)
        inject_client(scratch)

        old = "| 2026-05-29 | Active |"
        new = "| 2026-05-29 | Active |\n| 2026-05-30 | Planned |"
        result = str_replace(SCRATCH_NOTE, old, new)
        assert "Error" not in result, f"str_replace failed: {result}"

        updated = scratch.read_file(SCRATCH_NOTE)
        lines = updated.splitlines()

        new_row_idx = None
        divider_idx = None
        next_heading_idx = None
        for i, line in enumerate(lines):
            if "2026-05-30" in line:
                new_row_idx = i
            if line.strip() == "---" and i > 3:
                divider_idx = i
            if line.strip() == "## Next":
                next_heading_idx = i

        assert new_row_idx is not None, "New row not found in output"
        assert divider_idx is not None, "Divider --- not found in output"
        assert next_heading_idx is not None, "## Next heading not found"

        assert new_row_idx < divider_idx, (
            f"New row (line {new_row_idx}) must be ABOVE divider (line {divider_idx}).\n"
            f"Full content:\n{updated}"
        )
        assert divider_idx < next_heading_idx, (
            f"Divider must be above ## Next heading.\nFull content:\n{updated}"
        )
        assert "2026-05-29" in lines[new_row_idx - 1], (
            "New row should be directly below the 2026-05-29 row"
        )
        assert lines[new_row_idx + 1].strip() == "", "Blank line expected after table"
        assert lines[new_row_idx + 2].strip() == "---", "Divider expected after blank"
        assert lines[new_row_idx + 3].strip() == "", "Blank line expected after divider"
        assert lines[new_row_idx + 4].strip() == "## Next", "## Next expected after blank"
