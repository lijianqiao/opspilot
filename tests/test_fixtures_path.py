"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_fixtures_path.py
@DateTime: 2026-05-20
@Docs: Tests fixtures directory resolution and mock mode flag.
    测试 fixtures 目录解析与 mock 模式开关。
"""

from collections.abc import Iterator
from pathlib import Path

import pytest

from opspilot.config import Settings, get_settings
from opspilot.tools.fixtures_path import get_fixtures_dir, read_fixture_json, use_mock_tools


@pytest.fixture(autouse=True)
def _clear_caches() -> Iterator[None]:
    get_settings.cache_clear()
    get_fixtures_dir.cache_clear()
    yield
    get_settings.cache_clear()
    get_fixtures_dir.cache_clear()


def test_default_fixtures_dir_points_to_repo_fixtures() -> None:
    root = Path(__file__).resolve().parents[1]
    assert get_fixtures_dir() == (root / "fixtures").resolve()
    assert (get_fixtures_dir() / "kubectl_pods.json").is_file()


def test_fixtures_dir_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    custom = tmp_path / "my_fixtures"
    custom.mkdir()
    (custom / "kubectl_pods.json").write_text('{"pods": []}', encoding="utf-8")
    monkeypatch.setenv("OPSPILOT_FIXTURES_DIR", str(custom))
    get_settings.cache_clear()
    get_fixtures_dir.cache_clear()
    assert get_fixtures_dir() == custom.resolve()


def test_use_mock_tools_default_true() -> None:
    assert Settings().use_mock_tools is True


def test_read_fixture_json_missing_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPSPILOT_FIXTURES_DIR", str(tmp_path))
    get_settings.cache_clear()
    get_fixtures_dir.cache_clear()
    with pytest.raises(FileNotFoundError, match="fixture 文件不存在"):
        read_fixture_json("no_such.json")


def test_use_mock_tools_env_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPSPILOT_USE_MOCK_TOOLS", "false")
    get_settings.cache_clear()
    assert use_mock_tools() is False


def test_kubectl_get_pods_mock_from_fixture() -> None:
    from opspilot.tools.kubectl_ops import kubectl_get

    out = kubectl_get("pods", namespace="default")
    assert "order-service" in out or "NAME" in out
