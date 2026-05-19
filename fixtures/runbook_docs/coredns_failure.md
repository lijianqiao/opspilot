# CoreDNS 解析失败故障排查

## 概述
集群内服务名无法解析或解析超时，通常是 CoreDNS 故障，影响所有依赖服务发现的工作负载。

## 常见原因
- CoreDNS Pod 未 Running 或副本不足
- CoreDNS 资源不足被限流（CPU throttling）
- 上游 DNS（forward .  /etc/resolv.conf）不可达
- Corefile 配置错误
- conntrack 表满导致 UDP 丢包
- NodeLocal DNSCache 异常

## 排查步骤

### 1. 检查 CoreDNS Pod 与日志
```bash
kubectl -n kube-system get pods -l k8s-app=kube-dns -o wide
kubectl -n kube-system logs -l k8s-app=kube-dns --tail=100
```

### 2. 集群内解析测试
```bash
kubectl run dnsutils --image=registry.k8s.io/e2e-test-images/jessie-dnsutils:1.7 -it --rm -- \
  nslookup kubernetes.default.svc.cluster.local
```

### 3. 检查 Corefile 与 Service
```bash
kubectl -n kube-system get configmap coredns -o yaml
kubectl -n kube-system get svc kube-dns
```

### 4. 检查 conntrack
```bash
ssh <node> "conntrack -C && sysctl net.netfilter.nf_conntrack_max"
```

## 解决方案

### 临时措施
- 重启 CoreDNS：`kubectl -n kube-system rollout restart deployment coredns`
- 扩容 CoreDNS 副本数

### 长期修复
- 提高 CoreDNS resources 并配置 HPA
- 部署 NodeLocal DNSCache 降低延迟与 conntrack 压力
- 调高 nf_conntrack_max，优化 forward 上游

## 相关告警
- CoreDNSDown
- CoreDNSLatencyHigh

## 参考链接
- Kubernetes 官方文档: Debugging DNS Resolution
- 内部 Wiki: 集群 DNS 优化
