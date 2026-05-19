# Prometheus 内存使用率持续过高故障排查

## 概述
告警显示服务内存使用持续接近 limit，存在 OOMKilled 风险，需定位是泄漏还是负载导致。

## 常见原因
- 内存泄漏（缓存无上限、监听器未释放）
- 一次性加载大数据集到内存
- 连接/对象池配置过大
- JVM heap 配置不合理
- 流量增长导致常驻内存上升
- Prometheus 自身 TSDB 内存膨胀（高基数）

## 排查步骤

### 1. 查看内存趋势
```promql
container_memory_working_set_bytes{pod=~"<app>.*"}
container_memory_working_set_bytes / container_spec_memory_limit_bytes
```

### 2. 采集 heap profile
```bash
kubectl exec <pod-name> -- curl -s "http://localhost:6060/debug/pprof/heap" -o /tmp/heap.prof
go tool pprof -top -inuse_space /tmp/heap.prof
```

### 3. JVM 堆分析
```bash
kubectl exec <pod-name> -- jmap -histo:live 1 | head -20
```

### 4. 检查高基数指标（Prometheus 自身）
```promql
topk(10, count by (__name__)({__name__=~".+"}))
```

## 解决方案

### 临时措施
- 重启 Pod 释放内存（争取排查时间）
- 提高 memory limit 防止 OOM

### 长期修复
- 修复泄漏：给缓存设上限/TTL，及时关闭资源
- 大数据集改为流式/分页处理
- JVM 配置 `-XX:MaxRAMPercentage`
- 控制指标基数，避免标签爆炸

## 相关告警
- HighMemoryUsage
- ContainerMemoryNearLimit

## 参考链接
- Prometheus 官方文档: Querying
- 内部 Wiki: 内存泄漏排查
