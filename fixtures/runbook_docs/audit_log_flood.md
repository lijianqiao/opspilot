# 审计日志量暴增故障排查

## 概述
Kubernetes 审计日志（audit log）量突然激增，占满磁盘、拖慢 API Server，并可能淹没安全分析。

## 常见原因
- 审计策略（audit-policy）过于宽泛（对所有请求记 RequestResponse）
- 自动化脚本/控制器失控，高频轮询 API
- ServiceAccount token 泄漏导致异常调用
- 某控制器 hot-loop（不断 list/watch/update）
- LIST 大资源被频繁调用
- 探活/监控组件配置不当造成高 QPS

## 排查步骤

### 1. 评估日志增长与来源
```bash
ssh <master> "ls -lh /var/log/kubernetes/audit.log; tail -n 1000 /var/log/kubernetes/audit.log \
  | jq -r '.user.username' | sort | uniq -c | sort -rn | head"
```

### 2. 定位高频 verb/resource
```bash
ssh <master> "tail -n 5000 /var/log/kubernetes/audit.log \
  | jq -r '[.verb,.objectRef.resource]|@tsv' | sort | uniq -c | sort -rn | head"
```

### 3. 检查 API Server QPS
```promql
sum(rate(apiserver_request_total[5m])) by (verb, resource)
```

### 4. 检查审计策略
```bash
ssh <master> "cat /etc/kubernetes/audit-policy.yaml"
```

## 解决方案

### 临时措施
- 收紧 audit-policy（高噪声资源降级为 Metadata 或 None）
- 暂停/限流失控的脚本或控制器；疑似泄漏立即吊销 token

### 长期修复
- 精细化审计策略：只对敏感资源记 RequestResponse
- 控制器加退避与缓存，避免 hot-loop
- 审计日志轮转 + 大小上限 + 异步落盘/外发 SIEM
- 监控 API QPS 异常与 audit 日志增速告警

## 相关告警
- AuditLogVolumeSpike
- APIServerHighRequestRate

## 参考链接
- Kubernetes 官方文档: Auditing
- 内部 Wiki: 审计与安全监控规范
