# 金丝雀部署中止故障排查

## 概述
金丝雀（canary）发布过程中新版本指标恶化（错误率/延迟上升），需立即中止并将流量切回稳定版本。

## 常见原因
- 新版本引入 bug 导致 5xx 升高
- 性能劣化（P99 延迟、CPU/内存上升）
- 依赖不兼容（DB schema、下游接口）
- 配置错误仅在生产流量下暴露
- 分析指标阈值设置不当触发误判

## 排查步骤

### 1. 查看 Rollout 状态
```bash
kubectl argo rollouts get rollout <rollout> --watch
```

### 2. 对比新旧版本指标
```promql
sum(rate(http_requests_total{app="<app>",version="canary",code=~"5.."}[5m]))
/ sum(rate(http_requests_total{app="<app>",version="canary"}[5m]))
```

### 3. 查看分析结果（AnalysisRun）
```bash
kubectl get analysisrun -l rollout=<rollout>
kubectl describe analysisrun <name>
```

## 解决方案

### 临时措施
- 立即中止金丝雀：
```bash
kubectl argo rollouts abort <rollout>
```
- 流量全部切回 stable，确认错误率恢复

### 长期修复
- 配置自动分析（success-rate/latency）+ 自动 abort/rollback
- 金丝雀比例从小步长开始（5% -> 25% -> 50%）
- 完善可观测性指标，预设明确 SLO 阈值
- 发布前做兼容性与回滚演练

## 相关告警
- CanaryErrorRateHigh
- RolloutAborted

## 参考链接
- Argo Rollouts 官方文档: Canary & Analysis
- 内部 Wiki: 渐进式交付规范
