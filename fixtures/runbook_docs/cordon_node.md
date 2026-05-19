# 节点 Cordon（隔离调度）操作手册

## 概述
cordon 将节点标记为 SchedulingDisabled，阻止新 Pod 调度到该节点，但不驱逐已有 Pod，常用于问题排查与维护前置。

## 常见原因
触发 cordon 的典型场景：
- 节点疑似异常需观察，但不想立即驱逐
- 维护前先阻止新负载进入
- 隔离故障节点避免影响扩大
- 灰度排查特定节点问题

## 排查步骤

### 1. 查看节点调度状态
```bash
kubectl get nodes
kubectl describe node <node> | grep -i unschedulable
```

### 2. 执行 cordon
```bash
kubectl cordon <node>
```

### 3. 确认不再有新 Pod 调度
```bash
kubectl get pods -o wide --field-selector spec.nodeName=<node> -w
```

### 4. 排查节点问题
```bash
ssh <node> "journalctl -u kubelet -n 100 --no-pager"
kubectl describe node <node> | grep -A10 Conditions
```

## 解决方案

### 临时措施
- 仅隔离不驱逐，保留现场便于排查
- 问题确认后再决定 drain 或修复

### 长期修复
- 排查完成恢复调度：`kubectl uncordon <node>`
- 结合 node-problem-detector 自动 cordon 异常节点
- 制定 cordon -> 排查 -> drain -> 修复 的标准流程

## 相关告警
- KubeNodeUnschedulable
- NodeProblemDetected

## 参考链接
- Kubernetes 官方文档: Manual Node Administration
- 内部 Wiki: 节点隔离规范
