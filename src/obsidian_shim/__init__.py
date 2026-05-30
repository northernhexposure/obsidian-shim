"""Obsidian MCP shim server — surgical, table-safe vault editing."""

from obsidian_shim.tools import mcp_server


def main():
    """Console-script entry point: run the MCP server over stdio."""
    mcp_server.run(transport="stdio")
