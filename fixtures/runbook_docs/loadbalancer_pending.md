# LoadBalancer Service 处于 Pending 故障排查

## 概述
type=LoadBalancer 的 Service 长时间没有 EXTERNAL-IP（Pending），导致外部无法访问该服务。

## 常见原因
- 集群无 cloud-controller-manager / LB 控制器（如裸金属未装 MetalLB）
- 云厂商配额不足（LB 数量/公网 IP 上限）
- 云凭据/权限不足，无法创建 LB
- 子网/安全组配置错误
- annotations 配置错误（如指定了不存在的子网/证书）
- MetalLB 地址池耗尽或未配置

## 排查步骤

### 1. 查看 Service 与事件
```bash
kubectl get svc <name> -o wide
kubectl describe svc <name> | grep -A10 Events
```

### 2. 检查 LB 控制器
```bash
kubectl -n kube-system get pods | grep -E "cloud-controller|metallb|aws-load-balancer"
kubectl -n metallb-system logs -l app=metallb --tail=80
```

### 3. 检查 MetalLB 地址池（裸金属）
```bash
kubectl -n metallb-system get ipaddresspool,l2advertisement
```

### 4. 检查云配额/权限
```bash
# 云控制台或 CLI 查看 LB / EIP 配额与控制器日志报错
```

## 解决方案

### 临时措施
- 临时改用 NodePort + 外部 LB/Ingress 暴露
- 释放闲置 LB / 申请提升配额

### 长期修复
- 裸金属部署并正确配置 MetalLB 地址池
- 校验云凭据 IAM 权限与子网/安全组
- 规范 Service annotations（按云厂商文档）
- 配置 LB 创建失败告警

## 相关告警
- ServiceLoadBalancerPending
- MetalLBAddressPoolExhausted

## 参考链接
- Kubernetes 官方文档: Service Type LoadBalancer
- 内部 Wiki: 外部访问接入方案
