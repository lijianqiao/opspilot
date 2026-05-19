# 节点 PIDPressure 故障排查

## 概述
PIDPressure 表示节点可用进程 ID 数量低于 kubelet 阈值，新进程无法创建，kubelet 会驱逐 Pod。

## 常见原因
- 应用产生大量进程/线程未回收（fork 炸弹、线程泄漏）
- 僵尸进程堆积（父进程未 wait 子进程）
- 容器内 PID limit 未设置
- 节点 kernel.pid_max 过低
- 某个 Pod 异常循环创建子进程

## 排查步骤

### 1. 确认 PIDPressure 状态
```bash
kubectl describe node <node-name> | grep -A2 PIDPressure
```

### 2. 查看节点进程数与上限
```bash
ssh <node> "ps -eLf | wc -l && sysctl kernel.pid_max"
```

### 3. 定位进程最多的容器
```bash
ssh <node> "for c in \$(crictl ps -q); do echo \$c \$(crictl inspect \$c | jq -r '.info.pid') ; done"
ssh <node> "ps -eo ppid= | sort | uniq -c | sort -rn | head"
```

## 解决方案

### 临时措施
- 重启失控 Pod 释放进程
- 清理僵尸进程的父进程

### 长期修复
- 配置 kubelet `podPidsLimit` 限制单 Pod 进程数
- 调高节点 `kernel.pid_max`
- 应用层修复线程池/子进程泄漏，正确 reap 子进程

## 相关告警
- NodePIDPressure
- KubeletTooManyPods

## 参考链接
- Kubernetes 官方文档: Process ID Limits And Reservations
- 内部 Wiki: 进程泄漏排查
