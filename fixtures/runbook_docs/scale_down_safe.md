# Deployment 安全缩容操作手册

## 概述
缩容需在保证服务容量与稳定的前提下逐步减少副本，避免一次性缩容导致过载或请求中断。

## 常见原因
触发缩容的典型场景：
- 业务低峰期降本
- 容量评估后回收冗余副本
- 错误扩容后回退
- 资源紧张需腾出配额

## 排查步骤

### 1. 确认当前副本与负载
```bash
kubectl get deployment <name>
kubectl top pods -l app=<app>
```

### 2. 评估单副本承载
```promql
sum(rate(http_requests_total{app="<app>"}[5m])) / count(up{app="<app>"})
```

### 3. 检查 PDB 与连接 draining
```bash
kubectl get pdb
kubectl get deployment <name> -o jsonpath='{.spec.template.spec.terminationGracePeriodSeconds}'
```

### 4. 逐步缩容并观察
```bash
kubectl scale deployment/<name> --replicas=<N-1>
# 观察错误率/延迟正常后再继续
```

## 解决方案

### 临时措施
- 发现错误率上升立即回调副本数
- 缩容前先把流量从待下线节点引开

### 长期修复
- 每次缩容 1-2 个副本，结合监控分批进行
- 配置 PDB（minAvailable）防止过度缩容
- preStop sleep + 优雅关闭，让 LB 摘除连接
- 用 HPA 让缩容由指标驱动并设 stabilizationWindow

## 相关告警
- HighErrorRateAfterScale
- KubeHpaMaxedOut

## 参考链接
- Kubernetes 官方文档: Pod Disruption Budgets
- 内部 Wiki: 容量与弹性规范
