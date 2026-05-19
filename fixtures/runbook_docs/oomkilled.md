# OOMKilled 故障排查

## 概述
OOMKilled 表示容器使用的内存超过了 memory limit，被 Linux OOM Killer 强制终止（退出码 137）。

## 常见原因
- 容器 memory limit 设置过低
- JVM heap（-Xmx）配置高于容器 limit
- 应用存在内存泄漏
- 并发请求突增导致内存暴涨
- 大对象（大文件、大查询结果）一次性加载到内存
- Cgroup limit 与应用感知内存不一致

## 排查步骤

### 1. 确认 OOMKilled 状态
```bash
kubectl describe pod <pod-name> | grep -A3 "Last State"
kubectl get pod <pod-name> -o jsonpath='{.status.containerStatuses[0].lastState.terminated.reason}'
```

### 2. 查看当前内存使用与 limit
```bash
kubectl top pod <pod-name> --containers
kubectl get pod <pod-name> -o jsonpath='{.spec.containers[0].resources}'
```

### 3. 查看历史内存曲线（Prometheus）
```promql
container_memory_working_set_bytes{pod="<pod-name>"}
```

### 4. 检查 JVM/运行时参数
```bash
kubectl exec <pod-name> -- jcmd 1 VM.flags 2>/dev/null
```

## 解决方案

### 临时措施
- 提高 resources.limits.memory（如 512Mi -> 1Gi）并滚动更新
- 临时扩容副本数分摊请求压力

### 长期修复
- 配置 JVM `-XX:MaxRAMPercentage=75` 让堆随容器自适应
- 使用 pprof / heap dump 定位内存泄漏
- 对大查询做分页或流式处理
- 设置合理的 requests/limits 并接入 VPA 推荐

## 相关告警
- ContainerOOMKilled
- PodMemoryUsageHigh

## 参考链接
- Kubernetes 官方文档: Resource Management for Pods
- 内部 Wiki: 内存调优案例集
