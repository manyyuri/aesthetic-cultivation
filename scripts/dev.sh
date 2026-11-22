#!/bin/sh
# 同起后端与前端；Ctrl-C 一起退。用 trap 而不是 kill %1（make 用的是 /bin/sh，没有 job control）
set -e
PYTHONPATH=apps/api/src apps/api/.venv/bin/python -m uvicorn ac_api.app:app \
  --app-dir apps/api/src --port "${PORT:-8710}" --reload &
API_PID=$!
trap 'kill "$API_PID" 2>/dev/null || true' EXIT INT TERM
pnpm --filter @ac/web dev --port "${WEB_PORT:-5173}"
