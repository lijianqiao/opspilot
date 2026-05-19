# Pending Pod 故障排查

## 概述
Pod 长时间处于 Pending 状态，表示调度器无法将其分配到任何节点。

## 常见原因
- 集群资源不足（CPU/内存无法满足 requests）
- 节点亲和性 / nodeSelector 无匹配节点
- 污点（taint）未被 Pod 容忍（toleration）
- PVC 未绑定导致挂载等待
- Pod 拓扑分布约束无法满足
- 资源配额（ResourceQuota）已耗尽

## 排查步骤

### 1. 查看调度失败原因
```bash
kubectl describe pod <pod-name> | grep -A10 "Events"
```

### 2. 检查节点可分配资源
```bash
kubectl describe nodes | grep -A5 "Allocated resources"
```

### 3. 检查节点污点与标签
```bash
kubectl get nodes -o json | jq '.items[].spec.taints'
```

### 4. 检查 PVC 状态
```bash
kubectl get pvc
```

## 解决方案

### 临时措施
- 降低 Pod 的 resources.requests
- 为 Pod 添加对应 toleration 或调整 nodeSelector

### 长期修复
- 配置 Cluster Autoscaler 自动扩容节点
- 合理设置 ResourceQuota 与 LimitRange
- 审视 topologySpreadConstraints 的 maxSkew

## 相关告警
- PodPendingTooLong
- KubeSchedulerFailed

## 参考链接
- Kubernetes 官方文档: Assigning Pods to Nodes
- 内部 Wiki: 调度问题排查手册
