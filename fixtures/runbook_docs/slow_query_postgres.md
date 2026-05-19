# PostgreSQL 慢查询故障排查

## 概述
PostgreSQL 慢查询突然增多，表现为接口响应变慢、连接数堆积、数据库 CPU/IO 升高。

## 常见原因
- 缺少索引导致全表扫描
- 统计信息过期，执行计划劣化
- 表膨胀（bloat），autovacuum 跟不上
- 锁等待 / 长事务阻塞
- 连接数过高，work_mem 争用
- 大结果集排序/哈希溢出到磁盘

## 排查步骤

### 1. 开启并查看慢查询
```sql
ALTER SYSTEM SET log_min_duration_statement = '500ms';
SELECT pg_reload_conf();
```

### 2. 用 pg_stat_statements 找 TOP SQL
```sql
SELECT query, calls, mean_exec_time, rows
FROM pg_stat_statements
ORDER BY mean_exec_time DESC LIMIT 10;
```

### 3. 分析执行计划
```sql
EXPLAIN (ANALYZE, BUFFERS) SELECT ...;
```

### 4. 检查锁与长事务
```sql
SELECT pid, state, wait_event_type, query, now()-xact_start AS age
FROM pg_stat_activity WHERE state <> 'idle' ORDER BY age DESC;
SELECT * FROM pg_locks WHERE NOT granted;
```

## 解决方案

### 临时措施
- 终止阻塞的长事务：`SELECT pg_terminate_backend(<pid>);`
- 对热点查询临时加索引（CONCURRENTLY）

### 长期修复
- 按查询模式建立合适索引，定期 `ANALYZE`
- 调优 autovacuum，定期处理表膨胀
- 引入连接池（PgBouncer），优化 work_mem
- SQL 审核纳入上线流程

## 相关告警
- PostgresSlowQueries
- PostgresHighConnections

## 参考链接
- PostgreSQL 官方文档: Monitoring & EXPLAIN
- 内部 Wiki: 数据库性能调优
