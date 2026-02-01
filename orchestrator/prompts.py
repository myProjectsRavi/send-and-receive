from __future__ import annotations

from typing import Any


def build_agent1_prompt(product_prompt: str, mode: str = "replace", existing: dict[str, Any] | None = None) -> str:
    existing = existing or {}
    if mode == "append":
        return f"""
You are Agent 1 (Architect + Business Analyst).

Mode: APPEND. Do NOT modify or delete existing backlog items. Only add new items.

Input from product owner:
{product_prompt}

Existing backlog (for reference):
{_pretty(existing)}

Rules:
- Only add NEW epics, features, stories, and acceptance criteria.
- Use NEW unique IDs that do not exist yet.
- If you add a new feature, it must reference an epic ID.
- If you add a new story, it must reference a feature ID.
- If you have no new items for a section, return an empty array for that section.
- You may add new items to product constraints/rules/requirements only.

Return ONLY the JSON payload between the markers below. Do not include any extra text.

BEGIN_BACKLOG_JSON
{{
  "product": {{
    "constraints": [],
    "rules": [],
    "requirements": []
  }},
  "epics": [],
  "features": [],
  "stories": [],
  "acceptance": []
}}
END_BACKLOG_JSON
""".strip()

    return f"""
You are Agent 1 (Architect + Business Analyst).

Input from product owner:
{product_prompt}

Return ONLY the JSON payload between the markers below. Do not include any extra text.

BEGIN_BACKLOG_JSON
{{
  "product": {{
    "id": "prod-001",
    "name": "<short product name>",
    "owner": "product-owner",
    "vision": "<1-3 sentences>",
    "constraints": ["zero infra", "zero INR", "fire and forget"],
    "rules": ["<rule 1>", "<rule 2>"],
    "requirements": ["<req 1>", "<req 2>"],
    "status": "active"
  }},
  "epics": [
    {{"id": "E1", "title": "<epic>", "status": "planned", "description": "<short>"}}
  ],
  "features": [
    {{"id": "F1", "epic": "E1", "title": "<feature>", "status": "ready", "description": "<short>"}}
  ],
  "stories": [
    {{"id": "S1", "feature": "F1", "title": "<story>", "status": "ready", "description": "<short>"}}
  ],
  "acceptance": [
    {{"story": "S1", "criteria": ["<criterion 1>", "<criterion 2>"]}}
  ]
}}
END_BACKLOG_JSON
""".strip()


def build_agent2_prompt(feature: dict[str, Any], stories: list[dict[str, Any]], acceptance: list[dict[str, Any]]) -> str:
    return """
You are Agent 2 (Full-Stack Developer).

Implement the feature described below in a single PR. Implement all related stories and satisfy all acceptance criteria.
- Do not change unrelated files.
- Do not update backlog/status files.
- Keep the diff minimal and focused.

FEATURE:
{feature}

STORIES:
{stories}

ACCEPTANCE:
{acceptance}
""".strip().format(
        feature=_pretty(feature),
        stories=_pretty(stories),
        acceptance=_pretty(acceptance),
    )


def build_agent2_fix_prompt(pr_url: str, review: dict[str, Any]) -> str:
    return """
You are Agent 2 (Full-Stack Developer).

Fix the issues reported by the reviewer for this PR:
{pr_url}

Return the fixes in the same PR branch. Focus only on the blocking issues first.

REVIEW:
{review}
""".strip().format(pr_url=pr_url, review=_pretty(review))


def build_agent3_prompt(pr_url: str, feature: dict[str, Any], stories: list[dict[str, Any]], acceptance: list[dict[str, Any]]) -> str:
    return """
You are Agent 3 (Senior Reviewer).

Review the PR for correctness, security, performance, and adherence to acceptance criteria.
Return ONLY the JSON payload between the markers below. Do not include any extra text.

PR:
{pr_url}

FEATURE:
{feature}

STORIES:
{stories}

ACCEPTANCE:
{acceptance}

BEGIN_REVIEW_JSON
{{
  "verdict": "PASS",
  "blocking": ["<blocking issue 1>", "<blocking issue 2>"],
  "non_blocking": ["<suggestion 1>", "<suggestion 2>"],
  "notes": "<short notes>"
}}
END_REVIEW_JSON
""".strip().format(
        pr_url=pr_url,
        feature=_pretty(feature),
        stories=_pretty(stories),
        acceptance=_pretty(acceptance),
    )


def _pretty(obj: Any) -> str:
    import json

    return json.dumps(obj, indent=2, sort_keys=False)
