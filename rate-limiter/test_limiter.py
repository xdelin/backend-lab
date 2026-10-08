"""限流器测试：需要真实 Redis（docker run -d --rm -p 6399:6379 redis:6-alpine）。

用例覆盖：
  - 窗口内限流：limit 次放行，第 limit+1 次拒绝；
  - 窗口滑动：旧请求滑出窗口后名额恢复（注入毫秒级时间戳，测试无需 sleep）；
  - NOSCRIPT 回退：script flush 后自动重载 EVALSHA；
  - 分布式锁释放：持有者可释放、非持有者不能释放。
"""

import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

import redis  # noqa: E402

from limiter import SlidingWindowLimiter, release_lock  # noqa: E402

REDIS_URL = "redis://127.0.0.1:6399/0"


@pytest.fixture()
def r():
    client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    client.ping()
    yield client
    client.flushdb()


def test_window_limit(r):
    limiter = SlidingWindowLimiter(r, window_ms=10_000, limit=3)
    key = f"rl:{uuid.uuid4()}"
    assert limiter.allow(key) is True
    assert limiter.allow(key) is True
    assert limiter.allow(key) is True
    assert limiter.allow(key) is False, "窗口内第 4 次请求应被拒绝"


def test_window_slides(r):
    limiter = SlidingWindowLimiter(r, window_ms=1_000, limit=2)
    key = f"rl:{uuid.uuid4()}"
    t0 = 1_000_000
    assert limiter.allow(key, now_ms=t0) is True
    assert limiter.allow(key, now_ms=t0 + 100) is True
    assert limiter.allow(key, now_ms=t0 + 200) is False
    # t0+200 的请求滑出窗口后名额恢复
    assert limiter.allow(key, now_ms=t0 + 1_300) is True
    assert limiter.allow(key, now_ms=t0 + 1_400) is True
    assert limiter.allow(key, now_ms=t0 + 1_500) is False


def test_noscript_fallback(r):
    limiter = SlidingWindowLimiter(r, window_ms=10_000, limit=1)
    key = f"rl:{uuid.uuid4()}"
    assert limiter.allow(key) is True
    r.script_flush()  # 模拟 Redis 重启后脚本缓存丢失
    assert limiter.allow(key) is False, "script flush 后应回退 EVAL 重载且限流语义不变"


def test_release_lock(r):
    lock_key = f"lock:{uuid.uuid4()}"
    token = uuid.uuid4().hex
    assert r.set(lock_key, token, nx=True, px=5_000) is True
    assert release_lock(r, lock_key, "wrong-token") is False, "非持有者不能释放"
    assert r.exists(lock_key) == 1
    assert release_lock(r, lock_key, token) is True, "持有者可释放"
    assert r.exists(lock_key) == 0
