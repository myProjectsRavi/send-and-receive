# Setup & Usage (GitHub + Local)

## GitHub (web) setup
1. Install the Jules GitHub App on this repo.
2. Add Actions secrets:
   - JULES_KEY_ARCH
   - JULES_KEY_DEV
   - JULES_KEY_REVIEW
   - JULES_SOURCE (source name, not repo URL)
   - JULES_API_BASE (optional)
3. Open **Actions** → enable workflows if prompted.

## GitHub (web) usage
1. Create an issue.
2. Add a comment:
   - `/agent1 ...` (replace backlog)
   - `/agent1-append ...` (append enhancements)
3. Watch **Actions → Orchestrator**.
4. Download status from **Artifacts** after each run:
   - `orchestrator-status-<run_id>` contains `status/*.json`.

## Local setup (laptop)
1. Copy env template:
   ```
   cp .env.local.example .env.local
   ```
2. Fill `.env.local` with keys and `JULES_SOURCE`.
3. Optional: put long prompt into `prompt.txt` and set `ORCH_PROMPT_FILE=prompt.txt`.
4. Run:
   ```
   ./scripts/run_local.sh
   ```

## Status output
- In GitHub Actions runs: download artifact `orchestrator-status-<run_id>`.
- Local runs: status is written to `status/*.json`.
