from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

from .backlog import BacklogStore, extract_backlog_json
from .config import Config
from .git_utils import commit_all
from .github_client import create_pr, find_branch_by_session_id, find_pr_by_head, get_pr_info
from .intake import prompt_from_event
from .jules_client import JulesClient
from .prompts import build_agent1_prompt, build_agent2_prompt, build_agent2_fix_prompt, build_agent3_prompt
from .review import extract_review_json
from .utils import iter_strings, now_iso


PR_URL_RE = re.compile(r"https://github.com/[^/]+/[^/]+/pull/\d+")
BRANCH_REF_RE = re.compile(r"refs/heads/([A-Za-z0-9._/-]+)")
FEATURE_BRANCH_RE = re.compile(r"(feature/[A-Za-z0-9._/-]+)")


def log(message: str) -> None:
    print(message, flush=True)


def session_name_from(resp: dict[str, Any]) -> str:
    name = resp.get("name") or resp.get("session", {}).get("name") or resp.get("id")
    if not name:
        raise RuntimeError("Could not determine session id from response")
    return str(name)


def collect_activity_text(client: JulesClient, session_name: str) -> str:
    page_token: str | None = None
    texts: list[str] = []
    max_pages = int(os.getenv("ORCH_MAX_ACTIVITY_PAGES", "10"))
    for _ in range(max_pages):
        activities = client.list_activities(session_name, page_token=page_token)
        texts.extend(iter_strings(activities))
        page_token = activities.get("nextPageToken")
        if not page_token:
            break
    return "\n".join(texts)


def _extract_branch(text: str) -> str | None:
    candidates: list[str] = []
    for match in BRANCH_REF_RE.finditer(text):
        candidates.append(match.group(1))
    for match in FEATURE_BRANCH_RE.finditer(text):
        candidates.append(match.group(1))
    return candidates[-1] if candidates else None


def _ensure_pr_exists(cfg: Config, branch: str, feature_id: str | None) -> str | None:
    if not cfg.github_repository or not cfg.github_token:
        return None
    existing = find_pr_by_head(cfg.github_repository, branch, cfg.github_token, cfg.github_api_url)
    if existing and existing.get("html_url"):
        return str(existing["html_url"])
    title = f"Feature {feature_id or branch}"
    body = "Auto-created by orchestrator when Jules session completed without publishing a PR."
    created = create_pr(
        cfg.github_repository,
        branch,
        cfg.starting_branch,
        title,
        body,
        cfg.github_token,
        cfg.github_api_url,
    )
    return created.get("html_url") if created else None


def poll_for_pr_url(client: JulesClient, session_name: str, cfg: Config, feature_id: str | None) -> str:
    deadline = time.time() + cfg.max_poll_minutes * 60
    branch: str | None = None
    session_id = session_name.split("/")[-1]
    while time.time() < deadline:
        text = collect_activity_text(client, session_name)
        match = PR_URL_RE.search(text)
        if match:
            return match.group(0)
        if not branch:
            branch = _extract_branch(text)
        session = client.get_session(session_name)
        state = str(session.get("state") or session.get("status") or "").upper()
        if state in {"FAILED", "CANCELLED"}:
            raise RuntimeError(f"Agent2 session ended with state {state}")
        if state == "COMPLETED":
            break
        time.sleep(cfg.poll_seconds)
    if not branch and cfg.github_repository and cfg.github_token:
        branch = find_branch_by_session_id(cfg.github_repository, session_id, cfg.github_token, cfg.github_api_url)
    if branch:
        pr_url = _ensure_pr_exists(cfg, branch, feature_id)
        if pr_url:
            return pr_url
    raise RuntimeError("Timed out waiting for PR url")


def poll_for_backlog(client: JulesClient, session_name: str, cfg: Config) -> dict[str, Any]:
    deadline = time.time() + cfg.max_poll_minutes * 60
    while time.time() < deadline:
        text = collect_activity_text(client, session_name)
        payload = extract_backlog_json(text)
        if payload:
            return payload
        time.sleep(cfg.poll_seconds)
    raise RuntimeError("Timed out waiting for backlog JSON")


def poll_for_review(client: JulesClient, session_name: str, cfg: Config) -> dict[str, Any]:
    deadline = time.time() + cfg.max_poll_minutes * 60
    while time.time() < deadline:
        text = collect_activity_text(client, session_name)
        payload = extract_review_json(text)
        if payload:
            return payload
        session = client.get_session(session_name)
        state = str(session.get("state") or session.get("status") or "").upper()
        if state in {"FAILED", "CANCELLED"}:
            raise RuntimeError(f"Agent3 session ended with state {state}")
        if state == "COMPLETED":
            # final attempt before exiting
            payload = extract_review_json(text)
            if payload:
                return payload
            break
        time.sleep(cfg.poll_seconds)
    return {
        "verdict": "PENDING",
        "blocking": [],
        "non_blocking": [],
        "notes": "Review JSON not found before timeout; manual check recommended.",
    }


def poll_for_session_completion(client: JulesClient, session_name: str, cfg: Config) -> str:
    deadline = time.time() + cfg.max_poll_minutes * 60
    while time.time() < deadline:
        session = client.get_session(session_name)
        state = str(session.get("state") or session.get("status") or "").upper()
        if state in {"COMPLETED", "FAILED", "CANCELLED"}:
            return state
        time.sleep(cfg.poll_seconds)
    raise RuntimeError("Timed out waiting for session completion")


def write_status(root: Path, store: BacklogStore, current_feature: str | None, notes: str = "") -> None:
    product = store.product.get("product", {})
    epics = store.epics.get("items", [])
    features = store.features.get("items", [])
    epic_done = sum(1 for item in epics if item.get("status") == "done")
    feature_done = sum(1 for item in features if item.get("status") == "done")
    product_status = {
        "product_id": product.get("id", "prod-001"),
        "status": product.get("status", "draft"),
        "last_run": now_iso(),
        "current_epic": None,
        "current_feature": current_feature,
        "current_story": None,
        "epics_total": len(epics),
        "epics_done": epic_done,
        "features_total": len(features),
        "features_done": feature_done,
        "notes": notes,
    }
    feature_items = []
    for item in features:
        feature_items.append({"id": item.get("id"), "status": item.get("status")})

    (root / "status" / "product_status.json").write_text(json.dumps(product_status, indent=2))
    (root / "status" / "feature_status.json").write_text(json.dumps({"items": feature_items}, indent=2))


def write_error(root: Path, error: Exception) -> None:
    payload = {
        "error": str(error),
        "context": type(error).__name__,
        "timestamp": now_iso(),
    }
    (root / "status" / "last_error.json").write_text(json.dumps(payload, indent=2))


def acceptance_for_stories(acceptance_items: list[dict[str, Any]], stories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    story_ids = {story.get("id") for story in stories}
    return [item for item in acceptance_items if item.get("story") in story_ids]


def run_agent1(cfg: Config, store: BacklogStore, mode: str) -> None:
    existing = {
        "product": store.product.get("product", {}),
        "epics": store.epics.get("items", []),
        "features": store.features.get("items", []),
        "stories": store.stories.get("items", []),
        "acceptance": store.acceptance.get("items", []),
    }
    prompt = build_agent1_prompt(cfg.require(cfg.product_prompt, "PRODUCT_PROMPT"), mode=mode, existing=existing)
    client = JulesClient(cfg.require(cfg.key_arch, "JULES_KEY_ARCH"), cfg.api_base)
    session = client.create_session(
        prompt=prompt,
        source=cfg.require(cfg.source, "JULES_SOURCE"),
        title="Agent1 Backlog",
        starting_branch=cfg.starting_branch,
        automation_mode=None,
        require_plan_approval=cfg.require_plan_approval,
    )
    session_name = session_name_from(session)
    log(f"Agent1 session: {session_name}")
    if cfg.require_plan_approval:
        client.approve_plan(session_name)
    payload = poll_for_backlog(client, session_name, cfg)
    store.apply_agent1_payload(payload, mode=mode)
    store.save_all()


def run_agent2(cfg: Config, feature: dict[str, Any], stories: list[dict[str, Any]], acceptance: list[dict[str, Any]]) -> str:
    prompt = build_agent2_prompt(feature, stories, acceptance)
    client = JulesClient(cfg.require(cfg.key_dev, "JULES_KEY_DEV"), cfg.api_base)
    session = client.create_session(
        prompt=prompt,
        source=cfg.require(cfg.source, "JULES_SOURCE"),
        title=f"Agent2 {feature.get('id')}",
        starting_branch=cfg.starting_branch,
        automation_mode="AUTO_CREATE_PR",
        require_plan_approval=cfg.require_plan_approval,
    )
    session_name = session_name_from(session)
    log(f"Agent2 session: {session_name}")
    if cfg.require_plan_approval:
        client.approve_plan(session_name)
    return poll_for_pr_url(client, session_name, cfg, feature.get("id"))


def run_agent2_fix(cfg: Config, pr_url: str, review: dict[str, Any], branch: str | None) -> None:
    prompt = build_agent2_fix_prompt(pr_url, review)
    client = JulesClient(cfg.require(cfg.key_dev, "JULES_KEY_DEV"), cfg.api_base)
    session = client.create_session(
        prompt=prompt,
        source=cfg.require(cfg.source, "JULES_SOURCE"),
        title="Agent2 Fix",
        automation_mode=None,
        starting_branch=branch or cfg.starting_branch,
        require_plan_approval=cfg.require_plan_approval,
    )
    session_name = session_name_from(session)
    log(f"Agent2 fix session: {session_name}")
    if cfg.require_plan_approval:
        client.approve_plan(session_name)
    poll_for_session_completion(client, session_name, cfg)


def run_agent3(cfg: Config, pr_url: str, feature: dict[str, Any], stories: list[dict[str, Any]], acceptance: list[dict[str, Any]], branch: str | None) -> dict[str, Any]:
    prompt = build_agent3_prompt(pr_url, feature, stories, acceptance)
    client = JulesClient(cfg.require(cfg.key_review, "JULES_KEY_REVIEW"), cfg.api_base)
    session = client.create_session(
        prompt=prompt,
        source=cfg.require(cfg.source, "JULES_SOURCE"),
        title=f"Agent3 Review {feature.get('id')}",
        starting_branch=branch or cfg.starting_branch,
        automation_mode=None,
        require_plan_approval=cfg.require_plan_approval,
    )
    session_name = session_name_from(session)
    log(f"Agent3 session: {session_name}")
    if cfg.require_plan_approval:
        client.approve_plan(session_name)
    return poll_for_review(client, session_name, cfg)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    cfg = Config.from_env(dry_run=args.dry_run)
    root = Path.cwd()
    store = BacklogStore(root)
    store.load()

    try:
        agent1_mode = cfg.agent1_mode if cfg.agent1_mode in ("replace", "append") else "replace"

        if not cfg.product_prompt:
            event_path = os.getenv("GITHUB_EVENT_PATH")
            if event_path:
                prompt, mode = prompt_from_event(event_path)
                cfg.product_prompt = prompt
                if mode:
                    agent1_mode = mode

        if cfg.product_prompt:
            log("Running Agent 1 (backlog)...")
            if cfg.dry_run:
                log("Dry run: skipping Agent 1 API call")
            else:
                run_agent1(cfg, store, agent1_mode)
                write_status(root, store, None, notes=f"Agent1 backlog updated ({agent1_mode})")
                commit_all("backlog: update from agent1")

        feature = store.next_ready_feature()
        if not feature:
            log("No ready features found")
            write_status(root, store, None, notes="No ready features")
            commit_all("status: no ready features")
            return 0

        feature_id = feature.get("id")
        log(f"Processing feature {feature_id}")
        store.update_feature_status(feature_id, "in_progress")
        store.save_all()
        write_status(root, store, feature_id, notes="Feature in progress")
        commit_all(f"backlog: start feature {feature_id}")

        stories = store.get_stories_for_feature(feature_id)
        acceptance = acceptance_for_stories(store.acceptance.get("items", []), stories)

        if cfg.dry_run:
            log("Dry run: skipping Agent 2/3 API calls")
            return 0

        pr_url = run_agent2(cfg, feature, stories, acceptance)
        log(f"PR created: {pr_url}")
        store.update_feature_status(feature_id, "review")
        store.save_all()
        write_status(root, store, feature_id, notes="Feature in review")
        commit_all(f"backlog: review feature {feature_id}")

        pr_info = get_pr_info(pr_url, cfg.require(cfg.github_token, "GITHUB_TOKEN"), cfg.github_api_url)
        review = run_agent3(cfg, pr_url, feature, stories, acceptance, pr_info.get("head_ref"))
        verdict = str(review.get("verdict", "")).upper()

        if verdict == "PENDING":
            log("Review pending; no verdict found. Leaving feature in review state.")
            store.update_feature_status(feature_id, "review")
            store.save_all()
            write_status(root, store, feature_id, notes="Review pending (no verdict)")
            commit_all(f"backlog: review pending {feature_id}")
            return 0

        if verdict == "NEEDS_CHANGES":
            log("Reviewer requested changes")
            run_agent2_fix(cfg, pr_url, review, pr_info.get("head_ref"))
            review = run_agent3(cfg, pr_url, feature, stories, acceptance, pr_info.get("head_ref"))
            verdict = str(review.get("verdict", "")).upper()

        if verdict != "PASS":
            raise RuntimeError("Review did not pass")

        store.update_feature_status(feature_id, "done")
        store.update_story_status(feature_id, "done")
        store.save_all()
        write_status(root, store, feature_id, notes="Feature done")
        commit_all(f"backlog: complete feature {feature_id}")
        return 0
    except Exception as exc:
        write_error(root, exc)
        commit_all("status: record error")
        raise


if __name__ == "__main__":
    sys.exit(main())
