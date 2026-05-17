# Stage 0 — 地基 + 第一条纵切 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 打通一条最薄的端到端纵切：用户从 CLI（和飞书）提一个运维问题 → 手写 ReAct 循环 → 调用一个读 fixture 的 mock 工具 → 返回基于真实采样数据的回答。

**Architecture:** 单一可安装包 `opspilot`（src 布局），内部按逻辑分层：`config`(设置) / `llm`(OpenAI 兼容客户端) / `tools`(mock 工具) / `agent`(手写 ReAct，零框架) / `entrypoints`(Typer CLI + 飞书 WS)。LLM 走本地 llama.cpp OpenAI 兼容 server。所有外部 I/O（HTTP、LLM）在测试中被 mock，ReAct 逻辑用 FakeLLM 脚本化驱动。

**Tech Stack:** Python 3.12、uv、httpx、pydantic-settings、Typer、anyio、lark-oapi；测试 pytest + respx + anyio 插件；质量 ruff + pyright。

---

## 关于仓库结构的决策（必读）

ARCHITECTURE.md §4 描述的是 `apps/agent-core/...` 多包 monorepo。**Stage 0 刻意不做多包拆分**（YAGNI）：现在没有第二个包，uv workspace 会拖慢 TDD 节奏。Stage 0 用单包 `src/opspilot/`，内部模块名对齐架构文档的逻辑分层（tools/agent/entrypoints）。当 Stage 3+ 真出现独立可部署单元时再拆。这是一个明确假设——执行前若用户坚持 Stage 0 就要 monorepo，停下来确认。

## Risks & Assumptions

- **llama.cpp server**：假设本地已按 ARCHITECTURE.md §2.1 启动 OpenAI 兼容 server 于 `http://localhost:8080/v1`。CLI/飞书的真实联调步骤依赖它；单元测试不依赖（全 mock）。
- **飞书凭据**：飞书 WS 真实联调需要 `OPSPILOT_FEISHU_APP_ID/SECRET`。`handle_question` 纯函数单测不需要；WS 接线为手动验证项。

---

## File Structure

- Create `src/opspilot/__init__.py` — 包入口，导出公共 API + `__version__`
- Create `src/opspilot/config.py` — pydantic-settings 配置（LLM/飞书）
- Create `src/opspilot/llm/__init__.py`、`src/opspilot/llm/client.py` — OpenAI 兼容异步 chat 客户端
- Create `src/opspilot/tools/__init__.py`、`src/opspilot/tools/pod_status.py` — `get_pod_status` mock 工具
- Create `src/opspilot/agent/__init__.py`、`src/opspilot/agent/react.py` — 手写 ReAct 循环
- Create `src/opspilot/entrypoints/__init__.py`、`entrypoints/cli.py`、`entrypoints/feishu_ws.py` — 入口
- Create `fixtures/kubectl_pods.json` — 真实采样 pod 数据
- Create `tests/conftest.py` 及各 `tests/test_*.py`
- Create `.env.example`、`docs/stages/stage0_foundation.md`
- Modify `pyproject.toml`（依赖、脚本、工具配置）；删除空 `main.py`

---

## Task 0: 项目工具链与骨架

**Files:**
- Modify: `pyproject.toml`
- Create: `src/opspilot/__init__.py`, `tests/conftest.py`, `.env.example`
- Delete: `main.py`

- [ ] **Step 1: 改 pyproject.toml**

把 `pyproject.toml` 整体替换为：

```toml
[project]
name = "opspilot"
version = "0.1.0"
description = "一个用 LLM Agent 驱动的运维智能助手平台"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "httpx>=0.28.1",
    "pydantic-settings>=2.14.1",
    "typer>=0.25.1",
    "anyio>=4.13.0",
    "lark-oapi>=1.6.5",
]

[project.scripts]
opspilot = "opspilot.entrypoints.cli:main"

[dependency-groups]
dev = [
    "pytest>=9.0.3",
    "respx>=0.23.1",
    "ruff>=0.15.13",
    "pyright>=1.1.409",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/opspilot"]

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ruff]
line-length = 120
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]

[tool.pyright]
include = ["src", "tests"]
typeCheckingMode = "standard"
```

- [ ] **Step 2: 同步依赖**

Run: `uv sync`
Expected: 成功创建 `.venv` 并安装全部依赖；生成/更新 `uv.lock`，无解析错误。

- [ ] **Step 3: 建包骨架文件**

Create `src/opspilot/__init__.py`:

```python
"""OpsPilot — 用 LLM Agent 驱动的运维智能助手平台。"""

__version__ = "0.1.0"

__all__ = ["__version__"]
```

Create `tests/conftest.py`:

```python
import pytest


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
```

Create `.env.example`:

```
OPSPILOT_LLM_BASE_URL=http://localhost:8080/v1
OPSPILOT_LLM_MODEL=qwen3.5-9b
OPSPILOT_LLM_API_KEY=sk-local
OPSPILOT_FEISHU_APP_ID=
OPSPILOT_FEISHU_APP_SECRET=
```

- [ ] **Step 4: 删除空 main.py**

Run: `git rm -f main.py`
Expected: `main.py` 被移除（功能由 `opspilot` 控制台脚本取代）。

- [ ] **Step 5: 校验空跑**

Run: `uv run python -c "import opspilot; print(opspilot.__version__)"`
Expected: 输出 `0.1.0`

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock src/opspilot/__init__.py tests/conftest.py .env.example
git commit -m "$(cat <<'EOF'
chore(stage0): bootstrap uv project, tooling, and package skeleton

Stage 0 starts from a bare pyproject. This sets up the foundation
every later task builds on.

- Pin runtime/dev deps (httpx, pydantic-settings, typer, anyio,
  lark-oapi; pytest, respx, ruff, pyright) and lock via uv
- Target Python 3.12 (requires-python >=3.12)
- src/ layout with hatchling; expose `opspilot` console script
- Add anyio_backend fixture so async tests run on asyncio
- Add .env.example documenting all OPSPILOT_* settings
- Remove the now-unused empty main.py (replaced by console script)

EOF
)"
```

---

## Task 1: get_pod_status mock 工具 + fixture

**Files:**
- Create: `fixtures/kubectl_pods.json`
- Create: `src/opspilot/tools/__init__.py`, `src/opspilot/tools/pod_status.py`
- Test: `tests/test_pod_status.py`

- [ ] **Step 1: 写 fixture**

Create `fixtures/kubectl_pods.json`:

```json
{
  "pods": [
    {"namespace": "default", "name": "user-service-7d9f8c-abcde", "ready": "1/1", "status": "Running", "restarts": 0},
    {"namespace": "default", "name": "user-service-7d9f8c-fghij", "ready": "1/1", "status": "Running", "restarts": 2},
    {"namespace": "default", "name": "order-service-5c7b9d-klmno", "ready": "0/1", "status": "CrashLoopBackOff", "restarts": 7},
    {"namespace": "staging", "name": "user-service-6a8e2f-pqrst", "ready": "1/1", "status": "Running", "restarts": 0}
  ]
}
```

- [ ] **Step 2: 写失败测试**

Create `tests/test_pod_status.py`:

```python
from opspilot.tools.pod_status import get_pod_status


def test_get_pod_status_default_namespace_lists_pods() -> None:
    out = get_pod_status("default")
    assert "user-service-7d9f8c-abcde" in out
    assert "CrashLoopBackOff" in out
    assert "order-service-5c7b9d-klmno" in out


def test_get_pod_status_filters_by_namespace() -> None:
    out = get_pod_status("staging")
    assert "user-service-6a8e2f-pqrst" in out
    assert "order-service-5c7b9d-klmno" not in out


def test_get_pod_status_unknown_namespace() -> None:
    assert "没有找到 pod" in get_pod_status("does-not-exist")
```

- [ ] **Step 3: 运行测试确认失败**

Run: `uv run pytest tests/test_pod_status.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'opspilot.tools'`

- [ ] **Step 4: 实现工具**

Create `src/opspilot/tools/__init__.py`:

```python
from opspilot.tools.pod_status import get_pod_status

__all__ = ["get_pod_status"]
```

Create `src/opspilot/tools/pod_status.py`:

```python
import json
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parents[3] / "fixtures"


def get_pod_status(namespace: str = "default") -> str:
    """查询指定 namespace 下的 pod 状态，返回类似 kubectl get pods 的文本表。"""
    raw = (FIXTURES_DIR / "kubectl_pods.json").read_text(encoding="utf-8")
    pods = [p for p in json.loads(raw)["pods"] if p["namespace"] == namespace]
    if not pods:
        return f"namespace {namespace} 下没有找到 pod。"
    lines = ["NAME\tREADY\tSTATUS\tRESTARTS"]
    lines += [
        f"{p['name']}\t{p['ready']}\t{p['status']}\t{p['restarts']}" for p in pods
    ]
    return "\n".join(lines)
```

- [ ] **Step 5: 运行测试确认通过**

Run: `uv run pytest tests/test_pod_status.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add fixtures/kubectl_pods.json src/opspilot/tools tests/test_pod_status.py
git commit -m "$(cat <<'EOF'
feat(tools): add get_pod_status mock tool backed by fixtures

The hand-written ReAct loop needs exactly one real tool to call in
Stage 0. get_pod_status reads a realistic sampled kubectl-get-pods
dataset and renders a tab-separated table filtered by namespace,
returning a friendly message when the namespace is empty.

- fixtures/kubectl_pods.json: Running + CrashLoopBackOff pods across
  default and staging namespaces (gives the agent something
  non-trivial to reason about in demos)
- pod_status.py resolves the fixtures dir relative to the package so
  it works regardless of CWD
- Tests cover happy path, namespace filtering, and empty-namespace

EOF
)"
```

---

## Task 2: Settings 配置

**Files:**
- Create: `src/opspilot/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: 写失败测试**

Create `tests/test_config.py`:

```python
import pytest

from opspilot.config import Settings, get_settings


def test_settings_defaults() -> None:
    s = Settings()
    assert s.llm_base_url == "http://localhost:8080/v1"
    assert s.llm_model == "qwen3.5-9b"


def test_settings_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPSPILOT_LLM_MODEL", "custom-model")
    assert Settings().llm_model == "custom-model"


def test_get_settings_returns_settings() -> None:
    assert isinstance(get_settings(), Settings)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'opspilot.config'`

- [ ] **Step 3: 实现配置**

Create `src/opspilot/config.py`:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OPSPILOT_", env_file=".env", extra="ignore"
    )

    llm_base_url: str = "http://localhost:8080/v1"
    llm_model: str = "qwen3.5-9b"
    llm_api_key: str = "sk-local"
    feishu_app_id: str = ""
    feishu_app_secret: str = ""


def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run pytest tests/test_config.py -v`
Expected: 3 passed
（注意：`test_settings_defaults` 假设运行环境未设置 `OPSPILOT_*` 且无 `.env`。CI 上成立；本地若有 `.env` 用真实值，跑测试前用 `env -u` 或在干净 shell 运行。）

- [ ] **Step 5: Commit**

```bash
git add src/opspilot/config.py tests/test_config.py
git commit -m "$(cat <<'EOF'
feat(config): typed settings via pydantic-settings

Centralize all runtime config behind one typed Settings object so
later components (LLM client, Feishu entrypoint) depend on a single
source of truth instead of reading os.environ ad hoc.

- OPSPILOT_ env prefix + optional .env file
- Sensible local-first defaults pointing at the llama.cpp OpenAI
  server on :8080
- extra="ignore" so unrelated env vars never crash startup
- Tests cover defaults, env override, and the get_settings() helper

EOF
)"
```

---

## Task 3: LLM 客户端（OpenAI 兼容）

**Files:**
- Create: `src/opspilot/llm/__init__.py`, `src/opspilot/llm/client.py`
- Test: `tests/test_llm_client.py`

- [ ] **Step 1: 写失败测试**

Create `tests/test_llm_client.py`:

```python
import httpx
import pytest
import respx

from opspilot.config import Settings
from opspilot.llm.client import LLMClient


@pytest.mark.anyio
@respx.mock
async def test_chat_posts_openai_payload_and_parses_reply() -> None:
    settings = Settings(
        llm_base_url="http://test/v1", llm_model="m", llm_api_key="k"
    )
    route = respx.post("http://test/v1/chat/completions").mock(
        return_value=httpx.Response(
            200, json={"choices": [{"message": {"content": "hello"}}]}
        )
    )
    client = LLMClient(settings)
    try:
        reply = await client.chat([{"role": "user", "content": "hi"}])
    finally:
        await client.aclose()

    assert reply == "hello"
    assert route.called
    sent = route.calls.last.request
    assert sent.headers["authorization"] == "Bearer k"
    body = httpx.Response(200, content=sent.content).json()
    assert body["model"] == "m"
    assert body["messages"] == [{"role": "user", "content": "hi"}]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_llm_client.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'opspilot.llm'`

- [ ] **Step 3: 实现客户端**

Create `src/opspilot/llm/__init__.py`:

```python
from opspilot.llm.client import LLMClient

__all__ = ["LLMClient"]
```

Create `src/opspilot/llm/client.py`:

```python
from collections.abc import Sequence

import httpx

from opspilot.config import Settings

Message = dict[str, str]


class LLMClient:
    """调用 OpenAI 兼容 /chat/completions 的最小异步客户端。"""

    def __init__(
        self, settings: Settings, http_client: httpx.AsyncClient | None = None
    ) -> None:
        self._settings = settings
        self._client = http_client or httpx.AsyncClient(timeout=120.0)

    async def chat(self, messages: Sequence[Message]) -> str:
        resp = await self._client.post(
            f"{self._settings.llm_base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self._settings.llm_api_key}"},
            json={
                "model": self._settings.llm_model,
                "messages": list(messages),
                "temperature": 0.0,
            },
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    async def aclose(self) -> None:
        await self._client.aclose()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run pytest tests/test_llm_client.py -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add src/opspilot/llm tests/test_llm_client.py
git commit -m "$(cat <<'EOF'
feat(llm): minimal async OpenAI-compatible chat client

The ReAct loop talks to the local llama.cpp server through one thin
seam so it can be swapped or mocked. Kept deliberately tiny — no
streaming, retries, or provider routing (those are Stage 1+/Stage 5).

- POST {base_url}/chat/completions with temperature=0 for
  deterministic agent behavior
- Inject httpx.AsyncClient for testability; respx-based test asserts
  the exact request shape (auth header, model, messages) and reply
  parsing
- raise_for_status so upstream errors surface instead of silently
  returning garbage to the agent

EOF
)"
```

---

## Task 4: 手写 ReAct 循环（零框架）

**Files:**
- Create: `src/opspilot/agent/__init__.py`, `src/opspilot/agent/react.py`
- Test: `tests/test_react.py`

- [ ] **Step 1: 写失败测试**

Create `tests/test_react.py`:

```python
import pytest

from opspilot.agent.react import run_react


class FakeLLM:
    def __init__(self, replies: list[str]) -> None:
        self._replies = replies
        self.calls: list[list[dict[str, str]]] = []

    async def chat(self, messages: list[dict[str, str]]) -> str:
        self.calls.append([dict(m) for m in messages])
        return self._replies.pop(0)


@pytest.mark.anyio
async def test_react_calls_tool_then_returns_final_answer() -> None:
    llm = FakeLLM(
        [
            "Thought: 查一下\nAction: get_pod_status\nAction Input: default",
            "Thought: 有了\nFinal Answer: default 下 order-service 处于 CrashLoopBackOff。",
        ]
    )
    answer = await run_react("default 有几个 pod", llm)  # type: ignore[arg-type]
    assert "CrashLoopBackOff" in answer
    assert len(llm.calls) == 2
    assert any("Observation:" in m["content"] for m in llm.calls[1])


@pytest.mark.anyio
async def test_react_unknown_tool_is_reported_then_recovers() -> None:
    llm = FakeLLM(
        [
            "Action: delete_everything\nAction Input: x",
            "Final Answer: 已向用户说明该工具不可用。",
        ]
    )
    answer = await run_react("q", llm)  # type: ignore[arg-type]
    assert "已向用户说明" in answer
    obs = llm.calls[1][-1]["content"]
    assert "不存在" in obs


@pytest.mark.anyio
async def test_react_stops_at_max_steps() -> None:
    llm = FakeLLM(["Action: get_pod_status\nAction Input: default"] * 10)
    answer = await run_react("q", llm, max_steps=3)  # type: ignore[arg-type]
    assert "最大推理步数" in answer
    assert len(llm.calls) == 3
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_react.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'opspilot.agent'`

- [ ] **Step 3: 实现 ReAct**

Create `src/opspilot/agent/__init__.py`:

```python
from opspilot.agent.react import run_react

__all__ = ["run_react"]
```

Create `src/opspilot/agent/react.py`:

```python
import re
from collections.abc import Callable
from typing import Protocol

from opspilot.tools.pod_status import get_pod_status

Tool = Callable[[str], str]

TOOLS: dict[str, Tool] = {"get_pod_status": get_pod_status}

SYSTEM_PROMPT = """你是运维助手 OpsPilot。可用工具：

工具：get_pod_status(namespace)
描述：查询指定 namespace 下的 pod 状态。

严格按格式逐步推理，每次只输出一步。需要调用工具时：

Thought: <思考>
Action: get_pod_status
Action Input: <namespace，如 default>

拿到足够信息后：

Thought: <总结>
Final Answer: <给用户的最终回答>
"""

_ACTION_RE = re.compile(r"Action:\s*(\w+)")
_ACTION_INPUT_RE = re.compile(r"Action Input:\s*(.*)")
_FINAL_RE = re.compile(r"Final Answer:\s*(.*)", re.DOTALL)


class SupportsChat(Protocol):
    async def chat(self, messages: list[dict[str, str]]) -> str: ...


async def run_react(
    question: str, llm: SupportsChat, max_steps: int = 5
) -> str:
    messages: list[dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    for _ in range(max_steps):
        reply = await llm.chat(messages)
        messages.append({"role": "assistant", "content": reply})

        if final := _FINAL_RE.search(reply):
            return final.group(1).strip()

        action = _ACTION_RE.search(reply)
        if action is None:
            return reply.strip()

        tool_name = action.group(1)
        tool = TOOLS.get(tool_name)
        if tool is None:
            observation = (
                f"错误：工具 {tool_name} 不存在。可用工具：{list(TOOLS)}"
            )
        else:
            arg = _ACTION_INPUT_RE.search(reply)
            namespace = (arg.group(1).strip() if arg else "default") or "default"
            observation = tool(namespace)

        messages.append(
            {"role": "user", "content": f"Observation: {observation}"}
        )

    return "达到最大推理步数，未能得到最终答案。"
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run pytest tests/test_react.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/opspilot/agent tests/test_react.py
git commit -m "$(cat <<'EOF'
feat(agent): hand-written ReAct loop with zero framework

Stage 0's core learning artifact: implement Reason-Act-Observe by
hand (no LangGraph) so the mechanics are fully understood before
Stage 1 migrates this to a StateGraph.

- Regex-parsed Action / Action Input / Final Answer protocol
- Observation is fed back as a user turn so the model can re-reason
- Defensive branches that Stage 2 Eval will later assert on:
  unknown-tool reported back instead of crashing, and a max_steps
  ceiling to prevent infinite loops
- Depends on llm via a SupportsChat Protocol so tests drive it with
  a scripted FakeLLM (no network, deterministic)

EOF
)"
```

---

## Task 5: Typer CLI 入口

**Files:**
- Create: `src/opspilot/entrypoints/__init__.py`, `src/opspilot/entrypoints/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: 写失败测试**

Create `tests/test_cli.py`:

```python
import pytest
from typer.testing import CliRunner

from opspilot.entrypoints import cli

runner = CliRunner()


class _NoopLLM:
    def __init__(self, *args: object, **kwargs: object) -> None: ...

    async def aclose(self) -> None:
        return None


def test_cli_ask_outputs_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_run_react(
        question: str, llm: object, max_steps: int = 5
    ) -> str:
        return f"FAKE:{question}"

    monkeypatch.setattr(cli, "run_react", fake_run_react)
    monkeypatch.setattr(cli, "LLMClient", _NoopLLM)

    result = runner.invoke(cli.app, ["ask", "user-service 状态"])

    assert result.exit_code == 0
    assert "FAKE:user-service 状态" in result.stdout
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_cli.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'opspilot.entrypoints'`

- [ ] **Step 3: 实现 CLI**

Create `src/opspilot/entrypoints/__init__.py`:

```python
```

(空文件即可——入口模块不对外导出符号。)

Create `src/opspilot/entrypoints/cli.py`:

```python
import anyio
import typer

from opspilot.agent.react import run_react
from opspilot.config import get_settings
from opspilot.llm.client import LLMClient

app = typer.Typer(help="OpsPilot 运维智能助手 CLI")


@app.command()
def ask(question: str) -> None:
    """向 OpsPilot 提一个运维问题。"""

    async def _run() -> str:
        llm = LLMClient(get_settings())
        try:
            return await run_react(question, llm)
        finally:
            await llm.aclose()

    typer.echo(anyio.run(_run))


def main() -> None:
    app()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run pytest tests/test_cli.py -v`
Expected: 1 passed

- [ ] **Step 5: 真实联调（需要 llama.cpp 在跑，手动验证）**

Run: `uv run opspilot ask "default 命名空间有哪些 pod 不正常？"`
Expected: 终端输出一段中文回答，提到 `order-service` 处于 `CrashLoopBackOff`（来自 fixture）。
（若 llama.cpp 未启动会报连接错误——这是预期的，单测已覆盖逻辑；记录到阶段文档踩坑区。）

- [ ] **Step 6: Commit**

```bash
git add src/opspilot/entrypoints/__init__.py src/opspilot/entrypoints/cli.py tests/test_cli.py
git commit -m "$(cat <<'EOF'
feat(cli): Typer entrypoint `opspilot ask`

CLI lands before Feishu because it's the fastest local debug loop and
has zero external setup — you can exercise the full ReAct path with
one command.

- `opspilot ask "<question>"` bridges sync Typer to the async stack
  via anyio.run, always closing the LLM client
- Wired as the `opspilot` console script in pyproject
- Test uses Typer's CliRunner with run_react/LLMClient patched so it
  asserts wiring only, no network
- Manual llama.cpp smoke step documented for the stage summary

EOF
)"
```

---

## Task 6: 飞书 WS 入口

**Files:**
- Create: `src/opspilot/entrypoints/feishu_ws.py`
- Test: `tests/test_feishu_ws.py`

- [ ] **Step 1: 写失败测试**

Create `tests/test_feishu_ws.py`:

```python
import pytest

from opspilot.entrypoints.feishu_ws import handle_question


@pytest.mark.anyio
async def test_handle_question_delegates_and_trims() -> None:
    async def agent(text: str) -> str:
        return f"answered: {text}"

    assert await handle_question("  pod 状态  ", agent) == "answered: pod 状态"


@pytest.mark.anyio
async def test_handle_question_rejects_empty() -> None:
    async def agent(text: str) -> str:
        raise AssertionError("空输入不应调用 agent")

    assert "请输入" in await handle_question("   ", agent)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_feishu_ws.py -v`
Expected: FAIL，`ImportError: cannot import name 'handle_question'`

- [ ] **Step 3: 实现飞书入口**

Create `src/opspilot/entrypoints/feishu_ws.py`:

```python
from collections.abc import Awaitable, Callable

import anyio
import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateMessageRequest,
    CreateMessageRequestBody,
    P2ImMessageReceiveV1,
)

from opspilot.agent.react import run_react
from opspilot.config import get_settings
from opspilot.llm.client import LLMClient

AgentFn = Callable[[str], Awaitable[str]]


async def handle_question(text: str, agent: AgentFn) -> str:
    """飞书消息处理核心：纯函数，便于单测。"""
    text = text.strip()
    if not text:
        return "请输入你的运维问题。"
    return await agent(text)


def _extract_text(event: P2ImMessageReceiveV1) -> str:
    import json

    content = event.event.message.content or "{}"
    return json.loads(content).get("text", "")


def run() -> None:  # 手动验证，不进单测
    """启动飞书 WS 长连接 bot。需要 OPSPILOT_FEISHU_APP_ID/SECRET。"""
    settings = get_settings()

    async def _agent(text: str) -> str:
        llm = LLMClient(settings)
        try:
            return await run_react(text, llm)
        finally:
            await llm.aclose()

    def _on_message(event: P2ImMessageReceiveV1) -> None:
        question = _extract_text(event)
        answer = anyio.run(handle_question, question, _agent)
        client = lark.Client.builder().app_id(settings.feishu_app_id).app_secret(
            settings.feishu_app_secret
        ).build()
        client.im.v1.message.create(
            CreateMessageRequest.builder()
            .receive_id_type("chat_id")
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(event.event.message.chat_id)
                .msg_type("text")
                .content(lark.JSON.marshal({"text": answer}))
                .build()
            )
            .build()
        )

    handler = (
        lark.EventDispatcherHandler.builder("", "")
        .register_p2_im_message_receive_v1(_on_message)
        .build()
    )
    ws = lark.ws.Client(
        settings.feishu_app_id, settings.feishu_app_secret, event_handler=handler
    )
    ws.start()


if __name__ == "__main__":
    run()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run pytest tests/test_feishu_ws.py -v`
Expected: 2 passed

- [ ] **Step 5: 全量质量门禁**

Run: `uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pytest -v`
Expected: ruff 无报错；pyright 0 errors；全部测试 passed（约 12 个）
（若 ruff format 报告需格式化，运行 `uv run ruff format .` 后重跑;若 pyright 对 lark-oapi 缺类型报警，在该文件顶部加 `# pyright: reportMissingTypeStubs=false` 并在阶段文档踩坑区记录。）

- [ ] **Step 6: 真实联调（需飞书凭据，手动验证）**

设置 `.env` 里的 `OPSPILOT_FEISHU_APP_ID/SECRET`，Run: `uv run python -m opspilot.entrypoints.feishu_ws`
Expected: WS 连接建立；在飞书向机器人发「default 有哪些 pod 不正常」，收到提及 `order-service CrashLoopBackOff` 的回复。

- [ ] **Step 7: Commit**

```bash
git add src/opspilot/entrypoints/feishu_ws.py tests/test_feishu_ws.py
git commit -m "$(cat <<'EOF'
feat(feishu): WebSocket bot entrypoint wired to ReAct

Adds Feishu (lark-oapi long-connection) as a first-class entrypoint
per ARCHITECTURE.md. Testable core (handle_question) is isolated as a
pure async function; the lark SDK socket wiring in run() is
manual-verify only (integration, not unit-testable).

- handle_question: trims input, rejects empty, delegates to an
  injected agent fn — fully unit-tested
- run(): subscribes im.message.receive_v1 over WS, extracts text,
  replies via im.message.create
- Quality gate run for the whole package (ruff + pyright + pytest)

EOF
)"
```

---

## Task 7: 阶段总结文档 + Release

**Files:**
- Create: `docs/stages/stage0_foundation.md`
- Modify: `README.md`

- [ ] **Step 1: 写阶段总结文档**

Create `docs/stages/stage0_foundation.md`，严格套 ARCHITECTURE.md §3 模板，至少包含：

1. **做了什么 + Mermaid 流程图**：
   ```mermaid
   sequenceDiagram
     participant U as 用户(CLI/飞书)
     participant R as run_react
     participant L as LLMClient->llama.cpp
     participant T as get_pod_status
     U->>R: 问题
     loop 最多 max_steps
       R->>L: messages
       L-->>R: Thought/Action 或 Final Answer
       alt 是 Action
         R->>T: namespace
         T-->>R: pod 表(来自 fixture)
         R->>R: 把 Observation 回灌
       else 是 Final Answer
         R-->>U: 最终回答
       end
     end
   ```
2. **核心原理**：ReAct 为什么需要 Observation 回灌；OpenAI 兼容协议结构；为什么手写而不直接上框架。至少 3 个面试问答。
3. **关键代码走读**：`agent/react.py`、`llm/client.py`、`tools/pod_status.py`。
4. **如何运行**：`uv sync` → 启 llama.cpp → `uv run opspilot ask "..."` → 飞书联调步骤。
5. **踩坑记录**：pyright 对 lark-oapi 的类型告警等实际遇到的问题。
6. **验收自检**：逐条对照下方 Acceptance Criteria 打勾 + 证据。

- [ ] **Step 2: 更新 README**

在 `README.md` 增加 Quickstart 段（3 行命令：`uv sync` / 启 llama.cpp / `uv run opspilot ask "default 有哪些 pod 不正常"`）。

- [ ] **Step 3: 验收自检**

Run: `uv run pytest -v`
Expected: 全绿（约 12 passed）。逐条核对：
- ✅ `uv run opspilot ask "..."` 基于 mock 数据回答（手动，需 llama.cpp）
- ✅ 飞书问答打通（手动，需凭据）
- ✅ 阶段总结文档含 ReAct 时序流程图
- ✅ ruff + pyright 全绿

- [ ] **Step 4: Commit + Tag**

```bash
git add docs/stages/stage0_foundation.md README.md
git commit -m "$(cat <<'EOF'
docs(stage0): stage summary, flow diagram, and quickstart

Closes Stage 0. The stage summary is the portfolio artifact (per
ARCHITECTURE.md §3): what was built, the ReAct sequence diagram, the
principles an interviewer will probe, code walkthrough, run
instructions, and the gotchas log (lark type stubs).

EOF
)"
git tag -a stage0 -m "Stage 0: end-to-end vertical slice (CLI + Feishu + hand-written ReAct + mock tool)"
```

---

## Acceptance Criteria（对应 ARCHITECTURE.md §5 阶段 0）

- ✅ CLI `opspilot ask` 跑通手写 ReAct，基于 fixture 回答（手动 smoke + 单测覆盖逻辑）
- ✅ 飞书 WS 入口：`handle_question` 单测通过；`run()` 手动联调说明
- ✅ 单一 `opspilot` 包，分层清晰，`uv sync` 一键装
- ✅ 全套质量门禁绿：ruff / pyright / pytest（约 12 用例）
- ✅ `docs/stages/stage0_foundation.md` 含 Mermaid 流程图 + 原理 + 运行说明 + 踩坑
- ✅ 每个 Task 一个语义化、带 body 的详细 commit；阶段末打 `stage0` tag

---

## Self-Review 记录

- **Spec 覆盖**：ARCHITECTURE.md §5 阶段 0 五项要点（uv monorepo→单包决策已说明 / CLI 先行 / 飞书 WS / 手写 ReAct / mock 工具读 fixture / 阶段总结文档）均有对应 Task。
- **占位符扫描**：无 TBD/TODO；所有代码块完整可粘贴运行。
- **类型一致性**：`run_react(question, llm, max_steps)` 签名在 Task 4 定义、Task 5/6 调用一致；`SupportsChat.chat` 与 `LLMClient.chat`、`FakeLLM.chat` 签名一致；`handle_question(text, agent)` 在 Task 6 定义与测试一致；`get_pod_status(namespace)` 全程一致。
- **后续阶段计划**：Stage 1-6 不在本文件——按 just-in-time 原则，每阶段开工前依据上一阶段真实接口单独成文，避免投机性占位（见对话说明）。
