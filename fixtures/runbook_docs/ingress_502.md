# Ingress 502 Bad Gateway 故障排查

## 概述
Ingress 返回 502 表示反向代理（ingress-nginx 等）成功接收请求，但从上游后端获取响应失败。

## 常见原因
- 后端 Pod 未就绪或全部崩溃
- upstream 连接被重置（应用提前关闭连接）
- 后端响应超时（proxy-read-timeout 太短）
- Service endpoints 为空
- 后端返回非法 HTTP 响应头
- TLS 后端（HTTPS upstream）协议不匹配

## 排查步骤

### 1. 查看 ingress-controller 日志
```bash
kubectl -n ingress-nginx logs -l app.kubernetes.io/name=ingress-nginx --tail=100 | grep 502
```

### 2. 检查后端 Service 与 Endpoints
```bash
kubectl get ingress <name> -o yaml
kubectl get endpoints <backend-svc>
```

### 3. 绕过 Ingress 直连后端
```bash
kubectl port-forward svc/<backend-svc> 8080:80
curl -v http://localhost:8080/healthz
```

### 4. 检查超时注解
```bash
kubectl get ingress <name> -o jsonpath='{.metadata.annotations}'
```

## 解决方案

### 临时措施
- 重启异常后端 Pod，确认 readiness 通过
- 临时调大 `nginx.ingress.kubernetes.io/proxy-read-timeout`

### 长期修复
- 后端开启 keepalive 并优雅关闭连接
- 完善 readiness/liveness 探针
- 对慢接口做异步化或调优

## 相关告警
- IngressHttp5xxRateHigh
- BackendUnhealthy

## 参考链接
- ingress-nginx 文档: Troubleshooting
- 内部 Wiki: 网关 5xx 排查
