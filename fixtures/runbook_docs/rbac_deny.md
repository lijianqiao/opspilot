# RBAC 权限不足（Forbidden）故障排查

## 概述
执行 kubectl 或控制器调用 API 时返回 Forbidden，表示当前用户/ServiceAccount 缺少对应 RBAC 授权。

## 常见原因
- ClusterRole/Role 的 rules 未覆盖目标 apiGroup/resource/verb
- RoleBinding/ClusterRoleBinding 未正确绑定主体（subject）
- 命名空间维度错误（Role 仅在某 ns，跨 ns 操作被拒）
- 使用了错误的 ServiceAccount
- 子资源（如 pods/log、pods/exec）未单独授权
- 聚合 ClusterRole 标签未匹配

## 排查步骤

### 1. 读取错误信息关键字段
```text
forbidden: User "system:serviceaccount:ns:sa" cannot get resource "pods/log" in API group "" in the namespace "ns"
```

### 2. 用 auth can-i 验证
```bash
kubectl auth can-i get pods/log --as=system:serviceaccount:<ns>:<sa> -n <ns>
kubectl auth can-i --list --as=system:serviceaccount:<ns>:<sa> -n <ns>
```

### 3. 检查角色与绑定
```bash
kubectl get rolebinding,clusterrolebinding -A -o wide | grep <sa>
kubectl describe clusterrole <role>
```

## 解决方案

### 临时措施
- 为 ServiceAccount 绑定满足最小需求的 Role/ClusterRole
- 修正 RoleBinding 的 subject 与 namespace

### 长期修复
- 遵循最小权限原则，按需精确授予 verb/resource
- 用 `kubectl auth can-i` 纳入 CI 校验关键权限
- 审计高权限绑定（cluster-admin）并定期 review
- 角色定义版本化（GitOps 管理）

## 相关告警
- RBACAccessDenied
- ServiceAccountPermissionError

## 参考链接
- Kubernetes 官方文档: Using RBAC Authorization
- 内部 Wiki: 权限最小化规范
