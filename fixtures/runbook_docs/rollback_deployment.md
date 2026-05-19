# Deployment 回滚操作手册

## 概述
当新版本上线后出现严重故障（错误率飙升、崩溃），需快速回滚到上一个已知稳定版本止损。

## 常见原因
触发回滚的典型场景：
- 新版本引入致命 bug / panic
- 性能严重劣化
- 配置/依赖不兼容
- 数据写入异常

## 排查步骤

### 1. 确认问题与版本
```bash
kubectl rollout history deployment/<name>
kubectl rollout history deployment/<name> --revision=<n>
```

### 2. 查看当前异常
```bash
kubectl get pods -l app=<app>
kubectl logs -l app=<app> --tail=100 | grep -i error
```

### 3. 执行回滚
```bash
kubectl rollout undo deployment/<name>                 # 回到上一版
kubectl rollout undo deployment/<name> --to-revision=<n>  # 指定版本
```

### 4. 验证回滚结果
```bash
kubectl rollout status deployment/<name>
kubectl get deployment <name> -o jsonpath='{.spec.template.spec.containers[0].image}'
```

## 解决方案

### 临时措施
- 回滚后立即验证核心链路与监控指标
- 必要时同步回滚关联的 ConfigMap/Secret/数据库变更

### 长期修复
- 保留足够的 revisionHistoryLimit
- 发布走金丝雀/灰度，自动回滚条件前置
- 数据库变更与代码解耦（向后兼容、可回滚迁移）
- 建立发布检查清单与回滚演练

## 相关告警
- DeploymentBadRollout
- HighErrorRateAfterDeploy

## 参考链接
- Kubernetes 官方文档: Rolling Back a Deployment
- 内部 Wiki: 回滚预案
