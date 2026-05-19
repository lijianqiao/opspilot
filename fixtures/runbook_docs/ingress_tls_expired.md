# Ingress TLS 证书过期故障排查

## 概述
Ingress 使用的 TLS 证书过期，浏览器报 NET::ERR_CERT_DATE_INVALID，客户端握手失败，HTTPS 服务不可用。

## 常见原因
- cert-manager 自动续期失败
- ACME challenge（HTTP-01/DNS-01）未通过
- Let's Encrypt 触发 rate limit
- Secret 中证书未更新或被覆盖
- Ingress 引用了错误的 tls secretName
- 手工证书未纳入自动续期

## 排查步骤

### 1. 检查证书有效期
```bash
echo | openssl s_client -connect <host>:443 -servername <host> 2>/dev/null \
  | openssl x509 -noout -dates
```

### 2. 检查 Certificate 资源状态
```bash
kubectl describe certificate <name> -n <ns>
kubectl get certificaterequest,order,challenge -n <ns>
```

### 3. 查看 cert-manager 日志
```bash
kubectl -n cert-manager logs deploy/cert-manager --tail=100 | grep -i <domain>
```

### 4. 核对 Ingress 引用的 Secret
```bash
kubectl get ingress <name> -o jsonpath='{.spec.tls}'
kubectl get secret <tls-secret> -o jsonpath='{.data.tls\.crt}' | base64 -d | openssl x509 -noout -enddate
```

## 解决方案

### 临时措施
- 触发重新签发：`kubectl delete certificate <name> -n <ns>`（cert-manager 会重建）
- 紧急情况手动替换有效证书到 tls secret

### 长期修复
- 用 cert-manager 自动续期（到期前 30 天）
- 配置证书到期监控告警（剩余 < 14 天）
- DNS-01 challenge 提升签发稳定性
- 关注 Let's Encrypt rate limit，必要时用 staging 验证

## 相关告警
- CertificateExpiringSoon
- CertManagerCertNotReady

## 参考链接
- cert-manager 官方文档: Troubleshooting
- 内部 Wiki: 证书生命周期管理
