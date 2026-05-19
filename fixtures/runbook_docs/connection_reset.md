# 连接被重置（Connection Reset by peer）故障排查

## 概述
客户端收到 RST，连接被强制中断，表现为偶发 5xx、读写报错 "connection reset by peer"。

## 常见原因
- 服务端连接池/线程池耗尽，主动拒绝
- idle/keepalive 超时不匹配（客户端复用了被服务端关闭的连接）
- 中间代理（envoy/nginx/LB）超时或主动断连
- 服务端 OOM/崩溃/重启导致连接中断
- backlog 队列满，SYN 被丢弃
- TLS 握手失败（协议/证书不匹配）

## 排查步骤

### 1. 定位发生位置（客户端/代理/服务端）
```bash
kubectl logs <client-pod> --tail=100 | grep -i "reset"
kubectl logs <proxy-pod> -c istio-proxy --tail=100 | grep -E "RST|UC|connection"
```

### 2. 抓包确认 RST 来源
```bash
ssh <node> "tcpdump -ni any 'tcp[tcpflags] & tcp-rst != 0' -c 50"
```

### 3. 检查服务端连接与队列
```bash
kubectl exec <server-pod> -- ss -s
ssh <node> "netstat -s | grep -E 'listen|overflow|reset'"
```

### 4. 核对超时配置
```bash
# 比对客户端连接池 idle timeout 与服务端/代理 keepalive timeout
```

## 解决方案

### 临时措施
- 客户端启用连接重试（幂等请求）与连接前探活
- 临时调大服务端连接数 / backlog

### 长期修复
- 统一客户端 idle 超时 < 服务端 keepalive 超时
- 服务端优雅关闭（drain 后再退出），扩容连接/线程池
- 调大 net.core.somaxconn 与应用 backlog
- 代理超时与后端能力对齐，开启重试

## 相关告警
- TCPResetRateHigh
- UpstreamConnectionErrors

## 参考链接
- Linux TCP 文档: Connection Tuning
- 内部 Wiki: 连接稳定性排查
