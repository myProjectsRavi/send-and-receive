from __future__ import annotations

import re
from typing import Any

import requests


def parse_pr_url(pr_url: str) -> tuple[str, str, int]:
    match = re.match(r"https://github.com/([^/]+)/([^/]+)/pull/(\d+)", pr_url)
    if not match:
        raise ValueError(f"Unsupported PR URL: {pr_url}")
    owner, repo, num = match.group(1), match.group(2), int(match.group(3))
    return owner, repo, num


def get_pr_info(pr_url: str, token: str, api_base: str) -> dict[str, Any]:
    owner, repo, number = parse_pr_url(pr_url)
    url = f"{api_base.rstrip('/')}/repos/{owner}/{repo}/pulls/{number}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    resp = requests.get(url, headers=headers, timeout=30)
    if resp.status_code >= 400:
        raise RuntimeError(f"GitHub API error {resp.status_code}: {resp.text}")
    data = resp.json()
    return {
        "number": number,
        "title": data.get("title"),
        "html_url": data.get("html_url", pr_url),
        "head_ref": data.get("head", {}).get("ref"),
        "state": data.get("state"),
    }
