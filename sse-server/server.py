"""SSE 流式服务：模拟 LLM 逐 token 推流。

SSE 关键实现点（与 WebSocket 的取舍见 README）：
  - Content-Type: text/event-stream，事件格式 `id/event/data` 以空行结尾；
  - 关闭一切缓冲：Nginx `proxy_buffering off`、响应头 `X-Accel-Buffering: no`；
  - 每个事件立即 flush（StreamingResponse 对 async generator 的每个 yield 即发）；
  - 断连治理：客户端断开时 async generator 收到 CancelledError，清理 per-connection
    资源（这里是取消 token 任务），避免泄漏。
"""

from __future__ import annotations

import asyncio
import json

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

app = FastAPI(title="sse-lab")

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",  # Nginx 不攒包
}


async def fake_llm_stream(prompt: str, chunk_delay: float = 0.02):
    """模拟 LLM token 流：按字切分异步产出。"""
    reply = f"Echo: {prompt}"
    for ch in reply:
        await asyncio.sleep(chunk_delay)
        yield ch


async def event_gen(prompt: str):
    seq = 0
    task = asyncio.current_task()
    try:
        async for token in fake_llm_stream(prompt):
            seq += 1
            yield f"id: {seq}\ndata: {json.dumps({'t': token}, ensure_ascii=False)}\n\n"
        yield "event: done\ndata: [DONE]\n\n"
    except asyncio.CancelledError:
        # 客户端断连：FastAPI/Starlette 取消 generator，这里做 per-connection 清理
        raise


@app.get("/chat")
async def chat(prompt: str = "hello"):
    return StreamingResponse(
        event_gen(prompt),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
