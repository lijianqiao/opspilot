# Evicted Pod 故障排查

## 概述
Pod 状态为 Evicted 表示节点资源（磁盘/内存/PID）紧张，kubelet 主动驱逐了该 Pod 以保护节点稳定。

## 常见原因
- 节点磁盘压力（nodefs/imagefs 空间或 inode 不足）
- 节点内存压力（可用内存低于 eviction 阈值）
- Pod 超出本地临时存储（ephemeral-storage）limit
- 大量日志或临时文件写满磁盘
- 节点上 BestEffort/Burstable Pod 优先被驱逐

## 排查步骤

### 1. 查看驱逐原因
```bash
kubectl get pod <pod-name> -o jsonpath='{.status.message}'
kubectl describe pod <pod-name> | grep -A3 "Status"
```

### 2. 检查节点资源压力
```bash
kubectl describe node <node-name> | grep -A5 "Conditions"
```

### 3. 检查节点磁盘与 inode
```bash
ssh <node> "df -h /var/lib/kubelet && df -i /var/lib/kubelet"
```

### 4. 清理已驱逐 Pod 残留
```bash
kubectl get pods --all-namespaces -o json \
  | jq -r '.items[] | select(.status.reason=="Evicted") | "\(.metadata.namespace) \(.metadata.name)"'
```

## 解决方案

### 临时措施
- 删除已 Evicted 的 Pod 对象释放 etcd 记录
- 清理节点磁盘（旧镜像 `crictl rmi --prune`、日志轮转）

### 长期修复
- 为 Pod 设置 ephemeral-storage requests/limits
- 调整 kubelet eviction-hard 阈值并配置告警
- 接入 Cluster Autoscaler 缓解资源争抢

## 相关告警
- KubeletEvictionThresholdMet
- NodeDiskPressure

## 参考链接
- Kubernetes 官方文档: Node-pressure Eviction
- 内部 Wiki: 节点资源治理
