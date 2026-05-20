"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: conftest.py
@DateTime: 2026-05-20
@Docs: Shared pytest fixtures (anyio asyncio backend).
    pytest 共享 fixture（anyio asyncio 后端）。
"""

import pytest


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
