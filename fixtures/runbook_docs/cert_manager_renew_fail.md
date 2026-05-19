# cert-manager 证书续期失败故障排查

## 概述
cert-manager 无法完成证书签发/续期，Certificate 长期 Ready=False，最终导致证书过期。

## 常见原因
- ACME HTTP-01 challenge 路径无法访问（Ingress 未放行 /.well-known）
- DNS-01 challenge 的 DNS provider 凭据错误或权限不足
- Let's Encrypt 触发 rate limit / 账户问题
- ClusterIssuer/Issuer 配置错误（错误的 ACME server / solver）
- 网络出口被限制，无法访问 ACME server
- 时间不同步导致 nonce/证书校验失败

## 排查步骤

### 1. 查看 Certificate 与下游资源
```bash
kubectl describe certificate <name> -n <ns>
kubectl describe order -n <ns>
kubectl describe challenge -n <ns>
```

### 2. 查看 cert-manager 日志
```bash
kubectl -n cert-manager logs deploy/cert-manager --tail=150
```

### 3. 验证 challenge 可达性（HTTP-01）
```bash
curl -v http://<domain>/.well-known/acme-challenge/test
```

### 4. 检查 Issuer 配置
```bash
kubectl describe clusterissuer <issuer>
```

## 解决方案

### 临时措施
- 修复 solver 配置后删除 challenge/order 触发重试
- 切到 staging issuer 验证流程，绕开 rate limit

### 长期修复
- 优先使用 DNS-01（不依赖入站可达性）
- DNS provider 凭据用 Secret 管理并最小授权
- 节点/集群启用 NTP 时间同步
- 监控 Certificate Ready 状态与 renewalTime

## 相关告警
- CertManagerCertNotReady
- ACMEChallengeFailed

## 参考链接
- cert-manager 官方文档: ACME & Troubleshooting
- 内部 Wiki: 自动证书签发方案
