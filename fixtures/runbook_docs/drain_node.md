# 节点 Drain（驱逐）操作手册

## 概述
drain 用于在节点维护/下线前安全驱逐其上的 Pod，使工作负载迁移到其他节点，同时遵守 PDB。

## 常见原因
触发 drain 的典型场景：
- 节点内核/系统升级
- 硬件更换或下线
- 节点异常需隔离修复
- 集群缩容

## 排查步骤

### 1. 查看节点上的 Pod
```bash
kubectl get pods --all-namespaces -o wide --field-selector spec.nodeName=<node>
```

### 2. 先 cordon 阻止新调度
```bash
kubectl cordon <node>
```

### 3. 执行 drain
```bash
kubectl drain <node> \
  --ignore-daemonsets \
  --delete-emptydir-data \
  --grace-period=120 \
  --timeout=300s
```

### 4. 确认节点已清空
```bash
kubectl get pods -o wide --field-selector spec.nodeName=<node>
```

## 解决方案

### 临时措施
- drain 被 PDB 阻塞时，分批驱逐或临时调整 PDB
- emptyDir 数据需备份后再加 `--delete-emptydir-data`

### 长期修复
- 维护后用 `kubectl uncordon <node>` 重新纳入调度
- 为关键服务配置合理 PDB 与多副本反亲和
- 自动化节点轮转（如 Cluster API / 节点池滚动）

## 相关告警
- NodeDrainBlockedByPDB
- KubeNodeUnschedulable

## 参考链接
- Kubernetes 官方文档: Safely Drain a Node
- 内部 Wiki: 节点维护流程
