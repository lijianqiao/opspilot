# CrashLoopBackOff 故障排查

## 概述
CrashLoopBackOff 表示 Pod 反复启动后崩溃，Kubernetes 进入退避重启循环。

## 常见原因
- 启动命令或参数错误
- 配置文件缺失或格式错误
- 依赖服务（数据库/缓存）不可达
- 内存不足导致 OOMKilled
- 健康检查（liveness probe）配置不当
- 端口冲突

## 排查步骤

### 1. 查看 Pod 状态和重启次数
```bash
kubectl get pods -l app=<service-name>
```

### 2. 查看上次崩溃日志
```bash
kubectl logs <pod-name> --previous --tail=200
```

### 3. 查看 Pod 事件
```bash
kubectl describe pod <pod-name> | tail -50
```

### 4. 检查资源限制
```bash
kubectl describe pod <pod-name> | grep -A5 -E "Limits|Requests"
```

### 5. 检查配置挂载
```bash
kubectl get configmap <config-name> -o yaml
kubectl describe pod <pod-name> | grep -A10 "Mounts"
```

## 解决方案

### 临时措施
- 回滚到上一个正常版本：`kubectl rollout undo deployment/<name>`
- 增加内存限制：编辑 deployment 的 resources.limits.memory

### 长期修复
- 添加启动探针（startupProbe）防止过早健康检查
- 实现优雅关闭（SIGTERM handler）
- 添加 initContainer 等待依赖服务就绪
- 代码层面修复 panic/nil pointer

## 相关告警
- PodCrashLooping
- PodRestartRateHigh

## 参考链接
- Kubernetes 官方文档: Pod Lifecycle
- 内部 Wiki: CrashLoop 案例集
