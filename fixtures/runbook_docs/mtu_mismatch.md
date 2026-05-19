# MTU 不匹配导致网络异常故障排查

## 概述
MTU 配置不一致会导致大包被丢弃或分片，表现为小请求正常、大响应/大文件传输 hang 或 TLS 握手失败。

## 常见原因
- CNI overlay（VXLAN/IPIP）封装开销未从 MTU 扣除
- 节点网卡 MTU 与云网络/隧道 MTU 不一致
- Path MTU Discovery 失效（ICMP 被防火墙丢弃）
- Jumbo frame 仅部分链路启用
- 跨集群/VPN 链路 MTU 更小

## 排查步骤

### 1. 查看各层 MTU
```bash
ssh <node> "ip link show | grep -E 'eth0|vxlan|cni|tunl'"
kubectl exec <pod> -- ip link show eth0
```

### 2. 用不分片大包探测真实 MTU
```bash
kubectl exec <pod> -- ping -M do -s 1472 -c2 <dst-ip>   # 逐步减小直到不丢
ssh <node> "tracepath <dst-ip>"
```

### 3. 抓包确认分片/丢弃
```bash
ssh <node> "tcpdump -ni eth0 'icmp or (tcp port 443)' -c 50"
```

## 解决方案

### 临时措施
- 临时调小 Pod/CNI MTU 规避丢包
- 在受影响链路启用 TCP MSS clamping

### 长期修复
- CNI 配置正确 MTU（物理 MTU 减去封装开销，如 VXLAN -50）
- 全链路 MTU 统一规划（节点、隧道、云网络一致）
- 防火墙放行必要 ICMP（Fragmentation Needed）以支持 PMTUD
- 变更网络后回归大包传输测试

## 相关告警
- NetworkPacketDropHigh
- TCPRetransmitRateHigh

## 参考链接
- Kubernetes 网络文档: Cluster Networking / MTU
- 内部 Wiki: 网络 MTU 规划
