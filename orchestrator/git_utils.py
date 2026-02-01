from __future__ import annotations

import subprocess


def run_git(args: list[str]) -> str:
    result = subprocess.run(["git", *args], check=True, capture_output=True, text=True)
    return result.stdout.strip()


def is_dirty() -> bool:
    status = run_git(["status", "--porcelain"])
    return bool(status)


def commit_all(message: str) -> bool:
    run_git(["add", "-A"])
    if not is_dirty():
        return False
    run_git(["commit", "-m", message])
    run_git(["push"])
    return True
