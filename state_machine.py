from __future__ import annotations

from typing import Any


ALLOWED_STATUSES = {
    "product": {"draft", "active", "shipped", "archived"},
    "epic": {"planned", "in_progress", "done", "blocked"},
    "feature": {"ready", "in_progress", "review", "done", "blocked"},
    "story": {"ready", "in_progress", "done", "verified", "blocked"},
}


def validate_status(entity: str, status: str) -> bool:
    allowed = ALLOWED_STATUSES.get(entity)
    return bool(allowed and status in allowed)


def validate_items(entity: str, items: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for item in items:
        item_id = item.get("id", "<missing>")
        status = item.get("status")
        if status is None:
            errors.append(f"{entity} {item_id}: missing status")
            continue
        if not validate_status(entity, status):
            errors.append(f"{entity} {item_id}: invalid status {status}")
    return errors
