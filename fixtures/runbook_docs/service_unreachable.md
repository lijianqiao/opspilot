# Service 不可达（Connection Refused）故障排查

## 概述
通过 Service 名称或 ClusterIP 访问返回 connection refused / timeout，通常是 selector、endpoints 或端口配置问题。

## 常见原因
- Service selector 与 Pod labels 不匹配，endpoints 为空
- targetPort 与容器实际监听端口不一致
- Pod 未就绪（readiness probe 失败）被移出 endpoints
- 应用监听 127.0.0.1 而非 0.0.0.0
- NetworkPolicy 拦截了流量
- kube-proxy 异常导致 iptables/ipvs 规则未生效

## 排查步骤

### 1. 检查 Service 与 Endpoints
```bash
kubectl get svc <svc-name> -o wide
kubectl get endpoints <svc-name>
```

### 2. 核对 selector 与 Pod labels
```bash
kubectl get svc <svc-name> -o jsonpath='{.spec.selector}'
kubectl get pods --show-labels | grep <app>
```

### 3. 直接访问 Pod 验证
```bash
kubectl port-forward <pod-name> 8080:<container-port>
kubectl exec <pod-name> -- netstat -tlnp
```

### 4. 检查 kube-proxy 与 NetworkPolicy
```bash
kubectl -n kube-system logs -l k8s-app=kube-proxy --tail=50
kubectl get networkpolicy
```

## 解决方案

### 临时措施
- 修正 Service selector / targetPort 后 apply
- 让应用监听 0.0.0.0

### 长期修复
- CI 校验 Service 与 Deployment 端口一致性
- 完善 readiness probe，避免流量打到未就绪 Pod
- NetworkPolicy 变更纳入评审

## 相关告警
- ServiceEndpointsEmpty
- KubeProxyDown

## 参考链接
- Kubernetes 官方文档: Debug Services
- 内部 Wiki: 服务发现排障
