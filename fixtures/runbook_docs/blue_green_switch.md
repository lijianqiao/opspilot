# 蓝绿部署流量切换操作手册

## 概述
蓝绿部署维护两套环境（blue=当前生产，green=新版本），验证 green 后一次性切换流量，问题时秒级切回。

## 常见原因
触发蓝绿切换的典型场景：
- 大版本升级，需完整环境验证
- 不支持渐进灰度的有状态变更
- 要求零停机且可快速回退
- 重大依赖/中间件升级

## 排查步骤

### 1. 确认 green 环境就绪
```bash
kubectl get pods -l app=<app>,version=green
kubectl rollout status deployment/<app>-green
```

### 2. 对 green 做冒烟验证
```bash
kubectl port-forward svc/<app>-green 8080:80
curl -s http://localhost:8080/healthz && curl -s http://localhost:8080/version
```

### 3. 切换 Service selector 到 green
```bash
kubectl patch svc <app> -p '{"spec":{"selector":{"app":"<app>","version":"green"}}}'
```

### 4. 切换后验证生产指标
```promql
sum(rate(http_requests_total{app="<app>",code=~"5.."}[2m]))
```

## 解决方案

### 临时措施
- 出现异常立即切回 blue：
```bash
kubectl patch svc <app> -p '{"spec":{"selector":{"app":"<app>","version":"blue"}}}'
```

### 长期修复
- 切换后观察期内保留 blue 环境随时回退
- 数据库变更保证蓝绿双版本兼容
- 用 Argo Rollouts blueGreen 策略管理 preview/active
- 切换前后自动化健康检查与指标门禁

## 相关告警
- BlueGreenSwitchErrorSpike
- ServiceSelectorMismatch

## 参考链接
- Argo Rollouts 官方文档: BlueGreen Strategy
- 内部 Wiki: 蓝绿发布规范
