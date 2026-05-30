"""Tests for command tools (list_commands, execute_command)."""

from __future__ import annotations

import pytest

from obsidian_shim.client import ObsidianAPIError
from obsidian_shim.tools import list_commands, execute_command
from conftest import inject_client, mock_client


# =========================================================================
# Unit tests — list_commands
# =========================================================================

class TestListCommandsUnit:

    def test_returns_command_list(self):
        client = mock_client()
        client.list_commands.return_value = [
            {"id": "app:open-settings", "name": "Open settings"},
            {"id": "editor:toggle-bold", "name": "Toggle bold"},
        ]
        inject_client(client)

        result = list_commands()
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["id"] == "app:open-settings"
        client.list_commands.assert_called_once()

    def test_handles_api_error(self):
        client = mock_client()
        client.list_commands.side_effect = ObsidianAPIError(500, "Internal Server Error")
        inject_client(client)

        result = list_commands()
        assert isinstance(result, str)
        assert "Error" in result
        assert "500" in result


# =========================================================================
# Unit tests — execute_command
# =========================================================================

class TestExecuteCommandUnit:

    def test_returns_success_message(self):
        client = mock_client()
        inject_client(client)

        result = execute_command("app:open-settings")
        assert "Executed" in result
        assert "app:open-settings" in result
        client.execute_command.assert_called_once_with("app:open-settings")

    def test_handles_404(self):
        client = mock_client()
        client.execute_command.side_effect = ObsidianAPIError(404, "Not Found")
        inject_client(client)

        result = execute_command("nonexistent:command")
        assert "not found" in result.lower()
        assert "nonexistent:command" in result

    def test_unexpected_error_reraises(self):
        client = mock_client()
        client.execute_command.side_effect = ObsidianAPIError(500, "Internal Server Error")
        inject_client(client)

        with pytest.raises(ObsidianAPIError) as exc_info:
            execute_command("app:open-settings")
        assert exc_info.value.status_code == 500


# =========================================================================
# Integration tests — live Obsidian Local REST API
# =========================================================================

@pytest.mark.integration
class TestCommandsIntegration:

    def test_list_commands_nonempty(self, live_client):
        inject_client(live_client)
        result = list_commands()
        assert isinstance(result, list)
        assert len(result) > 0
        assert "id" in result[0]
        assert "name" in result[0]

    def test_execute_command_safe(self, live_client):
        inject_client(live_client)
        # Open help is a safe, no-op-ish command available in all vaults.
        result = execute_command("app:open-help")
        assert "Executed" in result
