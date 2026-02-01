from __future__ import annotations

import json
from typing import Any

from .utils import extract_between


def extract_review_json(text: str) -> dict[str, Any] | None:
    payload = extract_between(text, "BEGIN_REVIEW_JSON", "END_REVIEW_JSON")
    if not payload:
        return _extract_from_any_json(text)
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return _extract_from_any_json(text)


def _extract_from_any_json(text: str) -> dict[str, Any] | None:
    decoder = json.JSONDecoder()
    idx = 0
    text_len = len(text)
    while idx < text_len:
        if text[idx] != "{":
            idx += 1
            continue
        try:
            obj, end = decoder.raw_decode(text[idx:])
        except json.JSONDecodeError:
            idx += 1
            continue
        if isinstance(obj, dict) and "verdict" in obj:
            return obj
        idx += max(end, 1)
    return None
