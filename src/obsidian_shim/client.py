"""Thin REST client for the Obsidian Local REST API plugin."""

from __future__ import annotations

import os

import httpx


class ObsidianAPIError(Exception):
    """An error returned by the Obsidian REST API."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        super().__init__(f"HTTP {status_code}: {detail}")


class ObsidianClient:
    """Synchronous client for the Obsidian Local REST API plugin."""

    def __init__(
        self,
        api_key: str | None = None,
        host: str | None = None,
        port: int | str | None = None,
    ):
        self.api_key = api_key or os.environ["OBSIDIAN_API_KEY"]
        host = host or os.environ.get("OBSIDIAN_HOST", "127.0.0.1")
        port = int(port or os.environ.get("OBSIDIAN_PORT", "27123"))
        self.base_url = f"http://{host}:{port}"
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=30.0,
        )

    # -- low-level helpers --------------------------------------------------

    def _raise_for_status(self, resp: httpx.Response) -> None:
        if resp.status_code >= 400:
            detail = resp.text[:300] if resp.text else resp.reason_phrase
            raise ObsidianAPIError(resp.status_code, detail)

    # -- public API used by tools -------------------------------------------

    def read_file(self, filepath: str) -> str:
        """GET /vault/{filepath} → raw UTF-8 content."""
        resp = self._client.get(
            f"/vault/{filepath}",
            headers={"Accept": "text/markdown"},
        )
        self._raise_for_status(resp)
        return resp.text

    def write_file(self, filepath: str, content: str) -> None:
        """PUT /vault/{filepath} with full content (overwrite)."""
        resp = self._client.put(
            f"/vault/{filepath}",
            content=content.encode("utf-8"),
            headers={"Content-Type": "text/markdown"},
        )
        self._raise_for_status(resp)

    def list_files(self, dirpath: str = "") -> list[str]:
        """GET /vault/{dirpath}/ → list of file/dir entries."""
        path = f"/vault/{dirpath}/" if dirpath else "/vault/"
        resp = self._client.get(path, headers={"Accept": "application/json"})
        self._raise_for_status(resp)
        return resp.json()["files"]

    def search(self, query: str, context_length: int = 100) -> list[dict]:
        """POST /search/simple/ → JSON array of search results."""
        resp = self._client.post(
            "/search/simple/",
            params={"query": query, "contextLength": context_length},
        )
        self._raise_for_status(resp)
        return resp.json()

    def delete_file(self, filepath: str) -> None:
        """DELETE /vault/{filepath} — used only for test cleanup."""
        resp = self._client.delete(f"/vault/{filepath}")
        self._raise_for_status(resp)
