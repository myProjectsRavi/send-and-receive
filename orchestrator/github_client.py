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


def list_branches(repo_full: str, token: str, api_base: str, per_page: int = 100, max_pages: int = 10) -> list[str]:
    owner, repo = parse_repo(repo_full)
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    branches: list[str] = []
    page = 1
    while page <= max_pages:
        url = f"{api_base.rstrip('/')}/repos/{owner}/{repo}/branches?per_page={per_page}&page={page}"
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code >= 400:
            raise RuntimeError(f"GitHub API error {resp.status_code}: {resp.text}")
        data = resp.json() or []
        if not data:
            break
        for item in data:
            name = item.get("name")
            if name:
                branches.append(name)
        if len(data) < per_page:
            break
        page += 1
    return branches


def find_branch_by_session_id(repo_full: str, session_id: str, token: str, api_base: str) -> str | None:
    if not session_id:
        return None
    branches = list_branches(repo_full, token, api_base)
    # Prefer feature branches containing the session id
    for name in branches:
        if session_id in name and name.startswith("feature/"):
            return name
    for name in branches:
        if session_id in name:
            return name
    return None


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


def is_pr_merged(pr_url: str, token: str, api_base: str) -> bool:
    owner, repo, number = parse_pr_url(pr_url)
    url = f"{api_base.rstrip('/')}/repos/{owner}/{repo}/pulls/{number}/merge"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    resp = requests.get(url, headers=headers, timeout=30)
    if resp.status_code == 204:
        return True
    if resp.status_code == 404:
        return False
    if resp.status_code >= 400:
        raise RuntimeError(f"GitHub API error {resp.status_code}: {resp.text}")
    return False


def merge_pr(pr_url: str, token: str, api_base: str, merge_method: str | None = None) -> dict[str, Any]:
    if merge_method and merge_method not in {"merge", "squash", "rebase"}:
        merge_method = None
    owner, repo, number = parse_pr_url(pr_url)
    url = f"{api_base.rstrip('/')}/repos/{owner}/{repo}/pulls/{number}/merge"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    payload = {}
    if merge_method:
        payload["merge_method"] = merge_method
    resp = requests.put(url, headers=headers, json=payload, timeout=30)
    if resp.status_code in (200, 201):
        data = resp.json()
        return {
            "merged": bool(data.get("merged", True)),
            "message": data.get("message", ""),
            "sha": data.get("sha"),
        }
    if resp.status_code in (404, 405, 409):
        try:
            data = resp.json()
        except ValueError:
            data = {}
        return {
            "merged": False,
            "message": data.get("message") or resp.text,
        }
    if resp.status_code >= 400:
        raise RuntimeError(f"GitHub API error {resp.status_code}: {resp.text}")
    return {"merged": False, "message": resp.text}
