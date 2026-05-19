# ConfigMap 挂载失败故障排查

## 概述
Pod 因 ConfigMap 挂载失败而无法启动（卡在 ContainerCreating），或挂载内容与预期不符。

## 常见原因
- 引用的 ConfigMap 不存在或不在同一 namespace
- ConfigMap key 名称与 volume items 不匹配
- subPath 挂载后不会自动更新
- ConfigMap 数据过大（超过 1MiB 限制）
- 挂载路径与镜像内已有文件冲突
- 文件权限（defaultMode）导致应用读取失败

## 排查步骤

### 1. 查看 Pod 事件
```bash
kubectl describe pod <pod-name> | grep -A10 Events
```

### 2. 确认 ConfigMap 存在
```bash
kubectl get configmap <cm-name> -o yaml
```

### 3. 检查 volume 与 mount 配置
```bash
kubectl get pod <pod-name> -o jsonpath='{.spec.volumes}'
kubectl get pod <pod-name> -o jsonpath='{.spec.containers[0].volumeMounts}'
```

### 4. 进入容器核对文件
```bash
kubectl exec <pod-name> -- ls -l <mount-path>
kubectl exec <pod-name> -- cat <mount-path>/<key>
```

## 解决方案

### 临时措施
- 创建缺失的 ConfigMap 或修正 namespace
- 修正 volume items 的 key/path 后重建 Pod

### 长期修复
- 用 Kustomize/Helm 统一管理 ConfigMap，避免漂移
- 避免 subPath 挂载需要热更新的配置
- 大配置改用外部存储或拆分

## 相关告警
- PodStuckContainerCreating
- ConfigMapNotFound

## 参考链接
- Kubernetes 官方文档: ConfigMaps
- 内部 Wiki: 配置管理规范
