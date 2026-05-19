# Ceph 集群 HEALTH_WARN 故障排查

## 概述
Ceph 集群健康为 HEALTH_WARN（或 HEALTH_ERR），可能影响 RBD/CephFS/对象存储的可用性与数据冗余。

## 常见原因
- OSD down/out，PG 处于 degraded/undersized
- OSD 磁盘接近满（nearfull/full ratio）
- PG 数量不合理或 PG 卡在 peering/incomplete
- MON 时钟漂移（clock skew）
- 慢请求（slow ops）/ OSD 心跳超时
- 网络分区影响 OSD 通信

## 排查步骤

### 1. 查看整体健康
```bash
ceph -s
ceph health detail
```

### 2. 检查 OSD 状态与容量
```bash
ceph osd tree
ceph osd df
```

### 3. 检查 PG 状态
```bash
ceph pg stat
ceph pg dump_stuck
```

### 4. 检查 MON 与慢请求
```bash
ceph mon stat
ceph daemon osd.<id> ops
```

## 解决方案

### 临时措施
- 拉起 down 的 OSD：`systemctl start ceph-osd@<id>`
- 磁盘将满时临时调高 nearfull 阈值并清理/迁移数据

### 长期修复
- 扩容 OSD / 平衡数据（balancer 模块）
- 合理设置 PG 数（pg_autoscaler）
- MON 节点启用 NTP 消除 clock skew
- 监控 OSD 容量水位与 slow ops 告警

## 相关告警
- CephClusterWarningState
- CephOSDDown / CephOSDNearFull

## 参考链接
- Ceph 官方文档: Troubleshooting
- 内部 Wiki: Ceph 存储运维
