"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: fixtures_path.py
@DateTime: 2026-05-20
@Docs: Resolve fixtures directory and mock vs real cluster tool mode.
    解析 fixtures 目录路径，以及 mock / 真实集群工具模式。
"""

from __future__ import annotations

import json
import subprocess
from functools import lru_cache
from pathlib import Path

from opspilot.config import get_settings
from opspilot.tools.policy import kubectl_describe_kind, reject_kubectl_read_resource


def _default_fixtures_dir() -> Path:
    """Infer project fixtures/ by walking up from this module.

    从本模块向上查找含 pyproject.toml 的目录，定位 fixtures/。

    Returns:
        Path to fixtures directory.
            fixtures 目录的绝对路径。
    """
    here = Path(__file__).resolve().parent
    for parent in [here, *here.parents]:
        fixtures = parent / "fixtures"
        if fixtures.is_dir():
            return fixtures
        if (parent / "pyproject.toml").is_file():
            return parent / "fixtures"
    return here.parents[2] / "fixtures"


@lru_cache(maxsize=1)
def get_fixtures_dir() -> Path:
    """Return the directory containing JSON/markdown fixture files.

    返回存放 JSON / markdown fixture 的目录。

    Priority:
        1. OPSPILOT_FIXTURES_DIR if set
        2. Auto-detected repo fixtures/ (or /app/fixtures in Docker when copied)

    Returns:
        Absolute path to fixtures directory.
            fixtures 目录的绝对路径。
    """
    settings = get_settings()
    configured = settings.fixtures_dir.strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return _default_fixtures_dir()


def use_mock_tools() -> bool:
    """Whether tools read mock data from fixtures instead of live backends.

    工具是否从 fixtures 读取模拟数据（而非真实集群 / 观测后端）。

    Returns:
        Value of Settings.use_mock_tools (OPSPILOT_USE_MOCK_TOOLS).
            Settings.use_mock_tools 的值。
    """
    return get_settings().use_mock_tools


def read_fixture_json(filename: str) -> object:
    """Load a JSON fixture file; raise FileNotFoundError with Chinese message if missing.

    加载 JSON fixture；缺失时抛出带中文说明的 FileNotFoundError。

    Args:
        filename: Basename under fixtures dir (e.g. kubectl_pods.json).
            fixtures 目录下的文件名。

    Returns:
        Parsed JSON value.
            解析后的 JSON 对象。
    """
    path = get_fixtures_dir() / filename
    if not path.is_file():
        raise FileNotFoundError(
            f"fixture 文件不存在：{path}。"
            f" mock 联调请设置 OPSPILOT_USE_MOCK_TOOLS=true 并确保 fixtures 已挂载或打入镜像。"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def kubectl_get_pods_real(namespace: str) -> str:
    """Run kubectl get pods against the live cluster.

    对真实集群执行 kubectl get pods。

    Args:
        namespace: Kubernetes namespace.
            命名空间。

    Returns:
        Command output or user-facing error message in Chinese.
            命令输出或中文错误说明。
    """
    try:
        proc = subprocess.run(
            ["kubectl", "get", "pods", "-n", namespace],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except FileNotFoundError:
        return "真实集群模式需要 kubectl 与有效 KUBECONFIG，但未找到 kubectl 命令。"
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        return f"kubectl 执行失败：{err}"
    out = proc.stdout.strip()
    return out if out else f"namespace {namespace} 下没有找到 pod。"


def kubectl_describe_real(resource: str, name: str, namespace: str) -> str:
    """Run kubectl describe against the live cluster.

    对真实集群执行 kubectl describe。

    Args:
        resource: Resource kind (pod, deployment, ...).
            资源类型。
        name: Resource name.
            资源名称。
        namespace: Namespace.
            命名空间。

    Returns:
        Command output or user-facing error message in Chinese.
            命令输出或中文错误说明。
    """
    rejection = reject_kubectl_read_resource(resource)
    if rejection is not None:
        return rejection

    kind = kubectl_describe_kind(resource)
    try:
        proc = subprocess.run(
            ["kubectl", "describe", kind, name, "-n", namespace],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except FileNotFoundError:
        return "真实集群模式需要 kubectl 与有效 KUBECONFIG，但未找到 kubectl 命令。"
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        return f"kubectl 执行失败：{err}"
    return proc.stdout.strip()
