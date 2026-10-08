"""SSE 服务测试：httpx ASGITransport 直打 app，无需起端口。"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import httpx

from server import app


def test_sse_event_format():
    async def inner():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            async with client.stream("GET", "/chat", params={"prompt": "hi"}) as resp:
                assert resp.status_code == 200
                assert resp.headers["content-type"].startswith("text/event-stream")
                assert resp.headers["x-accel-buffering"] == "no"

                body = ""
                async for chunk in resp.aiter_text():
                    body += chunk
        return body

    body = asyncio.run(inner())

    events = [e for e in body.split("\n\n") if e.strip()]
    # Echo: hi 共 8 个字符 → 8 个 token 事件 + 1 个 done 事件
    assert len(events) == 9
    for i, event in enumerate(events[:-1]):
        lines = event.split("\n")
        assert lines[0] == f"id: {i + 1}", "每个事件应有递增 id"
        assert lines[1].startswith("data: "), "token 事件应有 data 行"
    assert events[-1] == "event: done\ndata: [DONE]", "结束事件应为 event: done + [DONE]"

    # token 按序拼接还原完整回复
    tokens = [e.split("data: ", 1)[1] for e in events[:-1]]
    assert "".join(json.loads(t)["t"] for t in tokens) == "Echo: hi"
