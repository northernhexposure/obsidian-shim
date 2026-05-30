"""Tests for periodic note tools (get_periodic_note, get_recent_periodic_notes)."""

from __future__ import annotations

import datetime

import pytest

from obsidian_shim.client import ObsidianAPIError, PeriodicNoteResult
from obsidian_shim.tools import get_periodic_note, get_recent_periodic_notes, _step_back
from conftest import inject_client, mock_client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _note(content: str = "", filepath: str = "") -> PeriodicNoteResult:
    return PeriodicNoteResult(content=content, filepath=filepath)


def _freeze_today(monkeypatch, date: datetime.date):
    """Patch datetime.date.today() in tools module while keeping real date/timedelta."""
    monkeypatch.setattr(
        "obsidian_shim.tools.datetime",
        type("dt", (), {
            "date": type("d", (datetime.date,), {
                "today": staticmethod(lambda: date),
            }),
            "timedelta": datetime.timedelta,
        }),
    )


# ===========================================================================
# Unit tests — get_periodic_note
# ===========================================================================

class TestGetPeriodicNote:
    def test_returns_content(self):
        client = mock_client()
        client.get_periodic_note.return_value = _note(content="# Today\nDid stuff")
        inject_client(client)

        result = get_periodic_note("daily")
        assert result == "# Today\nDid stuff"
        client.get_periodic_note.assert_called_once_with("daily")

    def test_invalid_period(self):
        inject_client(mock_client())
        result = get_periodic_note("biweekly")
        assert "invalid period" in result

    def test_404_no_note(self):
        client = mock_client()
        client.get_periodic_note.side_effect = ObsidianAPIError(404, "Not found")
        inject_client(client)

        result = get_periodic_note("daily")
        assert "no daily note found" in result

    def test_500_not_configured(self):
        client = mock_client()
        client.get_periodic_note.side_effect = ObsidianAPIError(
            500, "Failed to find daily notes folder"
        )
        inject_client(client)

        result = get_periodic_note("daily")
        assert "not configured" in result


# ===========================================================================
# Unit tests — get_recent_periodic_notes
# ===========================================================================

class TestGetRecentPeriodicNotes:
    def test_collects_notes_backward(self, monkeypatch):
        _freeze_today(monkeypatch, datetime.date(2026, 5, 30))

        client = mock_client()
        client.get_periodic_note_by_date.return_value = _note(
            content="content", filepath="/daily/2026-05-30.md"
        )
        inject_client(client)

        results = get_recent_periodic_notes("daily", limit=3)
        assert isinstance(results, list)
        assert len(results) == 3
        assert results[0]["period_date"] == "2026-05-30"
        assert results[1]["period_date"] == "2026-05-29"
        assert "content" not in results[0]  # include_content defaults False

    def test_respects_limit(self, monkeypatch):
        _freeze_today(monkeypatch, datetime.date(2026, 5, 30))

        client = mock_client()
        client.get_periodic_note_by_date.return_value = _note(filepath="note.md")
        inject_client(client)

        results = get_recent_periodic_notes("daily", limit=2)
        assert len(results) == 2

    def test_stops_on_max_consecutive_misses(self, monkeypatch):
        _freeze_today(monkeypatch, datetime.date(2026, 5, 30))

        client = mock_client()
        client.get_periodic_note_by_date.side_effect = ObsidianAPIError(404, "Not found")
        inject_client(client)

        results = get_recent_periodic_notes("daily", limit=5)
        assert results == []
        # Should have tried limit*3 = 15 times
        assert client.get_periodic_note_by_date.call_count == 15

    def test_include_content_flag(self, monkeypatch):
        _freeze_today(monkeypatch, datetime.date(2026, 5, 30))

        client = mock_client()
        client.get_periodic_note_by_date.return_value = _note(
            content="# My Note", filepath="daily/2026-05-30.md"
        )
        inject_client(client)

        results = get_recent_periodic_notes("daily", limit=1, include_content=True)
        assert len(results) == 1
        assert results[0]["content"] == "# My Note"

    def test_500_not_configured(self, monkeypatch):
        _freeze_today(monkeypatch, datetime.date(2026, 5, 30))

        client = mock_client()
        client.get_periodic_note_by_date.side_effect = ObsidianAPIError(
            500, "Failed to find daily notes folder"
        )
        inject_client(client)

        result = get_recent_periodic_notes("daily")
        assert isinstance(result, str)
        assert "not configured" in result

    def test_invalid_period(self):
        inject_client(mock_client())
        result = get_recent_periodic_notes("biweekly")
        assert isinstance(result, str)
        assert "invalid period" in result

    def test_mixed_hits_and_misses(self, monkeypatch):
        _freeze_today(monkeypatch, datetime.date(2026, 5, 30))

        client = mock_client()
        call_count = 0

        def alternate(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:
                raise ObsidianAPIError(404, "Not found")
            return _note(content="x", filepath="note.md")

        client.get_periodic_note_by_date.side_effect = alternate
        inject_client(client)

        results = get_recent_periodic_notes("daily", limit=3)
        assert len(results) == 3

    def test_monthly_iteration(self, monkeypatch):
        _freeze_today(monkeypatch, datetime.date(2026, 5, 30))

        client = mock_client()
        client.get_periodic_note_by_date.return_value = _note(filepath="monthly.md")
        inject_client(client)

        results = get_recent_periodic_notes("monthly", limit=3)
        assert len(results) == 3
        assert results[0]["period_date"] == "2026-05-30"
        assert results[1]["period_date"] == "2026-04-30"
        assert results[2]["period_date"] == "2026-03-30"


# ===========================================================================
# Unit tests — _step_back helper
# ===========================================================================

class TestStepBack:
    def test_daily(self):
        assert _step_back(datetime.date(2026, 5, 30), "daily") == datetime.date(2026, 5, 29)

    def test_weekly(self):
        assert _step_back(datetime.date(2026, 5, 30), "weekly") == datetime.date(2026, 5, 23)

    def test_monthly(self):
        assert _step_back(datetime.date(2026, 5, 30), "monthly") == datetime.date(2026, 4, 30)

    def test_monthly_clamps_day(self):
        # March 31 → Feb 28 (non-leap)
        assert _step_back(datetime.date(2026, 3, 31), "monthly") == datetime.date(2026, 2, 28)

    def test_quarterly(self):
        assert _step_back(datetime.date(2026, 5, 30), "quarterly") == datetime.date(2026, 2, 28)

    def test_yearly(self):
        assert _step_back(datetime.date(2026, 5, 30), "yearly") == datetime.date(2025, 5, 30)

    def test_yearly_leap_day(self):
        # Feb 29 leap year → Feb 28 non-leap year
        assert _step_back(datetime.date(2024, 2, 29), "yearly") == datetime.date(2023, 2, 28)

    def test_monthly_january_wraps(self):
        assert _step_back(datetime.date(2026, 1, 15), "monthly") == datetime.date(2025, 12, 15)

    def test_quarterly_wraps_year(self):
        assert _step_back(datetime.date(2026, 2, 15), "quarterly") == datetime.date(2025, 11, 15)


# ===========================================================================
# Integration tests
# ===========================================================================

@pytest.mark.integration
class TestPeriodicIntegration:
    def test_get_periodic_note(self, live_client):
        inject_client(live_client)
        result = get_periodic_note("daily")
        if "not configured" in result:
            pytest.skip("Periodic notes not configured in vault")
        assert isinstance(result, str)

    def test_get_recent_periodic_notes(self, live_client):
        inject_client(live_client)
        result = get_recent_periodic_notes("daily", limit=3)
        if isinstance(result, str) and "not configured" in result:
            pytest.skip("Periodic notes not configured in vault")
        assert isinstance(result, list)
