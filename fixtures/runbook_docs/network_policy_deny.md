# NetworkPolicy 拦截导致通信失败故障排查

## 概述
两个 Pod/服务间通信被拒（连接超时），通常是 NetworkPolicy 默认拒绝或规则不匹配导致。

## 常见原因
- 命名空间存在 default-deny 策略，但未放行所需流量
- policy 的 podSelector / namespaceSelector 标签不匹配
- 只配置了 Ingress 未配置 Egress（或反之）
- DNS（kube-dns）端口未放行导致解析失败
- CNI 不支持 NetworkPolicy（如部分 Flannel 配置）
- 端口/协议（TCP/UDP）未覆盖

## 排查步骤

### 1. 列出相关 NetworkPolicy
```bash
kubectl get networkpolicy -n <ns>
kubectl describe networkpolicy <name> -n <ns>
```

### 2. 从源 Pod 测试连通性
```bash
kubectl exec <src-pod> -- nc -zv -w3 <dst-svc> <port>
kubectl exec <src-pod> -- nslookup <dst-svc>
```

### 3. 核对标签匹配
```bash
kubectl get pod <dst-pod> --show-labels
kubectl get ns <ns> --show-labels
```

### 4. 检查 CNI 是否支持
```bash
kubectl -n kube-system get pods | grep -E "calico|cilium"
```

## 解决方案

### 临时措施
- 临时添加放行规则验证（确认后再收紧）
- 显式放行 DNS（53/UDP+TCP 到 kube-system）

### 长期修复
- 采用 default-deny + 显式 allow 的最小权限模型
- 用标签规范统一 podSelector/namespaceSelector
- Ingress 与 Egress 成对设计并评审
- 使用支持 NetworkPolicy 的 CNI（Calico/Cilium）

## 相关告警
- NetworkPolicyBlockingTraffic
- PodConnectivityFailed

## 参考链接
- Kubernetes 官方文档: Network Policies
- 内部 Wiki: 零信任网络规范
