# send-and-receive

## Local Daytime Runs
1. Copy `.env.local.example` to `.env.local` and fill in keys.
2. Optionally put your long prompt in a file and set `ORCH_PROMPT_FILE=prompt.txt`.
3. Optional: set `ORCH_AGENT1_MODE=append` for incremental enhancements.
4. Optional: set `ORCH_AUTO_MERGE=true` and `ORCH_MERGE_METHOD=squash`.
5. Run `scripts/run_local.sh`.

## Comment Intake
- `/agent1 ...` (replace backlog)
- `/agent1-append ...` (append enhancements)

## Automation
- Only manual triggers are enabled (issue comments + workflow dispatch).

## Docs
- `docs/SETUP.md`
