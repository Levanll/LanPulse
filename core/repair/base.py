"""修复动作协议、注册表，以及全部系统命令的唯一入口。

为什么要把命令集中在这一层：
  * 修复动作「执行」和「回滚」必须走同一套命令封装。如果执行用 A 写法、
    回滚用 B 写法，回滚就会在关键时刻因为参数拼错而失效——这是本项目
    最不能接受的缺陷形态。
  * netsh / reg / ipconfig 的失败必须带上返回码和原始输出抛出去，
    否则用户只看到"修复失败"四个字，无法定位。

参数化动作（需要构造参数的）：
  注册表存的是 factory 而不是实例。`get("mtu.optimize")` 无参获取会抛
  ValueError 并要求传入 params，避免出现"用默认值偷偷改了 MTU"这种事。
"""
from __future__ import annotations

import inspect
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol, Sequence

from .. import platform_win as pw
from ..action_ids import ACTIONS
from ..i18n import t
from ..models import ActionState, ActionResult, ChangePreview, RiskLevel

# --------------------------------------------------------------------------- #
# 动作协议
# --------------------------------------------------------------------------- #
class RepairAction(Protocol):
    """一个原子修复动作。

    实现约定：
      * preview / backup / apply / verify / rollback 各自独立可调用；
      * apply 只做修改，不做校验；校验由 engine 在 apply 之后立即调用 verify；
      * rollback 只在 engine.rollback 里被调用，且必须只依赖备份会话，
        不依赖进程内存（软件重启后仍能回滚）。
    """

    action_id: str

    def preview(self, ctx: Any) -> ChangePreview: ...

    def available(self, ctx: Any) -> tuple[bool, str]:
        """当前系统/环境是否支持该动作。默认支持。

        为什么需要这个探针：`execute()` 的规则是"任一动作备份失败即整轮中止"。
        这个规则本身是对的，但如果某个动作在本机根本不可能成功（例如旧版
        Windows 才有的参数），用户勾了 10 项就会因为 1 项不可用而一项都不执行。
        把不可用判定提前到 plan()，让用户在执行前就知道"这项在你的系统上不需要
        修复"，而不是执行到一半整批中止。
        """
        ...


    def backup(self, store: Any, session: Any, ctx: Any) -> list[str]: ...

    def apply(self, ctx: Any) -> ActionResult: ...

    def verify(self, ctx: Any) -> tuple[bool, str]: ...

    def rollback(self, store: Any, session: Any, ctx: Any) -> ActionResult: ...


# --------------------------------------------------------------------------- #
# 动作基类
# --------------------------------------------------------------------------- #
class BaseAction:
    """所有修复动作的基类，只提供默认实现，不替子类做任何决策。

    存在的理由：`available()` 的默认语义是"支持"，绝大多数动作确实不需要
    覆盖它；把默认值写在一个基类里，比在每个动作里复制一遍或在上层用
    hasattr 探测都要清楚。
    """

    action_id = ""

    def available(self, ctx: Any) -> tuple[bool, str]:
        return True, ""

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.action_id}>"


# --------------------------------------------------------------------------- #
# 注册表
# --------------------------------------------------------------------------- #
ActionFactory = Callable[..., RepairAction]


@dataclass(frozen=True)
class ActionSpec:
    action_id: str
    factory: ActionFactory
    required_params: tuple[str, ...] = ()
    optional_params: tuple[str, ...] = ()

    @property
    def parameterized(self) -> bool:
        return bool(self.required_params)


class ActionRegistry:
    """action_id -> 实现 的登记表。"""

    def __init__(self) -> None:
        self._specs: dict[str, ActionSpec] = {}

    def register(self, spec: ActionSpec) -> None:
        if spec.action_id in self._specs:
            raise RuntimeError(t("err.action_duplicate", id=spec.action_id))
        if spec.action_id not in ACTIONS:
            # 权威清单在 action_ids.py，未登记的动作不允许实现，否则 UI 拿不到标题与风险等级
            raise RuntimeError(t("err.action_unregistered", id=spec.action_id))
        self._specs[spec.action_id] = spec

    def get(self, action_id: str, params: dict[str, Any] | None = None) -> RepairAction:
        spec = self._specs.get(action_id)
        if spec is None:
            raise KeyError(t("err.action_no_impl", id=action_id,
                             list=", ".join(sorted(self._specs))))
        params = dict(params or {})
        missing = [p for p in spec.required_params if p not in params]
        if missing:
            raise ValueError(t("err.action_missing_param", id=action_id,
                               list=", ".join(missing)))
        unknown = set(params) - set(spec.required_params) - set(spec.optional_params)
        if unknown:
            raise ValueError(
                t("err.action_unknown_param", id=action_id,
                  list=", ".join(sorted(unknown)),
                  allowed=", ".join(spec.required_params + spec.optional_params)
                  or t("common.none"))
            )
        return spec.factory(**params)

    def all_actions(self) -> list[RepairAction]:
        """返回全部「无需参数」的动作实例。

        需要构造参数的动作（mtu.optimize）不会出现在这里——它没有可供
        盲猜的默认值，必须由调用方给出实测结果。
        """
        return [s.factory() for s in self._ordered_specs() if not s.parameterized]

    def parameterized_action_ids(self) -> list[str]:
        return [s.action_id for s in self._ordered_specs() if s.parameterized]

    def ids(self) -> list[str]:
        return [s.action_id for s in self._ordered_specs()]

    def spec(self, action_id: str) -> ActionSpec | None:
        return self._specs.get(action_id)

    def _ordered_specs(self) -> list[ActionSpec]:
        return sorted(self._specs.values(), key=lambda s: _order_key(s.action_id))


REGISTRY = ActionRegistry()


def register_action(action_id: str) -> Callable[[ActionFactory], ActionFactory]:
    """类装饰器：把动作类登记进全局注册表。

    构造参数由 __init__ 签名推导：无默认值的必填、有默认值的可选。
    这样 `get(id)` 在缺少必填参数时能给出明确中文提示，而不是 TypeError。
    """

    def decorate(factory: ActionFactory) -> ActionFactory:
        required: list[str] = []
        optional: list[str] = []
        for name, param in inspect.signature(factory.__init__).parameters.items():
            if name == "self" or param.kind in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            ):
                continue
            (optional if param.default is not inspect.Parameter.empty else required).append(name)
        REGISTRY.register(
            ActionSpec(
                action_id=action_id,
                factory=factory,
                required_params=tuple(required),
                optional_params=tuple(optional),
            )
        )
        if getattr(factory, "action_id", None) != action_id:
            factory.action_id = action_id  # type: ignore[attr-defined]
        return factory

    return decorate


# --------------------------------------------------------------------------- #
# 执行顺序与冲突
# --------------------------------------------------------------------------- #
# 顺序原则：
#   1. 无状态、只读性质的操作（清缓存）先做，快速改善用户体感；
#   2. 改配置类（DNS / 代理 / hosts / TCP 参数 / MTU / NetBIOS / 防火墙）居中；
#   3. 会短暂断网的动作（DHCP 续租）靠后，避免前面的动作因断网而校验失败；
#   4. 需要重启的协议栈重置最后，它是"兜底"，不该影响其它动作的 verify。
ACTION_ORDER: tuple[str, ...] = (
    "dns.flush_cache",
    "hosts.clean_bad_lines",
    "hosts.restore_default",
    "proxy.reset",
    "proxy.restore_auto",
    "dns.set_public",
    "dns.restore_dhcp",
    "tcp.autotuning",
    "tcp.heuristics",
    "mtu.optimize",
    "netbios.disable_public",
    "firewall.ensure_enabled",
    "adapter.renew_dhcp",
    "tcp.reset_stack",
    "adapter.reset_stack",
)

# 同一设置被两个动作争抢：同时执行会互相覆盖，最后一个赢，用户看到的结果
# 与他勾选的两个选项都不一致。这类组合一律剔除后者并说明原因。
# 第三个字段是 i18n key（UI 渲染时翻译），不是文案本身。
CONFLICTS: tuple[tuple[str, str, str], ...] = (
    ("dns.set_public", "dns.restore_dhcp", "conflict.dns"),
    ("proxy.reset", "proxy.restore_auto", "conflict.proxy"),
    ("tcp.reset_stack", "adapter.reset_stack", "conflict.reset"),
)


def _order_key(action_id: str) -> tuple[int, str]:
    try:
        return (ACTION_ORDER.index(action_id), action_id)
    except ValueError:
        # 未排序列里的动作放最后，保持确定性
        return (len(ACTION_ORDER), action_id)


def conflict_pairs(action_ids: Sequence[str]) -> list[tuple[str, str, str]]:
    """返回输入里实际命中的冲突组合。第三个元素是 i18n key。"""
    present = set(action_ids)
    hits: list[tuple[str, str, str]] = []
    for a, b, why in CONFLICTS:
        if a in present and b in present:
            hits.append((a, b, why))
    # action_ids.py 里也可能声明 conflicts_with，一并尊重，保证单一清单不失控
    for aid in present:
        meta = ACTIONS.get(aid)
        if not meta:
            continue
        for other in meta.conflicts_with:
            if other in present and (aid, other, "") not in [(x, y, "") for x, y, _ in hits]:
                hits.append((aid, other, "conflict.declared"))
    return hits


# --------------------------------------------------------------------------- #
# 前置条件
# --------------------------------------------------------------------------- #
def require_primary(ctx: Any) -> pw.AdapterInfo:
    """取当前上网网卡，并强制它不是虚拟/隧道适配器。

    为什么必须拦：往 VPN / 虚拟机网卡上写 DNS、MTU、NetBIOS，会破坏用户
    既有的隧道配置，而且这类网卡重启后配置会被驱动重置，等于白改。
    """
    primary = ctx.primary
    if primary is None:
        raise RuntimeError(
            "未找到当前上网网卡（没有已连接且带默认网关/有效 IPv4 的适配器），"
            "请先确认网络连接正常"
        )
    if primary.is_virtual:
        raise RuntimeError(
            f"当前上网网卡「{primary.name}」被识别为虚拟/隧道适配器，"
            f"为避免破坏 VPN 或虚拟机配置，不对其执行修复"
        )
    if not primary.interface_guid:
        raise RuntimeError(f"网卡「{primary.name}」缺少 InterfaceGuid，无法安全定位注册表配置项")
    return primary


def adapter_by_guid(guid: str) -> pw.AdapterInfo | None:
    """按 GUID 重新采集并定位网卡。

    校验必须用硬标识：网卡别名可以被用户随时改名，ifIndex 也可能在驱动
    重装后变化，但 InterfaceGuid 是稳定的。
    """
    if not guid:
        return None
    for adapter in pw.collect_adapters():
        if adapter.interface_guid.lower() == guid.lower():
            return adapter
    return None


def adapter_by_index(if_index: int) -> pw.AdapterInfo | None:
    if not if_index:
        return None
    for adapter in pw.collect_adapters():
        if adapter.if_index == if_index:
            return adapter
    return None


# --------------------------------------------------------------------------- #
# 命令封装 —— 执行与回滚共用
# --------------------------------------------------------------------------- #
# netsh 的一个坑：参数非法时返回码常常仍为 0，只在输出里打印错误，
# 因此"rc==0"不足以证明命令生效，必须同时扫描输出文本。
_NETSH_ERROR_MARKERS = (
    "不是这个指令的有效参数",
    "此命令提供的语法不正确",
    "语法不正确",
    "请求的操作需要提升",
    "命令行参数错误",
    "is not a valid argument",
    "syntax is incorrect",
    "requires elevation",
    "The following command was not found",
    "找不到以下命令",
    "el comando especificado",
    "не является допустимым",
)


def _netsh_failed(out: str) -> str:
    """返回命中的错误标记；没有命中返回空串。"""
    text = (out or "").lower()
    for marker in _NETSH_ERROR_MARKERS:
        if marker.lower() in text:
            return marker
    return ""


def run_or_raise(argv: Sequence[str], *, timeout: float, what: str) -> str:
    """执行命令，非零返回码或 netsh 文本错误都抛带原始输出的中文异常。"""
    rc, out = pw.run_cmd(list(argv), timeout=timeout)
    if rc != 0:
        raise RuntimeError(
            f"{what}失败（返回码 {rc}）。命令：{' '.join(argv)}\n系统输出：{out or '（无输出）'}"
        )
    marker = _netsh_failed(out)
    if marker:
        # 返回码 0 但输出里有错误：按失败处理，否则上层会误记为"已应用"
        raise RuntimeError(
            f"{what}失败（返回码为 0，但系统输出含错误「{marker}」）。"
            f"命令：{' '.join(argv)}\n系统输出：{out[:600] or '（无输出）'}"
        )
    return out


_NETSH_TIMEOUT = 30.0
_REG_TIMEOUT = 40.0


def netsh_dns_static(alias: str, servers: Sequence[str]) -> str:
    """把网卡 DNS 设为静态列表：首条 set，其余 add index=2..n。"""
    if not servers:
        raise ValueError("DNS 服务器列表为空")
    _check_alias(alias)
    out = run_or_raise(
        ["netsh", "interface", "ipv4", "set", "dnsservers",
         f"name={alias}", "source=static", f"address={servers[0]}",
         "register=primary", "validate=no"],
        timeout=_NETSH_TIMEOUT,
        what=f"设置「{alias}」的首选 DNS",
    )
    for idx, server in enumerate(servers[1:], start=2):
        out += run_or_raise(
            ["netsh", "interface", "ipv4", "add", "dnsservers",
             f"name={alias}", f"address={server}", f"index={idx}", "validate=no"],
            timeout=_NETSH_TIMEOUT,
            what=f"设置「{alias}」的第 {idx} 个 DNS（{server}）",
        )
    return out


def netsh_dns_dhcp(alias: str) -> str:
    _check_alias(alias)
    return run_or_raise(
        ["netsh", "interface", "ipv4", "set", "dnsservers", f"name={alias}", "source=dhcp"],
        timeout=_NETSH_TIMEOUT,
        what=f"把「{alias}」的 DNS 恢复为自动获取",
    )


def _check_alias(alias: str) -> None:
    """网卡别名会直接进命令行，先挡掉会破坏参数的字符。

    说明：netsh 的 `name="以太网"` 里引号是 shell 语法；我们用 argv 传参，
    引号由系统自带的命令行解析处理，因此这里只传 `name=<别名>` 本身。
    别名里出现引号/换行才需要拒绝——那种别名不可能由 Windows 生成。
    """
    if not alias or not alias.strip():
        raise ValueError("网卡别名为空，无法执行 netsh 命令")
    if any(ch in alias for ch in ('"', "\r", "\n")):
        raise ValueError(f"网卡别名包含非法字符，拒绝拼接命令：{alias!r}")


_DNS_IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


def read_dns_config(alias: str) -> tuple[list[str], bool]:
    """读取网卡的 DNS 现状，返回 (服务器列表, 是否由 DHCP 下发)。

    备份必须记下 was_dhcp：回滚时"原本是自动获取"和"原本是静态列表"
    走的是两条完全不同的命令，搞错会把用户的手工配置写死。
    """
    out = run_or_raise(
        ["netsh", "interface", "ipv4", "show", "dnsservers", f"name={alias}"],
        timeout=_NETSH_TIMEOUT,
        what=f"读取「{alias}」的 DNS 配置",
    )
    # 中英文输出里 DHCP 分支都会出现 "DHCP" 字样；静态分支不会。
    was_dhcp = "dhcp" in out.lower()
    servers: list[str] = []
    for match in _DNS_IPV4_RE.findall(out):
        if match not in servers:
            servers.append(match)
    return servers, was_dhcp


def netsh_mtu_set(alias: str, mtu: int) -> str:
    _check_alias(alias)
    return run_or_raise(
        ["netsh", "interface", "ipv4", "set", "subinterface", alias,
         f"mtu={int(mtu)}", "store=persistent"],
        timeout=_NETSH_TIMEOUT,
        what=f"设置「{alias}」的 MTU 为 {mtu}",
    )


# --------------------------------------------------------------------------- #
# 防火墙
# --------------------------------------------------------------------------- #
FIREWALL_PROFILES: tuple[tuple[str, str, str], ...] = (
    ("domain", "域配置文件", "Domain Profile"),
    ("private", "专用配置文件", "Private Profile"),
    ("public", "公用配置文件", "Public Profile"),
)

_ON_WORDS = ("on", "启用", "开启", "yes", "是")
_OFF_WORDS = ("off", "关闭", "禁用", "no", "否")


def read_firewall_profiles() -> dict[str, str]:
    """解析 `netsh advfirewall show allprofiles`，返回 {profile: ON/OFF}。

    不做"解析失败就当 OFF"的兜底：错误的备份会导致回滚把本来开着的防火墙
    关掉，这比不备份更危险，所以解析不全一律抛异常。
    """
    out = run_or_raise(
        ["netsh", "advfirewall", "show", "allprofiles"],
        timeout=25,
        what="读取防火墙配置",
    )
    profiles: dict[str, str] = {}
    current: str | None = None
    for line in out.splitlines():
        for key, zh, en in FIREWALL_PROFILES:
            if zh in line or en.lower() in line.lower():
                current = key
                break
        else:
            if current is None:
                continue
            stripped = line.strip()
            matched = re.match(r"^(?:State|状态)\s*[:：]?\s*(\S+)", stripped, re.IGNORECASE)
            if not matched:
                continue
            token = matched.group(1).strip().lower()
            if token in _ON_WORDS:
                profiles[current] = "ON"
            elif token in _OFF_WORDS:
                profiles[current] = "OFF"
    missing = [key for key, _, _ in FIREWALL_PROFILES if key not in profiles]
    if missing:
        raise RuntimeError(
            f"无法从 netsh 输出解析防火墙配置文件 {', '.join(missing)} 的开关状态，"
            f"为避免生成错误备份已中止。原始输出：\n{out[:800]}"
        )
    return profiles


def netsh_firewall_set(profile: str, enabled: bool) -> str:
    if profile not in {key for key, _, _ in FIREWALL_PROFILES}:
        raise ValueError(f"未知的防火墙配置文件: {profile}")
    return run_or_raise(
        ["netsh", "advfirewall", "set", f"{profile}profile", "state",
         "on" if enabled else "off"],
        timeout=25,
        what=f"设置防火墙「{profile}」为 {'开启' if enabled else '关闭'}",
    )


# --------------------------------------------------------------------------- #
# TCP 全局参数
# --------------------------------------------------------------------------- #
def read_tcp_global() -> dict[str, str]:
    """解析 `netsh int tcp show global`，返回 {原始键名: 值}。

    中文系统的键名是本地化的（如"接收窗口自动调谐级别"），所以这里保留
    原始键名，由调用方按关键字匹配，避免给每个语言写一套映射。
    """
    out = run_or_raise(
        ["netsh", "int", "tcp", "show", "global"],
        timeout=25,
        what="读取 TCP 全局参数",
    )
    values: dict[str, str] = {}
    for line in out.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        values[key.strip()] = value.strip()
    return values


def tcp_value(values: dict[str, str], *keywords: str) -> str:
    """按关键字（不区分大小写）取第一项命中的值。"""
    for key, value in values.items():
        text = key.lower()
        if any(kw.lower() in text for kw in keywords):
            return value
    return ""


def netsh_tcp_set(name: str, value: str) -> str:
    return run_or_raise(
        ["netsh", "int", "tcp", "set", "global", f"{name}={value}"],
        timeout=25,
        what=f"设置 TCP 参数 {name}={value}",
    )


# --------------------------------------------------------------------------- #
# 注册表
# --------------------------------------------------------------------------- #
def reg_import(reg_path: str) -> str:
    """把 .reg 备份导回系统。用户也可以直接双击这个文件手工还原。"""
    if not reg_path:
        raise ValueError("注册表备份路径为空")
    return run_or_raise(["reg", "import", reg_path], timeout=_REG_TIMEOUT,
                        what=f"导入注册表备份 {reg_path}")


def capture_registry_or_state(store: Any, session: Any, *, key: str, hive_path: str,
                              label: str, fallback_payload: dict[str, Any]) -> str:
    """优先 reg export；键不存在时退化成结构化状态快照。

    典型场景是 NetBIOS：部分网卡在 NetBT 下没有 Tcpip_{GUID} 子键，
    reg export 会失败。此时必须记录"原本不存在"这个事实，回滚才知道
    应该把值删掉而不是改回某个数。

    为什么退化项的 key 用 `.snapshot` 后缀而不是 `:state`：
    BackupStore.capture_state 直接用 key 拼文件名，而 Windows 文件名里的
    冒号表示 NTFS 备用数据流（ADS）。`a:b:state` 这种双冒号会直接被系统
    拒绝（OSError 22），单冒号也会把数据藏进 ADS，用户打开备份目录看不到。
    冒号只保留在与 action_ids 约定对齐的单层 key 上。
    """
    try:
        store.capture_registry(session, hive_path, key=key, label=label)
        return key
    except (RuntimeError, FileNotFoundError) as exc:
        payload = dict(fallback_payload)
        payload["registry_export_error"] = str(exc)
        payload["hive_path"] = hive_path
        alt_key = f"{key}.snapshot"
        store.capture_state(
            session,
            key=alt_key,
            kind=fallback_payload.get("kind", "state"),
            label=f"{label}（注册表导出不可用，已记录结构化状态）",
            payload=payload,
        )
        return alt_key


# --------------------------------------------------------------------------- #
# 结果构造
# --------------------------------------------------------------------------- #
def failed_result(action_id: str, exc: BaseException, *, started: float = 0.0) -> ActionResult:
    return ActionResult(
        action_id=action_id,
        state=ActionState.FAILED,
        message="执行失败",
        error=f"{type(exc).__name__}: {exc}",
        started_at=started or pw.now(),
        finished_at=pw.now(),
    )


def risk_of(action_id: str) -> RiskLevel:
    meta = ACTIONS.get(action_id)
    return meta.risk if meta else RiskLevel.MEDIUM


def requires_elevation(action_id: str) -> bool:
    meta = ACTIONS.get(action_id)
    return meta.requires_elevation if meta else True


def elevation_blocked(action_id: str, ctx: Any) -> tuple[bool, str]:
    """动作需要管理员权限但当前不是管理员时，返回 (False, 原因)。

    用于 plan() 的可用性判定：执行时会明确失败的动作，不如提前告知用户
    "以管理员身份运行才能修复这一项"。注意这是"降级提示"而非静默跳过——
    原因会原样写进 plan.notes。
    """
    if not requires_elevation(action_id):
        return True, ""
    elevated = bool(getattr(ctx, "elevated", pw.is_elevated()))
    if elevated:
        return True, ""
    return False, "需要管理员权限才能修改系统配置，请以管理员身份重新运行后再修复此项"


__all__ = [
    "ACTION_ORDER",
    "CONFLICTS",
    "FIREWALL_PROFILES",
    "REGISTRY",
    "ActionRegistry",
    "ActionSpec",
    "RepairAction",
    "adapter_by_guid",
    "adapter_by_index",
    "capture_registry_or_state",
    "conflict_pairs",
    "failed_result",
    "netsh_dns_dhcp",
    "netsh_dns_static",
    "netsh_firewall_set",
    "netsh_mtu_set",
    "netsh_tcp_set",
    "read_dns_config",
    "read_firewall_profiles",
    "read_tcp_global",
    "reg_import",
    "register_action",
    "require_primary",
    "requires_elevation",
    "risk_of",
    "run_or_raise",
    "tcp_value",
]
