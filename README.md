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