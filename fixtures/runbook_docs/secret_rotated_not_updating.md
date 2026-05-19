# Secret 轮换后应用仍用旧密钥故障排查

## 概述
Secret 已轮换，但应用仍使用旧凭据，导致认证失败或继续使用过期密钥，存在安全与可用性风险。

## 常见原因
- Secret 以 env 注入：env 在 Pod 启动时固化，更新不会生效
- Secret 以 subPath 挂载：subPath 不会自动同步更新
- 应用启动时一次性读取文件，不监听变更
- kubelet 同步有延迟（默认 60-90 秒）
- External Secrets/Vault 未触发 refresh
- 客户端缓存了旧连接/凭据

## 排查步骤

### 1. 确认 Secret 已更新
```bash
kubectl get secret <name> -o jsonpath='{.metadata.resourceVersion}'
kubectl get secret <name> -o jsonpath='{.data.<key>}' | base64 -d
```

### 2. 检查注入方式
```bash
kubectl get pod <pod> -o jsonpath='{.spec.containers[0].env}'      # env 注入?
kubectl get pod <pod> -o jsonpath='{.spec.containers[0].volumeMounts}' # subPath?
```

### 3. 进入容器核对实际值
```bash
kubectl exec <pod> -- printenv | grep <KEY>
kubectl exec <pod> -- cat <mount-path>/<key>
```

### 4. 检查 External Secret 刷新
```bash
kubectl describe externalsecret <name> | grep -i refresh
```

## 解决方案

### 临时措施
- 滚动重启让应用加载新 Secret：
```bash
kubectl rollout restart deployment/<name>
```

### 长期修复
- Secret 用普通 volume 挂载（非 subPath）并让应用监听文件变更（inotify/Reloader）
- 使用 Stakater Reloader 在 Secret 变更时自动重启
- 改用 Vault Agent / CSI driver 注入动态短期凭据
- 轮换流程纳入自动化（轮换 -> 触发重载 -> 校验）

## 相关告警
- SecretRotationNotApplied
- AuthFailureAfterRotation

## 参考链接
- Kubernetes 官方文档: Secrets - Mounted Secrets Auto-Update
- 内部 Wiki: 密钥轮换流程
