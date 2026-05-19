# Service Mesh 调用超时故障排查

## 概述
在 Istio/Linkerd 等服务网格中，服务间调用出现超时或 503 UC/UF，需区分是应用、sidecar 还是网格配置问题。

## 常见原因
- VirtualService/DestinationRule 超时与重试配置不当
- 熔断（outlier detection）误触发，实例被弹出
- sidecar（envoy）未就绪或 mTLS 握手失败
- 连接池上限过小导致排队
- 目标服务无健康实例
- 应用响应慢超过网格超时

## 排查步骤

### 1. 查看 sidecar 与流量配置
```bash
istioctl proxy-status
istioctl proxy-config cluster <pod> --fqdn <svc> -o json | jq '.[].circuitBreakers'
```

### 2. 查看 envoy 访问日志
```bash
kubectl logs <pod> -c istio-proxy --tail=100 | grep -E "UC|UF|UO|503"
```

### 3. 检查超时/重试策略
```bash
kubectl get virtualservice <vs> -o yaml | grep -A5 -E "timeout|retries"
kubectl get destinationrule <dr> -o yaml | grep -A8 outlierDetection
```

### 4. 验证 mTLS
```bash
istioctl authn tls-check <pod> <svc>
```

## 解决方案

### 临时措施
- 临时调大 VirtualService timeout / 放宽 outlierDetection
- 重启异常 sidecar Pod

### 长期修复
- 按依赖耗时合理设置 timeout，配置幂等重试
- 调优连接池（maxConnections/http2MaxRequests）
- 完善就绪探针，确保 mTLS 策略一致（STRICT/PERMISSIVE）
- 应用层优化慢接口

## 相关告警
- IstioRequestTimeoutHigh
- EnvoyUpstreamConnectionErrors

## 参考链接
- Istio 官方文档: Traffic Management & Circuit Breaking
- 内部 Wiki: 服务网格运维
