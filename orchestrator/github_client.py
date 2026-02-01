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


def parse_repo(repo_full: str) -> tuple[str, str]:
    if not repo_full or "/" not in repo_full:
        raise ValueError(f"Invalid repo: {repo_full}")
    owner, repo = repo_full.split("/", 1)
    return owner, repo


def find_pr_by_head(repo_full: str, head_ref: str, token: str, api_base: str) -> dict[str, Any] | None:
    owner, repo = parse_repo(repo_full)
    url = f"{api_base.rstrip('/')}/repos/{owner}/{repo}/pulls?state=open&head={owner}:{head_ref}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    resp = requests.get(url, headers=headers, timeout=30)
    if resp.status_code >= 400:
        raise RuntimeError(f"GitHub API error {resp.status_code}: {resp.text}")
    data = resp.json() or []
    if not data:
        return None
    pr = data[0]
    return {
        "number": pr.get("number"),
        "title": pr.get("title"),
        "html_url": pr.get("html_url"),
        "head_ref": pr.get("head", {}).get("ref"),
        "state": pr.get("state"),
    }


def create_pr(
    repo_full: str,
    head_ref: str,
    base_ref: str,
    title: str,
    body: str,
    token: str,
    api_base: str,
) -> dict[str, Any]:
    owner, repo = parse_repo(repo_full)
    url = f"{api_base.rstrip('/')}/repos/{owner}/{repo}/pulls"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    payload = {
        "title": title,
        "head": f"{owner}:{head_ref}",
        "base": base_ref,
        "body": body,
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    if resp.status_code == 422:
        # Likely PR already exists; caller should check with find_pr_by_head
        return {"error": resp.text}
    if resp.status_code >= 400:
        raise RuntimeError(f"GitHub API error {resp.status_code}: {resp.text}")
    pr = resp.json()
    return {
        "number": pr.get("number"),
        "title": pr.get("title"),
        "html_url": pr.get("html_url"),
        "head_ref": pr.get("head", {}).get("ref"),
        "state": pr.get("state"),
    }


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
