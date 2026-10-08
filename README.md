# backend-lab

后端核心组件的手写可运行实现（Agent 后端方向面试向）：**每个组件都带 pytest 测试，测试全部通过**。

| 组件 | 内容 | 测试 |
|---|---|---|
| [`lru/`](lru/) | LRU 缓存双实现：OrderedDict 版 + HashMap/双向链表版（哨兵节点），同一组用例驱动两个实现保证行为等价 | 5 |
| [`rate-limiter/`](rate-limiter/) | Redis + Lua 滑动窗口限流器（ZSet，SCRIPT LOAD/EVALSHA + NOSCRIPT 回退）+ 分布式锁原子释放脚本 | 4 |
| [`sse-server/`](sse-server/) | SSE 流式服务（模拟 LLM token 推流）：事件格式、关闭缓冲、断连清理 | 1 |

## 运行测试

```bash
python3 -m venv .venv && ./.venv/bin/pip install pytest redis httpx fastapi uvicorn

# LRU 与 SSE 无外部依赖
./.venv/bin/python -m pytest lru/ sse-server/ -q

# 限流器需要真实 Redis
docker run -d --rm -p 6399:6379 redis:6-alpine
./.venv/bin/python -m pytest rate-limiter/ -q
```

## Design notes（面试深挖点）

- **LRU 为什么必须双向链表**：HashMap O(1) 定位节点后，摘除需要改前驱指针——单向链表找前驱是 O(n)。头尾哨兵消掉空链表/单节点的边界分支。
- **限流为什么用 Lua 而不是 INCR**：固定窗口的 INCR 在边界突刺会放行 2 倍流量，且「读-判-写」多条命令存在竞态；Lua 脚本在 Redis 单线程中整体原子执行。
- **测试驱动出的真实 bug**：脚本最初用 `math.random()` 生成 ZSet member，同毫秒并发下 member 相同被 ZADD 覆盖 → 限流**少计数**。根因是 Redis Lua 的 `math.random` 是确定性种子（保证主从复制效果一致，同种子序列复现）。修复：member 唯一性由调用方注入 uuid（见 `rate-limiter/sliding_window.lua` 注释）。
- **SSE vs WebSocket 选型**：LLM 流式输出是服务器单向推 token 流，SSE 恰好匹配且复用全部 HTTP 基建（鉴权/代理/CDN）；只有客户端高频上行（语音、协同）才需要 WebSocket。服务端要点：`X-Accel-Buffering: no` 关代理缓冲、每事件立即 flush、客户端断连时 async generator 收到 CancelledError 做 per-connection 清理。
