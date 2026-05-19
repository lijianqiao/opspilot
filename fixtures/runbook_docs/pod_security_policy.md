# Pod 安全准入（Pod Security）拦截故障排查

## 概述
Pod 创建被拒绝，提示违反 Pod Security Admission（PSA）标准（baseline/restricted），或旧集群的 PodSecurityPolicy 限制。

## 常见原因
- 命名空间启用了 restricted 级别，Pod 以 root 运行
- 使用了 privileged 容器 / hostNetwork / hostPath
- 未设置 securityContext（runAsNonRoot、allowPrivilegeEscalation）
- 缺少 seccompProfile=RuntimeDefault
- 添加了被禁的 Linux capabilities
- 旧集群 PSP 绑定缺失或策略过严

## 排查步骤

### 1. 查看被拒原因
```bash
kubectl apply -f pod.yaml
# 错误示例: violates PodSecurity "restricted:latest": allowPrivilegeEscalation != false ...
```

### 2. 查看命名空间 PSA 标签
```bash
kubectl get ns <ns> -o jsonpath='{.metadata.labels}'
# pod-security.kubernetes.io/enforce=restricted
```

### 3. 用 dry-run 预检
```bash
kubectl label --dry-run=server --overwrite ns <ns> \
  pod-security.kubernetes.io/enforce=restricted
```

## 解决方案

### 临时措施
- 修正工作负载 securityContext 满足策略：
```yaml
securityContext:
  runAsNonRoot: true
  allowPrivilegeEscalation: false
  capabilities: { drop: ["ALL"] }
  seccompProfile: { type: RuntimeDefault }
```
- 确需特权的命名空间用 privileged 级别（严格限制范围）

### 长期修复
- 镜像以非 root 构建，遵循 restricted 基线
- 用 audit/warn 级别灰度评估再切 enforce
- 用 Kyverno/Gatekeeper 做更细粒度策略
- 安全基线纳入 CI 校验

## 相关告警
- PodSecurityViolation
- PrivilegedContainerDetected

## 参考链接
- Kubernetes 官方文档: Pod Security Admission
- 内部 Wiki: 容器安全基线
