# Loki 日志解析错误故障排查

## 概述
Loki 查询时出现 parse error 或 `__error__="JSONParserErr"`，导致结构化过滤失效，无法按字段检索。

## 常见原因
- 日志并非合法 JSON（混入非结构化前缀）
- 多行日志（堆栈）未正确合并
- LogQL parser 用错（json vs logfmt vs pattern）
- 时间戳格式与 timestamp stage 不匹配
- promtail/fluent-bit pipeline 配置错误
- 字段名含特殊字符导致 label 提取失败

## 排查步骤

### 1. 查看原始未解析日志
```logql
{app="<svc>"} | line_format "{{.__line__}}"
```

### 2. 检查解析错误标记
```logql
{app="<svc>"} | json | __error__ != ""
```

### 3. 切换合适的 parser
```logql
{app="<svc>"} | logfmt
{app="<svc>"} | pattern `<_> level=<level> msg=<msg>`
```

### 4. 检查采集 pipeline
```bash
kubectl -n logging get configmap promtail -o yaml | grep -A20 pipeline_stages
```

## 解决方案

### 临时措施
- 改用 pattern/regexp parser 适配当前格式
- 用 `| __error__=""` 过滤掉解析失败行

### 长期修复
- 应用统一输出单行 JSON 日志
- promtail 配置 multiline stage 合并堆栈
- 在采集端规范时间戳与字段名

## 相关告警
- LokiParseErrorRateHigh
- LogPipelineErrors

## 参考链接
- Grafana Loki 官方文档: LogQL Parsers
- 内部 Wiki: 日志规范与采集配置
