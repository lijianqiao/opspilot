# OpsPilot

> LLM Agent 驱动的运维智能助手平台。

## 简介

OpsPilot 通过 Agent 编排与工具调用，帮助运维工程师在告警处理、日志/指标分析与标准化操作上更高效、可追溯地工作。详细架构见 [架构文档](docs/ARCHITECTURE.md)。

## 环境要求

- **Python**：`>= 3.12`
- **Docker**：用于 Postgres、Qdrant、Redis 等依赖服务

## 快速开始

```bash
# 安装依赖
uv sync

# 启动依赖服务
docker compose -f infra/docker-compose.yml up -d

# 运行测试
uv run pytest -q

# 提一个运维问题（需要本地 llama.cpp 或 OpenAI-compatible server :8080）
uv run opspilot ask "default 有哪些 pod 不正常"

# Plan-Execute 模式（复杂多步任务）
uv run opspilot ask "default 有哪些 pod 不正常" --plan

# 启动 HTTP API
uv run uvicorn opspilot.entrypoints.http_api:app --port 8000

# 启动 LLM Gateway（OpenAI 兼容代理，默认 :8090）
uv run opspilot-gateway
```

Grafana: http://localhost:3000 (`admin` / `admin`)
Prometheus: http://localhost:9090

### 可选能力

```bash
# RAG 知识库：导入 Runbook 到 Qdrant
uv run python scripts/ingest_runbooks.py

# Eval 评估
uv run python scripts/run_eval.py

# RAGAS 评估（需要真实 LLM）
uv run python scripts/run_rag_eval.py

# 接收 Alertmanager webhook
curl -X POST http://localhost:8000/alert \
  -H "Content-Type: application/json" \
  -d @fixtures/alertmanager_webhook.json

# QLoRA 微调实验（需要 WSL2/Linux + GPU）
python experiments/stage5_finetune/train_qlora.py --max-steps 20
```

> 未启动 llama.cpp 时 `/ask` 会报连接错误，属预期——核心逻辑已被单测覆盖。

## 安全模型

OpsPilot 对外服务与危险操作遵循 **fail-closed**：未配置密钥时拒绝服务，而非匿名开放。

### 鉴权

| 入口 | 机制 | 环境变量 |
| ---- | ---- | -------- |
| HTTP API `/ask`、`/alert` | `Authorization: Bearer <token>` | `OPSPILOT_API_AUTH_TOKEN` |
| Alertmanager Webhook `/alert` | `X-OpsPilot-Signature`（HMAC-SHA256 body） | `OPSPILOT_ALERTMANAGER_HMAC_SECRET` |
| LLM Gateway `/v1/chat/completions` | Bearer + Redis 限流 | `OPSPILOT_GATEWAY_AUTH_TOKEN`（见 gateway 配置） |
| 飞书 WS / 卡片 | 事件验签 | `OPSPILOT_FEISHU_VERIFICATION_TOKEN`、`OPSPILOT_FEISHU_ENCRYPT_KEY` |

`OPSPILOT_API_AUTH_TOKEN` 或 `OPSPILOT_ALERTMANAGER_HMAC_SECRET` 为空时，对应端点返回 **503**（未配置鉴权），避免“忘配 token 就裸奔”。`/healthz`、`/metrics` 不鉴权。

### 人工确认（HITL）

1. Agent 尝试执行 **高风险工具** 或输入含破坏性意图时，`guarded_call_tool` 拦截并登记 `ConfirmationStore`（随机 `request_id` + 一次性 token，带 TTL）。
2. 飞书交互卡片回调 `handle_card_action` 经人工点击后调用 `STORE.confirm(...)`。
3. 同一 `request_id` 在已确认状态下再次执行工具时 `consume()` 一次性放行，并记录 `confirmed_by`。
4. `confirm_dangerous_op` 工具**仅提示**，不能自行放行（已移除静态 `CONFIRM` token）。

生产路径使用 `langgraph_agent` / `plan_execute`（`guarded_call_tool`）；`react.py` 为无 guardrails 的学习参照，**未从包级导出**。

### 操作审计与回滚

- 路径：默认 `logs/opspilot_audit.jsonl`（`OPSPILOT_AUDIT_LOG_PATH`）。
- 字段：`ts`、`tool`、`tool_input`、`actor`、`confirmed_by`、`status`（`blocked` / `executed`）、`result`、`rollback`（如 scale 前的副本数）。
- 写失败只打日志，不阻断主流程。

### LLM 容错

- **重试**：tenacity，仅 5xx / 传输错误，最多 3 次，指数退避。
- **熔断**：连续失败达阈值后 `CircuitOpenError` 快速失败，冷却后半开探测。
- 不在 Agent 层叠加重试（避免与 Gateway fallback 双重重试）。

### 必配环境变量（生产建议）

完整模板与说明见 [.env.example](.env.example)。对外服务前至少配置：

| 变量 | 用途 |
| ---- | ---- |
| `OPSPILOT_API_AUTH_TOKEN` | HTTP `/ask`、`/alert` Bearer 鉴权 |
| `OPSPILOT_ALERTMANAGER_HMAC_SECRET` | Alertmanager Webhook HMAC 验签 |
| `OPSPILOT_FEISHU_VERIFICATION_TOKEN` | 飞书事件验签（启用飞书时） |
| `OPSPILOT_FEISHU_ENCRYPT_KEY` | 飞书消息加密（启用加密时） |
| `OPSPILOT_GATEWAY_AUTH_TOKEN` | LLM Gateway Bearer 鉴权（启用网关时） |
| `OPSPILOT_CONFIRM_TTL_SECONDS` | 人工确认 pending TTL（默认 300） |
| `OPSPILOT_AUDIT_LOG_PATH` | 操作审计 JSONL 路径（默认 `logs/opspilot_audit.jsonl`） |

```bash
cp .env.example .env   # 或 cp .env.example infra/.env（按你的部署方式）
```

## 阶段文档

| 阶段 | 内容                | 文档                                                                                     |
| ---- | ------------------- | ---------------------------------------------------------------------------------------- |
| 0    | Agent 基础框架      | [docs/stages/stage0_foundation.md](docs/stages/stage0_foundation.md)                     |
| 1    | ReAct + 工具层      | [docs/stages/stage1_agent_core.md](docs/stages/stage1_agent_core.md)                     |
| 2    | Plan-Execute + Eval | [docs/stages/stage2_agent_advanced.md](docs/stages/stage2_agent_advanced.md)             |
| 3    | 多智能体 Supervisor | [docs/stages/stage3_multi_agent.md](docs/stages/stage3_multi_agent.md)                   |
| 4    | RAG 知识库          | [docs/stages/stage4_rag_knowledge_base.md](docs/stages/stage4_rag_knowledge_base.md)     |
| 5    | LLM Gateway + QLoRA | [docs/stages/stage5_gateway_finetune.md](docs/stages/stage5_gateway_finetune.md)         |
| 6    | 工程化交付          | [docs/stages/stage6_engineering_delivery.md](docs/stages/stage6_engineering_delivery.md) |
