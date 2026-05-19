# OpsPilot

> 一个用 LLM Agent 驱动的运维智能助手平台。

<!-- TODO: 可选徽章（替换为你的仓库地址与 CI） -->
<!-- [![Python](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/downloads/) -->
<!-- [![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE) -->

## 简介

<!-- TODO: 用 2～4 句话写清：解决什么问题、给谁用、与同类方案的区别 -->

OpsPilot 旨在通过 Agent 编排与工具调用，帮助运维同学在告警处理、日志/指标分析与标准化操作上更高效、可追溯地工作。详细愿景与分层设计见 [架构文档](docs/ARCHITECTURE.md)。

## 功能特性

<!-- TODO: 开发过程中逐项勾选或改写 -->

- [ ] **入口**：飞书 Bot（WebSocket）/ CLI / HTTP / Alertmanager（规划中）
- [ ] **Agent Core**：Supervisor + 专用子 Agent（规划中）
- [ ] **工具层**：Mock + 采样数据；可选接真实集群（规划中）
- [ ] **可观测**：追踪与最小 Eval Harness（规划中）

## 环境要求

- **Python**：`>= 3.14`（见 `.python-version` / `pyproject.toml`）
- **其他**：<!-- TODO: 如 llama.cpp、Postgres、Redis 等，随实现补充 -->

## 快速开始

<!-- TODO: 待有可运行入口后更新命令 -->

```bash
# 克隆仓库
git clone <YOUR_REPO_URL>
cd opspilot

# 建议使用 uv / pip 安装依赖（任选其一）
# uv sync
# pip install -e .

# 运行入口（占位）
python main.py
```

## 10 分钟复现

```bash
uv sync
uv run pytest -q
uv run python scripts/run_eval.py

# 启动依赖与 agent-core
docker compose -f infra/docker-compose.yml up -d postgres qdrant redis
docker compose -f infra/docker-compose.yml up --build agent-core prometheus grafana

# 健康检查
curl http://localhost:8000/healthz
curl http://localhost:8000/metrics

# 运行 demo smoke（需要本地 llama.cpp/OpenAI-compatible server 可用）
uv run python scripts/demo_smoke.py
```

Grafana: http://localhost:3000 (`admin` / `admin`)
Prometheus: http://localhost:9090

默认 `agent-core` 连接 `http://host.docker.internal:8080/v1` 的 OpenAI-compatible LLM server。没有启动 llama.cpp 时，单测和离线 Eval 仍可运行；真实 `/ask` demo 需要可用 LLM。

## Quickstart

跑通第一条纵切（CLI → 手写 ReAct → mock 工具，基于 fixture 回答）只需 3 步。详见 [阶段 0 总结文档](docs/stages/stage0_foundation.md)。

```bash
# 1. 安装依赖（一键创建 .venv 并锁定）
uv sync

# 2. 另开终端，启动本地 llama.cpp（OpenAI 兼容 server，:8080；模型路径换成你本地的 GGUF）
./llama-server -m /path/to/Qwen3.5-9B.Q4_K_M.gguf --port 8080

# 3. 提一个运维问题
uv run opspilot ask "default 有哪些 pod 不正常"
```

> 未启动 llama.cpp 时会报连接错误，属预期——核心逻辑已被单测覆盖（`uv run pytest -v`，13 passed）。

### Stage 2 新增能力

```bash
# Plan-Execute 模式：先规划步骤再逐步执行（复杂多步任务）
uv run opspilot ask "default 有哪些 pod 不正常" --plan

# 最小 Eval：一条命令出 10-case 分数表（无需 llama.cpp，CI 友好）
uv run python scripts/run_eval.py

# Postgres Memory：断点续跑（需 Docker）
docker compose -f infra/docker-compose.yml up -d
export OPSPILOT_PG_DSN=postgresql://opspilot:opspilot@localhost:5432/opspilot
```

详见 [阶段 2 总结文档](docs/stages/stage2_agent_advanced.md)。

### Stage 3 新增能力 — 多智能体 Supervisor

```bash
# Supervisor 自动路由（普通消息走 Supervisor 分类 → 子 Agent）
uv run opspilot ask "查一下 user-service 的错误日志"

# Alert Handler HTTP 端点（接收 Alertmanager webhook）
uv run uvicorn opspilot.entrypoints.alert_webhook:app --port 8000
curl -X POST http://localhost:8000/alert \
  -H "Content-Type: application/json" \
  -d @fixtures/alertmanager_webhook.json

# 飞书交互卡片确认（危险操作二次确认，仅飞书入口触发）
# Eval 已扩展至 15 cases
uv run python scripts/run_eval.py
```

详见 [阶段 3 总结文档](docs/stages/stage3_multi_agent.md)。

### Stage 4 新增能力 — RAG 知识库

```bash
# 启动 Qdrant（如果未启动）
docker compose -f infra/docker-compose.yml up -d qdrant

# Ingestion: 导入 Runbook 文档到 Qdrant
uv run python scripts/ingest_runbooks.py

# RAGAS 评估: 30 QA 对 faithfulness + context_precision（需要真实 LLM）
uv run python scripts/run_rag_eval.py

# retrieve_runbook 现基于 Qdrant RAG（Qdrant 不可用时自动 fallback 到 keyword-match）
# Eval 已扩展至 18 cases
uv run python scripts/run_eval.py
```

详见 [阶段 4 总结文档](docs/stages/stage4_rag_knowledge_base.md)。

### Stage 5 新增能力 — LLM Gateway + QLoRA 原理实验

```bash
# 启动 Redis（Gateway 限流用）
docker compose -f infra/docker-compose.yml up -d redis

# 另开终端启动 llama.cpp OpenAI 兼容 server（默认 :8080）
./llama-server -m /path/to/Qwen3.5-9B.Q4_K_M.gguf --port 8080

# 启动 Gateway（OpenAI 兼容代理，默认 :8090）
uv run opspilot-gateway

# 用 curl 打 Gateway
curl http://localhost:8090/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer anything" \
  -d '{"model":"qwen3.5-9b","messages":[{"role":"user","content":"hello"}]}'

# 指标
curl http://localhost:8090/metrics
```

QLoRA 实验见 `experiments/stage5_finetune/README.md`。训练依赖不进入主项目依赖。

详见 [阶段 5 总结文档](docs/stages/stage5_gateway_finetune.md)。