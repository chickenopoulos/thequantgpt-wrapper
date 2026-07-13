from __future__ import annotations

from typing import Any

import httpx


class TqgApiError(RuntimeError):
    pass


class TqgApiClient:
    def __init__(self, base_url: str, api_key: str, *, timeout: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            resp = httpx.post(url, json=payload, headers=self._headers(), timeout=self.timeout)
        except httpx.RequestError as exc:
            raise TqgApiError(f"MCP API unreachable at {url}: {exc}") from exc
        if resp.status_code >= 400:
            raise TqgApiError(f"MCP API error {resp.status_code}: {resp.text[:500]}")
        data = resp.json()
        if not isinstance(data, dict):
            raise TqgApiError("MCP API returned non-object JSON")
        return data

    def health(self) -> dict[str, Any]:
        url = self.base_url.replace("/v1", "") + "/health"
        resp = httpx.get(url, headers=self._headers(), timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def create_strategy_plan(
        self,
        *,
        user_request: str,
        run_id: str,
        run_root: str,
        data_summary: str | None = None,
    ) -> dict[str, Any]:
        return self._post(
            "/tqg_create_strategy_plan",
            {
                "user_request": user_request,
                "run_id": run_id,
                "run_root": run_root,
                "data_summary": data_summary,
            },
        )

    def validate_strategy_code(
        self,
        *,
        code: str,
        user_request: str,
        strategy_spec: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._post(
            "/tqg_validate_strategy_code",
            {
                "code": code,
                "user_request": user_request,
                "strategy_spec": strategy_spec,
            },
        )

    def get_psa_workflow(
        self,
        *,
        strategy_type: str,
        parameters: list[str] | None = None,
        oos_start: str | None = None,
    ) -> dict[str, Any]:
        return self._post(
            "/tqg_get_psa_workflow",
            {
                "strategy_type": strategy_type,
                "parameters": parameters or [],
                "oos_start": oos_start,
            },
        )
