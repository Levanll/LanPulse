# 交接文档（HANDOFF）

> 面向：接手 continua 开发的新会话
> 更新时间：2026-11-08
> 当前版本：LanPulse v1.2.0

---

## 一、这是什么

**LanPulse（澜脉冲）** —— Windows 桌面网络诊断与一键修复工具。

面向普通用户，不是技术员工具。核心主张：

- **先备份、后修改、可回滚**，禁止不可逆操作
- 系统级改动必须确认，不静默执行
- 不收集、不上传任何用户网络隐私数据，全本地运行

技术栈：Python 3.12 + PySide6 6.8 + PyInstaller 6.22（onedir）+ Inno Setup 6.7.3。

---

## 二、快速上手

```powershell
# 工作目录
cd D:\Documents\deepseek-harness\default-workspace\lanpulse

# 运行（开发模式）
$env:PYTHONPATH="."
.\.venv\Scripts\python.exe main.py

# 全量测试（136 项）
.\.venv\Scripts\python.exe -m pytest tests -q

# 发布前必跑：一致性检查
.\.venv\Scripts\python.exe tools\check_consistency.py

# i18n 完整性
.\.venv\Scripts\python.exe tools\audit_i18n.py

# 隐私核查（不得有本机敏感值命中）
.\.venv\Scripts\python.exe tools\privacy_audit.py

# 完整构建（PyInstaller + Inno Setup，产出 release\）
powershell -ExecutionPolicy Bypass -File scripts\build_installer.ps1 -Fresh
```

**环境事实**：
- Inno Setup 装在 `D:\Tools\InnoSetup6`（不占 C 盘）
- 构建脚本会自动探测 `D:/E:/F:\Tools\InnoSetup6`，必要时设 `$env:INNO_SETUP_HOME`
- 任何打印非 ASCII 的脚本必须先调用 `tools/_console.py` 的 `setup_console()`（CI runner 是 cp1252）
- `.ps1` 文件必须带 UTF-8 BOM，否则 PowerShell 5.1 按 GBK 解析中文而报错

---

## 三、架构

```
lanpulse/
├── main.py                    入口：单实例检查、提权检测、异常兜底
├── core/                      纯逻辑，不依赖 Qt
│   ├── branding.py            品牌与版本的唯一来源（改名只改这里）
│   ├── models.py              Severity / Metric / CheckResult / DiagnosticReport
│   ├── platform_win.py        netsh / ipconfig / reg / WMI 封装，控制台解码
│   ├── backup.py              BackupStore，所有写操作的唯一入口
│   ├── context.py             单次体检的只读快照
│   ├── registry.py            检测项注册与执行（run_check 统一包裹）
│   ├── scenarios.py           6 个场景定义
│   ├── rootcause.py           根因分析引擎（10 条规则）+ 健康分
│   ├── region.py              12 套区域探测剖面
│   ├── i18n.py / i18n_args.py 文案与占位符解析
│   ├── settings.py            设置持久化
│   ├── action_ids.py          15 个修复动作的元数据
│   ├── checks/                14 个检测单元（各自独立可测）
│   └── repair/                修复引擎 + 15 个原子动作 + 回滚
├── app/
│   ├── i18n_zh.py / i18n_en.py  1332 条文案，两语言 key 必须完全一致
│   ├── report.py              HTML / JSON / TXT 导出
│   └── ui/                    PySide6 界面（9 个页面）
├── tests/                     136 项
├── tools/                     开发与运维脚本
├── installer/                 Inno Setup 脚本与资源
└── docs/                      设计、使用、实测、对比分析
```

**四层数据流**：

```
checks（测量） → rootcause（解释） → repair（动作） → backup（兜底）
```

每层职责单一。检测项只负责产出 `CheckResult`，不判断根因；根因规则只读取 `CheckResult`，不发命令；修复动作只执行原子修改，备份由中间层强制拦截。

---

## 四、关键设计决策（改代码前必读）

### 1. 备份是唯一的写入口

`BackupStore.begin()` 必须先成功，否则整轮修复中止。这不是防御性代码，是产品承诺的实现方式。

**不要**为了"让流程继续"而在备份失败时降级。

### 2. `CheckResult` 存 i18n key 而非文案

`summary_key` + `summary_args`，UI 层才调用 `t()` 渲染。

原因：体检在后台线程执行，用户可能在体检过程中切换语言。若存的是渲染后文案，切换语言后结果会冻结在旧语言。

**不要**在检测项里直接写中文文案。

### 3. 场景只影响"跑哪些"，不影响"怎么判"

同一个检测项在任何场景下产出的数据必须完全一致。场景是过滤与排序，不是不同的判定逻辑。

### 4. 根因规则必须显式写出"已排除的可能"

`RootCause.excluded` 不是装饰。例如 DNS 慢，只有在链路与网关都正常时才能给出高置信度——否则 DNS 慢可能是结果而非原因。

**不要**因为"看起来像"就加规则。没有证据链的根因比没有根因更有害。

### 5. 测不准就报 SKIP，不要给虚假结论

缓冲膨胀最初在负载源不可达时仍输出"A 级"。已修复为报 SKIP 并说明原因。

同类问题的判断标准：**这个结论如果错了，用户会不会做出错误决策？** 会，就宁可报 SKIP。

### 6. 品牌名与版本号只从 `core/branding.py` 读

界面标题、报告页眉、安装包名、数据目录全部引用它。

---

## 五、当前状态

### 已完成

| 项 | 状态 |
|---|---|
| 14 项检测 | 全部实现并实测 |
| 6 个场景 | 已接入 UI，场景过滤生效 |
| 根因引擎（10 规则） | 已实现，29 项单元测试覆盖 |
| 15 个修复动作 | 已实现，9 个动作做过闭环实测 |
| 备份回滚 | 已实现，含 ADS 路径修复 |
| 跨区域自适应 | 12 套剖面已实现 |
| 中英双语 | 1377 条，key 集合完全一致 |
| 报告导出 | HTML / JSON / TXT |
| CI + Release 工作流 | 已配齐四道门禁，v1.2.0 起由 CI 强制 |
| GitHub 发布 | v1.1.0 已发布；v1.2.0 待发布 |

### 仓库

- 地址：https://github.com/Levanll/LanPulse
- 分支：`main`（历史已重写为干净起点）
- Release：`v1.1.0`，3 个资产（v1.2.0 发布后为最新）
- 数据目录：`%LOCALAPPDATA%\LanPulse`
- Packages：**有意保持为空**（本项目为 Windows exe，GitHub Packages 的五种 registry 均不匹配）

### 已知限制（诚实记录，不要当作已解决）

1. **语言切换不重译已生成的详情文案** —— 结论摘要会跟随，`detail` 字段不会。重新体检即可。
2. **区域自动识别是启发式的** —— 延迟打分只能判定「在不在中国大陆」（东亚各区互差十几毫秒、anycast 处处就近，光靠延迟分不出国家），具体区域靠时区与语言。跨国专线、海外 VPS 可能判错，设置页可手动固定。大陆、香港、澳门共用 `China Standard Time`，港澳完全依赖系统地区码判定。
3. **闭环实测覆盖 9/15 个动作** —— v1.1.0 验证了 `dns.set_public` / `dns.flush_cache`；v1.2.0 补测 `proxy.reset` / `firewall.ensure_enabled` / `tcp.autotuning` / `hosts.clean_bad_lines`，4/4 通过。仍未做真实闭环：`tcp.reset_stack`、`adapter.reset_stack`（需重启）、`mtu.optimize`、`adapter.renew_dhcp`（会断网）、`netbios.disable_public`（导入缺陷已修但未跑闭环）、`hosts.restore_default`、`proxy.restore_auto`、`firewall` 之外的其余项。
4. **回滚失败路径未测试** —— 代码有处理，但没有构造过"回滚中途失败"的场景。
5. **无代码签名** —— SmartScreen 会提示"未知发布者"。
6. **VPN 网卡不参与优化决策** —— 刻意为之，避免破坏既有 VPN 配置。

---

## 六、测试与验证

### 三层验证

| 层级 | 命令 | 说明 |
|---|---|---|
| 单元 | `pytest tests -q` | 136 项，<2 秒 |
| 一致性 | `tools/check_consistency.py` | 检测项数/版本/品牌/截图/i18n 交叉校验 |
| 端到端 | 构建 → 安装 → 启动 → 卸载 | 手动，见下 |

### 端到端检查清单

```powershell
# 1. 构建
powershell -ExecutionPolicy Bypass -File scripts\build_installer.ps1 -Fresh

# 2. 静默安装到临时目录
$tmp = "$env:TEMP\lp_test"
Start-Process release\LanPulse-1.2.0-Setup.exe `
  -ArgumentList "/VERYSILENT","/SUPPRESSMSGBOXES","/NORESTART","/DIR=`"$tmp`"" -Wait

# 3. 启动，确认无崩溃、窗口标题正确、数据目录写入 LanPulse
Start-Process "$tmp\LanPulse.exe"

# 4. 卸载
Start-Process "$tmp\unins000.exe" -ArgumentList "/VERYSILENT","/SUPPRESSMSGBOXES" -Wait
```

**验证要点**：数据目录应为 `%LOCALAPPDATA%\LanPulse`，且**不应**创建 `NetPulse` 目录。<!-- brand-ok -->

### 截图生成

```powershell
# 中英各一套，README.md 用 zh，README_EN.md 用 en
.\.venv\Scripts\python.exe tools\regen_screenshots.py --lang zh
.\.venv\Scripts\python.exe tools\regen_screenshots.py --lang en
.\.venv\Scripts\python.exe tools\make_hero.py     # 首图
```

截图用合成数据（`EXAMPLE-PC` / `192.0.2.42`，RFC 5737 保留段），**不含任何本机信息**。

---

## 七、踩过的坑（不要重犯）

### ADS 备份损坏（最严重）

Windows 注册表项的 `key` 含 `:`（如 `reg:tcpip`），作为文件名会变成 NTFS 数据流，创建出 0 字节的可见文件。结果：备份看起来成功，回滚 100% 失败。

**已在 `core/backup.py` 的 `safe_name()` 修复**，并加了回归测试。任何新的备份路径都必须走这个函数。

### PowerShell `Set-Content -Encoding utf8` 破坏中文

批量编辑中文文件时会写入 U+E0xx 私有区字符，不可逆。

**规则**：改文件用编辑工具，不要用 `Get-Content -Raw | Set-Content`。

### `shiboken6` 不能加进 PyInstaller EXCLUDES

加了之后窗口版 exe 崩溃，只报 "Unhandled exception in script"，无堆栈。

**已在 `build.spec` 注释说明原因**。

### `netsh` 参数非法时返回 0

不能只看退出码判断成功，还要检查输出文本。

### `tcp.heuristics` 在 Win10 1803+ 已移除

检测项现在会 `available()` 探测并跳过，不产生误报建议。

### CI 的 cp1252 编码

GitHub Actions Windows runner 默认 cp1252。打印中文的脚本必须 `setup_console()`。

### git push 会把凭据写进 `branch.main.remote`

不是常见的 `remote.origin.url`。推送后必须：

```powershell
git remote set-url origin https://github.com/Levanll/LanPulse.git
git config --local branch.main.remote origin
git config --local branch.main.merge refs/heads/main
```

并清理 Windows 凭据管理器中的 `git:https://github.com`。

---

## 八、开发约定

### 新增检测项

1. 在 `core/checks/` 建文件，实现 `check_id` / `title` / `category` / `run(ctx)`
2. `title` 与 `category` 存 i18n key，不存文案
3. 在 `core/registry.py` 的 `load_checks()` 注册
4. 若某场景需要它，加入 `core/scenarios.py`
5. 补 `app/i18n_zh.py` 与 `app/i18n_en.py`（key 必须两边都加）
6. 跑 `check_consistency.py`（会检查场景引用的 check_id 是否存在）

### 新增修复动作

1. 在 `core/repair/` 实现，登记到 `core/action_ids.py`
2. 动作必须先调 `BackupStore` 备份，再执行
3. 执行后要读回校验，不能假设命令成功
4. 实现回滚逻辑到 `core/repair/rollback.py`
5. 补 `action.<id>.title` 与 `.description` 文案

### 新增 i18n 文案

两语言必须同时加，且占位符集合一致。`audit_i18n.py` 会检查。

**缺失 key 时 `t()` 返回 `⟦key⟧`** —— 这是刻意的可见失败，不要改成静默回退。

### 提交前必跑

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe tools\check_consistency.py
.\.venv\Scripts\python.exe tools\audit_i18n.py
.\.venv\Scripts\python.exe tools\privacy_audit.py
```

---

## 九、可选的下一步

按价值排序，均未开始：

| 优先级 | 事项 | 说明 |
|---|---|---|
| 高 | 补齐修复动作的闭环实测 | 注册表 / 文件 / 网络配置类动作尚未真实验证 |
| 高 | 回滚失败路径测试 | 构造中途失败场景验证提示与恢复 |
| 中 | 语言切换重译 detail | 需把 detail 也改成 key + args |
| 中 | IPv6 完整诊断 | 目前只采集不诊断 |
| 中 | 代码签名 | SignPath Foundation 对 OSS 免费，但个人受限地区 |
| 低 | WiFi 信号与信道分析 | 需 `netsh wlan`，部分网卡不可用 |
| 低 | 打包为 MSIX | 走 Microsoft Store 可完全消除 SmartScreen 警告 |

**不建议做**：

- 盯障模式 / 抓包取证 —— 需 Npcap 驱动与管理员权限，与最小权限原则冲突
- 异常自动上报 —— 违反"零上传"承诺
- 强制填充 GitHub Packages —— 本项目形态不匹配

---

## 十、参考

- 设计与取舍：[docs/设计方案.md](docs/设计方案.md)
- 使用说明：[docs/使用说明.md](docs/使用说明.md)
- 闭环实测记录：[docs/闭环实测报告.md](docs/闭环实测报告.md)
- 与同类项目对比：[docs/对比分析与借鉴决策.md](docs/对比分析与借鉴决策.md)
- 变更历史：[CHANGELOG.md](CHANGELOG.md)

参考项目（借鉴设计思路，未复制代码）：https://github.com/silentcrow09/netpulse
