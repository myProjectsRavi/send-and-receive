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
from .git_utils import commit_all, commit_paths
from .github_client import (
    create_pr,
    find_branch_by_session_id,
    find_pr_by_head,
    get_pr_info,
    is_pr_merged,
    merge_pr,
)
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


def _out_of_time(run_deadline: float, buffer_seconds: int = 60) -> bool:
    return time.time() + buffer_seconds >= run_deadline


def poll_for_pr_url(
    client: JulesClient,
    session_name: str,
    cfg: Config,
    feature_id: str | None,
    run_deadline: float,
) -> str | None:
    deadline = time.time() + cfg.max_poll_minutes * 60
    branch: str | None = None
    session_id = session_name.split("/")[-1]
    while time.time() < deadline:
        if _out_of_time(run_deadline):
            break
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
    return None


def poll_for_backlog(
    client: JulesClient,
    session_name: str,
    cfg: Config,
    run_deadline: float,
) -> dict[str, Any] | None:
    deadline = time.time() + cfg.max_poll_minutes * 60
    while time.time() < deadline:
        if _out_of_time(run_deadline):
            break
        text = collect_activity_text(client, session_name)
        payload = extract_backlog_json(text)
        if payload:
            return payload
        time.sleep(cfg.poll_seconds)
    return None


def poll_for_review(
    client: JulesClient,
    session_name: str,
    cfg: Config,
    run_deadline: float,
) -> dict[str, Any]:
    deadline = time.time() + cfg.max_poll_minutes * 60
    while time.time() < deadline:
        if _out_of_time(run_deadline):
            break
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


def normalize_verdict(value: str) -> str:
    verdict = value.strip().upper()
    if verdict in {"CHANGES_REQUESTED", "REQUEST_CHANGES", "REQUESTED_CHANGES"}:
        return "NEEDS_CHANGES"
    if verdict in {"APPROVED", "PASS"}:
        return "PASS"
    return verdict


def poll_for_session_completion(client: JulesClient, session_name: str, cfg: Config, run_deadline: float) -> str:
    deadline = time.time() + cfg.max_poll_minutes * 60
    while time.time() < deadline:
        if _out_of_time(run_deadline):
            return "PENDING"
        session = client.get_session(session_name)
        state = str(session.get("state") or session.get("status") or "").upper()
        if state in {"COMPLETED", "FAILED", "CANCELLED"}:
            return state
        time.sleep(cfg.poll_seconds)
    return "PENDING"


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


def handle_passed_review(
    cfg: Config,
    store: BacklogStore,
    root: Path,
    feature_id: str,
    pr_url: str,
) -> bool:
    store.update_feature_fields(feature_id, status="review", pr_url=pr_url, review_verdict="PASS")
    token = cfg.github_token
    if token and is_pr_merged(pr_url, token, cfg.github_api_url):
        store.update_feature_status(feature_id, "done")
        store.update_story_status(feature_id, "done")
        store.update_feature_fields(feature_id, review_verdict="PASS", merge_status="merged")
        store.save_all()
        write_status(root, store, feature_id, notes="Feature merged")
        commit_backlog(cfg, f"backlog: merge feature {feature_id}")
        return True
    if cfg.auto_merge and token:
        merge_result = merge_pr(pr_url, token, cfg.github_api_url, cfg.merge_method)
        message = str(merge_result.get("message", "")).strip()
        if merge_result.get("merged") or ("already" in message.lower() and "merge" in message.lower()):
            store.update_feature_status(feature_id, "done")
            store.update_story_status(feature_id, "done")
            store.update_feature_fields(feature_id, review_verdict="PASS", merge_status="merged")
            store.save_all()
            write_status(root, store, feature_id, notes="Feature merged")
            commit_backlog(cfg, f"backlog: merge feature {feature_id}")
            return True
        if not message:
            message = "Auto-merge blocked; manual merge required."
        store.update_feature_fields(
            feature_id,
            status="review",
            pr_url=pr_url,
            review_verdict="PASS",
            merge_status=message,
        )
        store.save_all()
        write_status(root, store, feature_id, notes=message)
        commit_backlog(cfg, f"backlog: merge blocked {feature_id}")
        return True

    note = "Review passed; awaiting manual merge"
    if not token:
        note = "Review passed; manual merge required (no GITHUB_TOKEN)."
    store.update_feature_fields(
        feature_id,
        status="review",
        pr_url=pr_url,
        review_verdict="PASS",
        merge_status=note,
    )
    store.save_all()
    write_status(root, store, feature_id, notes=note)
    commit_backlog(cfg, f"backlog: awaiting merge {feature_id}")
    return True


def acceptance_for_stories(acceptance_items: list[dict[str, Any]], stories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    story_ids = {story.get("id") for story in stories}
    return [item for item in acceptance_items if item.get("story") in story_ids]


def commit_backlog(cfg: Config, message: str) -> bool:
    paths = ["backlog"]
    if cfg.status_mode == "git":
        paths.append("status")
    return commit_paths(message, paths, push=True)


def commit_status(cfg: Config, message: str) -> bool:
    if cfg.status_mode != "git":
        return False
    return commit_paths(message, ["status"], push=True)


def run_agent1(cfg: Config, store: BacklogStore, mode: str, run_deadline: float) -> bool:
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
    payload = poll_for_backlog(client, session_name, cfg, run_deadline)
    if not payload:
        return False
    store.apply_agent1_payload(payload, mode=mode)
    store.save_all()
    return True


def run_agent2(
    cfg: Config,
    feature: dict[str, Any],
    stories: list[dict[str, Any]],
    acceptance: list[dict[str, Any]],
    run_deadline: float,
) -> tuple[str | None, str]:
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
    pr_url = poll_for_pr_url(client, session_name, cfg, feature.get("id"), run_deadline)
    return pr_url, session_name


def resume_agent2(
    cfg: Config,
    session_name: str,
    feature_id: str | None,
    run_deadline: float,
) -> str | None:
    client = JulesClient(cfg.require(cfg.key_dev, "JULES_KEY_DEV"), cfg.api_base)
    return poll_for_pr_url(client, session_name, cfg, feature_id, run_deadline)


def get_session_state(cfg: Config, session_name: str) -> str:
    client = JulesClient(cfg.require(cfg.key_dev, "JULES_KEY_DEV"), cfg.api_base)
    session = client.get_session(session_name)
    return str(session.get("state") or session.get("status") or "UNKNOWN").upper()


def run_agent2_fix(
    cfg: Config,
    pr_url: str,
    review: dict[str, Any],
    branch: str | None,
    run_deadline: float,
) -> tuple[str, str]:
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
    state = poll_for_session_completion(client, session_name, cfg, run_deadline)
    return state, session_name


def resume_agent2_fix(cfg: Config, session_name: str, run_deadline: float) -> str:
    client = JulesClient(cfg.require(cfg.key_dev, "JULES_KEY_DEV"), cfg.api_base)
    return poll_for_session_completion(client, session_name, cfg, run_deadline)


def run_agent3(
    cfg: Config,
    pr_url: str,
    feature: dict[str, Any],
    stories: list[dict[str, Any]],
    acceptance: list[dict[str, Any]],
    branch: str | None,
    run_deadline: float,
) -> dict[str, Any]:
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
    return poll_for_review(client, session_name, cfg, run_deadline)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    cfg = Config.from_env(dry_run=args.dry_run)
    run_deadline = time.time() + cfg.run_max_minutes * 60
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
                ok = run_agent1(cfg, store, agent1_mode, run_deadline)
                if not ok:
                    write_status(root, store, None, notes="Agent1 backlog pending")
                    commit_backlog(cfg, "backlog: pending agent1")
                    return 0
                write_status(root, store, None, notes=f"Agent1 backlog updated ({agent1_mode})")
                commit_backlog(cfg, "backlog: update from agent1")

        feature = store.next_review_feature() or store.next_ready_feature()
        if not feature:
            log("No ready features found")
            write_status(root, store, None, notes="No ready features")
            commit_status(cfg, "status: no ready features")
            return 0

        feature_id = feature.get("id")
        pr_url = feature.get("pr_url")
        agent2_session = feature.get("agent2_session")
        agent2_fix_session = feature.get("agent2_fix_session")
        log(f"Processing feature {feature_id}")
        if (
            feature.get("status") == "review"
            and normalize_verdict(str(feature.get("review_verdict", ""))) == "PASS"
            and pr_url
        ):
            handle_passed_review(cfg, store, root, feature_id, pr_url)
            return 0
        if (
            feature.get("status") == "review"
            and normalize_verdict(str(feature.get("review_verdict", ""))) == "NEEDS_CHANGES"
            and agent2_fix_session
        ):
            fix_state = resume_agent2_fix(cfg, agent2_fix_session, run_deadline)
            if fix_state != "COMPLETED":
                store.update_feature_fields(
                    feature_id,
                    status="review",
                    agent2_fix_session=agent2_fix_session,
                    agent2_fix_state=fix_state,
                )
                store.save_all()
                write_status(root, store, feature_id, notes="Agent2 fix pending")
                commit_backlog(cfg, f"backlog: fix pending {feature_id}")
                return 0
        if feature.get("status") != "review":
            store.update_feature_status(feature_id, "in_progress")
            store.save_all()
            write_status(root, store, feature_id, notes="Feature in progress")
            commit_backlog(cfg, f"backlog: start feature {feature_id}")

        stories = store.get_stories_for_feature(feature_id)
        acceptance = acceptance_for_stories(store.acceptance.get("items", []), stories)

        if cfg.dry_run:
            log("Dry run: skipping Agent 2/3 API calls")
            return 0

        if not pr_url and agent2_session:
            pr_url = resume_agent2(cfg, agent2_session, feature_id, run_deadline)
        if not pr_url:
            pr_url, agent2_session = run_agent2(cfg, feature, stories, acceptance, run_deadline)
            store.update_feature_fields(feature_id, agent2_session=agent2_session)
            store.save_all()
            commit_backlog(cfg, f"backlog: agent2 session {feature_id}")
        if not pr_url:
            log("PR not ready; leaving feature in progress.")
            agent2_state = None
            if agent2_session:
                agent2_state = get_session_state(cfg, agent2_session)
            store.update_feature_fields(
                feature_id,
                status="in_progress",
                agent2_session=agent2_session,
                agent2_state=agent2_state,
            )
            store.save_all()
            write_status(root, store, feature_id, notes="PR pending")
            commit_backlog(cfg, f"backlog: pr pending {feature_id}")
            return 0

        log(f"PR created: {pr_url}")
        store.update_feature_fields(feature_id, status="review", pr_url=pr_url)
        store.save_all()
        write_status(root, store, feature_id, notes="Feature in review")
        commit_backlog(cfg, f"backlog: review feature {feature_id}")

        pr_info = get_pr_info(pr_url, cfg.require(cfg.github_token, "GITHUB_TOKEN"), cfg.github_api_url)
        review = run_agent3(cfg, pr_url, feature, stories, acceptance, pr_info.get("head_ref"), run_deadline)
        verdict = normalize_verdict(str(review.get("verdict", "")))

        if verdict == "PENDING":
            log("Review pending; no verdict found. Leaving feature in review state.")
            store.update_feature_fields(feature_id, status="review", pr_url=pr_url, review_verdict="PENDING")
            store.save_all()
            write_status(root, store, feature_id, notes="Review pending (no verdict)")
            commit_backlog(cfg, f"backlog: review pending {feature_id}")
            return 0

        if verdict == "NEEDS_CHANGES":
            log("Reviewer requested changes")
            fix_state, fix_session = run_agent2_fix(cfg, pr_url, review, pr_info.get("head_ref"), run_deadline)
            store.update_feature_fields(
                feature_id,
                status="review",
                agent2_fix_session=fix_session,
                agent2_fix_state=fix_state,
            )
            store.save_all()
            commit_backlog(cfg, f"backlog: fix session {feature_id}")
            if fix_state != "COMPLETED":
                write_status(root, store, feature_id, notes="Agent2 fix pending")
                return 0
            review = run_agent3(cfg, pr_url, feature, stories, acceptance, pr_info.get("head_ref"), run_deadline)
            verdict = normalize_verdict(str(review.get("verdict", "")))

        if verdict != "PASS":
            store.update_feature_fields(feature_id, status="review", pr_url=pr_url, review_verdict=verdict)
            store.save_all()
            write_status(root, store, feature_id, notes=f"Review verdict: {verdict}")
            commit_backlog(cfg, f"backlog: review verdict {feature_id}")
            return 0
        handle_passed_review(cfg, store, root, feature_id, pr_url)
        return 0
    except Exception as exc:
        write_error(root, exc)
        commit_status(cfg, "status: record error")
        raise


if __name__ == "__main__":
    sys.exit(main())
