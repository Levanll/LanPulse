# 贡献指南 / Contributing to LanPulse

感谢你有兴趣改进 LanPulse。这是一个会**直接修改用户系统网络配置**的工具，
因此对代码质量与安全边界的要求高于普通项目。

---

## 一、开发环境

```bash
git clone https://github.com/<owner>/LanPulse.git
cd LanPulse

python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1

pip install -r requirements-dev.txt
```

依赖很少是刻意的：**不引入任何第三方网络库或 UI 框架**。所有系统能力都走
Windows 原生（`netsh` / `ipconfig` / `reg` / WMI-CIM / `dnsapi` / `wininet`）。

---

## 二、跑测试

```powershell
$env:PYTHONPATH="."
.\.venv\Scripts\python.exe -m pytest tests -q
```

当前 74 项，全部是**不碰系统状态**的纯逻辑测试。涉及真实修改系统的路径
不放进自动化测试，用 dry-run 手工验证。

额外的开发期自检脚本：

```powershell
# 跨区域：确认三套剖面的探测目标真的不同
.\.venv\Scripts\python.exe tools\verify_regions.py

# 双语：确认两种语言下 14 项检测都能翻译、判定不随语言变化
.\.venv\Scripts\python.exe tools\verify_i18n.py

# i18n 审计：代码引用的 key 是否都在语言包里（CI 门禁）
.\.venv\Scripts\python.exe tools\audit_i18n.py

# 修复引擎 dry-run：只建备份、不改系统
.\.venv\Scripts\python.exe tools\verify_repair.py

# 备份完整性：检查是否有 ADS 空壳文件
.\.venv\Scripts\python.exe tools\inspect_backups.py
```

---

## 三、构建

```powershell
# 只打 exe（PyInstaller，单目录）
.\.venv\Scripts\python.exe -m PyInstaller build.spec --noconfirm --clean

# 打安装包 + 绿色包（需要 Inno Setup 6）
powershell -ExecutionPolicy Bypass -File scripts\build_installer.ps1
```

产物输出到 `release/`：
- `LanPulse-<版本>-Setup.exe`
- `LanPulse-<版本>-win64-portable.zip`
- `SHA256SUMS.txt`

版本号唯一来源是 `installer/LanPulse.iss` 里的 `MyAppVersion`。

---

## 四、代码规范

### 4.1 安全是第一位的

任何会修改系统的代码，**必须**遵守：

1. **先备份、后修改**：写操作前必须 `BackupStore.capture_*()`，备份失败则拒绝执行。
2. **可回滚**：每个动作都要有对应的回滚路径，且回滚只依赖备份目录，不依赖进程内存。
3. **执行后校验**：`apply()` 之后必须 `verify()` 读回确认，不能假设命令成功。
4. **不静默失败**：`netsh` 参数非法时返回码可能仍是 0，必须同时检查输出文本。
5. **需要提权的动作**在 `available()` 或规划阶段就暴露，不要让用户点了才失败。

新动作的落点：`core/repair/*_actions.py`，并在 `core/action_ids.py` 登记元数据。
**两处必须同步**，`tests/test_core_logic.py` 有一致性测试。

### 4.2 所有用户可见文案必须走 `t()`

```python
from core.i18n import t

# 正确
label = t("metric.link_speed")

# 错误：硬编码中文或英文
label = "链路速率"
```

新增 key 必须**同时**加到 `app/i18n_zh.py` 和 `app/i18n_en.py`，
且两边的 `{}` 占位符集合一致。改完跑 `tools/audit_i18n.py` 确认。

检测单元在后台线程执行，**不要把 t() 的结果存进结果对象的 `summary`/`title`**
而应同时记录 `summary_key` + `summary_args`，否则切换语言后旧结果不会更新
（详见 `docs/设计方案.md` 第五节）。

### 4.3 不要加第三方依赖

新增依赖需要在本文件里说明理由并解释为什么标准库做不到。
当前允许的第三方库只有：`PySide6`（UI）、
`pyinstaller`（打包，仅构建期）、`pytest`（测试，仅开发期）。

### 4.4 不要硬编码地域相关的东西

探测目标（DNS 服务器、测试域名、MTU 目标）必须从 `ctx.profile`（区域剖面）取，
不能写死 `223.5.5.5` 或 `www.baidu.com`——这会让软件在其它国家失效。

### 4.5 编码

- 源文件 UTF-8。**PowerShell 脚本需要 UTF-8 BOM**，否则 Windows PowerShell 5.1
  会按 GBK 解析导致中文乱码和语法错误。
- 中文注释解释"为什么"，不复述代码。

---

## 五、提交规范

用 Conventional Commits 前缀：

```
feat:     新功能
fix:      缺陷修复
docs:     文档
test:     测试
chore:    构建/杂项
refactor: 重构（不改变行为）
```

提交信息用中文或英文都可以，但要说清**为什么改**。

**如果修复的是真实缺陷，请在提交正文里写清楚复现方式与影响面。**
本项目已记录 13 个实测发现的缺陷（见 `docs/设计方案.md` 第九节），
其中 ADS 那个"备份看起来成功但回滚 100% 失败"的问题，就是靠明确记录才没被再次引入。

---

## 六、报 Issue

请尽量附上：

- Windows 版本（`winver`）
- LanPulse 版本
- 是否以管理员运行
- **在软件内导出的诊断报告**（报告与日志页 → 导出 HTML），它包含完整证据

---

## English

LanPulse is a **Windows network diagnostics and one-click repair** tool that
modifies real system network settings. Contributions are welcome, but the bar
for safety is higher than in a typical project.

**Before you start:**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
$env:PYTHONPATH="."
.\.venv\Scripts\python.exe -m pytest tests -q
```

**Non-negotiable rules:**

1. Every system mutation goes through `core/backup.py` first. No backup, no write.
2. Every action must be reversible from the backup directory alone.
3. Verify after apply — never assume a command succeeded. `netsh` returns 0 even
   when the argument is invalid; check the output text too.
4. All user-facing strings go through `t()`, and new keys must be added to
   **both** `app/i18n_zh.py` and `app/i18n_en.py` with identical `{}` placeholders.
5. Do not hardcode region-specific targets (DNS servers, probe domains). Pull them
   from `ctx.profile` so the tool keeps working outside China.
6. No new third-party dependencies without justification.

**Commit style:** Conventional Commits (`feat:` / `fix:` / `docs:` / `test:` /
`chore:` / `refactor:`). If you fixed a real defect, describe how to reproduce it
and what the impact was.

**Reporting bugs:** include your Windows build, LanPulse version, whether it ran
as administrator, and the exported diagnostic report (Reports & Logs → Export HTML).
