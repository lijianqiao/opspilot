# 镜像扫描发现高危漏洞故障处置

## 概述
镜像安全扫描（Trivy/Grype 等）报告 CRITICAL/HIGH 漏洞，需评估风险并修复，必要时阻断部署。

## 常见原因
- 基础镜像过旧，携带已知 CVE
- 应用依赖库版本存在漏洞
- 引入了带漏洞的系统包
- 使用了不再维护的镜像
- 镜像未定期重建（依赖未随安全补丁更新）

## 排查步骤

### 1. 扫描并查看漏洞详情
```bash
trivy image --severity CRITICAL,HIGH <image>:<tag>
trivy image --format json <image>:<tag> | jq '.Results[].Vulnerabilities[].VulnerabilityID'
```

### 2. 定位漏洞来源（OS 包 vs 应用依赖）
```bash
trivy image --vuln-type os,library <image>:<tag>
```

### 3. 评估可利用性
```bash
# 查看 CVE 详情、CVSS、是否有 EXPLOIT、是否在攻击面（对外暴露）
```

## 解决方案

### 临时措施
- 用准入策略（Kyverno/Gatekeeper）阻断含 CRITICAL 漏洞镜像部署
- 高危且已暴露：临时下线或加 WAF/网络隔离

### 长期修复
- 升级基础镜像到最新 patch（或换用 distroless/最小镜像）
- 升级存在漏洞的依赖库并重建推送
- CI 集成镜像扫描门禁（CRITICAL 阻断合并）
- 定期重建镜像吸收安全补丁，维护 SBOM

## 相关告警
- ImageCriticalVulnerability
- AdmissionImagePolicyBlocked

## 参考链接
- Trivy 官方文档: Vulnerability Scanning
- 内部 Wiki: 镜像安全治理
