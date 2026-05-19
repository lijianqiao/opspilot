# DNS 解析失败故障排查

## 概述
Pod 内域名解析失败或超时（既包括集群内 Service，也包括外部域名），导致服务调用大面积报错。

## 常见原因
- CoreDNS 故障或资源不足
- Pod 的 /etc/resolv.conf 配置错误（dnsPolicy）
- ndots:5 导致大量无效 search 域查询放大延迟
- 上游 DNS 不可达（外部域名解析失败）
- conntrack 表满导致 UDP DNS 丢包
- NetworkPolicy 阻断了到 kube-dns 的流量

## 排查步骤

### 1. 在 Pod 内测试解析
```bash
kubectl exec <pod> -- nslookup kubernetes.default
kubectl exec <pod> -- nslookup www.example.com
kubectl exec <pod> -- cat /etc/resolv.conf
```

### 2. 检查 CoreDNS
```bash
kubectl -n kube-system get pods -l k8s-app=kube-dns
kubectl -n kube-system logs -l k8s-app=kube-dns --tail=80
```

### 3. 检查 conntrack 与丢包
```bash
ssh <node> "conntrack -C; sysctl net.netfilter.nf_conntrack_max"
```

### 4. 检查到 DNS 的网络策略
```bash
kubectl get networkpolicy -A | grep -i dns
```

## 解决方案

### 临时措施
- 重启 CoreDNS；必要时给 Pod 显式配置 dnsConfig
- 外部域名问题：临时指定可用上游 DNS

### 长期修复
- 部署 NodeLocal DNSCache 降低延迟与 conntrack 压力
- 对内部短名优化（合理设置 ndots、使用 FQDN）
- CoreDNS 扩容 + HPA，上游 forward 高可用
- 放行到 kube-dns 的 NetworkPolicy（53/UDP+TCP）

## 相关告警
- CoreDNSDown
- DNSResolutionLatencyHigh

## 参考链接
- Kubernetes 官方文档: DNS for Services and Pods
- 内部 Wiki: 集群 DNS 优化
