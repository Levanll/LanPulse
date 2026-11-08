"""生成 GitHub 仓库 About 的中英双语描述。

GitHub 的 description 是单字段、单行、**且明确拒绝控制字符**（换行会返回
422 "description control characters are not allowed"）。它也不跟随界面语言。
因此「双语」只能靠同一行里并置两种语言，用可见分隔符断开，不能用换行。

中文在前（仓库主要受众），英文在后，用「 · EN · 」这类可见标记分隔。
英文部分压缩到关键词式，保证 350 字符上限内两边都完整可读。
"""

ZH = ("Windows 网络体检与一键修复 —— 14 项检测 / 6 个场景 / 10 条根因规则 / "
      "15 个可回滚修复动作 · 12 套区域剖面 · 中英双语 · 全本地运行")

# 用全角竖线做语言分界：在 About 的紧凑排版里比 " | " 更醒目，且不算控制字符
SEP = " ｜ "

EN = ("Windows network diagnostics with reversible one-click repair — 14 checks, "
      "6 scenarios, 10 root-cause rules, 15 rollback-safe actions, 12 region profiles, "
      "fully offline")


def build() -> str:
    full = ZH + SEP + EN
    if len(full) <= 350:
        return full
    # 超限时压缩英文（中文是主要受众，优先保留完整）
    short_en = ("Windows network diagnostics with reversible one-click repair "
                "(14 checks / 15 actions / 12 regions, offline)")
    out = ZH + SEP + short_en
    assert len(out) <= 350, f"压缩后仍超限：{len(out)}"
    return out


if __name__ == "__main__":
    desc = build()
    print(f"长度: {len(desc)} / 350")
    print(f"含控制字符: {any(ord(c) < 32 for c in desc)}")
    print("-" * 60)
    print(desc)
    assert len(desc) <= 350
    assert not any(ord(c) < 32 for c in desc), "GitHub 拒绝控制字符"
