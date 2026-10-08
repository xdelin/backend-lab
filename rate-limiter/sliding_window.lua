-- 滑动窗口限流（ZSet 实现）：清理窗口外 → 判限 → 记录，单脚本原子执行。
-- KEYS[1] = 限流 key（如 rl:{user_id}:{api}）
-- ARGV[1] = now（毫秒时间戳，由客户端注入以保证多实例时钟语义一致）
-- ARGV[2] = window_ms 窗口长度
-- ARGV[3] = limit 窗口内允许的最大请求数
-- ARGV[4] = 本次请求的唯一 id（uuid）：Redis Lua 的 math.random 是确定性种子
--   （保证主从复制效果一致），同毫秒内会生成相同 member 被 ZADD 覆盖导致少计数
-- 返回 1 = 放行；0 = 拒绝
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])

redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
if redis.call('ZCARD', key) >= limit then
  return 0
end
redis.call('ZADD', key, now, now .. '-' .. ARGV[4])
redis.call('PEXPIRE', key, window)
return 1
