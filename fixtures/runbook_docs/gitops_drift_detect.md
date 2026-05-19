# GitOps 配置漂移检测与处理

## 概述
集群实际状态与 Git 中声明的期望状态不一致（drift），可能由人工 kubectl 修改或其他控制器引入，破坏单一事实来源。

## 常见原因
- 运维直接 `kubectl edit/patch` 线上资源
- HPA/VPA/其他控制器修改了副本数等字段
- 手动扩缩容未回写 Git
- webhook/mutating admission 注入字段
- 多个工具管理同一资源

## 排查步骤

### 1. 查看 ArgoCD 漂移
```bash
argocd app diff <app>
kubectl -n argocd get application <app> -o jsonpath='{.status.sync.status}'
```

### 2. 定位被修改资源与字段
```bash
argocd app get <app> --show-params
kubectl get <kind> <name> -o yaml | kubectl neat
```

### 3. 审计谁改的
```bash
kubectl get events --sort-by=.lastTimestamp | tail
# 结合审计日志查 user/serviceaccount
```

## 解决方案

### 临时措施
- 确认期望态正确后执行 `argocd app sync <app>` 拉回一致
- 紧急人工变更需同步提 PR 回写 Git

### 长期修复
- 开启 ArgoCD selfHeal 自动纠正漂移
- 对 HPA 管理的副本数用 `ignoreDifferences` 排除
- 收紧线上写权限，强制走 GitOps 流程
- 配置漂移告警（OutOfSync 持续 N 分钟）

## 相关告警
- ArgoCDAppOutOfSync
- ConfigDriftDetected

## 参考链接
- Argo CD 官方文档: Diffing & Self Heal
- 内部 Wiki: GitOps 单一事实来源规范
