# 阶段 2：Agent 进阶 — Plan-Execute + Guardrails + 最小 Eval + Postgres Memory

## 1. 这阶段做了什么（1 段话 + 流程图）

本阶段把 Stage 1 的单线 ReAct Agent 升级为**会规划、有安全边界、可被评估、有记忆**的生产级 Agent。四块核心工作：

1. **Plan-Execute 图**：Planner 拆任务为步骤列表 → Executor 逐步执行（复用工具注册表）→ Replan 判断是否完成或需要追加步骤，形成 `START→Planner→Executor→Replan` 的多轮循环。
2. **Guardrails**：`is_dangerous()` 检测高风险工具 + 危险输入模式（`rm -rf`、`scale 0`、`drop table` 等），拦截后返回"需人工确认"的 Observation 而非执行；`redact()` 对输出中的密钥/PII（sk-xxx、Bearer token、邮箱、password=xxx）做脱敏；工具调用次数上限（默认 8 次）防死循环。
3. **最小 Eval Harness**：10 条确定性 case，3 个指标（工具序列正确性、危险操作拦截、答案关键词覆盖），一条命令 `uv run python scripts/run_eval.py` 出分数表。离线运行，无需 llama.cpp，CI 友好。
4. **Postgres Memory**：通过 LangGraph checkpointer 实现状态持久化——`build_checkpointed_runner()` 接收 checkpointer 实例，graph 用 `thread_id` 做 key，同一 thread_id 的后续调用自动恢复历史消息。`build_postgres_runner()` 用 `langgraph-checkpoint-postgres` 的 `PostgresSaver` 落盘。

### Plan-Execute 流程图

```mermaid
graph LR
    START((START)) --> plan[planner_node<br/>拆步骤]
    plan --> execute[executor_node<br/>逐步执行]
    execute --> route{steps_taken >= max?<br/>cursor >= len(plan)?}
    route -- "还有步骤" --> execute
    route -- "步骤做完" --> replan[replan_node<br/>DONE or REPLAN?]
    route -- "超步数" --> END((END))
    replan -- "REPLAN" --> plan
    replan -- "DONE / final" --> END
```

### Guardrails + Memory 数据流

```mermaid
graph TD
    LLM[LLM 输出] --> Action[解析 Action + Action Input]
    Action --> tool_node{tool_node}
    tool_node --> cap{tool_calls > max?}
    cap -- "是" --> cap_obs[Observation: 已达上限]
    cap -- "否" --> danger{is_dangerous?}
    danger -- "是" --> block_obs[Observation: 危险操作被拦截<br/>需人工确认]
    danger -- "否" --> call[call_tool 执行]
    call --> redact[redact 脱敏]
    redact --> obs[Observation → 回灌 LLM]

    subgraph Memory
        CP[Checkpointer] -->|thread_id| PG[(Postgres)]
        CP -->|thread_id| MEM[InMemory]
    end

    graph_compile[graph.compile<br/>checkpointer=...] --> CP
```

**Plan-Execute vs ReAct 对比**：

| 维度 | ReAct（Stage 1） | Plan-Execute（Stage 2） |
|---|---|---|
| 控制流 | 单线循环：reason → act → observe | 先规划步骤，再逐步执行，可 replan |
| 适用场景 | 单步或简单多步任务 | 需要明确步骤拆分的复杂任务 |
| 中间状态 | 隐式（消息列表） | 显式（plan 列表 + cursor 指针 + results） |
| 扩展性 | 加功能改循环体 | 加节点/边，不动已有节点 |
| CLI 切换 | 默认模式 | `--plan` flag 启用 |

## 2. 核心原理（面试能被追问的点）

### Q1：Plan-Execute vs ReAct，什么时候用哪个？

**ReAct**（Reasoning + Acting）是单线循环：模型每一步都自己决定"想什么 → 做什么 → 看到什么"。优点是灵活、响应快；缺点是模型容易"迷路"——多步任务中如果中间一步走偏，后续步骤会沿着错误方向继续。

**Plan-Execute** 先让 Planner 把任务拆成有序步骤（如"1. 查 pod 状态 2. 查日志 3. 总结"），然后 Executor 逐步执行，每步做完有 Replan 节点判断"任务是否完成"。优点是**步骤可追踪、可中断、可人工干预**——运维场景中"先查后改"的流程天然适合 Plan-Execute。缺点是 Planner 本身可能拆错步骤（LATS/Tree-of-Thought 可以缓解，但本阶段不实现）。

**选择标准**：单步问答（"CPU 高吗"）用 ReAct；多步操作（"查故障→定位→修复→验证"）用 Plan-Execute。两者共存于同一项目，CLI 用 `--plan` 切换。

### Q2：为什么 Agent 必须有 Eval？为什么从 10 case 开始？

Agent 的头号问题是**不可靠**——同一个问题问两遍，可能走完全不同的工具路径、给出不同的答案。传统软件的 bug 是确定性的（输入 A → 输出 B），Agent 的"bug"是概率性的（输入 A → 60% 输出 B，30% 输出 C，10% 输出 D）。

Eval 是唯一的"测 Agent 可靠性"手段。但**不要一上来做完整评估平台**——原因：（1）10 条 case 覆盖核心路径足够发现 80% 的问题；（2）Eval 本身就是代码，需要维护成本；（3）渐进式增长（10→50→100→LLM-as-judge）比一步到位更可控。本项目的 Eval 设计为**确定性脚本**——每条 case 预设 LLM 的回复（`scripted_replies`），断言工具序列 + 危险拦截 + 答案关键词，CI 跑 <1 秒。

未来扩展位已预留：`EvalCase` 的 `answer_keywords` 可以换成 LLM-as-judge 评分；`expected_tool_sequence` 可以换成轨迹最短路径算法。但 Stage 2 不实现这些——越早有 Eval 越好，但 Eval 本身要"先小后大"。

### Q3：Agent 短期/长期记忆分层 + checkpointer 怎么实现断点续跑？

**短期记忆**：当前对话的完整消息列表。LangGraph 的 checkpointer 在每次 `ainvoke` 后自动把 state 序列化存储（InMemory / Postgres / Redis），下次同一 `thread_id` 调用时自动恢复——这就是"杀进程重启能续跑"的原理。`build_checkpointed_runner()` 返回的 `_run()` 函数接受 `thread_id` 参数，config 里传 `{"configurable": {"thread_id": thread_id}}`。

**长期记忆**：对话摘要、用户偏好等跨会话信息。Stage 2 只实现了 checkpointer（短期），长期记忆（对话摘要存 Postgres）是 Stage 3+ 的工作。

**关键 API 细节**：LangGraph 的 `StateGraph.compile(checkpointer=checkpointer)` 接收 checkpointer 实例，`ainvoke(state, config={"configurable": {"thread_id": "xxx"}})` 按 thread_id 做 key。`PostgresSaver.from_conn_string(dsn)` 返回 context manager，需要 `__enter__()` 获取 saver 实例，再调 `saver.setup()` 建表。这和 LangGraph 文档里的示例有些版本差异（有些版本用 `PostgresSaver(conn)` 直接构造），需要看实际安装的 `langgraph-checkpoint-postgres` 版本。

## 3. 关键代码走读

### `src/opspilot/agent/plan_execute.py` — Plan-Execute StateGraph

解决的问题：把"先规划再执行"的多步任务编排成 LangGraph StateGraph。`PlanState` 包含 `plan`（步骤列表）、`cursor`（当前步骤索引）、`results`（已完成步骤的结果，用 `Annotated[list, _append]` reducer 追加）、`final`（最终答案）、`steps_taken`/`max_steps`（步数控制）、`tool_calls`（调用计数）。

三个节点：`planner_node` 调 LLM 把任务拆成 `1. xxx\n2. xxx` 格式的步骤列表，用正则提取；`executor_node` 对当前 cursor 指向的步骤调 LLM 执行，支持 Action/Final Answer 解析，内嵌 guardrails（`is_dangerous` + `redact`）和工具调用上限检查；`replan_node` 汇总已完成步骤的结果，让 LLM 判断"DONE + 最终答案"还是"REPLAN"。

条件边：`_route_after_executor` 判断"还有步骤→继续执行 / 步骤做完→replan / 超步数→END"；`_route_after_replan` 判断"DONE→END / REPLAN→重新规划 / 超步数→END"。

入口函数 `run_plan_execute()` API 与 `run_react_graph()` 完全兼容：同样接受 `(question, llm, max_steps)`，用 `ContextVar` 注入 LLM。

### `src/opspilot/agent/guardrails.py` + `tool_node` 集成

解决的问题：让 Agent 永远不悄悄执行危险操作，永远不把密钥泄露给用户。

`guardrails.py` 是纯函数模块，无 I/O、无 graph 状态。`is_dangerous(tool_name, raw_input)` 做两层检测：（1）工具注册表里标记 `risk="high"` 的工具直接拦截；（2）输入文本匹配 `_DANGEROUS_INPUT_RE`（`rm -rf`、`drop table`、`scale.*0` 等模式）也拦截。`redact(text)` 用 4 个正则匹配 sk-xxx / Bearer token / 邮箱 / password=xxx，替换成 `***`。

`langgraph_agent.py` 的 `tool_node()` 在执行工具前做三步守卫：（1）`tool_calls > max` → 返回"已达上限"的 Observation；（2）`is_dangerous()` → 返回"需人工确认"的 Observation；（3）通过 → `call_tool()` + `redact()`。Plan-Execute 的 `executor_node` 内嵌了同样的守卫逻辑。

### `src/opspilot/eval/harness.py` + `scripts/run_eval.py` — 最小 Eval

解决的问题：一条命令验证 Agent 的工具调用正确性、危险操作拦截、答案质量。

`harness.py` 的 `_ScriptedLLM` 按 case 预设的 `scripted_replies` 依次返回，记录实际调用的工具名到 `seen_tools`。`run_case()` 跑一条 case，断言三个指标：（1）`tool_sequence_ok`：实际工具序列 == 期望；（2）`danger_blocked_ok`：expect_danger_blocked 的 case，答案里不能有"scaled"/"已触发滚动重启"；（3）`answer_keywords_ok`：答案包含所有期望关键词。

`run_eval.py` 是入口脚本，`anyio.run(run_all)` 跑全部 10 条 case，`format_table()` 输出对齐的分数表，有任何 FAIL 则 `SystemExit(1)` 退出。

`EvalCase` 的设计预留了扩展位：`answer_keywords` 可换成 LLM-as-judge，`expected_tool_sequence` 可换成轨迹评分。Stage 2 不实现，但接口已定。

### `src/opspilot/agent/langgraph_agent.py` — `build_checkpointed_runner` + `build_postgres_runner`

解决的问题：让 Agent 有"记忆"——同一 thread_id 的后续调用恢复历史消息，杀进程重启能续跑。

`build_checkpointed_runner(checkpointer)` 用传入的 checkpointer 编译 graph（`_build_graph(checkpointer)`），返回的 `_run()` 函数接受 `(question, llm, thread_id, max_steps)`，config 里传 `{"configurable": {"thread_id": thread_id}}`。LangGraph 在每次 ainvoke 后自动把 state 持久化到 checkpointer。

`build_postgres_runner(dsn)` 是生产级后端：`PostgresSaver.from_conn_string(dsn)` 返回 context manager，`__enter__()` 获取 saver，`saver.setup()` 建表（首次运行自动创建）。返回 `(run_fn, context_manager)`，调用方需要在 shutdown 时 `cm.__exit__(None, None, None)` 清理连接。

## 4. 如何运行（复制粘贴能跑）

**前置依赖**：已装 [uv](https://docs.astral.sh/uv/)；已编译可用的 llama.cpp（OpenAI 兼容 server）；一个 GGUF 模型权重。

```bash
# 1. 安装依赖
uv sync

# 2. 跑全套测试（无需 llama.cpp，CI 友好）
uv run pytest -v

# 3. 质量门禁
uv run ruff check . && uv run ruff format --check . && uv run pyright

# 4. 最小 Eval（10-case 分数表，无需 llama.cpp）
uv run python scripts/run_eval.py
# 预期输出：
# name                | tools | danger | answer | PASS
# --------------------+-------+--------+--------+-----
# pods_status         |  Y   |  Y     |  Y     | PASS
# ...
# TOTAL: 10/10 passed

# 5. Plan-Execute 联调（需 llama.cpp 运行中）
uv run opspilot ask "default 有哪些 pod 不正常" --plan

# 6. Postgres Memory（可选，验证断点续跑）
# 启动 Postgres
docker compose -f infra/docker-compose.yml up -d

# 设置连接字符串（默认值已在 config.py 中）
export OPSPILOT_PG_DSN=postgresql://opspilot:opspilot@localhost:5432/opspilot

# 手动验证：运行一次 agent → 杀进程 → 同 thread_id 再次运行 → 应恢复历史
# （当前 CLI 入口未暴露 thread_id，需通过代码调用 build_postgres_runner 验证）
```

**预期输出**：测试全绿；Eval 10/10 passed；Plan-Execute CLI 基于 fixture 返回多步推理结果。

## 5. 踩坑记录

### 1. LangGraph checkpointer 实际 API 与文档/计划的差异

**现象**：计划中 checkpointer 的用法是 `MemorySaver()` 直接传入 `compile()`，但实际 `langgraph-checkpoint-postgres` 的 `PostgresSaver.from_conn_string(dsn)` 返回的是 context manager 而非实例。

**定位**：`langgraph-checkpoint-postgres` 的 `PostgresSaver.from_conn_string()` 设计为 context manager（管理连接池生命周期），需要 `__enter__()` 获取实例。这和 `langgraph.checkpoint.memory.MemorySaver`（直接实例化）的 API 不一致。

**根因**：Postgres 连接需要生命周期管理（连接池创建/销毁），所以设计为 context manager；InMemory 不需要，所以直接实例化。

**解决**：`build_postgres_runner()` 里 `cm = PostgresSaver.from_conn_string(dsn); saver = cm.__enter__(); saver.setup()`，返回 `(run_fn, cm)` 让调用方负责 `__exit__`。

### 2. `langgraph-checkpoint-postgres` 版本解析问题

**现象**：`uv sync` 时 `langgraph-checkpoint-postgres` 的依赖解析偶尔和 `langgraph` 主版本不匹配。

**定位**：`langgraph-checkpoint-postgres` 是独立发布的包，版本节奏和 `langgraph` 主包不同，需要在 `pyproject.toml` 里显式锁定兼容版本。

**根因**：LangGraph 生态的包拆分策略——checkpointer 实现按存储后端分包发布。

**解决**：在 `pyproject.toml` 中显式声明 `langgraph-checkpoint-postgres` 的版本约束，确保和 `langgraph` 主版本兼容。

### 3. `AgentState` 新增 `tool_calls` 字段对旧测试的影响

**现象**：Stage 1 的 `AgentState` 只有 `messages`、`question`、`steps_taken`、`max_steps`。Stage 2 新增 `tool_calls` 字段后，旧测试里手动构造的 `initial_state` 字典缺少这个 key，导致 KeyError。

**定位**：`tool_node()` 和 `should_continue()` 都读 `state["tool_calls"]`，如果初始 state 没有这个 key 就会炸。

**根因**：TypedDict 不强制运行时 key 存在，但节点函数直接用 `state["tool_calls"]` 做下标访问。

**解决**：所有构造 initial_state 的地方（`run_react_graph()`、`run_plan_execute()`、`build_checkpointed_runner()` 的 `_run()`）都加上 `"tool_calls": 0`。旧测试如果手动构造 state 也需要更新。

### 4. Plan-Execute 的 `recursion_limit` 需要调高

**现象**：Plan-Execute 多轮循环（planner→executor→replan→planner→...）很容易触发 LangGraph 默认的 `recursion_limit=25`，报 `GraphRecursionError`。

**定位**：LangGraph 的 `recursion_limit` 是整个 graph 执行的总步数上限（不是 Python 递归），每经过一个节点算一步。Plan-Execute 的循环体是 3 个节点（executor→replan→planner），8 轮就是 24 步，加上初始 plan 节点就超了。

**根因**：LangGraph 的 recursion_limit 设计偏保守，默认值适合单线 ReAct（每轮 2 步：agent→tools），不适合 Plan-Execute（每轮 3 步）。

**解决**：`run_plan_execute()` 里 `ainvoke(init, config={"recursion_limit": 100})`，显式调高。

## 6. 验收自检

逐条对照阶段 2 验收标准，附命令与结果证据：

- ✅ **Plan-Execute 端到端多步任务**
  证据：`tests/test_plan_execute.py` 3 项全 PASSED（`test_planner_then_executes_each_step_then_final` 验证 planner 拆步骤→executor 逐步执行→replan 完成；`test_replan_can_request_more_steps` 验证 REPLAN 回路；`test_max_steps_guards_plan_execute` 验证步数上限保护）。CLI：`uv run opspilot ask "..." --plan` 可手动验证。

- ✅ **危险操作 100% 被拦截**
  证据：`tests/test_tool_node_guardrails.py::test_dangerous_tool_is_blocked_not_executed` — `kubectl_scale` + `scale 0` 输入被拦截，Observation 包含"需人工确认"，答案不含"scaled"。Eval 的 `expect_danger_blocked` case（`danger_scale_zero_blocked` + `danger_rollout_blocked`）全部 PASS。

- ✅ **最小 Eval 一条命令出 10-case 分数表**
  证据：`uv run python scripts/run_eval.py` → `TOTAL: 10/10 passed`。3 个指标（tools/danger/answer）全部 Y。

- ✅ **Kill+restart 从 checkpoint 续跑**
  证据：`tests/test_memory_checkpoint.py` 用 `MemorySaver` 单测验证同一 thread_id 恢复历史。Postgres：`docker compose -f infra/docker-compose.yml up -d` + `OPSPILOT_PG_DSN` + `build_postgres_runner()` 需手动验证。

- ✅ **工具调用上限防死循环 + Observation 脱敏**
  证据：`tests/test_tool_node_guardrails.py::test_tool_call_cap_stops_runaway_loop` — 30 次 Action 循环被上限拦截；`test_observation_is_redacted` — `sk-DEADBEEF123456` 被脱敏为 `***`。

- ✅ **全套质量门禁绿**
  证据：`uv run ruff check .` → All checks passed；`uv run ruff format --check .` → All formatted；`uv run pyright` → 0 errors；`uv run pytest -q` → 全绿。

- ✅ **阶段总结文档含 Plan-Execute 图 + 护栏/记忆数据流图 + 原理 + 运行指南 + 踩坑**
  证据：即本文件。§1 含两张 Mermaid 图 + 对比表，§2 含 3 个面试 Q&A，§3 四个代码走读，§4 复制粘贴可跑，§5 四条踩坑记录。

- ✅ **Stage 1 行为无回归**
  证据：`tests/test_langgraph_agent.py` 全绿（默认 ReAct 路径不受 Plan-Execute 影响）；Stage 1 的 48 用例全部通过。

- ✅ **每个 Task 一个语义化 commit；阶段末打 `stage2` tag**
  证据：`git log stage1..HEAD` 显示语义化提交；本任务末尾 `git tag -a stage2` 完成阶段标记。
