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
