# NFS 挂载 Hang 住故障排查

## 概述
Pod 挂载 NFS 卷时卡住（ContainerCreating 长时间不动），或运行中 I/O hang，进程进入不可中断睡眠（D 状态）。

## 常见原因
- NFS 服务器不可达或宕机
- 网络抖动/防火墙拦截 NFS 端口（2049 等）
- NFS 版本不匹配（v3 vs v4，需 rpcbind/portmap）
- 使用 hard mount 且服务器无响应导致永久阻塞
- NFS 服务器导出（exports）权限/网段配置错误
- 服务器侧负载过高响应缓慢

## 排查步骤

### 1. 查看 Pod 事件
```bash
kubectl describe pod <pod-name> | grep -A10 Events
```

### 2. 节点上测试 NFS 连通
```bash
ssh <node> "showmount -e <nfs-server>"
ssh <node> "nc -zv <nfs-server> 2049"
```

### 3. 查看挂载与 hang 进程
```bash
ssh <node> "mount | grep nfs && cat /proc/<pid>/wchan"
ssh <node> "dmesg | grep -i nfs | tail"
```

## 解决方案

### 临时措施
- 强制卸载：`umount -f -l <mountpoint>` 后重新挂载
- 重建 Pod 让其调度到正常路径；必要时切换备用存储

### 长期修复
- 挂载参数评估 hard+intr / soft+timeo（权衡数据安全与可中断）
- NFS 服务器高可用 + 网络稳定性保障
- 监控 NFS 服务器延迟与节点 D 状态进程
- 关键负载迁移到更可靠的存储（如分布式块存储）

## 相关告警
- NFSServerUnreachable
- NodeUninterruptibleProcesses

## 参考链接
- Linux NFS 文档: Mount Options
- 内部 Wiki: NFS 存储运维
