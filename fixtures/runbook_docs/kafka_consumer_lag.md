# Kafka 消费者滞后（Lag）故障排查

## 概述
消费者组 lag 持续增大，表示消费速度跟不上生产速度，导致数据处理延迟、下游数据陈旧。

## 常见原因
- 消费者数量少于分区数，并行度不足
- 单条消息处理逻辑慢（同步外部调用、DB 慢）
- 消费者频繁 rebalance（心跳超时、处理超 max.poll.interval）
- 生产突增（流量峰值、补数任务）
- 消费者异常退出导致分区无人消费
- 分区数据倾斜

## 排查步骤

### 1. 查看消费组 lag
```bash
kafka-consumer-groups.sh --bootstrap-server <broker> \
  --describe --group <group-id>
```

### 2. 检查分区与消费者数量
```bash
kafka-topics.sh --bootstrap-server <broker> --describe --topic <topic>
```

### 3. 查看 rebalance 与处理耗时
```bash
kubectl logs <consumer-pod> --tail=200 | grep -E "Rebalance|poll|commit"
```

### 4. 监控消费速率
```promql
sum(rate(kafka_consumergroup_current_offset[5m])) by (consumergroup)
```

## 解决方案

### 临时措施
- 扩容消费者实例（不超过分区数）
- 暂停非关键生产 / 限流补数任务

### 长期修复
- 增加分区数提升并行度（注意 key 分布）
- 消费逻辑异步化、批量化、幂等化
- 调大 max.poll.interval.ms / 减小 max.poll.records，减少 rebalance
- 处理数据倾斜（优化分区 key）

## 相关告警
- KafkaConsumerGroupLagHigh
- KafkaConsumerRebalanceFrequent

## 参考链接
- Apache Kafka 官方文档: Consumer Groups
- 内部 Wiki: Kafka 消费优化
