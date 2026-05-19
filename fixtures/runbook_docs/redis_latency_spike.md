# Redis 延迟突增故障排查

## 概述
Redis 命令延迟（P99）突然升高，导致依赖缓存的服务超时、雪崩到数据库。

## 常见原因
- 大 key 读写（大 hash/list/set）阻塞单线程
- O(N) 命令（KEYS、HGETALL 大集合、SMEMBERS）
- 内存达到 maxmemory 触发频繁淘汰
- key 集中过期导致瞬时 CPU 飙升
- RDB BGSAVE / AOF rewrite 时 fork 卡顿
- 网络抖动或 CPU 被压满

## 排查步骤

### 1. 实时延迟与慢日志
```bash
redis-cli --latency
redis-cli slowlog get 20
```

### 2. 查找大 key
```bash
redis-cli --bigkeys
redis-cli memory usage <key>
```

### 3. 查看内存与命中率
```bash
redis-cli info memory | grep -E "used_memory|maxmemory|evicted"
redis-cli info stats | grep -E "keyspace_hits|keyspace_misses|expired_keys"
```

### 4. 检查持久化与 CPU
```bash
redis-cli info persistence | grep -E "rdb_bgsave_in_progress|aof_rewrite_in_progress"
redis-cli info cpu
```

## 解决方案

### 临时措施
- 禁用/限制 KEYS 等危险命令（用 SCAN 替代）
- 拆分或删除大 key

### 长期修复
- 大 key 拆分为多个小 key，控制 value 大小
- 过期时间加随机抖动，避免集中失效
- 合理设置 maxmemory + LRU/LFU 淘汰策略
- 持久化错峰，必要时主从分离读写

## 相关告警
- RedisLatencyHigh
- RedisMemoryFragmentationHigh

## 参考链接
- Redis 官方文档: Latency Troubleshooting
- 内部 Wiki: 缓存使用规范
