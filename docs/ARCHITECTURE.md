# OpsPilot — AIOps Agent 平台架构设计文档（v2 · Agent 深耕版）

> 一个用 LLM Agent 驱动的运维智能助手平台。
> **主线 = Agent 工程深耕；周边层（Gateway / RAG / 微调 / 可观测）= 原理够用、能接进 Agent、面试能讲清楚。**
> 学习路径载体 · 可落地的运维工具

---

## 0. v2 相比 v1 改了什么（先看这个）

| 维度 | v1 | v2（本文档） |
|---|---|---|
| 主线 | 五层平铺，Agent 第 7 周才开始 | **Agent 第 1 周就纵切一刀**，全程主线 |
| 周边层定位 | 每层都做生产级 | Gateway/RAG/微调 = **原理向 + 接进 Agent**，不深挖 |
| 学习方式 | 直接上 LangGraph | **先手写 ReAct 一周 → 再迁移 LangGraph**，理解深一档 |
| 运维后端 | 假设有真 k8s/Loki | **全 Mock + 真实采样数据**；真集群作可选附录 |
| 模型 | Qwen3.5-9B 微调（4060 跑不动） | 推理 = 本地 **llama.cpp + Qwen3.5-9B.Q4_K_M**；微调 = **Qwen3.5-2B-GGUF**，只为懂原理 |
| Eval | 缺失 | **最小 Eval 先行**（10 case / 3 指标），再渐进扩成 Harness |
| RAG | 一次性做完整 | 阶段 3 先 `retrieve_runbook` **stub**，阶段 4 再换真 Qdrant |
| 应用入口 | Web/CLI/Webhook | **飞书 Bot（WebSocket 长连接）为一等入口** + CLI + HTTP + Alertmanager |
| Agent 评估 | 缺失 | **新增 Agent Eval Harness**（轨迹/工具正确率/护栏拦截率），单列重点 |
| 每阶段产出 | 仅代码 + release | **每阶段必交一份阶段总结文档**（流程图+原理+如何运行），见 §3 |

---

## 1. 项目愿景

**一句话**：让运维工程师在飞书里用自然语言定位故障、操作基础设施、处理告警。

**核心场景**：

- 飞书里发：「prod 集群昨晚 2-3 点所有 pod 的 OOM 情况」→ Agent 调日志/指标工具 → 返回结构化报告
- Alertmanager 触发告警 → Alert Handler Agent 自动诊断 → 飞书推送根因 + 修复建议
- 飞书里发：「把 staging 的 user-service 滚动重启」→ K8s Operator Agent 规划命令 → **飞书交互卡片二次确认** → 执行 → 回卡反馈

**你的护城河**：运维背景 = 你天然懂 Agent 该调什么工具、什么是危险操作、告警长什么样。这是纯算法背景的人补不上的。

---

## 2. 整体架构

```
                 ┌────────────────────────────────────────────┐
                 │                应用入口层                    │
                 │  飞书Bot(WS长连接) · CLI · HTTP · Alertmgr   │
                 └───────────────────┬────────────────────────┘
                                     │  统一 AgentRequest
                 ┌───────────────────▼────────────────────────┐
                 │            Agent Core  (本项目主线)          │
                 │  ┌────────────────────────────────────────┐ │
                 │  │ Supervisor (多智能体路由 / 编排)         │ │
                 │  │   ├─ Log Analyzer   (ReAct)             │ │
                 │  │   ├─ K8s Operator   (Plan-Execute)      │ │
                 │  │   └─ Alert Handler  (协调上面两个)       │ │
                 │  ├────────────────────────────────────────┤ │
                 │  │ Tool Registry · Memory · Guardrails      │ │
                 │  │ Eval Harness · Langfuse Trace            │ │
                 │  └────────────────────────────────────────┘ │
                 └────┬──────────────┬───────────────┬─────────┘
                      │              │               │
              ┌───────▼────┐  ┌──────▼──────┐  ┌─────▼────────────┐
              │ LLM 接入   │  │ RAG Service │  │ Tool 实现层       │
              │（薄层）    │  │ (Qdrant)    │  │ ★Mock + 采样数据  │
              └─────┬──────┘  └──────┬──────┘  └─────┬────────────┘
                    │                │                │
            ┌───────▼────────┐  ┌────▼─────┐   ┌──────▼──────────────┐
            │ llama.cpp 本地  │  │ bge-m3   │   │ (可选)真 kind 集群   │
            │ Qwen3.5-9B Q4_KM│  │ embedding│   │  Loki/Prom 样本     │
            └────────────────┘  └──────────┘   └─────────────────────┘

         ─── 横切：Langfuse(追踪) · Postgres(状态/记忆) · Redis(缓存) ───
```

**技术栈**：

| 层 | 选型 | 深度 |
|---|---|---|
| LLM 推理 | **本地 llama.cpp + Qwen3.5-9B.Q4_K_M**（OpenAI 兼容 server） | 用，不调优 |
| Agent 框架 | 先手写 ReAct → 再 LangGraph | **深耕** |
| 应用入口 | 飞书 lark-oapi（WS 长连接）/ Typer CLI / FastAPI | 深耕飞书 |
| 工具后端 | Mock 实现 + 真实采样 fixture | **深耕（抽象设计）** |
| 向量库 | Qdrant | 原理够用 |
| Embedding/Rerank | bge-m3 / bge-reranker-v2-m3 | 原理够用 |
| 状态/记忆 | Postgres（checkpointer）+ Redis | 深耕 |
| 可观测 | Langfuse + Prometheus + Grafana | Langfuse 深、其余够用 |
| 包管理 | uv | — |
| 容器化 | Docker Compose | 够用 |

### 2.1 模型与版本锁定（务必填实，Agent loop 对延迟敏感）

> 「本地能跑」≠「开发体验舒服」。下表填**已亲自验证**的仓库与文件，勿用未核实链接。

| 项 | 值（待填实测） |
|---|---|
| 推理模型仓库 | `<HF/ModelScope 仓库，填实测 URL>` |
| 推理量化文件 | `Qwen3.5-9B.Q4_K_M.gguf`（实际文件名为准） |
| 微调模型 | `Qwen3.5-2B-GGUF`（QLoRA 用，4060 8GB 可行） |
| 上下文长度 | `<启动实测的 n_ctx，如 8192>` |
| llama.cpp 启动参数 | `./server -m <gguf> -c 8192 -ngl <实测层数> --port 8080` |
| 备用 provider | `<云 API，如 DeepSeek/通义，作降级>` |
| 实测首 token 延迟 | `<填基准，超过则切备用 provider>` |

---

## 3. 【强制】每阶段交付物：阶段总结文档

每个阶段结束**必须**在 `docs/stages/stageN_xxx.md` 产出一份总结文档，模板如下（这是你作品集的核心，比代码更能让招聘官看懂）：

```markdown
# 阶段 N：<名字>

## 1. 这阶段做了什么（1 段话 + 1 张流程图）
   - Mermaid 流程图：数据/控制流怎么走

## 2. 核心原理（面试能被追问的点）
   - 关键概念：是什么 / 为什么这样设计 / 备选方案为何不选
   - 至少 3 个「面试官会问，我能答」的问答

## 3. 关键代码走读
   - 3-5 个核心文件，每个 1 段解释「它解决什么问题」

## 4. 如何运行（复制粘贴能跑）
   - 前置依赖、启动命令、验证命令、预期输出

## 5. 踩坑记录
   - 遇到的问题 + 怎么定位 + 根因（这部分最值钱）

## 6. 验收自检
   - 对照本阶段验收标准逐条打勾 + 证据（截图/日志/指标）
```

> 节奏：每阶段末发 1 个 GitHub release。产出 = **7 篇阶段总结文档**（套上方模板）+ **约 13 篇周报/学习博客**（每周一篇，记录进度与踩坑）。两者不同：阶段总结是体系化沉淀，周报是过程记录。

---

## 4. 仓库结构

```
opspilot/
├── apps/
│   ├── agent-core/             # ★主线
│   │   ├── graphs/             # react.py / plan_execute.py / supervisor.py
│   │   ├── tools/              # 注册中心 + 工具实现(mock)
│   │   ├── memory/             # 短期(checkpointer) / 长期(摘要)
│   │   ├── guardrails/         # 危险操作确认 / 限次 / 脱敏
│   │   ├── eval/               # ★Agent Eval Harness
│   │   ├── entrypoints/        # feishu_ws.py / cli.py / http.py / alert.py
│   │   └── api.py
│   ├── llm-gateway/            # 薄层，原理向
│   ├── rag-service/            # 原理向，产出 retrieve 工具
│   └── ml-service/             # 微调原理向（小模型）
├── packages/opspilot-core/     # 共享数据模型 / 工具基类
├── fixtures/                   # ★真实采样数据（loki/prom/kubectl 输出）
├── infra/docker-compose.yml
├── docs/
│   ├── ARCHITECTURE.md         # 本文件
│   └── stages/                 # ★每阶段总结文档
├── scripts/
├── pyproject.toml              # uv
└── README.md
```

---

## 5. 七阶段实现路线（约 13 周 · 20-30h/周）

> 核心原则：**任何时刻 main 分支都能 demo**。先有一条能跑的细线，再逐块加厚。

### 阶段 0 — 地基 + 第一条纵切（1 周）

**目标**：飞书发一句话 → 手写 ReAct → 1 个 mock 工具 → 飞书回一句话。**一条线打通比任何架构都重要。**

- uv 初始化 monorepo；接好本地 llama.cpp（`./server -m Qwen3.5-9B.Q4_K_M.gguf --port 8080`，OpenAI 兼容）
- **CLI 入口先行**（Typer）：本地调试最快，`opspilot ask "..."` 直接打通 ReAct，无需先配飞书
- 飞书入口：`lark-oapi` WS 长连接客户端，订阅 `im.message.receive_v1`，echo 通后再接 ReAct
- 手写最小 ReAct loop（**不用任何框架**）：prompt 里塞 1 个工具描述，解析 `Action/Action Input`，调 mock 工具，`Observation` 回灌
- mock 工具：`get_pod_status()` 返回 `fixtures/` 里一段真实 `kubectl get pods` 采样

**验收**：✅ 飞书里问「user-service 几个 pod 在跑」能得到基于 mock 数据的回答 ✅ 阶段总结文档（含 ReAct 时序流程图）

**原理重点**：ReAct = Reasoning+Acting 交替；为什么 LLM 需要「观察回灌」；OpenAI 兼容协议长啥样

---

### 阶段 1 — Agent 核心：ReAct + 工具系统（2 周 · 深耕）

**目标**：把手写 ReAct 打磨扎实，再迁移到 LangGraph，建立工具注册体系。

- 手写 ReAct 加深：多轮、错误重试、工具不存在的兜底、最大步数
- **Tool Registry**：装饰器自动注册 + 从函数签名/docstring 自动生成 JSON Schema
  ```python
  @register_tool(category="k8s", risk="low")
  def kubectl_get(resource: str, namespace: str = "default") -> str:
      """查询 k8s 资源。"""
  ```
- **迁移到 LangGraph**：把手写 loop 重写成 StateGraph，对比两者差异（这就是面试谈资）
- State 设计：`messages / next_action / tool_outputs / working_memory / trace_id`
- 流式输出（SSE / 飞书流式卡片）
- 工具实现 4-6 个（全 mock 读 fixture）：`query_loki / kubectl_get / kubectl_describe / query_prometheus`

**验收**：✅ 手写版与 LangGraph 版行为一致 ✅ 新增工具只需写函数 + 装饰器 ✅ Langfuse 看到完整 trace ✅ 阶段总结文档（含 LangGraph 状态图）

**原理重点**：手写 vs 框架的取舍；JSON Schema 工具调用怎么让模型「会用工具」；StateGraph 的节点/边/条件边

---

### 阶段 2 — Agent 进阶：Plan-Execute + Guardrails + 最小 Eval +（后半段）Memory（3 周 · 深耕，重头戏）

**目标**：从「单轮 ReAct」升级到「会规划、有安全边界、可被评估、有记忆」的生产级 Agent。**顺序刻意安排**：Eval 越早有越好（它是项目差异化核心），Memory 放后半段（不阻塞前面闭环）。

**前半段（W4-5）**：

- **Plan-Execute 图**：Planner 产出步骤列表 → Executor 逐步执行 → Replan 判断
- **Guardrails**（运维背景的加分项）：
  - 危险操作白名单：`delete/drop/rm -rf/scale 0` → 必须走 `confirm_dangerous_op`（飞书交互卡片等待人工点确认）
  - 工具调用次数上限（防死循环）；输出 PII/密钥脱敏
- **★最小 Eval 先行**（不要一上来做完整评估平台）：
  - **10 条 case**，**3 个指标**：① 工具调用序列是否正确 ② 危险操作是否被拦截 ③ 最终答案是否包含要点
  - 跑法：`pytest` 离线脚本，一条命令出分数表 → 后续阶段持续往里加 case
  - 设计上预留扩展位（LLM-as-judge / 轨迹最短性），但本阶段不实现

**后半段（W6）**：

- **Memory**：短期 = LangGraph checkpointer 落 Postgres（断点续跑）；长期 = 对话摘要存 Postgres

**验收**：✅ Plan-Execute 端到端跑通多步任务 ✅ 危险操作 100% 被拦并走飞书确认 ✅ 最小 Eval 一条命令出 10-case 分数表 ✅ 杀进程后重启能从 checkpoint 续跑 ✅ 阶段总结文档（含 Plan-Execute 图 + 护栏/记忆数据流图）

**原理重点**：Plan-Execute vs ReAct 各自适用场景；为什么 Agent 必须有 Eval（不可靠是 Agent 头号问题）；Agent 记忆的短/长期分层；为什么 Eval 要先小后大

---

### 阶段 3 — 多智能体 Supervisor + 三个业务 Agent（3 周 · 深耕，主线顶点）

**目标**：Supervisor 编排，落地三个真实运维 Agent，飞书入口完整闭环。

- **Supervisor 架构**：Supervisor 按意图路由到子 Agent，子 Agent handoff back
- **Log Analyzer Agent**（ReAct）：`query_loki/query_es/tail_pod_logs/aggregate_errors`
- **K8s Operator Agent**（Plan-Execute）：写操作必过 `confirm_dangerous_op`（飞书卡片）
- **Alert Handler Agent**（Supervisor 协调）：接 Alertmanager webhook → 解析告警 → 调 Log Analyzer 查日志 + 查指标 + 调 `retrieve_runbook` → LLM 综合诊断 → 推飞书 + 写故障库
- **`retrieve_runbook` 用 stub**：本阶段返回 `fixtures/` 里几条预置 runbook，**不实现真 RAG**。业务闭环不等 RAG，接口签名定死，阶段 4 原地替换实现
- **飞书闭环**：消息接收（WS）/ 流式回复 / 交互卡片二次确认 / 卡片回调处理 全部打通

**验收**：✅ 三个 Agent 各 5+ 真实场景演示 ✅ 飞书里能完成「问诊→确认→执行→反馈」全闭环 ✅ Langfuse 看多智能体完整 trace ✅ 阶段总结文档（含 Supervisor 架构图 + 一次告警处理全链路时序图）

**原理重点**：单 Agent vs 多 Agent 何时该拆；Supervisor 路由怎么设计；handoff 的状态怎么传

---

### 阶段 4 — RAG 知识库（2 周 · 原理够用，目标=接进 Agent）

**目标**：**原地替换阶段 3 的 `retrieve_runbook` stub** 为真实 RAG，签名不变、Alert Handler 零改动。不深挖工程，重点是「能用 + 面试能讲清原理」。

- Ingestion：Markdown/PDF 解析 → 语义切分 → bge-m3 embedding → Qdrant
- 检索：向量 + BM25(`rank_bm25`) → RRF 融合 → bge-reranker rerank → top-k
- 把真实检索塞进 `retrieve_runbook(query)`，**复用阶段 3 已定的接口签名**，Alert Handler 不动一行
- 评估：RAGAS 简化版（faithfulness / context_precision），自建 30 条运维 QA 即可

**验收**：✅ 50+ 篇运维文档建库 ✅ `retrieve_runbook` 被 Alert Handler 调用并改善诊断 ✅ RAGAS 出分 ✅ 阶段总结文档（含 RAG 数据流图）

**原理重点**：embedding/向量检索原理；为什么要 hybrid + rerank；RAG 评估怎么做

---

### 阶段 5 — 周边原理补全：LLM Gateway + 微调（2 周 · 原理向）

**目标**：补两块面试高频但本项目不需深做的能力。

- **LLM Gateway（极薄层，1 周）**：本地已有 llama.cpp OpenAI 兼容 server，Gateway **只做四件事**：透传 + provider 配置/路由 + Redis 限流 + Prometheus metrics。**严禁扩成第二个主项目**——不做缓存层/批处理/多租户/计费
- **微调（1 周，懂原理）**：用 **`Qwen3.5-2B-GGUF`** QLoRA 跑通 SFT 全流程，看 loss 曲线、对比微调前后。**不碰 9B**——4060 8GB 跑 9B 微调不现实，本阶段只为「面试不哑口」

**验收**：✅ openai SDK 能打通 Gateway ✅ LoRA 流程跑通有 loss 曲线 ✅ 阶段总结文档（含 Gateway 路由图 + 微调流程图）

**原理重点**：网关/限流/熔断；LoRA/QLoRA 原理；推理量化（Q4_K_M 是什么意思）

---

### 阶段 6 — 工程化与交付（1-2 周）

**目标**：一键起 + 全链路可观测 + 招聘官 10 分钟复现。

- `docker compose up`：agent-core + qdrant + postgres + redis + langfuse + prometheus + grafana + mock 后端
- Grafana：Agent 成功率 / 工具调用 P99 / token 消耗 / 护栏拦截率
- GitHub Actions：PR 跑 lint + test + Agent Eval，把分数 comment 到 PR
- README：架构图 + 30s 飞书 demo GIF + 「传统运维 30min vs OpsPilot 3min」对比 + 一键启动
- **（可选附录）真 k8s**：VMware Ubuntu + Docker + kind，把 mock 工具切到真集群（资源够再做）

**验收**：✅ 一键起全栈 ✅ CI 全绿 ✅ README 让陌生人 10 分钟复现 ✅ 阶段总结文档（含部署架构图）

---

## 6. 关键技术决策

| 决策点 | 选择 | 理由 / 不选 |
|---|---|---|
| 学 Agent 的方式 | 先手写 ReAct → 再 LangGraph | 直接上框架只会调 API，不懂本质 |
| 运维后端 | 全 Mock + 真实采样 fixture | 第一个项目不该陷在 infra；真集群作可选附录 |
| Agent 框架 | LangGraph | 状态机思维契合运维；LangChain Agent 过时 |
| LLM 推理 | 本地 llama.cpp + Qwen3.5-9B.Q4_K_M | 已有环境；零成本；离线可控 |
| 微调模型 | Qwen3.5-2B-GGUF | 4060 8GB 跑不动 9B 微调；只为懂原理 |
| Eval 起步 | 最小 Eval(10 case/3 指标) | 别一上来做评估平台；越早有越好，渐进扩 |
| RAG 落地顺序 | 阶段 3 stub → 阶段 4 真实 | 业务闭环不等 RAG；接口签名先定死 |
| Gateway 边界 | 仅透传/路由/限流/metrics | 已有 llama.cpp server，扩多了就是第二个项目 |
| 应用入口 | 飞书 WS 长连接为主 | 比 webhook 更适合交互/二次确认；贴近真实办公场景 |
| 向量库 | Qdrant | 自托管友好；原理够用即可 |
| 周边层深度 | 原理向 | 招聘需「知道」，但深耕点必须是 Agent |

---

## 7. 学习时间表（13 周）

| 周 | 阶段 | 关键产出 |
|---|---|---|
| 1 | 阶段 0 | CLI + 飞书 echo + 手写 ReAct + 单 mock tool 纵切打通 |
| 2-3 | 阶段 1 | Tool Registry + LangGraph 迁移 + Langfuse trace |
| 4-6 | 阶段 2 | Plan-Execute + Guardrails + 最小 Eval；Memory 放后半段(W6) |
| 7-9 | 阶段 3 | Supervisor + 3 业务 Agent + 飞书确认闭环（RAG 用 stub） |
| 10-11 | 阶段 4 | 正式 RAG 原地替换 `retrieve_runbook` stub |
| 12 | 阶段 5 | Gateway 极薄层 + `Qwen3.5-2B-GGUF` QLoRA 原理实验 |
| 13 | 阶段 6 | Compose + CI + README + demo GIF + 作品集包装 |

> 每阶段末交 1 篇阶段总结文档（共 7 篇）；每周一篇周报/学习博客（约 13 篇）。
> 13 周后：能在飞书里真用的多智能体运维助手 + 持续积累的 Eval 数据 + 7 篇体系化总结 + 13 篇过程记录。

---

## 8. 作品集策略

- **简介**：OpsPilot — 用 LangGraph 多智能体 + RAG 实现的运维智能助手，飞书为入口，含 Agent 评估体系与安全护栏
- **量化**：告警平均诊断时间 -85% / 护栏拦截率 100% / Agent 工具调用正确率 0.9x / 7 篇阶段总结 + 13 篇周报博客
- **30 秒看懂**：README 顶部架构图 + 飞书操作 minikube 的 GIF + 传统 vs OpsPilot 时间对比
- **差异化叙事**：「运维背景 → 我懂 Agent 该调什么工具、什么是危险操作、如何评估 Agent 可靠性」——这是纯算法人补不上的

---

## 9. 本周即可启动（阶段 0 拆解）

1. `uv init` monorepo；启动本地 llama.cpp server（OpenAI 兼容，:8080）；填实 §2.1 锁版本表
2. 写 `fixtures/kubectl_pods.json`（一段真实采样）
3. 手写 60 行 ReAct loop：单工具 `get_pod_status`
4. **先接 CLI**（Typer）：`opspilot ask "..."` 跑通 ReAct——本地调试最快，不依赖飞书
5. 再接飞书：开放平台建应用 → app_id/secret → `lark-oapi` WS 订阅消息 → echo 通 → 接上 ReAct
6. 写 `docs/stages/stage0_*.md`（套 §3 模板）→ 打第一个 release
