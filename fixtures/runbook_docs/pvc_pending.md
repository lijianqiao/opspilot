# PVC Pending 故障排查

## 概述
PersistentVolumeClaim 长时间 Pending，意味着没有可绑定的 PV，依赖该 PVC 的 Pod 也会卡在 Pending。

## 常见原因
- StorageClass 不存在或名称写错
- 动态供应失败（CSI driver 异常）
- 静态 PV 容量/访问模式与 PVC 不匹配
- volumeBindingMode=WaitForFirstConsumer，但 Pod 未调度
- 底层存储配额耗尽
- 可用区与节点不匹配（拓扑约束）

## 排查步骤

### 1. 查看 PVC 事件
```bash
kubectl describe pvc <pvc-name> | grep -A10 Events
```

### 2. 检查 StorageClass
```bash
kubectl get storageclass
kubectl get pvc <pvc-name> -o jsonpath='{.spec.storageClassName}'
```

### 3. 检查 CSI driver / provisioner
```bash
kubectl get pods -n kube-system | grep csi
kubectl logs -n kube-system <csi-provisioner-pod> --tail=80
```

### 4. 核对访问模式与容量
```bash
kubectl get pv
kubectl get pvc <pvc-name> -o jsonpath='{.spec.accessModes} {.spec.resources.requests.storage}'
```

## 解决方案

### 临时措施
- 指定正确的 StorageClass 重建 PVC
- 手动创建匹配的 PV（静态供应场景）

### 长期修复
- 设置默认 StorageClass
- 监控 CSI driver 健康并配置告警
- 规划存储配额与容量水位

## 相关告警
- PersistentVolumeClaimPending
- CSIProvisionerErrors

## 参考链接
- Kubernetes 官方文档: Persistent Volumes
- 内部 Wiki: 存储供应排障
