# Elasticsearch 集群状态变红故障排查

## 概述
Elasticsearch 集群健康为 red，表示至少有一个主分片不可用，部分索引读写受影响，存在数据丢失风险。

## 常见原因
- 节点离线导致主分片丢失
- 磁盘使用超过 flood_stage 水位，索引被置为只读
- 未分配分片（unassigned shards）无法恢复
- 分片数超过节点承载或副本无法分配
- 集群脑裂 / master 选举异常
- JVM heap 压力大导致节点频繁掉线

## 排查步骤

### 1. 查看集群健康与原因
```bash
curl -s localhost:9200/_cluster/health?pretty
curl -s "localhost:9200/_cluster/allocation/explain?pretty"
```

### 2. 找未分配分片
```bash
curl -s "localhost:9200/_cat/shards?v" | grep UNASSIGNED
```

### 3. 检查节点与磁盘水位
```bash
curl -s "localhost:9200/_cat/nodes?v&h=name,heap.percent,disk.used_percent"
curl -s "localhost:9200/_cat/allocation?v"
```

### 4. 检查 settings
```bash
curl -s localhost:9200/_cluster/settings?pretty
```

## 解决方案

### 临时措施
- 清理磁盘并解除只读：
```bash
curl -XPUT "localhost:9200/_all/_settings" -H 'Content-Type: application/json' \
  -d '{"index.blocks.read_only_allow_delete": null}'
```
- 拉起离线节点，触发分片恢复

### 长期修复
- 监控磁盘水位（low/high/flood_stage）并提前扩容
- 合理规划分片数与副本数（分片不宜过大过多）
- JVM heap 不超过 32G，配置节点反亲和

## 相关告警
- ElasticsearchClusterRed
- ElasticsearchDiskWatermarkReached

## 参考链接
- Elasticsearch 官方文档: Cluster Health & Allocation
- 内部 Wiki: ES 集群运维
