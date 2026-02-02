from __future__ import annotations

import subprocess
from typing import Iterable


def run_git(args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], check=check, capture_output=True, text=True)


def _read_stdout(args: list[str]) -> str:
    return run_git(args).stdout.strip()


def is_dirty() -> bool:
    status = _read_stdout(["status", "--porcelain"])
    return bool(status)


def has_staged_changes() -> bool:
    return bool(_read_stdout(["diff", "--cached", "--name-only"]))


def ensure_pushable() -> bool:
    run_git(["fetch", "origin"], check=False)
    status = _read_stdout(["status", "-sb"])
    if "[behind" in status:
        return False
    return True


def push_with_retry() -> None:
    if not ensure_pushable():
        return
    for _ in range(2):
        proc = run_git(["push"], check=False)
        if proc.returncode == 0:
            return
        # Try to rebase once and retry.
        run_git(["fetch", "origin"], check=False)
        run_git(["rebase", "origin/main"], check=False)
    return


def commit_paths(message: str, paths: Iterable[str], push: bool = True) -> bool:
    for path in paths:
        run_git(["add", path])
    if not has_staged_changes():
        return False
    run_git(["commit", "-m", message])
    if push:
        push_with_retry()
    return True


def commit_all(message: str) -> bool:
    run_git(["add", "-A"])
    if not is_dirty():
        return False
    run_git(["commit", "-m", message])
    push_with_retry()
    return True
