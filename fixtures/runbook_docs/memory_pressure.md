# 节点 MemoryPressure 故障排查

## 概述
MemoryPressure 表示节点可用内存低于 kubelet eviction 阈值（如 memory.available<100Mi），kubelet 将驱逐 Pod 回收内存。

## 常见原因
- 节点上 Pod 内存 requests 之和被严重超卖
- 某些 Pod 无 memory limit 导致内存暴涨
- 系统进程 / DaemonSet 占用大量内存
- 内存泄漏累积
- 大量页缓存未及时回收

## 排查步骤

### 1. 确认 MemoryPressure 状态
```bash
kubectl describe node <node-name> | grep -A2 MemoryPressure
```

### 2. 查看节点内存与 Top Pod
```bash
ssh <node> "free -m && cat /proc/meminfo | head"
kubectl top pods --all-namespaces --sort-by=memory | head -20
```

### 3. 查找无 limit 的 Pod
```bash
kubectl get pods --all-namespaces -o json \
  | jq -r '.items[] | select(.spec.containers[].resources.limits.memory==null) | .metadata.name'
```

## 解决方案

### 临时措施
- 驱逐/重启占用内存最高的非关键 Pod
- 临时为节点扩容内存或迁移负载

### 长期修复
- 强制所有 Pod 设置 memory requests/limits（LimitRange）
- 控制超卖比例，关键业务用 Guaranteed QoS
- 接入 VPA 给出合理内存推荐

## 相关告警
- NodeMemoryPressure
- KubeNodeMemoryUsageHigh

## 参考链接
- Kubernetes 官方文档: Node-pressure Eviction
- 内部 Wiki: 内存超卖治理
