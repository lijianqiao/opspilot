#!/bin/bash
# 部署后冒烟：健康检查 + 鉴权 /ask + 快速 pytest
set -euo pipefail
cd "$(dirname "$0")/.."
set -a && source .env && set +a
: "${OPSPILOT_API_AUTH_TOKEN:?请在项目根 .env 中设置 OPSPILOT_API_AUTH_TOKEN}"

AUTH="Authorization: Bearer ${OPSPILOT_API_AUTH_TOKEN}"

echo "== healthz =="
curl -sf http://localhost:8000/healthz
echo ""

echo "== /ask =="
curl -sf -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" -H "$AUTH" \
  -d '{"question":"default 有哪些 pod 不正常"}' | head -c 300
echo ""

echo "== pytest (quick) =="
uv run pytest -q --tb=no

echo "OK"
