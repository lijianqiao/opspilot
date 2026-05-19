# Loki 日志查询指南

## 概述
本指南介绍使用 LogQL 在 Grafana / logcli 中高效查询 Loki 日志，用于线上问题定位。

## 常见原因
排查问题前需明确日志检索范围与维度：
- 不清楚服务对应的 label（app/namespace/pod）
- 时间范围过大导致查询超时
- 高基数 label 拖慢查询
- 日志为非结构化文本，未做 parser

## 排查步骤

### 1. 列出可用 label
```bash
logcli labels
logcli labels app
```

### 2. 按标签筛选基础查询
```logql
{namespace="prod", app="order-service"} |= "error"
```

### 3. 结构化解析与过滤
```logql
{app="order-service"} | json | level="error" | line_format "{{.msg}}"
```

### 4. 统计错误速率
```logql
sum(rate({app="order-service"} |= "ERROR" [5m])) by (pod)
```

### 5. 使用 logcli 拉取
```bash
logcli query '{app="order-service"} |= "timeout"' --since=1h --limit=200
```

## 解决方案

### 临时措施
- 缩小时间范围（--since=15m）并加 label 过滤降低扫描量
- 用 `|=` 行过滤而非正则提高速度

### 长期修复
- 应用统一输出 JSON 日志，便于 `| json` 解析
- 控制 label 基数（不要把 request_id 设为 label）
- 配置 Loki retention 与 split_queries_by_interval

## 相关告警
- LokiRequestLatencyHigh
- LogIngestionRateAbnormal

## 参考链接
- Grafana Loki 官方文档: LogQL
- 内部 Wiki: 日志查询速查表
