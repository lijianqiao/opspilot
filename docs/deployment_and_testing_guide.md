# OpsPilot 部署与测试指南

> **目标环境**：Ubuntu 24.04 虚拟机（如 VMware Workstation 中的 Guest）+ Docker Compose。  
> **推荐 LLM**：云端 OpenAI-compatible API（DeepSeek / 硅基流动 / OpenAI 等），虚拟机无需 GPU、无需本地 llama.cpp。  
> **主联调路径**：飞书群/私聊 → `feishu-bot` 容器 → `agent-core`（HTTP）；curl `/ask` 仅作辅助验证。

## 目录

0. [生产部署假设 (Production assumptions for this MVP)](#0-生产部署假设-production-assumptions-for-this-mvp)
1. [环境准备](#1-环境准备)
2. [克隆代码与配置](#2-克隆代码与配置)
3. [启动服务](#3-启动服务)
4. [功能测试](#4-功能测试)（[§4.1 飞书联调](#41-飞书联调主路径) 为主）
5. [常见问题](#5-常见问题)
6. [附录：其他 LLM 接入方式](#6-附录其他-llm-接入方式)

---

## 0. 生产部署假设 (Production assumptions for this MVP)

当前阶段的生产部署边界（Production assumptions for this MVP）：

- **agent-core runs as a single replica.** 单副本部署即可承载现有负载；`ConfirmationStore` 等内存态尚未做多副本同步，扩多副本前需先抽到外部存储。
- **Infrastructure dependencies are internal-only.** `agent-core:8000`、Qdrant、Redis、Postgres、Grafana 仅在内网/VPC 暴露；外部访问只通过经过鉴权的渠道适配器（飞书 / 反向代理后的 HTTP）。
- **Audit source is `logs/opspilot_audit.jsonl`** and must be externally collected, backed up, protected from tampering, and monitored for disk-full conditions. 高危操作会先写一条 `approved` 审计再执行，若磁盘满或写失败，**操作不会执行**——所以磁盘容量与采集链路属于必须监控项。
- **Secrets may come from `.env` for MVP**; `.env` must not be committed and should be readable only by the service user（例如 `chmod 600 .env` 并归属运行 `agent-core` 的用户）。后续接入 KMS / Vault 后再迁移。

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
# 后续跑单元测试需要 uv，见 §4.6
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

# ---- HTTP API 鉴权（必填：agent-core 与 feishu-bot 共用同一 token）----
OPSPILOT_API_AUTH_TOKEN=请设置一串随机密钥-仅联调可自拟
# ---- 渠道内部鉴权（必填：feishu-bot 查询危险操作确认卡片 token）----
OPSPILOT_CHANNEL_INTERNAL_TOKEN=请设置另一串随机密钥-不要与 API token 相同

# ---- 飞书 Bot（飞书联调必填，与开放平台应用一致）----
OPSPILOT_FEISHU_APP_ID=cli_xxxxxxxx
OPSPILOT_FEISHU_APP_SECRET=xxxxxxxx
OPSPILOT_FEISHU_VERIFICATION_TOKEN=xxxxxxxx
OPSPILOT_FEISHU_ENCRYPT_KEY=xxxxxxxx
# 宿主机本地跑 opspilot-feishu 时用 localhost；Compose 内 feishu-bot 会被覆盖为 http://agent-core:8000
OPSPILOT_AGENT_CORE_URL=http://localhost:8000

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

# ---- Mock 联调（Docker / 飞书读 fixtures 数据，默认开启）----
OPSPILOT_USE_MOCK_TOOLS=true
# Docker 内由 compose 设为 /app/fixtures；宿主机 uv 可留空自动探测
# OPSPILOT_FIXTURES_DIR=
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

### 2.4 飞书开放平台（联调前 checklist）

在 [飞书开放平台](https://open.feishu.cn/app) 创建企业自建应用后：

| 项 | 说明 |
| ---- | ---- |
| **权限** | 开通「接收消息」「发送消息」「获取群组信息」等 IM 相关权限并发布版本 |
| **事件订阅** | 启用 **长连接（WebSocket）** 模式（与 `lark-oapi` WS 一致，无需公网回调 URL） |
| **机器人** | 将应用添加为群机器人，或在与机器人的私聊中 @ 机器人 |
| **凭证** | 将 App ID / App Secret、事件订阅的 Verification Token、Encrypt Key 填入根目录 `.env` 四项 `OPSPILOT_FEISHU_*` |

`OPSPILOT_API_AUTH_TOKEN`、`OPSPILOT_CHANNEL_INTERNAL_TOKEN` 与 `OPSPILOT_FEISHU_*` 须同时配置：`feishu-bot` 调 agent-core 的 `/ask` 等公开接口使用 API token，查询危险操作确认卡片 token 使用 channel internal token。

### 2.5 联调用的 shell 变量（可选）

```bash
# 写入当前 shell，后续 curl / 文档命令可直接引用
set -a && source .env && set +a
```

---

## 3. 启动服务

### 3.0 Compose 命令别名（推荐）

Compose 文件在 `infra/`，变量替换默认读 `infra/.env`；本项目使用**根目录** `.env`，请始终带 `--env-file .env`：

```bash
cd ~/opspilot
alias dc='docker compose --env-file .env -f infra/docker-compose.yml'
```

下文凡 `dc` 均指上述别名；未设置别名时，将 `dc` 替换为 `docker compose --env-file .env -f infra/docker-compose.yml`。

### 3.1 启动全部容器

在仓库根目录执行：

```bash
cd ~/opspilot
dc up -d --build
dc ps
```

预期 **7 个服务**均为 `Up`：`postgres`、`qdrant`、`redis`、`agent-core`、`feishu-bot`、`prometheus`、`grafana`。

架构：**飞书 WS → `feishu-bot`（薄适配器）→ HTTP `AgentClient` → `agent-core`（唯一 Agent 运行时与确认状态机）**。

仅验证 HTTP、暂不用飞书时，可不启动 `feishu-bot`：

```bash
dc up -d --build postgres qdrant redis agent-core prometheus grafana
```

### 3.2 查看日志

```bash
dc logs -f feishu-bot    # 飞书联调首选：WS 连接、收消息、调 agent-core
dc logs -f agent-core    # Agent 推理、工具调用、HITL 拦截
# Ctrl+C 退出
```

`feishu-bot` 启动成功时日志中应出现 lark WS 连接相关信息；收到群消息后应看到向 agent-core 发起 HTTP 的轨迹（或 Agent 模式日志）。

### 3.3 健康检查（无需鉴权）

```bash
curl -s http://localhost:8000/healthz
# {"status":"ok"}

curl -s http://localhost:9090/-/healthy
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000/
```

---

## 4. 功能测试

以下在 **虚拟机内** 执行。

### 4.1 飞书联调（主路径）

**前置**：§3.1 已 `Up`，且 `.env` 中 LLM、`OPSPILOT_API_AUTH_TOKEN`、四项 `OPSPILOT_FEISHU_*` 均已填写。

1. **看日志**（另开终端）  
   `dc logs -f feishu-bot`

2. **在飞书发消息**（群聊 @ 机器人，或私聊）  
   - 普通问答：`default 有哪些 pod 不正常`  
   - Plan 模式：`规划：查看 default 命名空间 pod` 或 `/plan 重启 order-service`

3. **预期**  
   - 机器人在数秒～数十秒内回复文本（首次调用云端 LLM 较慢）  
   - `feishu-bot` 日志：收到消息 → 调用 agent-core  
   - `agent-core` 日志：Supervisor / Plan-Execute 与工具调用  
   - 问「哪些 pod 不正常」应能列出 fixture 中的异常 Pod（如 `order-service` CrashLoopBackOff），**不要**出现 `/app/fixtures/... 不存在`

**Mock 数据**：`.env` 保持 `OPSPILOT_USE_MOCK_TOOLS=true`（默认）。镜像已包含 `fixtures/`，compose 另挂载 `../fixtures:/app/fixtures:ro` 便于改数据后无需重建。若改为 `false`，`kubectl get/describe` 会调真实集群（需容器内 `kubectl` 与 kubeconfig 挂载）；Prometheus/Loki/写操作尚未接真 API。

4. **危险操作（HITL）**  
   - 触发需确认的工具（如 scale）后，回复文本中含 `request_id=...`  
   - 机器人应**自动再发一张交互确认卡片**  
   - 点击「确认」→ toast 显示已确认；**当前版本确认后需再发一条消息**才会继续执行，不会自动续跑  
   - 卡片回调经 `feishu-bot` → `POST /channels/feishu/card-action` → agent-core 内 `STORE.confirm`

5. **排错顺序**  
   - 无回复：先看 `feishu-bot` 是否 `Up`、WS 是否报错、四项飞书凭证是否正确  
   - 有「处理出错」类固定文案：看 `agent-core` 日志（LLM 密钥、超时、工具异常）  
   - 有文字但无确认卡：看回复是否含 `request_id=`；用下面 curl 查 pending 是否存在

**本地不启容器、只调试飞书**（需本机已 `agent-core` 在 `localhost:8000`）：

```bash
# .env 中 OPSPILOT_AGENT_CORE_URL=http://localhost:8000
uv run opspilot-feishu
```

#### 辅助：用 curl 验证 agent-core（与飞书共用 token）

```bash
# 应先 source .env，见 §2.5
curl -s http://localhost:8000/healthz

curl -s -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${OPSPILOT_API_AUTH_TOKEN}" \
  -d '{"question": "default 有哪些 pod 不正常"}' | python3 -m json.tool
```

若 curl `/ask` 正常而飞书无回复，问题在飞书侧或 `feishu-bot`；若 curl 也失败，先修 `agent-core` / LLM 配置。

#### 辅助：查询 pending / 模拟卡片确认（进阶）

从 Agent 回复中复制 `request_id` 后：

```bash
curl -s "http://localhost:8000/channels/pending/<request_id>" \
  -H "Authorization: Bearer ${OPSPILOT_API_AUTH_TOKEN}" | python3 -m json.tool
```

公开 pending 查询不会返回确认 token。只有 `feishu-bot` 使用 `OPSPILOT_CHANNEL_INTERNAL_TOKEN` 调用内部接口生成确认卡片。

### 4.2 `/ask` — HTTP 直接问答（辅助）

```bash
curl -s -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${OPSPILOT_API_AUTH_TOKEN}" \
  -d '{"question": "default 有哪些 pod 不正常"}' | python3 -m json.tool
```

**预期**：JSON 含 `answer` 字段；首次调用较慢（云端推理）。  
**Plan 模式**：请求体加 `"plan": true`（飞书侧用 `规划：` / `/plan ` 前缀，由 `feishu-bot` 转发）。

### 4.3 `/alert` — 告警诊断

```bash
curl -s -X POST http://localhost:8000/alert \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${OPSPILOT_API_AUTH_TOKEN}" \
  -d @fixtures/alertmanager_webhook.json | python3 -m json.tool
```

**预期**：`status` 为 `ok`，`diagnosis` 含诊断文本。

### 4.4 Prometheus 指标（无需鉴权）

```bash
curl -s http://localhost:8000/metrics | head -30
```

### 4.5 RAG：导入 Runbook（在 VM 宿主机执行）

```bash
cd ~/opspilot
uv sync
uv run python scripts/ingest_runbooks.py
```

**预期**：`Ingestion complete: ...`。Qdrant 端口已映射到宿主机 `6333`。  
**说明**：当前 `agent-core` 容器内 Runbook 向量检索默认连 `localhost:6333`，在容器网络中可能回退为关键词匹配；ingest 仍建议执行，CLI/宿主机脚本可正常用 RAG。

### 4.6 单元测试与 Eval（无需真实 LLM）

```bash
cd ~/opspilot
uv run pytest -q
# 预期：全绿（含渠道 API / AgentClient 单测）

uv run python scripts/run_eval.py
# 预期：TOTAL: 18/18 passed
```

### 4.7 Grafana（可选）

浏览器打开 `http://<VM_IP>:3000`，默认 `admin` / `admin`。先执行几次 `/ask` 产生流量后再看 **OpsPilot Overview** 面板。

### 4.8 一键冒烟脚本

仓库已提供 `scripts/test_deploy.sh`（读取根目录 `.env` 中的鉴权 token）：

```bash
chmod +x scripts/test_deploy.sh
./scripts/test_deploy.sh
```

### 4.9 其他入口（可选）

| 组件 | 说明 |
| ---- | ---- |
| **飞书 Bot** | 生产路径：`dc up` 中的 `feishu-bot` 服务；本地调试：`uv run opspilot-feishu`（需 agent-core 可达） |
| **CLI** | `uv run opspilot ask "问题"` / `--plan`，直连 LLM，**不经过** feishu-bot（与飞书联调路径独立） |
| **LLM Gateway** | 宿主机 `uv run opspilot-gateway`，配置 `OPSPILOT_GATEWAY_*` |

---

## 5. 常见问题

### Q1: `/ask` 返回 503 `server auth not configured`

未设置 `OPSPILOT_API_AUTH_TOKEN`。在根目录 `.env` 中填写非空 token，重启 agent-core：

```bash
dc up -d agent-core feishu-bot
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
- 查看日志：`dc logs agent-core`

### Q4: `agent-core` 启动失败

```bash
dc logs agent-core
```

常见原因：构建失败（缺 `uv.lock`）、依赖服务未就绪。可 `dc up -d postgres qdrant redis` 后再启 `agent-core`。

### Q5: RAG ingest 失败

确认 Qdrant 已启动：`dc ps qdrant`，再重试 `uv run python scripts/ingest_runbooks.py`。

### Q6: 飞书发消息无回复

1. `dc ps feishu-bot` 是否为 `Up`；`dc logs feishu-bot` 是否有 WS 连接错误  
2. `.env` 中 `OPSPILOT_FEISHU_APP_ID` / `SECRET` / `VERIFICATION_TOKEN` / `ENCRYPT_KEY` 是否与开放平台一致  
3. 应用是否已发布、机器人是否已加入群并 @  
4. 事件订阅是否为 **长连接** 模式  
5. 同机 curl `/ask`（§4.1 辅助命令）是否正常；若 curl 失败，先修 agent-core / LLM  
6. `feishu-bot` 调 core 公开接口需 `OPSPILOT_API_AUTH_TOKEN`，查询确认卡片需 `OPSPILOT_CHANNEL_INTERNAL_TOKEN`

### Q7: 飞书有回复但没有确认卡片

- 回复正文是否包含 `request_id=`（未触发危险工具则不会发卡）  
- `dc logs feishu-bot` 是否出现 `get_pending` / `sent confirm card`  
- 用 §4.1 的 `GET /channels/pending/<id>` 确认 agent-core 侧 pending 仍存在（未过期）；该公开接口不会返回 token

### Q8: 点击确认卡片后 Agent 没有继续执行

当前设计：**确认只写入 STORE，不会自动发起下一轮 Agent**。请在飞书中**再发一条消息**（例如「继续执行 scale」）触发新的 `/ask`。后续版本可能增加 resume API。

### Q9: 停止 / 重置

```bash
dc down
dc down -v   # 含数据卷，完全重置
dc up -d --build
```

---

## 6. 附录：其他 LLM 接入方式

虚拟机默认推荐 **§2 云端 API**。若需本地推理，仅改根目录 `.env` 中 LLM 三项，无需改业务代码：

| 场景 | `OPSPILOT_LLM_BASE_URL` |
| ---- | ------------------------ |
| Windows 宿主机 llama.cpp，VM 内 Docker | `http://<Windows局域网IP>:8080/v1`（NAT 下网关多为 `ip route \| awk '/default/{print $3}'`） |
| Ubuntu 本机 llama.cpp | `http://host.docker.internal:8080/v1`，并在 `infra/docker-compose.yml` 的 `agent-core` 增加 `extra_hosts: ["host.docker.internal:host-gateway"]` |

本地方案需自行安装 llama.cpp、开放防火墙；细节见 [.env.example](../.env.example) 注释。
