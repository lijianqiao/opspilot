# ImagePullBackOff 故障排查

## 概述
ImagePullBackOff 表示 kubelet 无法拉取容器镜像，进入退避重试。常伴随 ErrImagePull。

## 常见原因
- 镜像名称或 tag 拼写错误
- 镜像不存在或已被删除
- 私有仓库未配置 imagePullSecrets
- 仓库认证失败或 token 过期
- 节点无法访问镜像仓库（网络/DNS）
- 镜像仓库限流（rate limit）

## 排查步骤

### 1. 查看具体错误信息
```bash
kubectl describe pod <pod-name> | grep -A5 "Events"
```

### 2. 验证镜像地址
```bash
kubectl get pod <pod-name> -o jsonpath='{.spec.containers[0].image}'
```

### 3. 在节点上手动拉取测试
```bash
crictl pull <image>:<tag>
```

### 4. 检查 imagePullSecrets
```bash
kubectl get sa default -o jsonpath='{.imagePullSecrets}'
kubectl get secret <pull-secret> -o jsonpath='{.data.\.dockerconfigjson}' | base64 -d
```

## 解决方案

### 临时措施
- 修正镜像 tag 后重新 apply deployment
- 重新创建并绑定正确的 imagePullSecrets

### 长期修复
- 使用 CI 流水线统一镜像 tag，禁止 latest
- 配置镜像仓库代理/缓存（如 Harbor proxy cache）减少限流
- 在准入控制中校验镜像来源白名单

## 相关告警
- ImagePullBackOff
- PodNotReady

## 参考链接
- Kubernetes 官方文档: Images
- 内部 Wiki: 镜像仓库接入指南
