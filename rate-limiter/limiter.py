"""基于 Redis + Lua 的滑动窗口限流器与分布式锁。

为什么用 Lua：INCR 式固定窗口限流的「读-判-写」是三条独立命令，命令间隙可插入
其他请求，边界上会超限；Lua 脚本在 Redis 单线程中整体原子执行，复合逻辑无竞态。
生产细节：
  - SCRIPT LOAD + EVALSHA：脚本只传一次，之后每次调用只传 sha，省带宽；
    NOSCRIPT 异常时回退 EVAL 重新加载（Redis 重启后脚本缓存清空）。
  - 时间由客户端注入：多实例部署时各机器时钟可能有偏差，统一由调用方传 now。
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path

import redis

_LUA_DIR = Path(__file__).parent
_SLIDING_WINDOW_LUA = (_LUA_DIR / "sliding_window.lua").read_text()
_UNLOCK_LUA = (_LUA_DIR / "unlock.lua").read_text()


class SlidingWindowLimiter:
    def __init__(self, client: redis.Redis, window_ms: int = 60_000, limit: int = 100) -> None:
        self.client = client
        self.window_ms = window_ms
        self.limit = limit
        self._script_sha = client.script_load(_SLIDING_WINDOW_LUA)

    def allow(self, key: str, now_ms: int | None = None) -> bool:
        """判断一次请求是否放行；放行则已在窗口内计数。"""
        now = now_ms if now_ms is not None else int(time.time() * 1000)
        try:
            allowed = self.client.evalsha(
                self._script_sha, 1, key, now, self.window_ms, self.limit, uuid.uuid4().hex
            )
        except redis.exceptions.NoScriptError:
            # Redis 重启 / SCRIPT FLUSH 后缓存丢失，重新加载
            self._script_sha = self.client.script_load(_SLIDING_WINDOW_LUA)
            allowed = self.client.evalsha(
                self._script_sha, 1, key, now, self.window_ms, self.limit, uuid.uuid4().hex
            )
        return bool(allowed)


def release_lock(client: redis.Redis, lock_key: str, token: str) -> bool:
    """释放分布式锁：仅当锁 value 等于自己持有的 token 时删除（原子）。"""
    return bool(client.eval(_UNLOCK_LUA, 1, lock_key, token))
