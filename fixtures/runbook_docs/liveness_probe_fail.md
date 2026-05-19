# Liveness Probe 失败导致反复重启故障排查

## 概述
Liveness probe 持续失败会使 kubelet 不断重启容器，表现为 Pod 重启次数飙升甚至 CrashLoopBackOff。

## 常见原因
- initialDelaySeconds 过短，应用未启动完就被探测
- periodSeconds 太频繁 / timeoutSeconds 太短
- failureThreshold 太低，偶发抖动即重启
- 健康检查接口本身耗时长或依赖外部服务
- 应用启动慢（JIT 预热、加载大模型）
- 探针端口/路径配置错误

## 排查步骤

### 1. 查看重启与探针事件
```bash
kubectl describe pod <pod-name> | grep -E "Liveness|Restart|Killing"
```

### 2. 查看探针配置
```bash
kubectl get pod <pod-name> -o jsonpath='{.spec.containers[0].livenessProbe}'
```

### 3. 手动验证健康接口
```bash
kubectl exec <pod-name> -- wget -qO- http://localhost:<port>/healthz
```

### 4. 查看应用启动耗时
```bash
kubectl logs <pod-name> --previous --tail=100
```

## 解决方案

### 临时措施
- 调大 initialDelaySeconds / failureThreshold 后滚动更新
- 暂时移除 liveness probe 定位是否探针误杀

### 长期修复
- 引入 startupProbe 给慢启动应用足够时间
- 健康接口做成轻量、不依赖外部依赖
- liveness 检查进程存活，readiness 检查依赖就绪，职责分离

## 相关告警
- PodRestartRateHigh
- LivenessProbeFailing

## 参考链接
- Kubernetes 官方文档: Configure Liveness, Readiness and Startup Probes
- 内部 Wiki: 探针配置最佳实践
