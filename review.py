from __future__ import annotations

import json
from typing import Any

from .utils import extract_between


def extract_review_json(text: str) -> dict[str, Any] | None:
    payload = extract_between(text, "BEGIN_REVIEW_JSON", "END_REVIEW_JSON")
    if not payload:
        return None
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return None
