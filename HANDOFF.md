# 交接文档（HANDOFF）

> 面向：接手继续开发的新会话
> 更新时间：2026-11-11
> 当前版本：LanPulse v1.2.2（已发布）
> 仓库：https://github.com/Levanll/LanPulse
> 工作目录：`D:\Documents\deepseek-harness\default-workspace\lanpulse`

---

## 一、这是什么

**LanPulse（澜脉冲）** —— Windows 桌面网络诊断与一键修复工具。

面向普通用户，不是技术员工具。三条不可违背的硬约束：

- **先备份、后修改、可回滚**，禁止不可逆操作
- **系统级改动必须确认**，不静默执行
- **不收集、不上传任何用户网络隐私数据**，全本地运行

技术栈：Python 3.12 + PySide6 6.8 + PyInstaller 6.22（onedir）+ Inno Setup 6.7.3。

**规模**：14 项检测 / 6 个场景 / 10 条根因规则 / 15 个可回滚修复动作 / 12 套区域剖面 / 9 个界面页面 / 1401 条双语文案 / 162 项测试。

---

## 二、快速上手

```powershell
# 工作目录
cd D:\Documents\deepseek-harness\default-workspace\lanpulse

# 运行（开发模式）
$env:PYTHONPATH="."
.\.venv\Scripts\python.exe main.py

# 全量测试（162 项，约 1.5 秒）
.\.venv\Scripts\python.exe -m pytest tests -q

# 提交前必跑的四道门禁（全部必须 exit=0）
.\.venv\Scripts\python.exe tools\check_consistency.py    # 12 节交叉校验
.\.venv\Scripts\python.exe tools\audit_i18n.py
.\.venv\Scripts\python.exe tools\privacy_audit.py

# 站点自检（改了 site/ 或发版后必跑）
.\.venv\Scripts\python.exe tools\sync_site_assets.py   # 先同步截图
.\.venv\Scripts\python.exe tools\check_site.py

# 完整构建（PyInstaller + Inno Setup，产出 release\）
powershell -ExecutionPolicy Bypass -File scripts\build_installer.ps1 -Fresh
```

**发版流程（v1.2.2 起按这个顺序）**：

1. 改版本号 → 构建 → 跑四道门禁（版本号改了必须过 [2] 与 [8] 节）
2. commit + **push main**；再打 tag 并 push
3. **用本地产物手工建 Release**，上传 `release\` 下的三个文件
   （`release.yml` 已是手动触发，推 tag 不再自动跑，见第七节）
4. 跑 `tools\update_release_bodies.py` 把 body 换成中英对照的
   `docs/release-notes/<tag>.merged.md`（CI 建 Release 时 body 是整份 CHANGELOG）
5. Pages 由 `pages.yml` 在推送 `site/**` 后自动部署，发完必须验证线上版本号

**环境事实**：

- Inno Setup 装在 `D:\Tools\InnoSetup6`（不占 C 盘）
- 构建脚本会自动探测 `D:/E:/F:\Tools\InnoSetup6`，必要时设 `$env:INNO_SETUP_HOME`
- 任何打印非 ASCII 的脚本必须先调 `tools/_console.py` 的 `setup_console()`（CI runner 是 cp1252）
- `.ps1` 文件必须带 UTF-8 BOM，否则 PowerShell 5.1 按 GBK 解析中文而报错
- 本机是 Windows PowerShell **5.1**，没有 `pwsh`。`Get-Content -NoNewline`、`Join-String`、
  `ConvertTo-Json` 的中文编码等都和 pwsh 7 不同 —— 发 HTTP 请求时要手动
  `[System.Text.Encoding]::UTF8.GetBytes(...)`，否则中文描述会 400

---

## 三、架构

```
lanpulse/
├── main.py                    入口：单实例检查、提权检测、异常兜底
├── core/                      纯逻辑，不依赖 Qt
│   ├── branding.py            品牌/版本/窗口标题的唯一来源（改名只改这里）
│   ├── models.py              Severity / Metric / CheckResult / DiagnosticReport
│   ├── platform_win.py        netsh / ipconfig / reg / WMI 封装，控制台解码
│   ├── backup.py              BackupStore，所有写操作的唯一入口
│   ├── context.py             单次体检的只读快照（含区域识别缓存）
│   ├── registry.py            检测项注册与执行（run_check 统一包裹）
│   ├── scenarios.py           6 个场景定义
│   ├── rootcause.py           根因分析引擎（10 条规则）+ 健康分
│   ├── region.py              12 套区域探测剖面
│   ├── i18n.py / i18n_args.py 文案与占位符解析
│   ├── settings.py            设置持久化
│   ├── update.py              更新检测（可选、默认关闭、失败静默）
│   ├── action_ids.py          15 个动作的元数据（含 needs_restart）
│   ├── checks/                14 个检测单元（各自独立可测）
│   └── repair/                修复引擎 + 15 个原子动作 + 回滚分派
├── app/
│   ├── i18n_zh.py / i18n_en.py 1401 条文案，两语言 key 必须完全一致
│   ├── sysutil.py             提权 / 单实例 / 环境自检
│   ├── report.py              HTML / JSON / TXT 导出
│   └── ui/                    PySide6 界面（9 个页面）
├── tests/                     162 项
├── tools/                     开发与运维脚本（见第八节）
├── installer/                 Inno Setup 脚本与资源
├── site/                      落地页（GitHub Pages 的发布源，自包含）
└── docs/                      设计、使用、实测、对比分析
```

**四层数据流**：

```
checks（测量） → rootcause（解释） → repair（动作） → backup（兜底）
```

每层职责单一。检测项只负责产出 `CheckResult`，不判断根因；根因规则只读取
`CheckResult`，不发命令；修复动作只执行原子修改，备份由中间层强制拦截。

---

## 四、关键设计决策（改代码前必读）

### 1. 备份是唯一的写入口

`BackupStore.begin()` 必须先成功，否则整轮修复中止。这不是防御性代码，
是产品承诺的实现方式。

**不要**为了"让流程继续"而在备份失败时降级。

### 2. `CheckResult` 存 i18n key 而非文案

`summary_key` + `summary_args`，UI 层才调用 `t()` 渲染。原因是体检在后台线程执行，
用户可能在体检过程中切换语言；存渲染后文案会让结果冻结在旧语言。

**不要**在检测项里直接写死中文文案。

### 3. 场景只影响「跑哪些」，不影响「怎么判」

同一个检测项在任何场景下产出的数据必须完全一致。场景是过滤与排序，
不是不同的判定逻辑。

### 4. 根因规则必须显式写出「已排除的可能」

`RootCause.excluded` 不是装饰。例如 DNS 慢，只有在链路与网关都正常时才能给出
高置信度——否则 DNS 慢可能是结果而非原因。

**不要**因为"看起来像"就加规则。没有证据链的根因比没有根因更有害。

### 5. 测不准就报 SKIP，不要给虚假结论

判断标准：**这个结论如果错了，用户会不会做出错误决策？** 会，就宁可报 SKIP。

### 6. 品牌名、版本号、窗口标题只从 `core/branding.py` 读

`app/sysutil.py` 曾硬编码 `WINDOW_TITLE`（旧标语），而单实例检测正是按这个常量
找窗口——标题对不上就会静默多开。现已改为转发 branding，并在
`check_consistency.py` 里加了强制校验。

**不要**在别处重新定义 `WINDOW_TITLE` 或 `app.version` 这类文案。

### 7. 区域剖面：探测集与判定逻辑分离

判定阈值是通用的（延迟分档、丢包率），只有「往哪里打」是地域相关的，全部收敛
在 `core/region.py`。

**延迟打分只能判定「在不在中国大陆」**。东亚各区彼此只差十几毫秒，全球 anycast
又处处就近，光靠延迟分不出具体国家——具体区域靠时区键，最后兜底是系统语言。

### 8. 「不可完全回滚」的动作必须把边界摆到界面上

`tcp.reset_stack` / `adapter.reset_stack` 重启前无法观测效果，且**回滚只在重启前
有效**（重启后协议栈已按新状态重建，导回旧注册表撤销不了）。

这类边界写在代码注释里等于没写。`ActionMeta.needs_restart=True` 会让修复页显示
红色警告。新增同类动作时必须设这个标志。

---

### 9. 更新检测：默认关闭，只读版本号文件

这是唯一一个"用户能感知到软件在往外发东西"的功能，因此有三条硬约束：

**默认关闭 + 首次询问**。产品的对外承诺是零上传，开启联网查版本必须由用户
知情同意。问一次，选了就记住，不再重复骚扰（`update_prompt_seen`）。

**请求形态被测试锁死**。只有 `GET https://levanll.github.io/LanPulse/latest.json`，
请求头仅 `User-Agent: LanPulse/<版本号>` 与 `Accept`。不含账号、设备标识、
安装 ID、主机名、用户名。`TestUpdatePrivacyBoundary` 会断言这些字段不出现。

**失败必须静默**。这是网络诊断工具，它自己联网失败时弹错误框是荒谬的。
`check_for_update()` 不抛异常，超时/404/JSON 坏一律返回 `None`。

**不做自动升级**。只提示 + 打开浏览器。当前无代码签名，静默替换可执行文件
等于给用户装一个来路不明的程序。

另外两条连带约束：

- **必须复用 `allow_network_probe`**：用户关掉联网探测后，更新检查也得停。
  这是同一条隐私边界，不能因为是另一个功能就绕开。
- **`site/latest.json` 与 `branding.VERSION` 必须同步**：门禁第 [11] 节校验。
  发版时忘了更新清单，用户会永远收到指向旧版的"有新版本"提示，且不报错。

## 五、当前状态

### 已完成

| 项 | 状态 |
|---|---|
| 14 项检测 | 全部实现并实测 |
| 6 个场景 | 已接入 UI，场景过滤生效 |
| 根因引擎（10 规则） | 已实现，单元测试覆盖 |
| 15 个修复动作 | 已实现，**8 个**做过真实闭环 |
| 备份回滚 | 已实现，含 ADS 路径修复 |
| 跨区域自适应 | 12 套剖面，设置页显示识别依据 |
| 中英双语 | 1401 条，key 集合完全一致 |
| 报告导出 | HTML / JSON / TXT |
| CI + Release 工作流 | 四道门禁已强制，失败即阻断发布 |
| GitHub 发布 | v1.1.0 / v1.2.0 / v1.2.1 / v1.2.2 均已发布 |

### 仓库

- 地址：https://github.com/Levanll/LanPulse
- 分支：`main`（历史已重写为干净起点）
- 最新 Release：`v1.2.2`，3 个资产（Setup.exe / portable.zip / SHA256SUMS.txt）
- 数据目录：`%LOCALAPPDATA%\LanPulse`
- Packages：**有意保持为空**（本项目为 Windows exe，GitHub Packages 的 registry 均不匹配）
- 落地页：https://levanll.github.io/LanPulse/ （源在 `site/`，双语互链）

### ✅ 本地与远端已完全同步

```powershell
git fetch origin
git rev-list --count origin/main..HEAD   # 必须为 0
git ls-remote origin refs/heads/main     # 与本地 HEAD 一致
```

**以 `git ls-remote` 为准**，不要只看 `git rev-list`：本地 `origin/main` 跟踪引用可能过时，
造成"有待推送提交"的假象（曾因此误判过 3 个提交）。

### Release 说明：中英对照，源稿在仓库里

三个 Release 的 body 都是「先中文 → `---` 分隔 → 再英文」，与仓库 About 的格式一致。

**源稿在 `docs/release-notes/`**，每个版本三份：

```
docs/release-notes/
├── v1.2.2.md           中文
├── v1.2.2.en.md        英文
└── v1.2.2.merged.md    合并稿（实际推送到 GitHub 的内容）
```

改发布说明**不要**去网页上直接编辑，改源稿再重推：

```powershell
# 改完 .md / .en.md 后
.\.venv\Scripts\python.exe tools\update_release_bodies.py merge   # 生成合并稿
.\.venv\Scripts\python.exe tools\update_release_bodies.py         # 推送到 GitHub
```

推完脚本会自动核对三个版本是否都含「中文 + 分隔符 + 英文」，并打印资产数量防止误改。

**只改 body，不动 tag / 资产 / 版本号**——发布说明的更新不需要发新版。

### 已知限制（诚实记录，不要当作已解决）

1. **语言切换不重译已生成的详情文案** —— 结论摘要会跟随，`detail` 字段不会。重新体检即可。
2. **区域自动识别是启发式的** —— 延迟只能排除「不在中国大陆」，具体区域靠时区 + 语言。
   大陆、香港、澳门共用 `China Standard Time`，港澳完全依赖系统地区码
   （`zh-HK` / `zh-MO`）。跨国专线、海外 VPS 可能判错，设置页可手动固定。
3. **闭环实测覆盖 8/15 个动作** —— 已测：`dns.set_public`、`dns.flush_cache`、
   `proxy.reset`、`firewall.ensure_enabled`、`tcp.autotuning`、`hosts.clean_bad_lines`、
   `netbios.disable_public`、`mtu.optimize`。
   未测：`tcp.reset_stack`、`adapter.reset_stack`（需重启）、
   `adapter.renew_dhcp`（会断网）、`dns.restore_dhcp`、`hosts.restore_default`、
   `proxy.restore_auto`、`tcp.heuristics`。

   **这个数字有单一来源，不要手写**：`tools/check_consistency.py` 第 [9] 节从
   `tools/closed_loop_test.py` 的 `TEST_ACTIONS` 与 `tools/closed_loop_v12.py` 的
   `TARGETS` 反推覆盖集合，与本节的清单逐项比对。此前曾把 7 个实数写成 10 个，
   因为把 `dns.set_public` / `dns.flush_cache` 在"已测清单"和"另有 dns.* 两项"里
   各数了一次。**新增闭环动作时改的是脚本，不是这段文字。**
4. **回滚失败路径未测试** —— 代码有处理，但没有构造过"回滚中途失败"的场景。
5. **无代码签名** —— SmartScreen 会提示"未知发布者"。
6. **VPN 网卡不参与优化决策** —— 刻意为之，避免破坏既有 VPN 配置。
7. **`privacy_audit.py` 阈值刻意宽松** —— 只在严重/高级别返回 1；当前的「中=2、低=75 上下」
   不阻断 CI。**不要把这个数字写死**：它随文档行数浮动，改一条路径就会 ±1
   （本次修掉 `update_release_bodies.py` 的硬编码路径后，低就从 76 掉到 75）。
   要看当前值直接跑脚本读末尾汇总行。

   这些命中多为正当数据（RFC 5737 测试地址、公共 DNS 的 IP、第三方翻译文件的
   维护者邮箱）。**收紧会制造误报，重演"门禁长期红灯被忽略"的老问题。**

---

## 六、测试与验证

### 三层验证

| 层级 | 命令 | 说明 |
|---|---|---|
| 单元 | `pytest tests -q` | 162 项，约 1.5 秒 |
| 一致性 | `tools/check_consistency.py` | 12 节交叉校验：数量声明/版本/品牌/数据目录/截图/i18n/链接/站点/闭环覆盖/测试数量/更新清单/自身规模 |
| 站点 | `tools/check_site.py` | 资源可达 / 版本一致 / 双语互链 / 无越界引用 |
| 端到端 | 构建 → 安装 → 启动 → 卸载 | 手动，见下 |

### 端到端检查清单

```powershell
# 1. 构建
powershell -ExecutionPolicy Bypass -File scripts\build_installer.ps1 -Fresh

# 2. 静默安装到临时目录
$tmp = "$env:TEMP\lp_test"
Start-Process release\LanPulse-1.2.2-Setup.exe `
  -ArgumentList "/VERYSILENT","/SUPPRESSMSGBOXES","/NORESTART","/DIR=`"$tmp`"" -Wait

# 3. 启动，确认无崩溃、窗口标题为「LanPulse - 网络体检与一键修复」
$p = Start-Process "$tmp\LanPulse.exe" -PassThru
Start-Sleep 9; $p.Refresh(); $p.MainWindowTitle
Stop-Process -Id $p.Id -Force

# 4. 卸载
Start-Process "$tmp\unins000.exe" -ArgumentList "/VERYSILENT","/SUPPRESSMSGBOXES" -Wait
```

**验证要点**：数据目录应为 `%LOCALAPPDATA%\LanPulse`，且**不应**创建旧的 `NetPulse` 目录。<!-- brand-ok -->

### 闭环实测（会真实改系统，需管理员）

```powershell
# 当前覆盖 5 个动作：proxy.reset / firewall / tcp.autotuning /
#                   hosts.clean_bad_lines / netbios.disable_public
.\.venv\Scripts\python.exe tools\closed_loop_v12.py   # 需提权

# v1.1.0 的 DNS 类闭环（单独脚本，仍可用）
.\.venv\Scripts\python.exe tools\closed_loop_test.py
```

**它的判据与普通测试不同**，先看 `tools/closed_loop_v12.py` 顶部注释再改：

- 这四个动作**只在需要时才动手**，必须先构造故障态才能验证
- 动作的 `backup()` 在构造之后才跑，所以它备份的是「造出来的故障态」
- 因此正确判据是 `快照D（回滚后） == 快照B（构造态）`，而不是回到更早的原始态
- 脚本额外用 `快照E（复原后） == 快照A（原始态）` 保证不污染本机

### 截图生成

```powershell
.\.venv\Scripts\python.exe tools\regen_screenshots.py --lang zh
.\.venv\Scripts\python.exe tools\regen_screenshots.py --lang en
.\.venv\Scripts\python.exe tools\make_hero.py     # 首图
```

截图用合成数据（`EXAMPLE-PC` / `192.0.2.42`，RFC 5737 保留段），**不含任何本机信息**。

**两个坑**：

- **不要设 `QT_QPA_PLATFORM=offscreen`**。脚本自己会设 `windows`；强行覆盖会让英文字体
  渲染成方块（中文因有中文字体反而正常，容易误判为"没问题"）
- 脚本跑完不退出（Qt 事件循环残留），用 `Start-Process ... -PassThru` + `WaitForExit(超时)`
  再 `Stop-Process` 收尾；截图在此之前已完成

---

## 七、踩过的坑（不要重犯）

### ADS 备份损坏（最严重）

Windows 注册表项的 `key` 含 `:`（如 `reg:tcpip`），作为文件名会变成 NTFS 数据流，
创建出 0 字节的可见文件。结果：备份看起来成功，回滚 100% 失败。

**已在 `core/backup.py` 的 `safe_name()` 修复**。任何新的备份路径都必须走这个函数。

### 修复动作漏 import，只在真实执行时崩溃

`firewall_actions.py` 与 `netbios_actions.py` 都用了 `pw.now()` 却没 `from .. import
platform_win as pw`。单元测试不执行动作、`dry_run` 也不走 `apply()`，两者都覆盖不到——
直到真实提权闭环才炸出 `NameError`。`netbios.disable_public` 还是 UI 默认勾选项。

**已加 `tests/test_repair_contracts.py`**：用 AST 静态扫描「使用了但未导入的模块级别名」。
新增修复动作后这个测试会自动覆盖。

### `localized_meta` 逐字段重建会静默丢字段

`app/ui/pages/repair.py` 的 `localized_meta()` 手工逐字段构造 `ActionMeta` 副本。
`ActionMeta` 每加一个字段，这里不同步就会静默丢失——表现为「警告中文有、英文没有」。

**加字段时必须同步这里**，`test_repair_contracts.py` 里有回归用例。

### push tag 会自动触发 Release，与本地发布互相打架（v1.2.2 撞上）

`release.yml` 原来的触发器是 `on: push: tags: v*`。发 v1.2.2 时本地
流程也在建 Release，推 tag 后 CI 同时启动——**两边都去创建 Release 并上传
同名资产**（`overwrite_files: true` 会让后跑的覆盖先跑的）。

当时的处置是人工 `cancel` 那次 run。它已经跑完四道门禁、正在编译安装包，
于是这个 commit 在仓库页面上挂了一个 **cancelled 的检查标记，显示为失败**。
看起来像构建坏了，实际是被人打断的。**这种"红叉"会误导下一个人排查半天。**

**已改成只保留 `workflow_dispatch`**。发布是低频且需要人判断的动作，不该
因为推了个 tag 就自动跑一遍完整构建 + 上传。连带的两个必改点：

- `actions/checkout` 必须显式 `ref: ${{ github.event.inputs.tag }}`。
  手动触发时 `github.ref` 是默认分支，不指明就会检出 main，产物与 tag 对不上。
- `tag_name` 去掉了 `|| github.ref_name` 兜底。手动触发时 `ref_name` 是
  `"main"`，兜底会在出错时静默建出一个名为 main 的 Release——比失败更糟。

**如果哪天又看到 commit 上有 cancelled/失败标记**，先看是不是 Release 工作流：
点进 Actions → 看是哪一步。门禁步骤若都是 success，那就是发布流程被打断，
不影响代码质量。

### Release 工作流把注释行当版本号

`installer/LanPulse.iss` 顶部有一条注释示例 `; #define MyAppVersion "1.0.0"`。
`release.yml` 原来用 `-match` 对整个文件做正则，匹配到的是**注释里那个 1.0.0**——
于是 v1.2.0 的绿色包叫 `LanPulse-1.0.0-...zip`、标题写成 `LanPulse 1.0.0`。
v1.1.0 也有同样缺陷，只是无人察觉。

**已改为逐行解析并跳过 `;` 开头的行**，与 `check_consistency.py` 保持一致。

### PowerShell 合并 run 块会吞掉失败

`release.yml` 曾把 `pytest` 与 `audit_i18n` 写在同一个 `run: |` 块里。PowerShell 遇到
外部命令非零退出**不会中断**，runner 只采信整块最后一条命令的退出码——pytest 挂了
也显示成功，坏代码直接发出去。

**已拆成独立 step**。写 workflow 时，多条命令要么各自一个 step，要么显式检查
`$LASTEXITCODE`。

### GitHub 仓库 description 拒绝控制字符

`PATCH /repos/{owner}/{repo}` 传含 `\n` 的 description 会返回 422
`description control characters are not allowed`。该字段是严格单行的。

双语只能单行并置（见 `tools/repo_about.py`）。另外 **topics 不能用 PATCH 更新**，
必须 `PUT /repos/{owner}/{repo}/topics`。

### README 页内锚点在改名后失效

两个 README 的「回到顶部」曾指向旧品牌的小写锚点。品牌检查匹配的是驼峰写法，
**抓不到全小写的锚点**。

**`check_consistency.py` 第 [7] 节现在会校验**：页内锚点对照实际标题、相对链接对照文件系统。

### 区域识别耗时被算进检测项预算

`ctx.profile` 首次访问会触发区域自动识别。在 8.8.8.8 / 9.9.9.9 不可达的网络上
（国内常态）它要跑 12 秒以上，而这段耗时曾被算进 connectivity 自己的 10 秒预算里，
导致真正的探测一个都没跑、结果报 SKIP。

**已修**：`started` 移到 `profile = ctx.profile` 之后。区域识别是共享的一次性准备，
不属于任何单个检测项的预算。`tests/test_checks.py` 有回归用例。

### `min()` 会完整消费生成器

区域识别原本写 `min(_rtt_ms(a) for a in _GLOBAL_ANCHORS)`——`min` 会遍历全部锚点，
即使第一个已经返回。在国内网络上等于白等两个超时（实测 +9.6 秒）。

**已改为 `_first_rtt_ms()`**：取到第一个可用值即停。整体 12.5s → 1.3s。

### PowerShell `Set-Content -Encoding utf8` 破坏中文

批量编辑中文文件时会写入 U+E0xx 私有区字符，不可逆。

**规则**：改文件用编辑工具，不要用 `Get-Content -Raw | Set-Content`。
（含 BOM 问题：`Set-Content -Encoding UTF8` 在 5.1 上会加 BOM，而仓库文件要求无 BOM。）

### `shiboken6` 不能加进 PyInstaller EXCLUDES

加了之后窗口版 exe 崩溃，只报 "Unhandled exception in script"，无堆栈。
**已在 `build.spec` 注释说明原因**。

### MTU 有两个，读写不能混用（v1.2.2 修正）

`AdapterInfo.mtu` 原先是 `Get-NetAdapter` 的 `MtuSize`（NDIS 链路层），
而 `netsh interface ipv4 set subinterface mtu=` 读写的是 `NlMtu`（IP 层）。
**在有封装的链路上两者不相等**（本机以太网 1500 vs 1492），后果是
verify 永久假失败、回滚把用户配置改成另一个值。

现在：`mtu` = `NlMtu`（**所有修复/检测/备份/回滚都用它**），
`link_mtu` = `MtuSize`（仅诊断展示）。
`tests/test_repair_contracts.py::TestMtuSemantics` 锁死这条。

**新增任何读 MTU 的代码，只能读 `.mtu`。** 本机这个差异是天然存在的，
不需要构造就能复现，改错了会立刻被闭环测试发现。

### 备份前必须刷新网卡缓存，否则备份的是"过去"（v1.2.2 修正）

`DiagnosticContext.adapters` 首次采集后永久缓存（为"一次体检内不重复
采集"设计）。但修复可能发生在体检几分钟之后，用户中途也可能手动改过配置。
用这份旧快照备份，回滚就会把系统恢复到**用户早已不处于的状态**，而报告
仍显示 `rolled_back=True`。

**已修**：`RepairEngine.execute()` 在建会话后、逐项 `backup()` 之前调用
`ctx.refresh_adapters()`。这条对所有动作生效。

**闭环脚本里也要刷**：构造出故障态之后必须 `ctx.refresh_adapters()`，
否则动作读到的还是构造前的值。`closed_loop_v12.py` 已加。

### 文档里的"零上传"表述与更新检测冲突（v1.3.0 前修正）

加了更新检测后，原来的说法"代码里没有任何上传逻辑 / 网络请求只有 ICMP 与
DNS"就变成**不准确**了——多了一条可选的 HTTPS GET。措辞必须同步改成
"对外请求有两类：检测探测 + 可选的版本号查询"，并写清楚它不带什么。

**这不是文字游戏**：这个产品的卖点就是"说什么就是什么"。留着一句不准确的
表述，等于把前面所有承诺的可信度一起打折。

改动点：`README.md`（特性表 + FAQ 两条）、`README_EN.md`、
`SECURITY.md` 第 3 节、`docs/设计方案.md` 抬头。

### 测试断言会命中注释里的文字（第三次踩）

写 `TestUpdatePrivacyBoundary` 时断言"源码里不得出现 hostname/username/guid"，
结果函数 docstring 里正写着"**不要**加主机名/用户名/GUID"——断言命中的是
这句说明本身，测试红。

这与门禁里"注释被当成一节"是同一类错误。**凡是拿源码文本做断言的检查，
先剥掉注释与 docstring**。本仓库已出现三次，值得记一笔。

### 编辑工具会把整份文件转成 CRLF，污染 diff

仓库基线全是 LF（`.py` / `.md` / `.iss` / `.ps1` 一律）。用部分编辑工具
（含 IDE、某些 `read-modify-write` 脚本）改文件时，工具可能按 Windows 默认
把**整份文件**重写成 CRLF。后果不是功能坏了，而是 `git diff` 显示 800+ 行
变更，真实改动被淹没，评审时根本看不出改了什么。

本仓库没有 `.gitattributes` 兜底，也没有开 `core.autocrlf`，所以这件事
完全靠改完自查。

**判据**（改完立刻查，别等提交后才发现）：

```bash
git diff --stat          # 行数应与你实际改的行数同量级
file tools/xxx.py        # 出现 "CRLF line terminators" 就是中招了
```

**修复**（转回 LF，不碰内容）：

```python
import pathlib
p = pathlib.Path("tools/xxx.py")
p.write_bytes(p.read_bytes().replace(b"\r\n", b"\n"))
```

转完 `git diff --stat` 应立刻回落到真实改动量。**提交前必看这一行**。

### `netsh` 参数非法时返回 0

不能只看退出码判断成功，还要检查输出文本。

### `tcp.heuristics` 在 Win10 1803+ 已移除

检测项会 `available()` 探测并跳过，不产生误报建议。动作仍保留用于兼容旧系统。

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

**发布用的 token 放在 `.gh_token`**（已被 `.gitignore` 覆盖），格式为下划线
细粒度 PAT（`github_pat_`，93 字符）。

#### `.gh_token` 的保留策略（2026-11-10 修订）

旧约定是「用完即删」。实测下来这条容易被理解成「每次会话都删」，导致每次
部署前都要重新签发，反而增加 token 在剪贴板、日志、shell 历史里暴露的机会。
现在的策略分两半：

| 位置 | 约定 |
|---|---|
| **本地 `D:\...\lanpulse\.gh_token`** | **允许长期保留**。它已被 `.gitignore` 覆盖、从未进入过 git 历史，本地留存不构成泄露面 |
| **GitHub 侧对应 token** | **每次部署完成后必须撤销**。部署结束 = 改动已推送 / Release 已上传 / 站点已更新 |

也就是说：文件留在本地，**凭据在远端作废**。下次部署重新签发一个新 token
写进同一个文件即可，不需要动任何其它环节。

**部署后必须执行（不要跳过）**：

1. 打开 https://github.com/settings/tokens?type=beta （细粒度 PAT 页）
2. 找到本次用的 token → **Delete**（不是 "Regenerate"；重新生成等于续命）
3. 本地 `.gh_token` 保持不动，但把它视为**已失效**，直到下次部署覆盖
4. `git remote set-url origin https://github.com/Levanll/LanPulse.git` 复原
   （推送时用的是 `https://x-access-token:<token>@github.com/...` 一次性 URL）
5. 清理 Windows 凭据管理器中的 `git:https://github.com`

**判据**：部署收尾时 `git ls-remote origin refs/heads/main` 仍能通（走的是
系统凭据或匿名读），而用旧 token 调 `GET /user` 返回 401 —— 说明远端已作废、
本地文件残留无害。

**不要把 token 写进任何会被提交的文件**（CHANGELOG、发布说明、脚本常量）。
`tools/privacy_audit.py` 会拦 `github_pat_` 前缀，但那是最后一道闸，不是第一道。

### Release 说明改双语时，中文稿的结构不统一

v1.1.0 的中文稿直接从「首个公开版本。」开头，缺 `## 本次更新` 标题——因为它是
从旧 CHANGELOG 抽出来的，而 v1.2.0 / v1.2.1 是后写的、有标题。

合并中英时如果不统一标题层级，渲染出来中文段没有小标题、英文段有，看起来像漏了内容。

**`update_release_bodies.py merge` 不做结构校验**（它只负责拼接），改稿时自己保证
两版的 `#` 标题数量一致。核对方法：

```powershell
.\.venv\Scripts\python.exe -c "import pathlib; [print(t, sum(1 for l in (pathlib.Path(f'docs/release-notes/{t}.md').read_text(encoding='utf-8')).splitlines() if l.startswith('#')), sum(1 for l in (pathlib.Path(f'docs/release-notes/{t}.en.md').read_text(encoding='utf-8')).splitlines() if l.startswith('#'))) for t in ('v1.1.0','v1.2.0','v1.2.1','v1.2.2')]"
```

### Release body 里的「1.0.0」不一定是描述错误

v1.2.0 的正文含 `1.0.0`，那是它自己的一条修复记录（「发布流程把版本号解析成了 1.0.0」），
不是旧版本内容。搜索旧版本痕迹时会误报，需看上下文再判断。

### 落地页截图放大被裁切（连踩三次）

给「界面」板块做「横向滑动画廊 + 悬停放大」时，放大后的图一直被上下切掉。三次尝试：

| 尝试 | 写法 | 结果 |
|---|---|---|
| 1 | `.shots { overflow: hidden }` | 全裁，放大溢出部分完全不可见 |
| 2 | `.shots { overflow-x: clip; overflow-y: visible }` | **仍裁**。CSS 规范规定 overflow 两个方向若一个非 visible，另一个的 `visible` 会被计算成 `auto` |
| 3 | 去掉 overflow，改用 `mask-image` 做两侧渐隐 | **仍裁**。`mask-image` 同样建立裁剪/合成上下文 |

**最终解法**：`.shots` 上**什么裁剪属性都不设**，横向溢出的裁剪交给
`html { overflow-x: hidden }`（页面层），两侧渐隐效果**取消**。

**验证方法**（不能只看 CSS 计算值，那会骗人）：

```js
// 用 elementFromPoint 检查溢出区域的命中元素
const b = figure.getBoundingClientRect();
document.elementFromPoint(cx, b.top + 15)   // 必须命中 IMG，不是 DIV.wrap
```

命中 `IMG`/`FIGCAPTION` 才算真的可见；命中背景元素说明仍被裁剪。

**另注**：改完 CSS 后浏览器可能用缓存样式，测试时要给 stylesheet 加时间戳
（`link.href = ... + '?v=' + Date.now()`）强制重载，否则会测到旧规则、误以为没生效。

---

## 八、开发约定

### 新增检测项

1. 在 `core/checks/` 建文件，实现 `check_id` / `title` / `category` / `run(ctx)`
2. `title` 与 `category` 存 i18n key，不存文案
3. 在 `core/registry.py` 的 `load_checks()` 注册
4. 若某场景需要它，加入 `core/scenarios.py`
5. 补 `app/i18n_zh.py` 与 `app/i18n_en.py`（key 必须两边都加）
6. 跑 `check_consistency.py`（会检查场景引用的 check_id 是否存在）

**注意预算的记账口径**：检测项自己的计时器不能把共享准备（区域识别、网卡采集）
算进去。参见第七节。

### 新增修复动作

1. 在 `core/repair/` 实现，登记到 `core/action_ids.py`
2. **确认模块顶部导入了 `platform_win as pw`**（`test_repair_contracts.py` 会查）
3. 动作必须先调 `BackupStore` 备份，再执行
4. 执行后要读回校验，不能假设命令成功
5. 实现回滚逻辑到 `core/repair/rollback.py` 的 `_dispatch`
6. 补 `action.<id>.title` 与 `.description` 文案
7. 若需重启才能生效，设 `needs_restart=True` 并在描述里写明回滚边界
8. 同步 `localized_meta()`（它逐字段重建元数据，会丢新字段）

### 新增区域剖面

1. 在 `core/region.py` 加常量 + 加进 `ALL_REGIONS`（顺序即设置页下拉顺序）
2. 加 `PROFILES` 条目：解析域名、ping/TCP 目标、MTU 目标、DNS 方案、阈值
3. 补时区映射（`_WIN_TZ_HINTS` / `_TZ_HINTS`）与语言映射（`_locale_region`）
4. 本地 DNS 地址要进 `DNS_VENDOR_KEYS`，否则界面显示「自定义/运营商」
5. 补 i18n：`region.<key>`、`dns.vendor.<x>`、`dns.plan.<x>.name/tag/desc`
6. 加测试：剖面完整性、地址段合法性、归属识别、时区别名

**不要**把新区域并入相邻区域凑数。澳门曾被并入香港，导致当地用户拿到不适用的
探测目标。

### 新增 i18n 文案

两语言必须同时加，且占位符集合一致。`audit_i18n.py` 会检查。

**缺失 key 时 `t()` 返回 `⟦key⟧`** —— 这是刻意的可见失败，不要改成静默回退。

### 修改落地页

站点在 `site/`，是 GitHub Pages 的**发布源**，因此必须自包含：

- 图片不能引用 `../docs/images/`（站点根就是 `site/`，上级目录不存在）
- 截图改动后跑 `tools/sync_site_assets.py` 同步到 `site/assets/`
- **发版后必须同步改页面里的版本号**：下载链接用
  `/releases/latest/download/LanPulse-<版本>-Setup.exe`，文件名带版本号，
  忘了改就会 404。`check_consistency.py` 第 [8] 节和 `check_site.py` 都会拦

预览：直接浏览器打开 `site/index.html` 即可，无需构建步骤。

**「界面」板块是横向滚动画廊**，不是网格。要点：

- 轨道里是**两份完全相同的 figure**（第二份 `aria-hidden`），CSS 平移 `-50%` 后
  首尾正好衔接，循环无跳变。改截图时必须**同时改两份**，否则循环处会跳
- 鼠标进入轨道即 `animation-play-state: paused`；悬停单张 `transform: scale(1.5)`
- **`.shots` 上不能设 `overflow`，也不能设 `mask-image`** —— 两者都会建立裁剪
  上下文，放大后的图会被切掉。横向溢出的裁剪由 `html { overflow-x: hidden }`
  承担。这是踩过三次的坑，详见第七节

### 修改发布说明（Release body）

1. 改 `docs/release-notes/<tag>.md`（中文）与 `<tag>.en.md`（英文）
2. **两版的 `#` 标题层级数量必须一致**，否则渲染后中英结构不齐
3. 跑 `tools/update_release_bodies.py merge` 生成合并稿
4. 跑 `tools/update_release_bodies.py` 推送

不改 tag、不动资产、不升版本号。

不要把 `**完整说明见 [CHANGELOG.md](...)**` 这类链接行删掉——它是通往完整变更记录的入口。

### 提交前必跑

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe tools\check_consistency.py
.\.venv\Scripts\python.exe tools\audit_i18n.py
.\.venv\Scripts\python.exe tools\privacy_audit.py
```

四道门禁现在都由 CI 强制执行（`ci.yml` 与 `release.yml`），本地跑是为了早发现。

---

## 九、可选的下一步

按价值排序：

| 优先级 | 事项 | 说明 |
|---|---|---|
| 高 | 补测 `mtu.optimize` | 需构造安全 MTU 值（如 1400），不能依赖自然触发——实测值等于当前值时动作会 SKIP |
| 高 | 补测 `adapter.renew_dhcp` | 会断网 3–10 秒，脚本里要明确提示并排到最后单独跑 |
| 高 | 回滚失败路径测试 | 构造中途失败（备份文件被删/改坏）验证提示与恢复 |
| 中 | 补测 `dns.restore_dhcp` / `hosts.restore_default` / `proxy.restore_auto` | 风险不高，可并入现有闭环脚本 |
| 中 | 语言切换重译 detail | 需把 detail 也改成 key + args |
| 中 | IPv6 完整诊断 | 目前只采集不诊断 |
| 中 | 代码签名 | SignPath Foundation 对 OSS 免费。可先在 `build.spec` / `LanPulse.iss` 预留签名钩子 |
| 低 | WiFi 信号与信道分析 | 需 `netsh wlan`，部分网卡不可用 |
| 低 | 打包为 MSIX | 走 Microsoft Store 可消除 SmartScreen 警告 |

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
- 各版本发布说明源稿：[docs/release-notes/](docs/release-notes/)

**发布相关脚本**：

- `tools/check_consistency.py` —— 12 节交叉校验，改文档/版本后必跑
- `tools/repo_about.py` + `tools/apply_repo_about.py` —— 生成并应用双语 About 与 topics
- `tools/update_release_bodies.py` —— 发布说明中英合并与推送（`merge` 子命令只生成不推送）
- `tools/publish_github.py` / `tools/final_publish.py` —— 版本号均从 branding 读（切勿改回硬编码）

**账号与凭据**：

- 组织/账号：`Levanll`
- 发布 token 走 `.gh_token`：**本地可长期保留，每次部署后必须在 GitHub 撤销**
  （细粒度 PAT 页 → Delete）。完整清单见第七节「`.gh_token` 的保留策略」
- 撤销入口：https://github.com/settings/tokens?type=beta

参考项目（借鉴设计思路，未复制代码）：https://github.com/silentcrow09/netpulse
