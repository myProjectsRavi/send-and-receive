from __future__ import annotations

import json
import time
from typing import Any

import requests


class JulesClient:
    def __init__(self, api_key: str, api_base: str) -> None:
        self.api_key = api_key
        self.api_base = api_base.rstrip("/")

    def _headers(self) -> dict[str, str]:
        return {
            "X-Goog-Api-Key": self.api_key,
            "Content-Type": "application/json",
        }

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        retry_on_404: bool = False,
        max_retries: int = 3,
    ) -> dict[str, Any]:
        url = f"{self.api_base}{path}"
        data = json.dumps(payload) if payload is not None else None
        for attempt in range(1, max_retries + 1):
            resp = requests.request(method, url, headers=self._headers(), data=data, timeout=30)
            if resp.status_code < 400:
                return resp.json()
            if resp.status_code == 404 and retry_on_404 and attempt < max_retries:
                time.sleep(2**attempt)
                continue
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < max_retries:
                time.sleep(2**attempt)
                continue
            raise RuntimeError(f"Jules API error {resp.status_code} for {method} {url}: {resp.text}")
        raise RuntimeError("Jules API request failed after retries")

    def _normalize_session_name(self, session_name: str) -> str:
        # Jules APIs expect resource names like "sessions/{id}".
        # If we get a longer resource name, strip it down to the last "sessions/{id}" segment.
        marker = "sessions/"
        if marker in session_name:
            session_id = session_name.rsplit(marker, 1)[-1]
            return f"{marker}{session_id}"
        return f"{marker}{session_name}"

    def _session_path(self, session_name: str) -> str:
        return f"/{self._normalize_session_name(session_name)}"

    def list_sources(self) -> dict[str, Any]:
        return self._request("GET", "/sources")

    def create_session(
        self,
        prompt: str,
        source: str,
        starting_branch: str | None = None,
        title: str | None = None,
        automation_mode: str | None = None,
        require_plan_approval: bool = False,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "prompt": prompt,
            "sourceContext": {
                "source": source,
                "githubRepoContext": {},
            },
        }
        if starting_branch:
            body["sourceContext"]["githubRepoContext"]["startingBranch"] = starting_branch
        if title:
            body["title"] = title
        if automation_mode:
            body["automationMode"] = automation_mode
        if require_plan_approval:
            body["requirePlanApproval"] = True
        return self._request("POST", "/sessions", body)

    def get_session(self, session_name: str) -> dict[str, Any]:
        return self._request("GET", self._session_path(session_name), retry_on_404=True, max_retries=6)

    def list_activities(
        self,
        session_name: str,
        page_size: int = 50,
        page_token: str | None = None,
    ) -> dict[str, Any]:
        path = f"{self._session_path(session_name)}/activities?pageSize={page_size}"
        if page_token:
            path = f"{path}&pageToken={page_token}"
        return self._request("GET", path, retry_on_404=True, max_retries=6)

    def send_message(self, session_name: str, prompt: str) -> dict[str, Any]:
        body = {"prompt": prompt}
        return self._request("POST", f"{self._session_path(session_name)}:sendMessage", body)

    def approve_plan(self, session_name: str) -> dict[str, Any]:
        return self._request("POST", f"{self._session_path(session_name)}:approvePlan")
