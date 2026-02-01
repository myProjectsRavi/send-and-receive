from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


BACKLOG_FILES = {
    "product": "backlog/product.yaml",
    "epics": "backlog/epics.yaml",
    "features": "backlog/features.yaml",
    "stories": "backlog/stories.yaml",
    "acceptance": "backlog/acceptance.yaml",
}


class BacklogStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.product: dict[str, Any] = {}
        self.epics: dict[str, Any] = {}
        self.features: dict[str, Any] = {}
        self.stories: dict[str, Any] = {}
        self.acceptance: dict[str, Any] = {}

    def load(self) -> None:
        self.product = self._read_yaml(BACKLOG_FILES["product"])
        self.epics = self._read_yaml(BACKLOG_FILES["epics"], default_items=True)
        self.features = self._read_yaml(BACKLOG_FILES["features"], default_items=True)
        self.stories = self._read_yaml(BACKLOG_FILES["stories"], default_items=True)
        self.acceptance = self._read_yaml(BACKLOG_FILES["acceptance"], default_items=True)

    def save_all(self) -> None:
        self._write_yaml(BACKLOG_FILES["product"], self.product)
        self._write_yaml(BACKLOG_FILES["epics"], self.epics)
        self._write_yaml(BACKLOG_FILES["features"], self.features)
        self._write_yaml(BACKLOG_FILES["stories"], self.stories)
        self._write_yaml(BACKLOG_FILES["acceptance"], self.acceptance)

    def apply_agent1_payload(self, payload: dict[str, Any], mode: str = "replace") -> None:
        if mode == "replace":
            if "product" in payload:
                self.product = {"version": 1, "product": payload["product"]}
            if "epics" in payload:
                self.epics = {"version": 1, "items": payload["epics"]}
            if "features" in payload:
                self.features = {"version": 1, "items": payload["features"]}
            if "stories" in payload:
                self.stories = {"version": 1, "items": payload["stories"]}
            if "acceptance" in payload:
                self.acceptance = {"version": 1, "items": payload["acceptance"]}
            return

        # append mode
        if "product" in payload:
            existing = self.product.get("product", {})
            incoming = payload["product"] or {}
            if not existing:
                self.product = {"version": 1, "product": incoming}
            else:
                merged = dict(existing)
                for key in ("constraints", "rules", "requirements"):
                    merged[key] = _merge_unique_list(existing.get(key, []), incoming.get(key, []))
                for key in ("name", "vision", "owner", "status"):
                    if not merged.get(key) and incoming.get(key):
                        merged[key] = incoming.get(key)
                self.product = {"version": 1, "product": merged}

        if "epics" in payload:
            self.epics = {"version": 1, "items": _merge_items(self.epics.get("items", []), payload["epics"])}
        if "features" in payload:
            self.features = {"version": 1, "items": _merge_items(self.features.get("items", []), payload["features"])}
        if "stories" in payload:
            self.stories = {"version": 1, "items": _merge_items(self.stories.get("items", []), payload["stories"])}
        if "acceptance" in payload:
            self.acceptance = {
                "version": 1,
                "items": _merge_acceptance(self.acceptance.get("items", []), payload["acceptance"]),
            }

    def next_ready_feature(self) -> dict[str, Any] | None:
        items = self.features.get("items", [])
        for item in items:
            if item.get("status") == "ready":
                return item
        return None

    def next_review_feature(self) -> dict[str, Any] | None:
        items = self.features.get("items", [])
        for item in items:
            if item.get("status") == "review" and item.get("pr_url"):
                return item
        return None

    def get_stories_for_feature(self, feature_id: str) -> list[dict[str, Any]]:
        items = self.stories.get("items", [])
        return [item for item in items if item.get("feature") == feature_id]

    def update_feature_status(self, feature_id: str, status: str) -> None:
        self.update_feature_fields(feature_id, status=status)

    def update_feature_fields(self, feature_id: str, **fields: Any) -> None:
        items = self.features.get("items", [])
        for item in items:
            if item.get("id") == feature_id:
                for key, value in fields.items():
                    if value is not None:
                        item[key] = value

    def update_story_status(self, feature_id: str, status: str) -> None:
        items = self.stories.get("items", [])
        for item in items:
            if item.get("feature") == feature_id:
                item["status"] = status

    def _read_yaml(self, rel_path: str, default_items: bool = False) -> dict[str, Any]:
        path = self.root / rel_path
        if not path.exists():
            if default_items:
                return {"version": 1, "items": []}
            return {"version": 1}
        data = yaml.safe_load(path.read_text()) or {}
        if default_items and "items" not in data:
            data["items"] = []
        if "version" not in data:
            data["version"] = 1
        return data

    def _write_yaml(self, rel_path: str, data: dict[str, Any]) -> None:
        path = self.root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(data, sort_keys=False))


def extract_backlog_json(text: str) -> dict[str, Any] | None:
    start = text.find("BEGIN_BACKLOG_JSON")
    end = text.find("END_BACKLOG_JSON")
    if start == -1 or end == -1 or end <= start:
        return _extract_from_any_json(text)
    payload_raw = text[start + len("BEGIN_BACKLOG_JSON"):end].strip()
    try:
        return json.loads(payload_raw)
    except json.JSONDecodeError:
        return _extract_from_any_json(text)


def _extract_from_any_json(text: str) -> dict[str, Any] | None:
    decoder = json.JSONDecoder()
    required = {"product", "epics", "features", "stories", "acceptance"}
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
        if isinstance(obj, dict) and required.intersection(obj.keys()):
            return obj
        idx += max(end, 1)
    return None


def _merge_unique_list(existing: list[Any], incoming: list[Any]) -> list[Any]:
    merged = list(existing)
    for item in incoming or []:
        if item not in merged:
            merged.append(item)
    return merged


def _merge_items(existing: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged = list(existing)
    existing_ids = {item.get("id") for item in existing if item.get("id")}
    for item in incoming or []:
        item_id = item.get("id")
        if not item_id or item_id in existing_ids:
            continue
        merged.append(item)
        existing_ids.add(item_id)
    return merged


def _merge_acceptance(existing: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged = list(existing)
    by_story: dict[str, dict[str, Any]] = {}
    for item in merged:
        story = item.get("story")
        if story:
            by_story[story] = item
    for item in incoming or []:
        story = item.get("story")
        if not story:
            continue
        if story in by_story:
            criteria = list(by_story[story].get("criteria", []))
            for entry in item.get("criteria", []) or []:
                if entry not in criteria:
                    criteria.append(entry)
            by_story[story]["criteria"] = criteria
        else:
            merged.append(item)
            by_story[story] = item
    return merged
