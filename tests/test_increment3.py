"""Unit and integration tests for obsidian-shim Increment 3 (write surface)."""

from __future__ import annotations

import pytest

from obsidian_shim.client import ObsidianAPIError
from obsidian_shim.tools import (
    create_file,
    append_content,
    patch_content,
    delete_file,
    _is_number,
)
from conftest import SCRATCH_NOTE, inject_client, mock_client


# =========================================================================
# Unit tests — mock the client
# =========================================================================

class TestCreateFileUnit:

    def test_existing_file_returns_error_no_write(self):
        client = mock_client()
        client.read_file.return_value = "existing content"
        inject_client(client)
        result = create_file("exists.md", "new stuff")
        assert "already exists" in result
        client.write_file.assert_not_called()

    def test_new_file_issues_put(self):
        client = mock_client()
        client.read_file.side_effect = ObsidianAPIError(404, "Not Found")
        inject_client(client)
        result = create_file("new.md", "hello world")
        assert "Created" in result
        client.write_file.assert_called_once_with("new.md", "hello world")

    def test_probe_non_404_reraises_without_writing(self):
        # A 500 during the existence probe must propagate, NOT be swallowed as
        # "file absent" — otherwise a transient read error could clobber an
        # existing file.
        client = mock_client()
        client.read_file.side_effect = ObsidianAPIError(500, "Internal Server Error")
        inject_client(client)
        with pytest.raises(ObsidianAPIError) as exc_info:
            create_file("note.md", "new stuff")
        assert exc_info.value.status_code == 500
        client.write_file.assert_not_called()


class TestAppendContentUnit:

    def test_issues_post(self):
        client = mock_client()
        inject_client(client)
        result = append_content("note.md", "\nnew line")
        assert "Appended" in result
        client.append_content.assert_called_once_with("note.md", "\nnew line")

    def test_error_returns_string(self):
        client = mock_client()
        client.append_content.side_effect = ObsidianAPIError(500, "Internal Server Error")
        inject_client(client)
        result = append_content("note.md", "text")
        assert "Error" in result
        assert "append failed" in result


class TestPatchContentUnit:

    def test_frontmatter_replace_scalar(self):
        client = mock_client()
        inject_client(client)
        result = patch_content("note.md", "new-value", "replace", "frontmatter", "status")
        assert "Patched" in result
        client.patch_content.assert_called_once_with(
            "note.md", "new-value", "replace", "frontmatter", "status",
            create_if_missing=False, content_type="text/markdown",
        )

    def test_frontmatter_append_json_array(self):
        client = mock_client()
        inject_client(client)
        result = patch_content("note.md", '["new-tag"]', "append", "frontmatter", "tags", create_if_missing=True)
        assert "Patched" in result
        client.patch_content.assert_called_once_with(
            "note.md", '["new-tag"]', "append", "frontmatter", "tags",
            create_if_missing=True, content_type="application/json",
        )

    def test_404_returns_error(self):
        client = mock_client()
        client.patch_content.side_effect = ObsidianAPIError(404, "Not Found")
        inject_client(client)
        result = patch_content("missing.md", "x", "replace", "frontmatter", "field")
        assert "not found" in result.lower()


class TestPatchContentTypeDetection:
    """The frontmatter content-type routing (tools.py) — JSON value shapes go
    out as application/json, everything else as text/markdown."""

    @staticmethod
    def _content_type_for(content: str, target_type: str = "frontmatter") -> str:
        client = mock_client()
        inject_client(client)
        patch_content("note.md", content, "replace", target_type, "field")
        # content_type is the last keyword arg the tool forwards to the client.
        _, kwargs = client.patch_content.call_args
        return kwargs["content_type"]

    # -- frontmatter: shapes that must route to application/json --------------

    @pytest.mark.parametrize("content", [
        '["a", "b"]',          # array
        '{"key": "value"}',    # object
        '"a quoted string"',   # JSON string
        "true",                 # bool
        "false",
        "null",                 # null
        "42",                   # integer
        "3.14",                 # float
        "-1.5e3",               # scientific notation
    ])
    def test_json_shapes_use_application_json(self, content):
        assert self._content_type_for(content) == "application/json"

    # -- frontmatter: shapes that must stay text/markdown ---------------------

    @pytest.mark.parametrize("content", [
        "draft",                # bare scalar word
        "published",
        "5 apples",             # starts with digit but not a number
        "true story",           # starts with 'true' but isn't the bool
        "",                     # empty
        "   ",                  # whitespace only
    ])
    def test_scalar_shapes_use_text_markdown(self, content):
        assert self._content_type_for(content) == "text/markdown"

    # -- non-frontmatter targets always stay text/markdown -------------------

    @pytest.mark.parametrize("target_type", ["heading", "block"])
    def test_non_frontmatter_targets_ignore_json_shape(self, target_type):
        # Even JSON-looking content goes out as markdown for heading/block.
        assert self._content_type_for('["x"]', target_type=target_type) == "text/markdown"

    def test_heading_target_forwards_headers_unchanged(self):
        client = mock_client()
        inject_client(client)
        result = patch_content(
            "note.md", "new text", "append", "heading", "Section A/Subsection"
        )
        assert "Patched" in result
        client.patch_content.assert_called_once_with(
            "note.md", "new text", "append", "heading", "Section A/Subsection",
            create_if_missing=False, content_type="text/markdown",
        )


class TestIsNumber:
    @pytest.mark.parametrize("s", ["42", "3.14", "-1.5e3", "0", "-0", "1_000"])
    def test_numbers(self, s):
        assert _is_number(s) is True

    @pytest.mark.parametrize("s", ["", "   ", "abc", "5 apples", "1,000", "true"])
    def test_non_numbers(self, s):
        assert _is_number(s) is False


class TestDeleteFileUnit:

    def test_confirm_false_returns_error_no_delete(self):
        client = mock_client()
        inject_client(client)
        result = delete_file("note.md", confirm=False)
        assert "requires confirm=true" in result
        client.delete_file.assert_not_called()

    def test_confirm_default_returns_error(self):
        client = mock_client()
        inject_client(client)
        result = delete_file("note.md")
        assert "requires confirm=true" in result
        client.delete_file.assert_not_called()

    def test_confirm_true_deletes(self):
        client = mock_client()
        inject_client(client)
        result = delete_file("note.md", confirm=True)
        assert "Deleted" in result
        client.delete_file.assert_called_once_with("note.md")

    def test_404_returns_error(self):
        client = mock_client()
        client.delete_file.side_effect = ObsidianAPIError(404, "Not Found")
        inject_client(client)
        result = delete_file("missing.md", confirm=True)
        assert "not found" in result.lower()


# =========================================================================
# Integration tests — live Obsidian Local REST API
# =========================================================================

@pytest.mark.integration
class TestIncrement3Integration:

    def test_create_file_new(self, scratch):
        inject_client(scratch)
        result = create_file(SCRATCH_NOTE, "# Brand New\n\nContent here.\n")
        assert "Created" in result
        content = scratch.read_file(SCRATCH_NOTE)
        assert content == "# Brand New\n\nContent here.\n"

    def test_create_file_no_overwrite(self, scratch):
        original = "# Original\n"
        scratch.write_file(SCRATCH_NOTE, original)
        inject_client(scratch)
        result = create_file(SCRATCH_NOTE, "# Overwrite attempt\n")
        assert "already exists" in result
        content = scratch.read_file(SCRATCH_NOTE)
        assert content == original

    def test_append_content_live(self, scratch):
        scratch.write_file(SCRATCH_NOTE, "Line one.\n")
        inject_client(scratch)
        result = append_content(SCRATCH_NOTE, "Line two.\n")
        assert "Appended" in result
        content = scratch.read_file(SCRATCH_NOTE)
        assert "Line one." in content
        assert "Line two." in content
        assert content.index("Line one.") < content.index("Line two.")

    def test_patch_frontmatter_add_tag(self, scratch):
        original = "---\ntitle: Test Note\ntags:\n  - existing\n---\n\n# Body\n\nContent.\n"
        scratch.write_file(SCRATCH_NOTE, original)
        inject_client(scratch)
        result = patch_content(SCRATCH_NOTE, '["new-tag"]', "append", "frontmatter", "tags")
        assert "Patched" in result
        updated = scratch.read_file(SCRATCH_NOTE)
        assert "new-tag" in updated
        assert "existing" in updated
        assert "# Body" in updated
        assert "Content." in updated

    def test_patch_frontmatter_set_field(self, scratch):
        original = "---\nstatus: draft\n---\n\n# Note\n"
        scratch.write_file(SCRATCH_NOTE, original)
        inject_client(scratch)
        result = patch_content(SCRATCH_NOTE, "published", "replace", "frontmatter", "status")
        assert "Patched" in result
        updated = scratch.read_file(SCRATCH_NOTE)
        assert "published" in updated
        assert "# Note" in updated

    def test_patch_frontmatter_create_if_missing(self, scratch):
        original = "---\ntitle: Test\n---\n\nBody.\n"
        scratch.write_file(SCRATCH_NOTE, original)
        inject_client(scratch)
        result = patch_content(
            SCRATCH_NOTE, '["project/active"]', "append", "frontmatter", "tags",
            create_if_missing=True,
        )
        assert "Patched" in result
        updated = scratch.read_file(SCRATCH_NOTE)
        assert "project/active" in updated

    def test_delete_file_confirm_false(self, scratch):
        scratch.write_file(SCRATCH_NOTE, "keep me\n")
        inject_client(scratch)
        result = delete_file(SCRATCH_NOTE, confirm=False)
        assert "requires confirm=true" in result
        content = scratch.read_file(SCRATCH_NOTE)
        assert content == "keep me\n"

    def test_delete_file_confirm_true(self, scratch):
        scratch.write_file(SCRATCH_NOTE, "delete me\n")
        inject_client(scratch)
        result = delete_file(SCRATCH_NOTE, confirm=True)
        assert "Deleted" in result
        with pytest.raises(ObsidianAPIError) as exc_info:
            scratch.read_file(SCRATCH_NOTE)
        assert exc_info.value.status_code == 404
