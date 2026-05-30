"""Unit and integration tests for obsidian-shim Increment 3 (write surface)."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, call

import pytest

from obsidian_shim.client import ObsidianClient, ObsidianAPIError
from obsidian_shim.tools import create_file, append_content, patch_content, delete_file


# =========================================================================
# Helpers
# =========================================================================

def _inject(client):
    import obsidian_shim.tools as m
    m._client = client


def _mock_client() -> MagicMock:
    return MagicMock(spec=ObsidianClient)


# =========================================================================
# Unit tests — mock the client
# =========================================================================

class TestCreateFileUnit:

    def test_existing_file_returns_error_no_write(self):
        client = _mock_client()
        client.read_file.return_value = "existing content"
        _inject(client)
        result = create_file("exists.md", "new stuff")
        assert "already exists" in result
        client.write_file.assert_not_called()

    def test_new_file_issues_put(self):
        client = _mock_client()
        client.read_file.side_effect = ObsidianAPIError(404, "Not Found")
        _inject(client)
        result = create_file("new.md", "hello world")
        assert "Created" in result
        client.write_file.assert_called_once_with("new.md", "hello world")


class TestAppendContentUnit:

    def test_issues_post(self):
        client = _mock_client()
        _inject(client)
        result = append_content("note.md", "\nnew line")
        assert "Appended" in result
        client.append_content.assert_called_once_with("note.md", "\nnew line")


class TestPatchContentUnit:

    def test_frontmatter_replace_scalar(self):
        client = _mock_client()
        _inject(client)
        result = patch_content("note.md", "new-value", "replace", "frontmatter", "status")
        assert "Patched" in result
        client.patch_content.assert_called_once_with(
            "note.md", "new-value", "replace", "frontmatter", "status",
            create_if_missing=False, content_type="text/markdown",
        )

    def test_frontmatter_append_json_array(self):
        client = _mock_client()
        _inject(client)
        result = patch_content("note.md", '["new-tag"]', "append", "frontmatter", "tags", create_if_missing=True)
        assert "Patched" in result
        client.patch_content.assert_called_once_with(
            "note.md", '["new-tag"]', "append", "frontmatter", "tags",
            create_if_missing=True, content_type="application/json",
        )

    def test_404_returns_error(self):
        client = _mock_client()
        client.patch_content.side_effect = ObsidianAPIError(404, "Not Found")
        _inject(client)
        result = patch_content("missing.md", "x", "replace", "frontmatter", "field")
        assert "not found" in result.lower()


class TestDeleteFileUnit:

    def test_confirm_false_returns_error_no_delete(self):
        client = _mock_client()
        _inject(client)
        result = delete_file("note.md", confirm=False)
        assert "requires confirm=true" in result
        client.delete_file.assert_not_called()

    def test_confirm_default_returns_error(self):
        client = _mock_client()
        _inject(client)
        result = delete_file("note.md")
        assert "requires confirm=true" in result
        client.delete_file.assert_not_called()

    def test_confirm_true_deletes(self):
        client = _mock_client()
        _inject(client)
        result = delete_file("note.md", confirm=True)
        assert "Deleted" in result
        client.delete_file.assert_called_once_with("note.md")

    def test_404_returns_error(self):
        client = _mock_client()
        client.delete_file.side_effect = ObsidianAPIError(404, "Not Found")
        _inject(client)
        result = delete_file("missing.md", confirm=True)
        assert "not found" in result.lower()


# =========================================================================
# Integration tests — live Obsidian Local REST API
# =========================================================================

SCRATCH_NOTE = "_mcp-test.md"
SCRATCH_NOTE_2 = "_mcp-test-2.md"


@pytest.fixture()
def live_client():
    key = os.environ.get("OBSIDIAN_API_KEY")
    if not key:
        pytest.skip("OBSIDIAN_API_KEY not set")
    return ObsidianClient(api_key=key)


@pytest.fixture()
def scratch(live_client: ObsidianClient):
    """Clean up scratch notes after each test."""
    yield live_client
    for note in (SCRATCH_NOTE, SCRATCH_NOTE_2):
        try:
            live_client.delete_file(note)
        except Exception:
            pass


@pytest.mark.integration
class TestIncrement3Integration:

    @staticmethod
    def _inject(client):
        import obsidian_shim.tools as m
        m._client = client

    # -- create_file --------------------------------------------------------

    def test_create_file_new(self, scratch: ObsidianClient):
        client = scratch
        self._inject(client)
        result = create_file(SCRATCH_NOTE, "# Brand New\n\nContent here.\n")
        assert "Created" in result
        content = client.read_file(SCRATCH_NOTE)
        assert content == "# Brand New\n\nContent here.\n"

    def test_create_file_no_overwrite(self, scratch: ObsidianClient):
        client = scratch
        original = "# Original\n"
        client.write_file(SCRATCH_NOTE, original)
        self._inject(client)
        result = create_file(SCRATCH_NOTE, "# Overwrite attempt\n")
        assert "already exists" in result
        # Original content unchanged
        content = client.read_file(SCRATCH_NOTE)
        assert content == original

    # -- append_content -----------------------------------------------------

    def test_append_content_live(self, scratch: ObsidianClient):
        client = scratch
        client.write_file(SCRATCH_NOTE, "Line one.\n")
        self._inject(client)
        result = append_content(SCRATCH_NOTE, "Line two.\n")
        assert "Appended" in result
        content = client.read_file(SCRATCH_NOTE)
        assert "Line one." in content
        assert "Line two." in content
        # Appended content should come after original
        assert content.index("Line one.") < content.index("Line two.")

    # -- patch_content (frontmatter) ----------------------------------------

    def test_patch_frontmatter_add_tag(self, scratch: ObsidianClient):
        client = scratch
        original = "---\ntitle: Test Note\ntags:\n  - existing\n---\n\n# Body\n\nContent.\n"
        client.write_file(SCRATCH_NOTE, original)
        self._inject(client)

        result = patch_content(
            SCRATCH_NOTE,
            '["new-tag"]',
            "append",
            "frontmatter",
            "tags",
        )
        assert "Patched" in result

        updated = client.read_file(SCRATCH_NOTE)
        assert "new-tag" in updated
        assert "existing" in updated
        # Body should be untouched
        assert "# Body" in updated
        assert "Content." in updated

    def test_patch_frontmatter_set_field(self, scratch: ObsidianClient):
        client = scratch
        original = "---\nstatus: draft\n---\n\n# Note\n"
        client.write_file(SCRATCH_NOTE, original)
        self._inject(client)

        result = patch_content(
            SCRATCH_NOTE,
            "published",
            "replace",
            "frontmatter",
            "status",
        )
        assert "Patched" in result

        updated = client.read_file(SCRATCH_NOTE)
        assert "published" in updated
        assert "# Note" in updated

    def test_patch_frontmatter_create_if_missing(self, scratch: ObsidianClient):
        client = scratch
        original = "---\ntitle: Test\n---\n\nBody.\n"
        client.write_file(SCRATCH_NOTE, original)
        self._inject(client)

        result = patch_content(
            SCRATCH_NOTE,
            '["project/active"]',
            "append",
            "frontmatter",
            "tags",
            create_if_missing=True,
        )
        assert "Patched" in result

        updated = client.read_file(SCRATCH_NOTE)
        assert "project/active" in updated

    # -- delete_file --------------------------------------------------------

    def test_delete_file_confirm_false(self, scratch: ObsidianClient):
        client = scratch
        client.write_file(SCRATCH_NOTE, "keep me\n")
        self._inject(client)
        result = delete_file(SCRATCH_NOTE, confirm=False)
        assert "requires confirm=true" in result
        # File still present
        content = client.read_file(SCRATCH_NOTE)
        assert content == "keep me\n"

    def test_delete_file_confirm_true(self, scratch: ObsidianClient):
        client = scratch
        client.write_file(SCRATCH_NOTE, "delete me\n")
        self._inject(client)
        result = delete_file(SCRATCH_NOTE, confirm=True)
        assert "Deleted" in result
        # File should be gone
        with pytest.raises(ObsidianAPIError) as exc_info:
            client.read_file(SCRATCH_NOTE)
        assert exc_info.value.status_code == 404
