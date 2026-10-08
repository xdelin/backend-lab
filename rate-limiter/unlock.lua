-- 分布式锁释放：校验持有者 token 再删除，「查 + 删」原子化，防止误删他人的锁。
-- KEYS[1] = 锁 key；ARGV[1] = 持有者 token
-- 返回 1 = 释放成功；0 = 不是持有者（锁已过期或被他人持有）
if redis.call('GET', KEYS[1]) == ARGV[1] then
  return redis.call('DEL', KEYS[1])
else
  return 0
end
