## 改动说明

<!-- 简要说明这个 PR 做了什么、为什么 -->

## 类型

- [ ] 缺陷修复
- [ ] 新功能
- [ ] 文档
- [ ] 重构（不改变行为）
- [ ] 构建 / 打包

## 涉及范围

- [ ] 检测引擎 `core/checks/`
- [ ] 修复引擎 `core/repair/`
- [ ] 备份 / 回滚 `core/backup.py`
- [ ] 跨区域 `core/region.py`
- [ ] 国际化 `core/i18n*.py` / `app/i18n_*.py`
- [ ] 界面 `app/ui/`
- [ ] 报告 `app/report.py`
- [ ] 打包 / 安装 `build.spec` / `installer/` / `scripts/`

## 安全自查（涉及系统修改时必填）

- [ ] 所有写操作都经过了 `BackupStore`，没有绕过备份直接改系统
- [ ] 备份内容足以完整恢复（记录的是"恢复所需状态"，不是差异）
- [ ] 新动作实现了 `verify()`，执行后读回确认
- [ ] 命令失败检测同时检查返回码**与**输出文本（`netsh` 非法参数时返回码仍为 0）
- [ ] 回滚路径在非管理员下会被标记为"权限不足"而不是"失败"
- [ ] 高危动作 `default_selected=False`

## 国际化自查（新增/修改文案时必填）

- [ ] 所有用户可见文案走 `t()`，没有硬编码中英文
- [ ] 新 key 已同时加入 `app/i18n_zh.py` 与 `app/i18n_en.py`
- [ ] 两种语言的 `{}` 占位符集合一致
- [ ] 运行 `python tools/audit_i18n.py` 通过
- [ ] 检测结果若新增文案，同时记录了 `summary_key` + `summary_args`（否则切换语言后不更新）

## 跨区域自查（涉及探测目标时必填）

- [ ] 没有硬编码地域相关的目标（DNS、探测域名、MTU 目标）
- [ ] 探测目标来自 `ctx.profile`
- [ ] 运行 `python tools/verify_regions.py` 通过

## 测试

```powershell
$env:PYTHONPATH="."
.\.venv\Scripts\python.exe -m pytest tests -q
```

<!-- 贴出测试结果 -->

## 截图（界面改动时）

<!-- 前后对比更佳 -->

## 相关 Issue

<!-- Closes #123 -->
