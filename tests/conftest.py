"""Shared fixtures for obsidian-shim tests."""

from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest

from obsidian_shim.client import ObsidianClient

SCRATCH_NOTE = "_mcp-test.md"
SCRATCH_NOTE_2 = "_mcp-test-2.md"


# -- helpers ----------------------------------------------------------------

def inject_client(client):
    """Inject a client (real or mock) into the tools module."""
    import obsidian_shim.tools as m
    m._client = client


def mock_client(**overrides) -> MagicMock:
    """Create a MagicMock of ObsidianClient with optional attribute overrides."""
    client = MagicMock(spec=ObsidianClient)
    for attr, val in overrides.items():
        setattr(client, attr, val)
    return client


# -- fixtures ---------------------------------------------------------------

@pytest.fixture()
def live_client():
    """Authenticated ObsidianClient for integration tests. Skips if no key."""
    key = os.environ.get("OBSIDIAN_API_KEY")
    if not key:
        pytest.skip("OBSIDIAN_API_KEY not set")
    return ObsidianClient(api_key=key)


@pytest.fixture()
def scratch(live_client: ObsidianClient):
    """Yield the live client; clean up scratch notes after each test."""
    yield live_client
    for note in (SCRATCH_NOTE, SCRATCH_NOTE_2):
        try:
            live_client.delete_file(note)
        except Exception:
            pass
