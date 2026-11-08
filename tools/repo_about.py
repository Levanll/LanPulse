"""生成 GitHub 仓库 About 的中英双语描述。

GitHub 的 description 是单字段、单行、上限 350 字符，没有「语言切换」这回事——
它不跟随界面语言。因此「双语」只能靠同一段文本里同时呈现两种语言。

做法：中文在前（仓库主要受众），用换行符分隔英文（GitHub 的 About 在
仓库首页会把它渲染成多行，API 也接受非空字符串里的 \n）。
若超出 350 字符上限，英文退化为关键词式短句，保证两边都在。
"""

ZH = ("Windows 网络体检与一键修复 —— 14 项检测 / 6 个场景 / 10 条根因规则 / "
      "15 个可回滚修复动作 · 12 套区域剖面 · 中英双语 · 全本地运行")

EN = ("Windows network diagnostics with reversible one-click repair — 14 checks, "
      "6 scenarios, 10 root-cause rules, 15 rollback-safe actions, 12 region profiles, "
      "fully offline")

SEP = "\n"


def build() -> str:
    full = ZH + SEP + EN
    if len(full) <= 350:
        return full
    # 超限时压缩英文（中文是主要受众，优先保留完整）
    short_en = ("Windows network diagnostics with reversible one-click repair "
                "(14 checks / 15 actions / 12 regions, fully offline)")
    return ZH + SEP + short_en


if __name__ == "__main__":
    desc = build()
    print(f"长度: {len(desc)} / 350")
    print("-" * 60)
    print(desc)
    assert len(desc) <= 350, "超出 GitHub description 上限"
