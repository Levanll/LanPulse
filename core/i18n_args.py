"""i18n 参数解析 —— 检测层与渲染层共用同一套规则。

背景：检测在后台线程执行，产出的 `summary_args` 里可能含有 **i18n key**
（如 `value.static`、`grade.excellent`）或嵌套片段（`head_parts`）。
若在检测时就翻译成中文再塞进参数，英文界面会出现「(静态)」「（阿里公共 DNS）」
这类中英混排——这是实际出现过的问题。

因此约定：检测层只管组装 **key + 原始值**，翻译统一由本模块在渲染时完成。
放在 core 层（而不是 app/ui）是为了让 core/checks 也能复用，
同时避免 core 依赖 UI。
"""
from __future__ import annotations

from typing import Any

from .i18n import t


def resolve_args(args: dict[str, Any]) -> dict[str, Any]:
    """把 summary_args 里的 key 值解析成当前语言的文本。

    支持的取值形态：
      * 普通值（IP、数字、网卡名）—— 原样返回；
      * i18n key（`value.static` 等）—— 翻译；非 key 的字符串原样保留，
        由调用方的 t() 决定是否出现 ⟦key⟧ 标记；
      * `head_parts` —— `[{"key": ..., "args": {...}}, ...]`，按分隔符拼成 `head`。
    """
    out: dict[str, Any] = {}
    for key, value in args.items():
        if key == "head_parts" and isinstance(value, (list, tuple)):
            parts: list[str] = []
            for item in value:
                if isinstance(item, dict) and "key" in item:
                    parts.append(t(item["key"], **resolve_args(item.get("args") or {})))
                else:
                    parts.append(str(item))
            out["head"] = t("sep.summary").join(parts)
        elif key.endswith("_parts") and isinstance(value, (list, tuple)):
            # 形如 profiles_parts=[...]、domains_parts=[...]：
            # 元素是 i18n key，按分隔符拼成同名去后缀的参数（profiles / domains）。
            base = key[: -len("_parts")]
            out[base] = t("sep.list").join(t(str(v)) for v in value)
        elif isinstance(value, str):
            out[key] = translate_if_key(value)
        else:
            out[key] = value
    return out


def translate_if_key(text: str) -> str:
    """是已知 key 就翻译，否则原样返回。

    用「翻译结果是否带缺失标记」判断，不维护"哪些字段是 key"的清单——
    那种清单一定会随代码演进失配。
    """
    if not text:
        return text
    translated = t(text)
    return text if translated.startswith("\u27e6") else translated


__all__ = ["resolve_args", "translate_if_key"]
