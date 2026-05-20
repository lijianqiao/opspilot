# OpsPilot 部署与测试指南

> **目标环境**：Ubuntu 24.04 虚拟机（如 VMware Workstation 中的 Guest）+ Docker Compose。  
> **推荐 LLM**：云端 OpenAI-compatible API（DeepSeek / 硅基流动 / OpenAI 等），虚拟机无需 GPU、无需本地 llama.cpp。

## 目录

1. [环境准备](#1-环境准备)
2. [克隆代码与配置](#2-克隆代码与配置)
3. [启动服务](#3-启动服务)
4. [功能测试](#4-功能测试)
5. [常见问题](#5-常见问题)
6. [附录：其他 LLM 接入方式](#6-附录其他-llm-接入方式)

---

## 1. 环境准备

### 1.1 安装 Docker

```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
newgrp docker   # 或重新登录 shell

docker --version
docker compose version
```

### 1.2 安装 git、curl（pytest 建议再装 uv）

```bash
sudo apt-get update
sudo apt-get install -y git curl
# 后续跑单元测试需要 uv，见 §4.5
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env   # 或按安装脚本提示
```

### 1.3 防火墙（启用 ufw 时）

```bash
sudo ufw allow 8000/tcp comment 'opspilot HTTP API'
sudo ufw allow 3000/tcp comment 'Grafana'
sudo ufw allow 9090/tcp comment 'Prometheus'
# 云端 API 走 HTTPS 出站，一般无需开放 8080
```

从 **Windows 宿主机** 访问 VM 内服务：确认 VMware 为桥接或 NAT 端口转发，在 VM 内 `ip a` 查看 IP，浏览器访问 `http://<VM_IP>:8000/healthz`。

---

## 2. 克隆代码与配置

### 2.1 克隆仓库

```bash
cd ~
git clone https://github.com/lijianqiao/opspilot.git
cd opspilot
ls Dockerfile infra/ src/ scripts/ fixtures/
```

### 2.2 创建根目录 `.env`

Compose 与宿主机 `uv`/`pytest` **共用项目根目录 `.env`**（`infra/docker-compose.yml` 中 `env_file: ../.env`）。

```bash
cp .env.example .env
nano .env
```

**虚拟机 + 云端 API 推荐最小配置示例：**

```bash
# ---- LLM（DeepSeek 示例，按平台替换）----
OPSPILOT_LLM_BASE_URL=https://api.deepseek.com/v1
OPSPILOT_LLM_MODEL=deepseek-chat
OPSPILOT_LLM_API_KEY=sk-你的云端密钥

# ---- HTTP API 鉴权（必填，否则 /ask、/alert 返回 503）----
OPSPILOT_API_AUTH_TOKEN=请设置一串随机密钥-仅联调可自拟

# ---- 飞书 Bot（启用 feishu-bot 容器时必填）----
# OPSPILOT_FEISHU_APP_ID=
# OPSPILOT_FEISHU_APP_SECRET=
# OPSPILOT_FEISHU_VERIFICATION_TOKEN=
# OPSPILOT_FEISHU_ENCRYPT_KEY=
# feishu-bot 容器内由 compose 覆盖为 http://agent-core:8000
# OPSPILOT_AGENT_CORE_URL=http://localhost:8000

# ---- 可选：告警 Webhook 验签（不配则 /alert 同样 503）----
# OPSPILOT_ALERTMANAGER_HMAC_SECRET=

# ---- 人工确认 / 审计（有默认值，一般可不改）----
OPSPILOT_CONFIRM_TTL_SECONDS=300
OPSPILOT_AUDIT_LOG_PATH=logs/opspilot_audit.jsonl

# ---- Postgres（与 compose 中 postgres 服务一致）----
POSTGRES_USER=opspilot
POSTGRES_PASSWORD=opspilot
POSTGRES_DB=opspilot
POSTGRES_HOST_PORT=5432
```

| 平台 | base_url | 模型名示例 |
| ---- | -------- | ---------- |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |
| 硅基流动 | `https://api.siliconflow.cn/v1` | `Qwen/Qwen2.5-7B-Instruct` |

完整变量说明见 [.env.example](../.env.example) 与 [README 安全模型](../README.md#安全模型)。

### 2.3 验证云端 API（启动容器前）

```bash
curl -s https://api.deepseek.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-你的云端密钥" \
  -d '{"model":"deepseek-chat","messages":[{"role":"user","content":"hi"}]}'
```

能返回 JSON 即可继续。

### 2.4 联调用的 curl 鉴权变量（可选）

```bash
# 写入当前 shell，后续测试命令可直接引用
export OPSPILOT_API_AUTH_TOKEN='你在根目录 .env 里设置的 token'
```

---

## 3. 启动服务

### 3.1 启动全部容器

在仓库根目录执行：

```bash
cd ~/opspilot
docker compose --env-file .env -f infra/docker-compose.yml up -d --build
docker compose -f infra/docker-compose.yml ps
```

预期 **7 个服务**均为 `Up`：`postgres`、`qdrant`、`redis`、`agent-core`、`feishu-bot`、`prometheus`、`grafana`。

架构：**飞书 WS → `feishu-bot`（薄适配器）→ HTTP `AgentClient` → `agent-core`（唯一 Agent 运行时与确认状态机）**。

### 3.2 查看日志

```bash
docker compose -f infra/docker-compose.yml logs -f agent-core
docker compose -f infra/docker-compose.yml logs -f feishu-bot   # 飞书联调
# Ctrl+C 退出
```

### 3.3 健康检查（无需鉴权）

```bash
curl -s http://localhost:8000/healthz
# {"status":"ok"}

curl -s http://localhost:9090/-/healthy
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000/
```

---

## 4. 功能测试

以下在 **虚拟机内** 执行。`/ask`、`/alert` 必须带 **`Authorization: Bearer <OPSPILOT_API_AUTH_TOKEN>`**。

### 4.1 `/ask` — Agent 问答

```bash
curl -s -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${OPSPILOT_API_AUTH_TOKEN}" \
  -d '{"question": "default 有哪些 pod 不正常"}' | python3 -m json.tool
```

**预期**：JSON 含 `answer` 字段；首次调用较慢（云端推理）。  
**Plan 模式**：HTTP 请求体加 `"plan": true`，或飞书发送 `规划：` / `/plan ` 前缀（由 `feishu-bot` 转发）；CLI：`uv run opspilot ask "..." --plan`。

### 4.2 `/alert` — 告警诊断

```bash
curl -s -X POST http://localhost:8000/alert \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${OPSPILOT_API_AUTH_TOKEN}" \
  -d @fixtures/alertmanager_webhook.json | python3 -m json.tool
```

**预期**：`status` 为 `ok`，`diagnosis` 含诊断文本。

### 4.3 Prometheus 指标（无需鉴权）

```bash
curl -s http://localhost:8000/metrics | head -30
```

### 4.4 RAG：导入 Runbook（在 VM 宿主机执行）

```bash
cd ~/opspilot
uv sync
uv run python scripts/ingest_runbooks.py
```

**预期**：`Ingestion complete: ...`。Qdrant 端口已映射到宿主机 `6333`。  
**说明**：当前 `agent-core` 容器内 Runbook 向量检索默认连 `localhost:6333`，在容器网络中可能回退为关键词匹配；ingest 仍建议执行，CLI/宿主机脚本可正常用 RAG。

### 4.5 单元测试与 Eval（无需真实 LLM）

```bash
cd ~/opspilot
uv run pytest -q
# 预期：全绿（含渠道 API / AgentClient 单测）

uv run python scripts/run_eval.py
# 预期：TOTAL: 18/18 passed
```

### 4.6 Grafana（可选）

浏览器打开 `http://<VM_IP>:3000`，默认 `admin` / `admin`。先执行几次 `/ask` 产生流量后再看 **OpsPilot Overview** 面板。

### 4.7 一键冒烟脚本

仓库已提供 `scripts/test_deploy.sh`（读取根目录 `.env` 中的鉴权 token）：

```bash
chmod +x scripts/test_deploy.sh
./scripts/test_deploy.sh
```

### 4.8 可选组件（不在 compose 内）

| 组件 | 说明 |
| ---- | ---- |
| **LLM Gateway** | 宿主机 `uv run opspilot-gateway`，配置根目录 `.env` 中 `OPSPILOT_GATEWAY_*`，需 `OPSPILOT_GATEWAY_AUTH_TOKEN` |
| **飞书 Bot** | 默认由 compose 服务 `feishu-bot` 运行；需在 `.env` 配置 `OPSPILOT_FEISHU_*` 与 `OPSPILOT_API_AUTH_TOKEN`；本地调试可 `uv run opspilot-feishu` |
| **CLI** | `uv run opspilot ask "问题"`，读项目根 `.env` 或环境变量 |

---

## 5. 常见问题

### Q1: `/ask` 返回 503 `server auth not configured`

未设置 `OPSPILOT_API_AUTH_TOKEN`。在根目录 `.env` 中填写非空 token，重启 agent-core：

```bash
docker compose -f infra/docker-compose.yml up -d agent-core
```

### Q2: `/ask` 返回 401 `unauthorized`

请求头缺少或 token 错误。确认：

```bash
grep OPSPILOT_API_AUTH_TOKEN .env
curl ... -H "Authorization: Bearer <与上一致>"
```

### Q3: `/ask` 超时或 5xx

- 检查根目录 `.env` 中 `OPSPILOT_LLM_BASE_URL` / `OPSPILOT_LLM_API_KEY` / 模型名  
- VM 能否访问外网：`curl -I https://api.deepseek.com`  
- 查看日志：`docker compose -f infra/docker-compose.yml logs agent-core`

### Q4: `agent-core` 启动失败

```bash
docker compose -f infra/docker-compose.yml logs agent-core
```

常见原因：构建失败（缺 `uv.lock`）、依赖服务未就绪。可 `docker compose ... up -d postgres qdrant redis` 后再启 `agent-core`。

### Q5: RAG ingest 失败

确认 Qdrant 已启动：`docker compose -f infra/docker-compose.yml ps qdrant`，再重试 `uv run python scripts/ingest_runbooks.py`。

### Q6: 停止 / 重置

```bash
docker compose -f infra/docker-compose.yml down
docker compose -f infra/docker-compose.yml down -v   # 含数据卷，完全重置
docker compose -f infra/docker-compose.yml up -d --build
```

---

## 6. 附录：其他 LLM 接入方式

虚拟机默认推荐 **§2 云端 API**。若需本地推理，仅改根目录 `.env` 中 LLM 三项，无需改业务代码：

| 场景 | `OPSPILOT_LLM_BASE_URL` |
| ---- | ------------------------ |
| Windows 宿主机 llama.cpp，VM 内 Docker | `http://<Windows局域网IP>:8080/v1`（NAT 下网关多为 `ip route \| awk '/default/{print $3}'`） |
| Ubuntu 本机 llama.cpp | `http://host.docker.internal:8080/v1`，并在 `infra/docker-compose.yml` 的 `agent-core` 增加 `extra_hosts: ["host.docker.internal:host-gateway"]` |

本地方案需自行安装 llama.cpp、开放防火墙；细节见 [.env.example](../.env.example) 注释。
