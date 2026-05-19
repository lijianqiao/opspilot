# 节点 NetworkUnavailable 故障排查

## 概述
NetworkUnavailable 表示节点网络（通常是 Pod 网络/CNI）未正确配置，节点无法承载需要网络的 Pod。

## 常见原因
- CNI 插件（Calico/Cilium/Flannel）未安装或 DaemonSet 异常
- 节点路由表 / VXLAN 隧道未建立
- 云厂商路由（route table）未同步
- CNI 配置文件缺失（/etc/cni/net.d 为空）
- 节点防火墙拦截了 overlay 流量

## 排查步骤

### 1. 查看节点 NetworkUnavailable Condition
```bash
kubectl describe node <node-name> | grep -A2 NetworkUnavailable
```

### 2. 检查 CNI DaemonSet 状态
```bash
kubectl -n kube-system get pods -o wide | grep -E "calico|cilium|flannel"
```

### 3. 检查节点 CNI 配置与路由
```bash
ssh <node> "ls -l /etc/cni/net.d/ && ip route && ip link show type vxlan"
```

### 4. 测试跨节点 Pod 连通性
```bash
kubectl run nettest --image=busybox -it --rm -- ping -c3 <other-pod-ip>
```

## 解决方案

### 临时措施
- 重启节点上的 CNI Pod（删除让 DaemonSet 重建）
- 重启 kubelet 触发网络重新初始化

### 长期修复
- 修复 CNI 配置 / 升级 CNI 版本
- 校验云厂商路由同步组件（如 Calico route reflector）
- 放行节点间 overlay 端口（如 VXLAN 4789/UDP）

## 相关告警
- KubeNodeNetworkUnavailable
- CNIPluginNotReady

## 参考链接
- Kubernetes 官方文档: Network Plugins
- 内部 Wiki: CNI 运维手册
