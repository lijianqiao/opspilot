# Prometheus 磁盘使用率过高故障排查

## 概述
告警显示节点或 PV 磁盘使用率持续偏高，可能导致写入失败、Pod 驱逐或 Prometheus TSDB 损坏。

## 常见原因
- 应用日志/临时文件未清理
- Prometheus retention 设置过长，TSDB 膨胀
- 高基数指标导致样本量暴涨
- WAL/数据未压缩或 compaction 滞后
- 备份文件堆积在数据盘
- PV 容量规划不足

## 排查步骤

### 1. 查看磁盘使用
```promql
(1 - node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}) * 100
```

### 2. 定位大目录
```bash
ssh <node> "du -sh /var/lib/* /var/log/* 2>/dev/null | sort -h | tail"
```

### 3. 检查 Prometheus TSDB 大小与基数
```bash
kubectl exec <prom-pod> -- du -sh /prometheus
```
```promql
prometheus_tsdb_head_series
```

### 4. 检查 retention 配置
```bash
kubectl get prometheus -o yaml | grep -E "retention|retentionSize"
```

## 解决方案

### 临时措施
- 清理日志/旧备份释放空间
- 临时缩短 Prometheus retention 触发数据清理

### 长期修复
- 设置 `retentionSize` 上限并扩容 PV
- 接入远程存储（Thanos/Mimir）做长期存储
- 治理高基数指标，配置 relabel drop
- 配置磁盘水位（75%/85%）分级告警

## 相关告警
- NodeFilesystemSpaceFillingUp
- PrometheusTSDBReloadsFailing

## 参考链接
- Prometheus 官方文档: Storage
- 内部 Wiki: 监控存储容量规划
