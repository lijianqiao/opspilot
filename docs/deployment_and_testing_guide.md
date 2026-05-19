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

sudo ufw allow 8000/tcp
sudo ufw allow 8090/tcp
sudo ufw allow 3000/tcp
sudo ufw allow 9090/tcp
sudo ufw allow 8080/tcp
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

agent-core 需要一个 OpenAI-compatible LLM 服务。推荐在宿主机运行 **llama.cpp server**。

### 3.1 安装 llama.cpp

```bash
# 在宿主机（非容器内）执行
cd ~
git clone https://github.com/ggerganov/llama.cpp.git
cd llama.cpp
cmake -B build
cmake --build build --config Release -j$(nproc)
```

### 3.2 下载模型

准备一个 GGUF 格式模型文件，例如 Qwen3-5-9B 或其他。将 `.gguf` 文件放到 `~/models/` 目录。

```bash
mkdir -p ~/models
# 示例：从 HuggingFace 下载（需安装 huggingface_hub）
# pip install huggingface_hub
# huggingface-cli download Qwen/Qwen3-5-9B-GGUF qwen3-5-9b-q4_k_m.gguf --local-dir ~/models
```

### 3.3 启动 llama.cpp server

```bash
# 建议在 screen/tmux 中运行，或写成 systemd service
~/llama.cpp/build/bin/llama-server \
  -m ~/models/qwen3-5-9b-q4_k_m.gguf \
  --port 8080 \
  --host 0.0.0.0
```

验证 LLM 服务可用：

```bash
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen","messages":[{"role":"user","content":"say hi"}]}'
```

---

## 4. 修改配置并启动

### 4.1 配置 docker-compose.yml 中的 LLM 地址

编辑 `infra/docker-compose.yml`，修改 `agent-core` 服务的 `OPSPILOT_LLM_BASE_URL`：

```yaml
agent-core:
  build:
    context: ../
    dockerfile: Dockerfile
  ports:
    - "8000:8000"
  environment:
    - OPSPILOT_LLM_BASE_URL=http://host.docker.internal:8080/v1
    - OPSPILOT_LLM_MODEL=qwen3.5-9b
    - OPSPILOT_LLM_API_KEY=sk-local
    - OPSPILOT_PG_DSN=postgresql://opspilot:opspilot@postgres:5432/opspilot
  depends_on:
    postgres:
      condition: service_started
    qdrant:
      condition: service_started
    redis:
      condition: service_started
  extra_hosts:
    - "host.docker.internal:host-gateway"
```

> **关键**：`extra_hosts` 让容器内的 `host.docker.internal` 能解析到宿主机 IP，从而访问宿主机上运行的 llama.cpp。

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

### 5.11 Grafana 控制台验证

浏览器访问 `http://<VM_IP>:3000`

- 用户名：`admin`
- 密码：`admin`

进入 **Dashboards → OpsPilot Overview**，确认能看到 4 个面板（需要先产生一些流量，即先执行几次 /ask）。

### 5.12 Prometheus 查询验证

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

### 5.13 一键完整测试脚本

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
