# Grafana Dashboard 404 / 无法访问故障排查

## 概述
访问 Grafana 或某个 Dashboard 返回 404 / 502，或 Dashboard 列表为空，影响监控可观测性。

## 常见原因
- Grafana Pod 未 Running 或反复重启
- Service / Ingress 配置错误（路径、端口）
- Grafana 数据库（PostgreSQL/MySQL/SQLite）连接失败
- 数据目录权限错误导致启动失败
- Dashboard ConfigMap/sidecar 同步失败
- root_url / serve_from_sub_path 配置不匹配反向代理

## 排查步骤

### 1. 检查 Grafana Pod 与日志
```bash
kubectl -n monitoring get pods -l app.kubernetes.io/name=grafana
kubectl -n monitoring logs <grafana-pod> --tail=100
```

### 2. 检查 Service / Ingress
```bash
kubectl -n monitoring get svc,ingress | grep grafana
curl -I http://<grafana-host>/api/health
```

### 3. 检查数据库连接
```bash
kubectl -n monitoring logs <grafana-pod> | grep -i "database"
```

### 4. 检查 Dashboard sidecar
```bash
kubectl -n monitoring logs <grafana-pod> -c grafana-sc-dashboard --tail=50
```

## 解决方案

### 临时措施
- 重启 Grafana Pod
- 修正 Ingress path / root_url 配置

### 长期修复
- Grafana 数据库使用高可用外部 DB 并配置备份
- Dashboard 全部 as-code（ConfigMap + sidecar / Terraform）
- 配置 readiness=/api/health 与可用性告警

## 相关告警
- GrafanaDown
- GrafanaRequestErrorsHigh

## 参考链接
- Grafana 官方文档: Troubleshooting
- 内部 Wiki: 监控平台运维
