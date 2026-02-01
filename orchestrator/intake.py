from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPLACE_PREFIXES = ("/agent1", "/product", "/idea")
APPEND_PREFIXES = ("/agent1-append", "/append", "/enhance", "/enhancement", "/agent1+")
MODE_REPLACE = "replace"
MODE_APPEND = "append"


def _strip_prefix(body: str, prefixes: tuple[str, ...]) -> str | None:
    lowered = body.lower().lstrip()
    for prefix in prefixes:
        if lowered.startswith(prefix):
            trimmed = body[len(prefix) :].lstrip(" \t:-\n")
            return trimmed or None
    return None


def _parse_body(body: str) -> tuple[str | None, str | None]:
    trimmed = _strip_prefix(body or "", APPEND_PREFIXES)
    if trimmed:
        return trimmed, MODE_APPEND
    trimmed = _strip_prefix(body or "", REPLACE_PREFIXES)
    if trimmed:
        return trimmed, MODE_REPLACE
    return None, None


def _mode_from_labels(labels: set[str]) -> str:
    if labels & {"append", "enhance", "enhancement"}:
        return MODE_APPEND
    return MODE_REPLACE


def prompt_from_event(event_path: str) -> tuple[str | None, str | None]:
    path = Path(event_path)
    if not path.exists():
        return None, None
    data = json.loads(path.read_text())

    # issue_comment event
    if "comment" in data and "issue" in data:
        issue = data.get("issue", {})
        if "pull_request" in issue:
            return None, None
        body = (data.get("comment", {}) or {}).get("body", "")
        return _parse_body(body or "")

    # issues event
    if "issue" in data:
        issue = data.get("issue", {})
        if "pull_request" in issue:
            return None, None
        labels = {lbl.get("name", "").lower() for lbl in issue.get("labels", [])}
        body = issue.get("body") or ""
        title = issue.get("title") or ""
        if labels & {"agent1", "product", "intake"}:
            payload = f"{title}\n\n{body}".strip()
            return payload or None, _mode_from_labels(labels)
        return _parse_body(body or "")

    return None, None
