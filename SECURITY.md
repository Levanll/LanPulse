# 安全策略 / Security Policy

## LanPulse 是一个会修改系统网络配置的工具

它通过 `netsh`、`reg`、`wininet` 等原生接口直接改写以下内容：

- 网络适配器的 DNS 服务器
- `C:\Windows\System32\drivers\etc\hosts`
- TCP/IP 协议栈参数（autotuning、heuristics）
- WinINET 系统代理设置
- 网卡 MTU 与 NetBIOS 选项
- Windows 防火墙 profile 开关

**这类软件的缺陷不止是"功能不正常"，而是可能让用户断网、丢失自定义配置，
或者在被利用时掩盖恶意改动。** 因此安全问题的处理优先级高于一切功能需求。

---

## 报告安全漏洞

**请不要在公开 Issue 里披露安全问题。**

请通过以下任一渠道私下联系维护者：

1. GitHub 的 [Private vulnerability reporting](../../security/advisories/new)
   （仓库 Settings → Security → Advisories，推荐）
2. 邮件：在仓库主页的维护者资料里查找联系方式

请在报告中包含：

- 受影响的版本（`LanPulse.exe` 属性里的版本号）
- 复现步骤
- 影响面（能否导致断网 / 权限提升 / 配置丢失 / 静默失败）
- 是否在你自己的机器上验证过

**我们承诺：**

| 阶段 | 时限 |
|---|---|
| 确认收到 | 72 小时内 |
| 初步评估（是否成立、严重程度） | 7 天内 |
| 修复或缓解方案 | 严重问题 30 天内 |

修复发布后，会在 Release Notes 里致谢（除非你要求匿名）。

---

## 支持版本

| 版本 | 安全更新 |
|---|---|
| 1.0.x | ✅ 支持 |
| < 1.0 | ❌ 不支持（预发布版本） |

---

## 我们如何保证安全（设计层面）

如果你要审计代码，重点看这几处：

### 1. 唯一的写系统入口

所有系统修改都必须经过 `core/backup.py` 的备份流程。
`core/repair/` 里的每个动作都实现了 `backup()` → `apply()` → `verify()`，
`engine.execute()` 保证**任一动作备份失败则整轮不执行**。

审查要点：是否存在绕过 `BackupStore` 直接写注册表/文件的代码路径。

### 2. 备份的完整性

- 备份内容是"恢复所需的全部状态"，不是差异
- `manifest.json` 记录每个文件的 sha256，回滚前比对，不一致则拒绝覆盖
- 备份是普通文件（`.reg` 可双击导入、`hosts.bak` 可直接复制），
  **软件本身损坏也不影响手工还原**

> 已知历史缺陷：早期版本把 `reg:tcpip.reg` 这样的 key 直接拼成文件名，
> Windows 会把冒号解释为 NTFS 交替数据流（ADS），导致备份"看起来成功"
> 但 `reg import` 读不到，回滚 100% 失败。已修复（`BackupStore.safe_name`），
> 并有回归测试锁定。审计时可重点检查文件名构造。

### 3. 不联网

代码里**没有任何上传逻辑**。运行时的网络请求只有：

- DNS 查询（测解析耗时）
- ICMP ping（测连通性）
- TCP 443 握手（测应用层可达性）
- 一次 HTTP GET 到 `connectivitycheck.gstatic.com/generate_204`
  （仅用于识别"酒店/机场需要网页登录"的强制门户）

全部不带本机身份信息。可在设置里关闭联网探测，此时只读本机配置。

### 4. 提权最小化

- 体检、报告导出、备份查看**不需要管理员权限**
- 需要提权的动作在 UI 上先拦截并提示，不会"点了没反应"
- 回滚时非管理员对注册表类项目标 `SKIPPED`（权限不足）而非 `FAILED`，
  避免用户误以为备份损坏

### 5. 命令返回码不可信

`netsh` 在参数非法时**返回码仍是 0**，只在输出文本里报错。
所有 netsh 调用都同时检查返回码与文本，否则会把"什么都没做"记成"已应用"。

---

## 不在范围内

以下**不视为**安全漏洞：

- 用户手动把自己的 HOSTS 改坏
- 用户选择了不合适的 DNS 导致访问变慢
- SmartScreen 提示"未知发布者"（本项目未购买代码签名证书）
- 卸载后 `%LOCALAPPDATA%\LanPulse\backups` 仍保留（这是**有意为之**，
  备份不应因为卸载而丢失）

---

# English

## LanPulse modifies real system network settings

It writes DNS servers, `hosts`, TCP/IP stack parameters, the WinINET proxy,
interface MTU, NetBIOS options and firewall profile states through native
Windows interfaces. A defect here is not just "a broken feature" — it can take
a user offline, destroy custom configuration, or mask malicious changes.

**Please do not disclose security issues in public Issues.**

Use GitHub's private vulnerability reporting (Settings → Security → Advisories)
or contact the maintainer privately.

**Timeline:** acknowledgement within 72 hours, initial assessment within 7 days,
fix or mitigation within 30 days for severe issues.

**Supported versions:** 1.0.x only.

**Where to look when auditing:**

1. `core/backup.py` is the single entry point for system writes. Verify nothing
   bypasses `BackupStore`.
2. Backups record sha256 per file and refuse to restore on mismatch. They are
   plain files (`.reg`, `hosts.bak`) restorable without the app.
3. No upload logic exists. Runtime network traffic is limited to DNS lookups,
   ICMP pings, TCP 443 handshakes, and one HTTP GET to detect captive portals.
4. Privilege is minimized; elevation-requiring actions are gated in the UI.
5. `netsh` returns 0 even on invalid arguments — we check output text as well.

**Out of scope:** user-broken HOSTS files, slower DNS chosen by the user,
SmartScreen "unknown publisher" warnings (no code signing certificate), and
backups surviving uninstall (intentional).
