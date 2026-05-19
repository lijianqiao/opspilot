# Ingress 503 Service Unavailable 故障排查

## 概述
Ingress 返回 503 通常表示没有可用的后端 endpoint，或后端被限流/熔断，代理无法转发请求。

## 常见原因
- 后端 Service endpoints 为空（无就绪 Pod）
- Deployment 副本数为 0 或全部 Pending
- 滚动更新期间瞬时无可用副本
- ingress-controller 限流（limit-rps）触发
- 后端被 readiness gate 全部摘除

## 排查步骤

### 1. 检查后端 Endpoints
```bash
kubectl get endpoints <backend-svc>
kubectl get pods -l app=<app> -o wide
```

### 2. 查看 ingress 日志中的 503
```bash
kubectl -n ingress-nginx logs -l app.kubernetes.io/name=ingress-nginx --tail=100 | grep 503
```

### 3. 检查副本与滚动状态
```bash
kubectl get deployment <name>
kubectl rollout status deployment/<name>
```

### 4. 检查限流注解
```bash
kubectl get ingress <name> -o jsonpath='{.metadata.annotations}' | tr ',' '\n' | grep limit
```

## 解决方案

### 临时措施
- 扩容后端副本：`kubectl scale deployment/<name> --replicas=3`
- 回滚有问题的发布

### 长期修复
- 配置 maxUnavailable=0 或 PDB 保障滚动期间有可用副本
- 合理设置 HPA 应对流量峰值
- 评估并调高限流阈值

## 相关告警
- IngressNoHealthyBackend
- KubeDeploymentReplicasMismatch

## 参考链接
- ingress-nginx 文档: Troubleshooting
- 内部 Wiki: 零停机发布规范
