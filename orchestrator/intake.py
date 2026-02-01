from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_PREFIXES = ("/agent1", "/product", "/idea")


def _strip_prefix(body: str, prefixes: tuple[str, ...]) -> str | None:
    lowered = body.lower().lstrip()
    for prefix in prefixes:
        if lowered.startswith(prefix):
            trimmed = body[len(prefix) :].lstrip(" \t:-\n")
            return trimmed or None
    return None


def prompt_from_event(event_path: str, prefixes: tuple[str, ...] = DEFAULT_PREFIXES) -> str | None:
    path = Path(event_path)
    if not path.exists():
        return None
    data = json.loads(path.read_text())

    # issue_comment event
    if "comment" in data and "issue" in data:
        issue = data.get("issue", {})
        if "pull_request" in issue:
            return None
        body = (data.get("comment", {}) or {}).get("body", "")
        return _strip_prefix(body or "", prefixes)

    # issues event
    if "issue" in data:
        issue = data.get("issue", {})
        if "pull_request" in issue:
            return None
        labels = {lbl.get("name", "").lower() for lbl in issue.get("labels", [])}
        body = issue.get("body") or ""
        title = issue.get("title") or ""
        if labels & {"agent1", "product", "intake"}:
            payload = f"{title}\n\n{body}".strip()
            return payload or None
        return _strip_prefix(body or "", prefixes)

    return None
