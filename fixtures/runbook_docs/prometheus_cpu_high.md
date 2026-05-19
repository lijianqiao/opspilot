# Prometheus CPU 使用率持续过高故障排查

## 概述
Prometheus 告警显示某服务 CPU 使用率持续高于 80%，可能导致请求延迟升高与 CPU throttling。

## 常见原因
- 最近上线新版本引入死循环或低效算法
- 正则灾难性回溯（catastrophic backtracking）
- 大量 JSON 序列化/反序列化
- 频繁 Full GC（内存不足引发）
- 流量突增但未扩容
- CPU limit 过低导致 throttling 假象

## 排查步骤

### 1. 确认 CPU 使用与限流
```promql
rate(container_cpu_usage_seconds_total{pod=~"<app>.*"}[5m])
rate(container_cpu_cfs_throttled_seconds_total{pod=~"<app>.*"}[5m])
```

### 2. 关联近期发布
```bash
kubectl rollout history deployment/<name>
```

### 3. 采集 CPU profile 定位热点
```bash
kubectl exec <pod-name> -- curl -s "http://localhost:6060/debug/pprof/profile?seconds=30" -o /tmp/cpu.prof
go tool pprof -top /tmp/cpu.prof
```

### 4. 查看线程/GC 状态（JVM）
```bash
kubectl exec <pod-name> -- jstack 1 | grep -A3 "RUNNABLE" | head
```

## 解决方案

### 临时措施
- 回滚到上一个稳定版本
- 临时扩容副本或提高 CPU limit 缓解 throttling

### 长期修复
- 优化热点函数 / 修复死循环
- 用 RE2 等线性正则引擎，限制输入长度
- 调优 GC 参数与内存配置
- 配置 HPA 按 CPU 自动扩缩

## 相关告警
- HighCpuUsage
- CPUThrottlingHigh

## 参考链接
- Prometheus 官方文档: Querying
- 内部 Wiki: CPU 性能调优
