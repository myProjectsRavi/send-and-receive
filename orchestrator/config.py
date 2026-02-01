from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass
class Config:
    api_base: str
    key_arch: str | None
    key_dev: str | None
    key_review: str | None
    source: str | None
    product_prompt: str | None
    poll_seconds: int
    max_poll_minutes: int
    require_plan_approval: bool
    github_token: str | None
    github_repository: str | None
    github_api_url: str
    github_server_url: str
    starting_branch: str
    agent1_mode: str
    run_max_minutes: int
    status_mode: str
    auto_merge: bool
    merge_method: str
    dry_run: bool

    @classmethod
    def from_env(cls, dry_run: bool = False) -> "Config":
        api_base = os.getenv("JULES_API_BASE") or "https://jules.googleapis.com/v1alpha"
        poll_seconds = int(os.getenv("ORCH_POLL_SECONDS", "10"))
        max_poll_minutes = int(os.getenv("ORCH_MAX_POLL_MINUTES", "20"))
        require_plan_approval = os.getenv("JULES_REQUIRE_PLAN_APPROVAL", "false").lower() in (
            "1",
            "true",
            "yes",
        )
        return cls(
            api_base=api_base,
            key_arch=os.getenv("JULES_KEY_ARCH"),
            key_dev=os.getenv("JULES_KEY_DEV"),
            key_review=os.getenv("JULES_KEY_REVIEW"),
            source=os.getenv("JULES_SOURCE"),
            product_prompt=os.getenv("PRODUCT_PROMPT") or None,
            poll_seconds=poll_seconds,
            max_poll_minutes=max_poll_minutes,
            require_plan_approval=require_plan_approval,
            github_token=os.getenv("GITHUB_TOKEN"),
            github_repository=os.getenv("GITHUB_REPOSITORY"),
            github_api_url=os.getenv("GITHUB_API_URL", "https://api.github.com"),
            github_server_url=os.getenv("GITHUB_SERVER_URL", "https://github.com"),
            starting_branch=os.getenv("ORCH_STARTING_BRANCH") or "main",
            agent1_mode=(os.getenv("ORCH_AGENT1_MODE") or "replace").lower(),
            run_max_minutes=int(os.getenv("ORCH_RUN_MAX_MINUTES", "27")),
            status_mode=(os.getenv("ORCH_STATUS_MODE") or "artifact").lower(),
            auto_merge=(os.getenv("ORCH_AUTO_MERGE") or "false").lower() in ("1", "true", "yes"),
            merge_method=(os.getenv("ORCH_MERGE_METHOD") or "squash").lower(),
            dry_run=dry_run,
        )

    def require(self, value: str | None, name: str) -> str:
        if value:
            return value
        raise RuntimeError(f"Missing required env var: {name}")
