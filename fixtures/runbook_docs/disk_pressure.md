# 节点 DiskPressure 故障排查

## 概述
DiskPressure 表示节点根文件系统或镜像文件系统的可用空间/inode 低于 kubelet eviction 阈值，会触发 Pod 驱逐并阻止新 Pod 调度。

## 常见原因
- 容器日志未轮转，写满 /var/log
- 镜像缓存堆积占满 imagefs
- emptyDir / 临时文件写满 nodefs
- 应用持续写大文件未清理
- inode 耗尽（大量小文件）

## 排查步骤

### 1. 确认 DiskPressure 状态
```bash
kubectl describe node <node-name> | grep -A2 DiskPressure
```

### 2. 检查磁盘与 inode 使用
```bash
ssh <node> "df -h && df -i"
ssh <node> "du -sh /var/lib/containerd /var/log/* 2>/dev/null | sort -h"
```

### 3. 查看 kubelet eviction 阈值
```bash
ssh <node> "cat /var/lib/kubelet/config.yaml | grep -A6 evictionHard"
```

## 解决方案

### 临时措施
- 清理无用镜像：`crictl rmi --prune`
- 清理已退出容器：`crictl rm $(crictl ps -a -q --state Exited)`
- 轮转/截断超大日志文件

### 长期修复
- 配置容器日志轮转（containerd `max_size`/`max_file`）
- 给 emptyDir 设置 sizeLimit
- 监控磁盘使用率并在 80% 提前告警
- 节点磁盘扩容或独立挂载 imagefs

## 相关告警
- NodeDiskPressure
- NodeFilesystemAlmostOutOfSpace

## 参考链接
- Kubernetes 官方文档: Node-pressure Eviction
- 内部 Wiki: 磁盘容量管理规范
