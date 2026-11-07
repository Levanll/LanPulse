# 更新日志

本文件格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [1.1.0] - 2026-11-08

### 重大变更

- **项目更名为 LanPulse**（原 NetPulse）。原名与 github.com/silentcrow09/netpulse
  重名，为避免混淆改名。**用户数据目录仍保留旧名** %LOCALAPPDATA%\\NetPulse，
  已有备份可继续还原，无需迁移。

### 新增

**场景化诊断（6 个场景）**

不再让用户面对“该测哪一项”的技术选择，而是选“我遇到什么情况”：

| 场景 | 适合 |
|---|---|
| 上网很慢 | 网页加载慢、下载慢、视频缓冲久 |
| 经常断网 | 偶尔掉线、需重启路由器 |
| 网页打不开 | 某些或全部网站无法访问 |
| 游戏 / 视频卡顿 | 网速够快但延迟高、会议卡 |
| 检查是否被劫持 | 怀疑网站被篡改、跳广告 |
| 完整体检 | 全部 14 项 |

**根因分析引擎（10 条规则）**

把 N 个检测项的证据合成 1-3 条可执行结论，每条带置信度、证据链与建议动作：

- DHCP 失败 / HOSTS 劫持 / DNS 污染 / 代理残留 / 网关质量差
- DNS 解析慢 / 网页分层断层 / MTU 不匹配 / 缓冲膨胀 / 防火墙关闭

规则明确写出“看到什么证据 → 判定为什么”，并给出“已排除的可能”，
避免臆造因果。未被规则覆盖的异常单独列出，不强行归因。

**新检测项（3 项，总计 14 项）**

- web_timing 网页分层计时：DNS / TCP / TLS / TTFB 四段独立测量，
  含证书有效期与重定向链。能回答“网页卡在哪一层”。
- dns_hijack DNS 篡改检测：向当前 DNS 与两个公共 DNS 分别查询同一域名，
  结果不一致即判定为劫持或污染。
- ufferbloat 缓冲膨胀评级：空闲 vs 下载负载下的延迟对比，A-F 分级。
  这是“网速够快但游戏卡”的典型原因，传统测速测不出来。

**健康分与等级**

扣分制评分（严重 -30 / 异常 -15 / 提示 -3 / 跳过不扣分），并给出 A-F 等级。

### 修复

- 缓冲膨胀最初用 TCP 握手测 RTT，实测样本在 0.3ms 与 26ms 间剧烈跳动
  （标准差 8.6ms），比要测的膨胀本身还大。改用 DNS 查询 RTT（标准差 2.1ms）。
- 缓冲膨胀在负载源不可达时会给出虚假的“A 级”。已改为：负载未真正建立时
  报 SKIP 并说明原因，绝不给假评级。
- UI 的检测项标题、指标名、动作标题、风险等级有多处未走 i18n，
  英文界面会显示 check.adapter.title、metric.link_speed 这类原始 key。
- 截图曾包含本机计算机名与内网 IP，已用合成数据（RFC 5737 保留段）重新生成。

### 移除

- 17 个一次性补丁脚本与开发期截图（已归档到 docs/images）

## [1.0.0] - 2026-11-07

首个正式版本。

### 新增

**检测引擎（11 项）**

- 网卡与链路状态：链路速率、适配器总数、虚拟网卡占比、APIPA 地址识别
- IP 地址配置：DHCP/静态判定、私有网段真实计算、网关同网段校验
- 默认网关与路由：多默认路由检测、网关 RTT 测量（ICMP 被禁时只给 INFO）
- DNS 服务器配置：24 个已知公共 DNS 归属识别、回环地址有效性校验
- 域名解析与响应速度：ctypes 调 `dnsapi!DnsQuery_W` 真实计时，四档分级
- HOSTS 文件：屏蔽型 / 劫持型风险分级、行级定位
- 系统代理设置：死端口代理检测（代理软件退出后残留导致完全无法上网）
- TCP/IP 协议栈参数：autotuning、heuristics、RSS 状态解析
- MTU 与分片：DF ping 二分实测路径 MTU，含丢包重试
- Windows 防火墙：三个 profile 状态聚合
- 外网连通性与延迟：IP 层 ping + TCP 443 握手 + 解析，三层定位

**修复引擎（15 个原子动作）**

- DNS：清空缓存 / 切换公共 DNS / 恢复 DHCP
- HOSTS：清理异常记录 / 恢复系统默认
- TCP/IP：恢复 autotuning / 关闭启发式 / 重置协议栈
- 代理：关闭残留代理 / 恢复自动检测
- 网卡：重新获取 IP / 重置 Winsock
- MTU 优化、防火墙重新启用、公网网卡禁用 NetBIOS

**安全机制**

- 备份与回滚中间层：任何修改前自动备份，备份失败则整轮不执行
- 备份为可读文件（`.reg` 可双击导入、`hosts.bak` 可直接复制），软件损坏也能手工还原
- 演练模式：完整走备份流程但不修改系统
- 逐条 `备份 → 执行 → 校验` 三阶段状态展示
- 操作审计流水（`audit.jsonl`），每次修改可追溯
- 高危动作默认不勾选，执行前二次确认

**跨区域自适应**

- 内置中国 / 国际 / 亚太三套区域剖面，各自独立的解析域名、连通性目标、MTU 目标、DNS 方案与判定阈值
- 自动识别：实测延迟打分 → 系统时区 → 系统语言，全本地完成
- 可在设置中手动固定区域
- 网络环境识别：强制门户（需网页登录）、VPN 活动、仅 IPv6、慢速网络

**国际化**

- 中文 / English 双语，设置内实时切换，无需重启
- 1199 条文案，两种语言 key 集合完全一致
- 检测结果记录 i18n key 与参数，切换语言后结论摘要随之更新

**界面**

- 8 个页面：总览 / DNS 优化 / HOSTS 管理 / 一键修复 / 备份与回滚 / 诊断详情 / 报告与日志 / 设置
- 自绘健康度环形仪表、严重度徽章、迷你折线图
- 深色科技感主题，高 DPI 适配

**分发**

- 安装包（Inno Setup，中英双语向导，支持用户级安装免管理员）
- 绿色压缩包（解压即用）
- 卸载时询问是否保留备份，默认保留

**报告**

- HTML（单文件、内联样式、含 CSP、无外部资源）/ JSON / TXT 三种格式
- 报告可安全分享：不含任何个人数据

### 修复

开发过程中实测发现并修复的缺陷（详见 `docs/设计方案.md` 第九节）：

- 备份文件名中的冒号被 NTFS 解释为交替数据流（ADS），导致备份"看起来成功"
  但回滚 100% 失败。改为 `safe_name()` 清洗文件名，并加回归测试
- 打包排除列表误删 `shiboken6.Shiboken`，导致窗口程序启动即崩且无 traceback
- `netsh` 参数非法时返回码仍为 0，把"什么都没做"记成"已应用"
- `tcp.heuristics` 在 Windows 10 1803 之后已废弃，检测侧不再建议该动作
- 回滚时非管理员被记为"失败"而非"权限不足"，误导用户以为备份损坏
- 中文 `netsh` 输出无冒号（`状态    关闭`），防火墙解析失败整项被吞
- 中文 `netsh` 用词与英文直译不同（"接收方缩放状态"/"窗口缩放启发"），RSS 恒显示未知
- MTU 实测因 ICMP 随机丢包误判上限，加单包重试后稳定
- 连通性单点抖动被误报为整体高延迟，改为"全部目标都慢才 WARN"
- 读取时区用了 `StandardName`，中文系统返回 `@tzres.dll,-572` 资源串，区域推断永远失败
- 检测在后台线程翻译文案，导致切换语言后旧结果停留在旧语言
- UI 与 core 各有一份 i18n 参数解析逻辑，分叉后界面出现未填充的 `{profiles}`
- `summary_ok` 模板含占位符却未传参数，界面显示 `{ip}/{prefix}`

### 已知限制

- 切换语言后，已完成体检的**详情文案**保持原语言（结论摘要会跟随）。重新体检即可
- 区域自动识别是启发式的，跨国专线/海外 VPS 等场景可能判错，可手动指定
- 闭环测试目前只覆盖 DNS 类动作（`dns.set_public` / `dns.flush_cache`）；
  注册表型、文件型、网络配置型动作尚未做真实闭环，建议按风险从低到高补测
- 未测「回滚本身失败」的兜底路径（如备份文件被外部删除或损坏）
- 未做代码签名，首次运行 SmartScreen 会提示未知发布者
- VPN 网卡不参与 DNS/MTU 优化决策（避免破坏既有配置）

---

## English Summary

**v1.0.0 — first stable release.**

- 11 diagnostic checks and 15 reversible repair actions
- Backup-first workflow: every mutation is snapshotted, verified, and restorable
  from plain files even if the app itself is broken
- Dry-run mode, per-action `backup → apply → verify` status, and an audit log
- Region-aware: separate CN / Global / APAC probe sets and thresholds, detected
  locally (latency scoring → timezone → system locale), overridable in Settings
- Chinese / English UI with in-place language switching (1199 strings)
- Dual distribution: Inno Setup installer and portable zip
- Report export as self-contained HTML / JSON / TXT

13 real defects were found and fixed during development, including an NTFS
alternate-data-stream bug that made backups appear successful while making
restore impossible. See `docs/设计方案.md` section 9.

[1.0.0]: https://github.com/<owner>/LanPulse/releases/tag/v1.0.0
