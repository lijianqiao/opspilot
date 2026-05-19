# Node NotReady 故障排查

## 概述
节点状态为 NotReady 表示 kubelet 未能向 API Server 上报健康心跳，该节点上的 Pod 可能被驱逐或重新调度。

## 常见原因
- kubelet 进程崩溃或未运行
- 容器运行时（containerd/CRI-O）异常
- 节点磁盘满或内存耗尽
- 节点与 API Server 网络不通
- CNI 插件故障导致网络未就绪
- 节点证书过期

## 排查步骤

### 1. 查看节点状态与 Conditions
```bash
kubectl get nodes -o wide
kubectl describe node <node-name> | grep -A10 "Conditions"
```

### 2. 检查 kubelet 服务
```bash
ssh <node> "systemctl status kubelet --no-pager"
ssh <node> "journalctl -u kubelet --no-pager -n 100"
```

### 3. 检查容器运行时
```bash
ssh <node> "systemctl status containerd && crictl info"
```

### 4. 检查节点资源
```bash
ssh <node> "df -h && free -m"
```

## 解决方案

### 临时措施
- 重启 kubelet：`systemctl restart kubelet`
- 重启容器运行时：`systemctl restart containerd`
- cordon + drain 节点后维护

### 长期修复
- 配置节点监控（node-exporter）与磁盘/内存告警
- 自动轮换 kubelet 证书（rotateCertificates: true）
- 节点自愈：node-problem-detector + remediation 控制器

## 相关告警
- KubeNodeNotReady
- KubeletDown

## 参考链接
- Kubernetes 官方文档: Nodes
- 内部 Wiki: 节点故障自愈方案
