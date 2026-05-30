"""Unit tests for the REST client (client.py).

These exercise the thin glue — error translation and JSON-key unwrapping —
without needing a live vault, so CI (unit-only) catches plugin-shape drift.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest

from obsidian_shim.client import ObsidianClient, ObsidianAPIError, PeriodicNoteResult


def _client(monkeypatch) -> ObsidianClient:
    """An ObsidianClient whose underlying httpx.Client is a mock."""
    monkeypatch.setenv("OBSIDIAN_API_KEY", "test-key")
    c = ObsidianClient(api_key="test-key")
    c._client = MagicMock()
    return c


# ===========================================================================
# _raise_for_status — error translation
# ===========================================================================

class TestRaiseForStatus:

    def test_ok_status_does_not_raise(self, monkeypatch):
        c = _client(monkeypatch)
        c._raise_for_status(httpx.Response(200, text="fine"))  # no exception

    def test_4xx_raises_with_status_and_detail(self, monkeypatch):
        c = _client(monkeypatch)
        with pytest.raises(ObsidianAPIError) as exc_info:
            c._raise_for_status(httpx.Response(404, text="Note not found"))
        assert exc_info.value.status_code == 404
        assert "Note not found" in str(exc_info.value)

    def test_detail_truncated_to_300_chars(self, monkeypatch):
        c = _client(monkeypatch)
        long_body = "x" * 1000
        with pytest.raises(ObsidianAPIError) as exc_info:
            c._raise_for_status(httpx.Response(500, text=long_body))
        # Message is "HTTP 500: " + at most 300 chars of body.
        assert str(exc_info.value).count("x") == 300

    def test_empty_body_falls_back_to_reason_phrase(self, monkeypatch):
        c = _client(monkeypatch)
        with pytest.raises(ObsidianAPIError) as exc_info:
            c._raise_for_status(httpx.Response(503, text=""))
        assert "Service Unavailable" in str(exc_info.value)


# ===========================================================================
# JSON-key unwrapping — the shapes that break on plugin API changes
# ===========================================================================

class TestJsonUnwrapping:

    def test_list_files_unwraps_files_key(self, monkeypatch):
        c = _client(monkeypatch)
        c._client.get.return_value = httpx.Response(200, json={"files": ["a.md", "b/"]})
        assert c.list_files() == ["a.md", "b/"]

    def test_list_commands_unwraps_commands_key(self, monkeypatch):
        c = _client(monkeypatch)
        c._client.get.return_value = httpx.Response(
            200, json={"commands": [{"id": "app:x", "name": "X"}]}
        )
        assert c.list_commands() == [{"id": "app:x", "name": "X"}]

    def test_search_returns_raw_json_array(self, monkeypatch):
        c = _client(monkeypatch)
        c._client.post.return_value = httpx.Response(200, json=[{"filename": "n.md"}])
        assert c.search("q") == [{"filename": "n.md"}]


# ===========================================================================
# Content passthrough + periodic note header extraction
# ===========================================================================

class TestContentMethods:

    def test_read_file_returns_text(self, monkeypatch):
        c = _client(monkeypatch)
        c._client.get.return_value = httpx.Response(200, text="# Title\nbody")
        assert c.read_file("note.md") == "# Title\nbody"

    def test_read_file_propagates_404(self, monkeypatch):
        c = _client(monkeypatch)
        c._client.get.return_value = httpx.Response(404, text="Not Found")
        with pytest.raises(ObsidianAPIError) as exc_info:
            c.read_file("missing.md")
        assert exc_info.value.status_code == 404

    def test_get_periodic_note_extracts_content_location(self, monkeypatch):
        c = _client(monkeypatch)
        c._client.get.return_value = httpx.Response(
            200, text="# Today", headers={"Content-Location": "Daily/2026-05-30.md"}
        )
        result = c.get_periodic_note("daily")
        assert isinstance(result, PeriodicNoteResult)
        assert result.content == "# Today"
        assert result.filepath == "Daily/2026-05-30.md"

    def test_get_periodic_note_missing_header_yields_empty_filepath(self, monkeypatch):
        c = _client(monkeypatch)
        c._client.get.return_value = httpx.Response(200, text="# Today")
        result = c.get_periodic_note("daily")
        assert result.filepath == ""

    def test_execute_command_raises_on_404(self, monkeypatch):
        c = _client(monkeypatch)
        c._client.post.return_value = httpx.Response(404, text="Command not found")
        with pytest.raises(ObsidianAPIError) as exc_info:
            c.execute_command("bogus:id")
        assert exc_info.value.status_code == 404
