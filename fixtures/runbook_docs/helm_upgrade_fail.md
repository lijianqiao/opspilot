# Helm Upgrade 失败故障排查

## 概述
helm upgrade 失败或卡住，release 进入 failed/pending-upgrade 状态，需要回滚或修复后重试。

## 常见原因
- values 缺失或类型错误，模板渲染失败
- 不可变字段被修改（如 Service.spec.clusterIP、StatefulSet 卷模板）
- CRD 未安装或版本不匹配
- 资源配额/RBAC 不足
- 上一次操作中断导致 release 处于 pending-*
- hook（pre/post-upgrade Job）失败

## 排查步骤

### 1. 查看 release 状态与历史
```bash
helm status <release> -n <ns>
helm history <release> -n <ns>
```

### 2. 预览渲染与差异
```bash
helm template <release> <chart> -f values.yaml | kubectl apply --dry-run=client -f -
helm diff upgrade <release> <chart> -f values.yaml
```

### 3. 查看失败资源/hook
```bash
kubectl get events -n <ns> --sort-by=.lastTimestamp | tail -20
kubectl logs job/<release>-pre-upgrade -n <ns>
```

## 解决方案

### 临时措施
- 回滚到上一个正常 revision：
```bash
helm rollback <release> <revision> -n <ns>
```
- pending 状态卡住时，回滚或 `helm rollback` 解锁后重试

### 长期修复
- 升级前固定执行 `helm diff` 评审变更
- 用 `--atomic --timeout` 让失败自动回滚
- CRD 单独管理（helm 不删 CRD），版本对齐
- CI 校验 values schema

## 相关告警
- HelmReleaseFailed
- ArgoCDAppDegraded

## 参考链接
- Helm 官方文档: Helm Upgrade & Rollback
- 内部 Wiki: Helm 发布规范
