# OpsPilot 部署与测试指南

> 目标环境：Ubuntu 24.04 虚拟机，Docker 部署，全功能测试。

## 目录

1. [环境准备](#1-环境准备)
2. [克隆代码](#2-克隆代码)
3. [配置 LLM Server](#3-配置-llm-server)
4. [修改配置并启动](#4-修改配置并启动)
5. [功能测试](#5-功能测试)
6. [常见问题](#6-常见问题)

---

## 1. 环境准备

### 1.1 安装 Docker

```bash
# 卸载旧版本（如有）
for pkg in docker.io docker-doc docker-compose docker-compose-v2 podman-docker containerd runc; do
  sudo apt-get remove -y $pkg
done

# 使用官方脚本安装（推荐，一步到位）
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 将当前用户加入 docker 组（免 sudo）
sudo usermod -aG docker $USER

# 生效组变更 —— 退出当前 shell 重新登录，或执行：
newgrp docker

# 验证安装
docker --version
docker compose version
```

### 1.2 安装 git 和 curl

```bash
sudo apt-get update
sudo apt-get install -y git curl
```

### 1.3 开放防火墙端口（如果启用 ufw）

```bash
# 以下端口需要在宿主机可访问：
# 8000 - agent-core HTTP API
# 8090 - LLM Gateway（如用到）
# 3000 - Grafana
# 9090 - Prometheus
# 8080 - llama.cpp（LLM server，在宿主机运行）

sudo ufw allow 8000/tcp comment 'opspilot-agent-core HTTP API'
sudo ufw allow 8090/tcp comment 'opspilot-LLM Gateway'
sudo ufw allow 3000/tcp comment 'opspilot-Grafana'
sudo ufw allow 9090/tcp comment 'opspilot-Prometheus'
sudo ufw allow 8080/tcp comment 'opspilot-llama.cpp'
```

---

## 2. 克隆代码

```bash
cd ~
git clone https://github.com/lijianqiao/opspilot.git
cd opspilot
```

确认分支和文件完整：

```bash
git log --oneline -5
ls -la
# 应看到 Dockerfile, infra/, scripts/, fixtures/, src/ 等
```

---

## 3. 配置 LLM Server

agent-core 需要一个 OpenAI-compatible LLM 服务。以下三种方案**任选其一**即可。

---

### 方案 A：Cloud 云端大模型（推荐，无需 GPU）

使用 DeepSeek / OpenAI / 其他云端 API，宿主机无需安装任何模型推理软件。

#### 获取 API Key

| 平台                   | 注册地址                      | base_url                                            |
| ---------------------- | ----------------------------- | --------------------------------------------------- |
| DeepSeek               | https://platform.deepseek.com | `https://api.deepseek.com/v1`                       |
| OpenAI                 | https://platform.openai.com   | `https://api.openai.com/v1`                         |
| 硅基流动 (SiliconFlow) | https://siliconflow.cn        | `https://api.siliconflow.cn/v1`                     |
| 阿里百炼               | https://dashscope.aliyun.com  | `https://dashscope.aliyuncs.com/compatible-mode/v1` |

> 国内网络推荐 DeepSeek（便宜、中文友好）或硅基流动（免费额度多），两者都支持 OpenAI-compatible 接口。

#### 创建 `infra/.env` 文件

复制模板并编辑：

```bash
cp .env.example infra/.env
nano infra/.env     # 或 vim
```

按所选平台修改 `infra/.env`：

```bash
# 以 DeepSeek 为例
OPSPILOT_LLM_BASE_URL=https://api.deepseek.com/v1
OPSPILOT_LLM_MODEL=deepseek-chat
OPSPILOT_LLM_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx     # 替换为你的 API Key
```

```bash
# 以 OpenAI 为例
OPSPILOT_LLM_BASE_URL=https://api.openai.com/v1
OPSPILOT_LLM_MODEL=gpt-4o-mini
OPSPILOT_LLM_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx     # 替换为你的 API Key
```

> `docker compose` 会自动读取 `infra/.env` 中的变量，无需修改 `infra/docker-compose.yml`。

#### 验证 Cloud API 可用

```bash
curl -s https://api.deepseek.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" \
  -d '{"model":"deepseek-chat","messages":[{"role":"user","content":"say hi"}]}'
```

> 采用方案 A 则**跳过**下方方案 B / C，直接进入 [第 4 节修改配置并启动](#4-修改配置并启动)。

---

### 方案 B：VMware 虚拟机 → Windows 宿主机 llama.cpp

如果你已经在 Windows 宿主机上运行了 llama.cpp server，想让 VMware Ubuntu 虚拟机内的 Docker 容器访问它。

#### 步骤 1：确认 Windows 宿主机 llama.cpp 正在运行

在 Windows 终端中验证：

```powershell
curl http://localhost:8080/v1/chat/completions -H "Content-Type: application/json" -d '{\"model\":\"qwen\",\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}]}'
```

#### 步骤 2：确认 VMware 网络模式

| VMware 网络模式    | Windows 宿主机在 VM 中的地址  | 说明                              |
| ------------------ | ----------------------------- | --------------------------------- |
| **NAT（默认）**    | 网关 IP，通常是 `192.168.x.2` | 运行 `ip route                    | grep default` 查看 |
| **桥接 (Bridged)** | 宿主机局域网 IP               | 在 Windows 上运行 `ipconfig` 查看 |

在 Ubuntu VM 中执行以下命令确认宿主机 IP：

```bash
# NAT 模式：查看网关（即宿主机）
ip route | grep default | awk '{print $3}'
# 输出类似 192.168.127.2

# 桥接模式：查看宿主机局域网 IP（在 Windows 上运行 ipconfig）
# 例如 192.168.1.100
```

#### 步骤 3：从 VM 测试能否连通宿主机 llama.cpp

```bash
# 替换 <HOST_IP> 为上一步获取的宿主机 IP
curl http://<HOST_IP>:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen","messages":[{"role":"user","content":"say hi"}]}'
```

如果报 `connection refused`，检查 Windows 防火墙：确保 `llama-server.exe` 监听的 8080 端口允许来自其他设备的入站连接（控制面板 → Windows Defender 防火墙 → 高级设置 → 入站规则 → 新建规则 → 端口 8080 TCP）。

#### 步骤 4：创建 `infra/.env` 文件

```bash
cp .env.example infra/.env
```

编辑 `infra/.env`：

```bash
OPSPILOT_LLM_BASE_URL=http://<HOST_IP>:8080/v1     # 替换为宿主机 IP
OPSPILOT_LLM_MODEL=qwen3.5-9b
OPSPILOT_LLM_API_KEY=sk-local
```

因为 Windows 宿主机 IP 是局域网地址，Docker 容器可直接路由到达，**不需要** `extra_hosts`。

> 采用方案 B 则**跳过**下方方案 C，直接进入 [第 4 节修改配置并启动](#4-修改配置并启动)。

---

### 方案 C：虚拟机本地运行 llama.cpp

在 Ubuntu 虚拟机内直接安装和运行 llama.cpp（需要虚拟机有 GPU 或使用 CPU 推理）。

#### 安装 llama.cpp

```bash
cd ~
git clone https://github.com/ggerganov/llama.cpp.git
cd llama.cpp
cmake -B build
cmake --build build --config Release -j$(nproc)
```

#### 下载模型

将 `.gguf` 文件放到 `~/models/` 目录：

```bash
mkdir -p ~/models
# 示例：从 HuggingFace 下载
# pip install huggingface_hub
# huggingface-cli download Qwen/Qwen3-5-9B-GGUF qwen3-5-9b-q4_k_m.gguf --local-dir ~/models
```

#### 启动 llama.cpp server

```bash
~/llama.cpp/build/bin/llama-server \
  -m ~/models/qwen3-5-9b-q4_k_m.gguf \
  --port 8080 \
  --host 0.0.0.0
```

#### 验证

```bash
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen","messages":[{"role":"user","content":"say hi"}]}'
```

#### 创建 `infra/.env` 文件

```bash
cp .env.example infra/.env
```

编辑 `infra/.env`：

```bash
OPSPILOT_LLM_BASE_URL=http://host.docker.internal:8080/v1
OPSPILOT_LLM_MODEL=qwen3.5-9b
OPSPILOT_LLM_API_KEY=sk-local
```

> **注意**：此方案需要在 `infra/docker-compose.yml` 的 `agent-core` 服务中保留 `extra_hosts: ["host.docker.internal:host-gateway"]`，让容器能解析 `host.docker.internal` 到宿主机 IP。

---

## 4. 修改配置并启动

### 4.1 确认 LLM 配置

`docker compose` 会自动读取 `infra/.env` 文件。确认 `infra/.env` 已按你选择的方案正确填写：

```bash
cat infra/.env
```

- **方案 A**：`OPSPILOT_LLM_BASE_URL` 填云端 API 地址 + `OPSPILOT_LLM_API_KEY` 填真实 Key
- **方案 B**：`OPSPILOT_LLM_BASE_URL` 填 `http://<Windows宿主IP>:8080/v1`
- **方案 C**：`OPSPILOT_LLM_BASE_URL` 填 `http://host.docker.internal:8080/v1`，且需在 `infra/docker-compose.yml` 保留 `extra_hosts`

可以先用 curl 验证 LLM 连通性（见各方案的验证命令），确认通过后再执行下一步 docker compose up。

### 4.2 首次启动所有服务

```bash
cd ~/opspilot

# 构建 agent-core 镜像并启动全部 6 个容器
docker compose -f infra/docker-compose.yml up -d --build

# 查看启动状态
docker compose -f infra/docker-compose.yml ps
# 预期看到 6 个 service 都是 Up / healthy 状态
```

### 4.3 检查日志

```bash
# 查看 agent-core 日志，确认连接 LLM 成功
docker compose -f infra/docker-compose.yml logs -f agent-core
# 按 Ctrl+C 退出日志

# 检查各服务
docker compose -f infra/docker-compose.yml logs postgres
docker compose -f infra/docker-compose.yml logs qdrant
```

### 4.4 确认所有端口可达

```bash
curl http://localhost:8000/healthz
# 预期：{"status":"ok"}

curl http://localhost:9090/-/healthy
# 预期：Prometheus is Healthy.

curl http://localhost:3000/api/health
# 预期 Grafana 健康信息
```

---

## 5. 功能测试

以下测试全部在 **虚拟机内部** 执行（`curl` 打 localhost 即可）。

### 5.1 基础健康检查

```bash
# agent-core
curl -s http://localhost:8000/healthz | python3 -m json.tool
# {"status":"ok"}

# Grafana（浏览器访问或 curl）
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/
# 200
```

### 5.2 /ask 接口 —— ReAct Agent

```bash
curl -s -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "default 有哪些 pod 不正常"}' | python3 -m json.tool
```

**预期**：返回 JSON，`answer` 字段包含工具调用结果。首次调用可能较慢（LLM 推理时间）。

### 5.3 /ask 接口 —— Plan-Execute 模式

```bash
curl -s -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "default 有哪些 pod 不正常", "plan": true}' | python3 -m json.tool
```

### 5.4 /alert 接口 —— Alertmanager Webhook

```bash
curl -s -X POST http://localhost:8000/alert \
  -H "Content-Type: application/json" \
  -d @fixtures/alertmanager_webhook.json | python3 -m json.tool
```

**预期**：返回 `triage_result` 字段，包含 Runbook 检索结果和诊断。

### 5.5 Prometheus 指标

```bash
curl -s http://localhost:8000/metrics | head -50
```

**预期**：看到 `opspilot_agent_requests_total`、`opspilot_tool_call_seconds_bucket`、`opspilot_llm_tokens_estimated_total`、`opspilot_guardrail_blocks_total` 等指标。

### 5.6 RAG 知识库 —— Ingestion

```bash
# 安装 Python 依赖（宿主机或容器内均可，这里在宿主机用 uv）
cd ~/opspilot

# 如果没有安装 uv：
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.cargo/env

# 安装项目依赖
uv sync

# 执行 ingestion（导入 Runbook 到 Qdrant）
uv run python scripts/ingest_runbooks.py
```

**预期**：输出 `Ingestion complete: <N> chunks in collection`。

### 5.7 单元测试

```bash
cd ~/opspilot
uv run pytest -q
```

**预期**：全部 PASS（约 150 条），可能有 1 skipped。

### 5.8 Eval 评估

```bash
cd ~/opspilot
uv run python scripts/run_eval.py
```

**预期**：输出 `TOTAL: 18/18 passed`（不需要真实 LLM，全部基于 fixture）。

### 5.9 Demo Smoke 测试

```bash
cd ~/opspilot
uv run python scripts/demo_smoke.py --base-url http://localhost:8000
```

**预期**：3 个问答全部完成（需要 LLM server 正常运行）。

### 5.10 LLM Gateway 测试（可选）

> Gateway 在容器外独立运行，需要项目根目录的 `.env`（不是 `infra/.env`）。确保已 `cp .env.example .env`。

```bash
cd ~/opspilot

# 启动物理机上的 Gateway（不是容器内）
# 需要先启动 redis：docker compose -f infra/docker-compose.yml up -d redis
uv run opspilot-gateway &

# 测试转发
curl -s http://localhost:8090/healthz
# {"status":"ok"}

curl -s http://localhost:8090/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer anything" \
  -d '{"model":"qwen3.5-9b","messages":[{"role":"user","content":"hello"}]}' | python3 -m json.tool

# Gateway 指标
curl -s http://localhost:8090/metrics | grep opspilot_gateway
```

### 5.11 飞书 Bot 测试（可选）

> 飞书 Bot 需要从**飞书开放平台**注册应用后才能使用。如果没有飞书账号或不需要 IM 入口，可以跳过本节。

#### 前置准备：创建飞书应用

1. 访问 [飞书开放平台](https://open.feishu.cn/app) → **创建企业自建应用**
2. **添加能力**：开启「消息与群组」→「机器人」→ 获取 **App ID** 和 **App Secret**
3. **配置权限**（需要管理员审批，测试时可先由自己批准）：
   - `im:message` — 接收和发送消息
   - `im:message:send_as_bot` — 以机器人身份发送消息
4. **事件订阅**：添加 `im.message.receive_v1` 事件
5. **发布版本**：创建新版本并发布（审批通过后生效）

#### 配置环境变量

飞书 Bot 在容器外独立运行，读取的是**项目根目录的 `.env`**（不是 `infra/.env`）：

```bash
cd ~/opspilot
cp .env.example .env
```

编辑 `.env`，添加：

```bash
OPSPILOT_FEISHU_APP_ID=cli_xxxxxxxxxxxxxxxx
OPSPILOT_FEISHU_APP_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

#### 启动飞书 Bot

```bash
cd ~/opspilot
uv run python -c "from opspilot.entrypoints.feishu_ws import run; run()"
```

> 飞书 Bot 是独立的 WebSocket 长连接，不需要 agent-core 容器。Bot 启动后会在控制台输出日志，按 Ctrl+C 停止。

#### 在飞书中测试

在飞书桌面端找到你的机器人，发送以下消息测试：

| 测试内容 | 发送的消息 | 预期回复 |
|---------|-----------|---------|
| **基础问答（ReAct）** | `default 有哪些 pod 不正常` | Agent 调用工具，返回 pod 状态汇总 |
| **Plan-Execute 模式** | `规划：排查 user-service 最近错误日志` | 先输出执行计划，再逐步执行 |
| | `/plan default 有哪些 pod 不正常` | 同上，`/plan` 前缀也触发 Plan-Execute |
| **危险操作二次确认** | `把 order-service 扩容到 50 个副本` | Bot 弹出确认卡片，需点击「确认执行」或「取消」 |
| **@提及** | `@机器人 default 有哪些 pod 不正常` | 自动去除 @ 前缀，正常回复 |

> 确认卡片功能：当 agent 识别到危险操作（如扩容、删除）时，会通过 `feishu_card.py` 发送交互卡片。用户点击「确认执行」后才会真正调用工具，点击「取消」则放弃。

#### 运行飞书相关单元测试

```bash
cd ~/opspilot
uv run pytest tests/test_feishu_ws.py tests/test_feishu_card.py -v
```

预期：3-5 条测试全部 PASS（不需要真实飞书账号，全部基于 mock）。

### 5.12 Grafana 控制台验证

浏览器访问 `http://<VM_IP>:3000`

- 用户名：`admin`
- 密码：`admin`

进入 **Dashboards → OpsPilot Overview**，确认能看到 4 个面板（需要先产生一些流量，即先执行几次 /ask）。

### 5.13 Prometheus 查询验证

浏览器访问 `http://<VM_IP>:9090`

在查询框输入以下 PromQL 验证：

```promql
# Agent 请求速率
sum(rate(opspilot_agent_requests_total[5m])) by (status)

# 工具调用 P99
histogram_quantile(0.99, sum(rate(opspilot_tool_call_seconds_bucket[5m])) by (le, tool))

# Guardrail 拦截统计
sum(increase(opspilot_guardrail_blocks_total[1h])) by (tool)
```

### 5.14 一键完整测试脚本

将以下脚本保存并运行，一次性覆盖所有无 LLM 依赖的测试：

```bash
#!/bin/bash
# 保存为 ~/opspilot/test_all.sh
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

check() {
  local desc="$1"
  shift
  echo -n "  [$desc] ... "
  if "$@" > /dev/null 2>&1; then
    echo -e "${GREEN}PASS${NC}"
  else
    echo -e "${RED}FAIL${NC}"
    echo "    Command: $*"
  fi
}

echo "=== OpsPilot 全功能测试 ==="
echo ""

echo "--- 1. 服务健康检查 ---"
check "agent-core /healthz"     curl -sSf http://localhost:8000/healthz
check "agent-core /metrics"    curl -sSf http://localhost:8000/metrics
check "prometheus"              curl -sSf http://localhost:9090/-/healthy
check "grafana"                 curl -sSf -o /dev/null -w '' http://localhost:3000/

echo ""
echo "--- 2. Agent API 测试 ---"
check "/ask 接口"                curl -sSf -X POST http://localhost:8000/ask \
                                 -H "Content-Type: application/json" \
                                 -d '{"question":"default有哪些pod不正常"}'
check "/alert webhook"          curl -sSf -X POST http://localhost:8000/alert \
                                 -H "Content-Type: application/json" \
                                 -d @fixtures/alertmanager_webhook.json

echo ""
echo "--- 3. 单元测试 & Eval ---"
cd ~/opspilot
check "pytest"                  uv run pytest -q
check "run_eval"                uv run python scripts/run_eval.py

echo ""
echo "--- 4. RAG Ingestion ---"
check "ingest_runbooks"         uv run python scripts/ingest_runbooks.py

echo ""
echo "--- 5. 代码质量 ---"
check "ruff lint"               uv run ruff check .
check "ruff format"             uv run ruff format --check .

echo ""
echo "=== 测试完成 ==="
```

使用方法：

```bash
chmod +x ~/opspilot/test_all.sh
cd ~/opspilot
./test_all.sh
```

---

## 6. 常见问题

### Q1: `host.docker.internal` 无法解析

在 Linux 上，Docker 默认不解析 `host.docker.internal`。解决方法：

**方案 A（推荐）**：在 `infra/docker-compose.yml` 的 `agent-core` 服务中添加：

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

**方案 B**：把 `OPSPILOT_LLM_BASE_URL` 改为宿主机的实际局域网 IP，例如 `http://192.168.1.100:8080/v1`。

### Q2: 容器内无法连接宿主机端口

检查宿主机防火墙：

```bash
sudo ufw status
# 确认 8080 端口开放
```

如果使用 iptables 而非 ufw：

```bash
sudo iptables -L INPUT -v -n | grep 8080
```

### Q3: `docker compose up` 时 `agent-core` 启动失败

查看详细错误：

```bash
docker compose -f infra/docker-compose.yml logs agent-core
```

常见原因：
- 缺少 `uv.lock` 文件（确保 `uv sync` 后提交了 lock 文件）
- LLM server 未启动或地址错误
- Postgres/Qdrant/Redis 未就绪

### Q4: /ask 一直超时

检查 LLM server 日志，确保模型已加载完成：

```bash
# llama.cpp 启动后会有 "model loaded" 日志
# 确认端口监听
ss -tlnp | grep 8080
```

### Q5: Eval 测试报 RAG 相关失败

确认 Qdrant 已启动且 ingestion 已完成：

```bash
docker compose -f infra/docker-compose.yml ps qdrant
# State 应为 Up

# 重新执行 ingestion
uv run python scripts/ingest_runbooks.py
```

### Q6: 停止/重启服务

```bash
# 停止所有服务
docker compose -f infra/docker-compose.yml down

# 停止并删除数据卷（完全重置）
docker compose -f infra/docker-compose.yml down -v

# 重新构建并启动
docker compose -f infra/docker-compose.yml up -d --build
```
