# ArgoCD 同步失败故障排查

## 概述
ArgoCD Application 处于 OutOfSync / Degraded 或 Sync 报错，表示期望状态未能正确应用到集群。

## 常见原因
- Git 仓库连接失败（凭据/网络/分支不存在）
- manifest / Helm values 语法错误
- 目标 namespace 不存在或权限不足
- CRD 未安装，自定义资源无法创建
- 资源配额 / LimitRange 拦截
- 字段冲突（其他控制器或人工修改导致 diff 不收敛）

## 排查步骤

### 1. 查看 Application 状态
```bash
kubectl -n argocd get application <app> -o jsonpath='{.status.sync.status} {.status.health.status}'
argocd app get <app>
```

### 2. 查看同步错误详情
```bash
argocd app sync <app> --dry-run
kubectl -n argocd logs deploy/argocd-application-controller --tail=100 | grep <app>
```

### 3. 检查仓库与目标
```bash
argocd repo list
kubectl get ns <target-ns>
```

### 4. 检查 diff
```bash
argocd app diff <app>
```

## 解决方案

### 临时措施
- 修正 manifest/values 后 `argocd app sync <app>`
- 使用 `--force` / `--replace` 处理不可变字段冲突（谨慎）

### 长期修复
- CI 阶段做 `kubeconform`/`helm lint` 校验
- 预装 CRD，资源开启 ServerSideApply
- 配置 selfHeal + 自动同步，减少漂移
- 仓库凭据用 Secret 管理并监控连接

## 相关告警
- ArgoCDAppOutOfSync
- ArgoCDAppDegraded

## 参考链接
- Argo CD 官方文档: Sync & Troubleshooting
- 内部 Wiki: GitOps 运维手册
