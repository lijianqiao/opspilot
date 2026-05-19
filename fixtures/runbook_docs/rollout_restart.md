# Deployment 滚动重启操作手册

## 概述
滚动重启用于在不修改镜像的情况下重建所有 Pod（如重载配置/Secret、清理状态），过程中保持服务可用。

## 常见原因
触发滚动重启的典型场景：
- ConfigMap/Secret 更新后需让 Pod 重新加载
- 应用出现内存泄漏需周期性重启
- 节点维护前主动重建 Pod
- 释放泄漏的连接/句柄

## 排查步骤

### 1. 重启前确认状态
```bash
kubectl get deployment <name> -o wide
kubectl rollout history deployment/<name>
```

### 2. 检查滚动策略与 PDB
```bash
kubectl get deployment <name> -o jsonpath='{.spec.strategy}'
kubectl get pdb
```

### 3. 执行滚动重启
```bash
kubectl rollout restart deployment/<name>
```

### 4. 观察滚动进度
```bash
kubectl rollout status deployment/<name> --timeout=300s
kubectl get pods -l app=<app> -w
```

## 解决方案

### 临时措施
- 出现异常立即暂停：`kubectl rollout pause deployment/<name>`
- 回滚：`kubectl rollout undo deployment/<name>`

### 长期修复
- 配置合理 maxSurge/maxUnavailable（建议 maxUnavailable=0）
- 设置 PDB 保证最小可用副本
- 完善 readiness probe，避免流量打到未就绪 Pod
- 配置 preStop hook + terminationGracePeriod 优雅退出

## 相关告警
- KubeDeploymentRolloutStuck
- PodReadinessLow

## 参考链接
- Kubernetes 官方文档: Deployments - Rolling Update
- 内部 Wiki: 发布操作规范
