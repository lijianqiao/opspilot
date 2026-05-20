"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: llm_gateway.py
@DateTime: 2026-05-20
@Docs: Console entrypoint for the opspilot-gateway uvicorn server.
    opspilot-gateway 控制台入口：启动 uvicorn 网关服务。
"""

from __future__ import annotations

import uvicorn


def main() -> None:
    """Start the LLM gateway via uvicorn on 0.0.0.0:8090.

    在 0.0.0.0:8090 上通过 uvicorn 启动 LLM 网关服务。
    """
    uvicorn.run("opspilot.gateway.app:app", host="0.0.0.0", port=8090)
