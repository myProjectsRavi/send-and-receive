#!/usr/bin/env bash
set -euo pipefail

if [ -f .env.local ]; then
  set -a
  source .env.local
  set +a
fi

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r orchestrator/requirements.txt
python -m orchestrator.run
