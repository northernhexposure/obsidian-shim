"""Unit and integration tests for obsidian-shim Increment 2 (read + search)."""

from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest

from obsidian_shim.client import ObsidianClient, ObsidianAPIError
from obsidian_shim.tools import get_file_contents, batch_get_file_contents, simple_search


# =========================================================================
# Unit tests — mock the client
# =========================================================================

class TestGetFileContentsUnit:

    @staticmethod
    def _inject(client):
        import obsidian_shim.tools as m
        m._client = client

    def test_returns_raw_content(self):
        client = MagicMock(spec=ObsidianClient)
        client.read_file.return_value = "# Title\n\nBody text\n"
        self._inject(client)
        result = get_file_contents("note.md")
        assert result == "# Title\n\nBody text\n"
        client.read_file.assert_called_once_with("note.md")

    def test_404_returns_error(self):
        client = MagicMock(spec=ObsidianClient)
        client.read_file.side_effect = ObsidianAPIError(404, "Not Found")
        self._inject(client)
        result = get_file_contents("missing.md")
        assert "not found" in result.lower()


class TestBatchGetFileContentsUnit:

    @staticmethod
    def _inject(client):
        import obsidian_shim.tools as m
        m._client = client

    def test_concatenates_with_headers(self):
        client = MagicMock(spec=ObsidianClient)
        client.read_file.side_effect = lambda fp: f"content of {fp}"
        self._inject(client)
        result = batch_get_file_contents(["a.md", "b.md"])
        assert "# a.md" in result
        assert "content of a.md" in result
        assert "# b.md" in result
        assert "content of b.md" in result

    def test_one_404_does_not_fail_batch(self):
        client = MagicMock(spec=ObsidianClient)

        def fake_read(fp):
            if fp == "bad.md":
                raise ObsidianAPIError(404, "Not Found")
            return f"content of {fp}"

        client.read_file.side_effect = fake_read
        self._inject(client)
        result = batch_get_file_contents(["good.md", "bad.md", "also_good.md"])
        assert "content of good.md" in result
        assert "content of also_good.md" in result
        assert "# bad.md" in result
        assert "not found" in result.lower()


class TestSimpleSearchUnit:

    @staticmethod
    def _inject(client):
        import obsidian_shim.tools as m
        m._client = client

    def test_passes_context_length_and_returns_results(self):
        client = MagicMock(spec=ObsidianClient)
        fake_results = [
            {
                "filename": "note.md",
                "score": -1.5,
                "matches": [{"context": "...text...", "match_position": {"start": 3, "end": 7}}],
            }
        ]
        client.search.return_value = fake_results
        self._inject(client)
        result = simple_search("text", context_length=50)
        client.search.assert_called_once_with("text", context_length=50)
        assert result == fake_results

    def test_empty_results(self):
        client = MagicMock(spec=ObsidianClient)
        client.search.return_value = []
        self._inject(client)
        result = simple_search("xyznonexistent999")
        assert result == []


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
def scratch_note(live_client: ObsidianClient):
    """Create and clean up scratch notes around each test."""
    yield live_client
    for note in (SCRATCH_NOTE, SCRATCH_NOTE_2):
        try:
            live_client.delete_file(note)
        except Exception:
            pass


@pytest.mark.integration
class TestIncrement2Integration:

    @staticmethod
    def _inject(client):
        import obsidian_shim.tools as m
        m._client = client

    def test_get_file_contents_live(self, scratch_note: ObsidianClient):
        client = scratch_note
        content = "# Integration\n\nHello from get_file_contents — 🌿\n"
        client.write_file(SCRATCH_NOTE, content)
        self._inject(client)
        result = get_file_contents(SCRATCH_NOTE)
        assert result == content

    def test_batch_get_file_contents_live(self, scratch_note: ObsidianClient):
        client = scratch_note
        c1 = "# Note One\n\nFirst note.\n"
        c2 = "# Note Two\n\nSecond note.\n"
        client.write_file(SCRATCH_NOTE, c1)
        client.write_file(SCRATCH_NOTE_2, c2)
        self._inject(client)
        result = batch_get_file_contents([SCRATCH_NOTE, SCRATCH_NOTE_2])
        assert f"# {SCRATCH_NOTE}" in result
        assert "First note." in result
        assert f"# {SCRATCH_NOTE_2}" in result
        assert "Second note." in result

    def test_simple_search_finds_distinctive_term(self, scratch_note: ObsidianClient):
        client = scratch_note
        # Use a distinctive term unlikely to appear elsewhere
        distinctive = "xylophoneUnicorn7742"
        content = f"# Search Test\n\nThis note contains {distinctive} for testing.\n"
        client.write_file(SCRATCH_NOTE, content)

        import time
        time.sleep(0.5)  # brief pause for indexing

        self._inject(client)
        results = simple_search(distinctive)
        assert isinstance(results, list)
        assert len(results) > 0
        filenames = [r["filename"] for r in results]
        assert any(SCRATCH_NOTE in fn for fn in filenames), (
            f"Expected {SCRATCH_NOTE} in results, got: {filenames}"
        )

    def test_simple_search_no_hits(self, scratch_note: ObsidianClient):
        client = scratch_note
        self._inject(client)
        results = simple_search("zzzNonExistentGibberish99182736")
        assert isinstance(results, list)
        assert len(results) == 0
