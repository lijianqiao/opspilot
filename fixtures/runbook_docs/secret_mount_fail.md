# Secret 挂载失败故障排查

## 概述
Pod 因 Secret 挂载失败卡在 ContainerCreating，或应用读取到的凭据为空/错误。

## 常见原因
- 引用的 Secret 不存在或跨 namespace
- Secret key 与 volume items 不匹配
- Secret 类型不匹配（如 dockerconfigjson 用错）
- RBAC 限制 ServiceAccount 读取 Secret
- 外部 Secret（External Secrets / Vault）同步失败
- base64 编码错误导致内容损坏

## 排查步骤

### 1. 查看 Pod 事件
```bash
kubectl describe pod <pod-name> | grep -A10 Events
```

### 2. 确认 Secret 存在与内容
```bash
kubectl get secret <secret-name> -o yaml
kubectl get secret <secret-name> -o jsonpath='{.data.<key>}' | base64 -d
```

### 3. 检查挂载配置
```bash
kubectl get pod <pod-name> -o jsonpath='{.spec.volumes}'
```

### 4. 检查 ExternalSecret 同步状态
```bash
kubectl describe externalsecret <name>
```

## 解决方案

### 临时措施
- 创建/修复缺失的 Secret
- 修正 volume items 的 key 后重建 Pod

### 长期修复
- 用 External Secrets Operator + Vault 统一管理
- 最小权限 RBAC，按需授予 Secret 读取
- Secret 变更通过流水线注入，避免手工 base64 出错

## 相关告警
- PodStuckContainerCreating
- ExternalSecretSyncFailed

## 参考链接
- Kubernetes 官方文档: Secrets
- 内部 Wiki: 密钥管理规范
