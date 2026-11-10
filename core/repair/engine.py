"""修复编排层。

这是全软件唯一被允许"动手改系统"的地方。执行流程是硬约束，任何绕过都会
让"可回滚"失效：

    1. store.begin(...)               建会话
    2. 逐个动作 backup()              任一失败 -> 整轮中止，不 apply 任何动作
    3. store.save(session)            备份落盘后才开始改
    4. 逐条 apply() + verify()        单条失败不中断后续（各动作彼此独立）
    5. rollback(session_id)           反序恢复，逐项容错

关于"备份失败即整轮中止"：这是刻意的。如果先改 A 再发现 B 备份不了，A 的
修改就处在"没有完整备份却已生效"的状态，用户按"回滚"也恢复不到原点。
宁可一条都不改，也不要制造半备份的现场。

参数化动作的传参方式见 plan() 的文档字符串。
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Sequence

from .. import platform_win as pw
from ..backup import BackupSession, BackupStore
from ..models import ActionState, ActionResult, ChangePreview
from .base import REGISTRY, RepairAction, conflict_pairs, _order_key
from .rollback import rollback_item

ProgressCb = Callable[[int, int, str, str], None]

# plan() 接受的两种入参形式
ActionRef = str | tuple[str, dict[str, Any]]


# --------------------------------------------------------------------------- #
# 计划
# --------------------------------------------------------------------------- #
@dataclass
class RepairPlan:
    """一轮修复的待执行清单。"""

    action_ids: list[str] = field(default_factory=list)
    params: dict[str, dict[str, Any]] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    skipped_action_ids: list[str] = field(default_factory=list)

    def actions(self) -> list[RepairAction]:
        return [REGISTRY.get(aid, self.params.get(aid)) for aid in self.action_ids]

    def __len__(self) -> int:
        return len(self.action_ids)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_ids": list(self.action_ids),
            "params": {k: dict(v) for k, v in self.params.items()},
            "notes": list(self.notes),
            "skipped_action_ids": list(self.skipped_action_ids),
        }


# --------------------------------------------------------------------------- #
# 报告
# --------------------------------------------------------------------------- #
@dataclass
class RepairReport:
    session_id: str = ""
    session_path: str = ""
    started_at: float = 0.0
    finished_at: float = 0.0
    results: list[ActionResult] = field(default_factory=list)
    partial: bool = False
    rollback_hint: str = ""
    dry_run: bool = False
    aborted: bool = False
    abort_reason: str = ""
    note: str = ""

    @property
    def ok_count(self) -> int:
        return sum(1 for r in self.results if r.state is ActionState.APPLIED)

    @property
    def fail_count(self) -> int:
        return sum(1 for r in self.results
                   if r.state in (ActionState.FAILED, ActionState.ROLLBACK_FAILED))

    @property
    def skipped_count(self) -> int:
        return sum(1 for r in self.results if r.state is ActionState.SKIPPED)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "session_path": self.session_path,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "results": [r.to_dict() for r in self.results],
            "partial": self.partial,
            "rollback_hint": self.rollback_hint,
            "dry_run": self.dry_run,
            "aborted": self.aborted,
            "abort_reason": self.abort_reason,
            "note": self.note,
            "ok_count": self.ok_count,
            "fail_count": self.fail_count,
            "skipped_count": self.skipped_count,
        }


@dataclass
class RollbackReport:
    session_id: str = ""
    started_at: float = 0.0
    finished_at: float = 0.0
    results: list[ActionResult] = field(default_factory=list)
    marked_restored: bool = False
    error: str = ""

    @property
    def ok_count(self) -> int:
        return sum(1 for r in self.results if r.state is ActionState.ROLLED_BACK)

    @property
    def skipped_count(self) -> int:
        """未能/无需恢复的项（含因权限不足被拦下的）。

        与 fail_count 分开统计很重要：UI 需要能说"3 项因权限不足未还原"
        而不是"3 项失败"，后者会让用户以为备份损坏了。
        """
        return sum(1 for r in self.results if r.state is ActionState.SKIPPED)

    @property
    def fail_count(self) -> int:
        return sum(1 for r in self.results
                   if r.state in (ActionState.ROLLBACK_FAILED, ActionState.FAILED))

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "results": [r.to_dict() for r in self.results],
            "ok_count": self.ok_count,
            "fail_count": self.fail_count,
            "skipped_count": self.skipped_count,
            "marked_restored": self.marked_restored,
            "error": self.error,
        }


# --------------------------------------------------------------------------- #
# 引擎
# --------------------------------------------------------------------------- #
class RepairEngine:
    def __init__(self, store: BackupStore | None = None, dry_run: bool = False) -> None:
        self.store = store or BackupStore()
        self.dry_run = bool(dry_run)

    # ------------------------------------------------------------------ #
    # 规划
    # ------------------------------------------------------------------ #
    def plan(self, action_ids: Iterable[ActionRef], ctx: Any, *,
             servers: Sequence[str] | None = None) -> RepairPlan:
        """去重 -> 校验参数 -> 剔除冲突 -> 按依赖顺序排序。

        入参支持两种形式，可混用：
            plan(["dns.flush_cache", "tcp.autotuning"], ctx)
            plan([("mtu.optimize", {"target_mtu": 1400}), "dns.set_public"],
                 ctx, servers=["1.1.1.1", "1.0.0.0"])

        `servers` 是本函数专为 dns.set_public 提供的快捷通道（UI 的 DNS 方案选择
        走这里），等价于给 dns.set_public 传 params={"servers": [...]}。
        """
        if servers is not None:
            if not isinstance(servers, (list, tuple)):
                raise ValueError(f"servers 必须是列表，收到 {type(servers).__name__}")
            if not servers:
                raise ValueError("servers 不能为空列表：至少需要一个 DNS 服务器地址")

        refs = self._normalize_refs(action_ids)
        plan = RepairPlan()
        seen: set[str] = set()

        for action_id, params in refs:
            if action_id in seen:
                plan.notes.append(f"「{action_id}」重复提交，已合并为一条")
                continue
            seen.add(action_id)

            merged = dict(params)
            if action_id == "dns.set_public" and servers is not None:
                if "servers" in merged and list(merged["servers"]) != list(servers):
                    plan.notes.append(
                        "dns.set_public 同时收到 params.servers 与 servers 参数，"
                        "以 servers 为准"
                    )
                merged["servers"] = list(servers)

            spec = REGISTRY.spec(action_id)
            if spec is None:
                plan.skipped_action_ids.append(action_id)
                plan.notes.append(f"「{action_id}」没有修复实现，已跳过")
                continue

            # 构造一次以尽早暴露参数错误。这里对**参数缺失**采取硬失败而不是跳过：
            # mtu.optimize 拿不到实测值就说明上游接线有 bug，静默跳过会掩盖它，
            # 而用猜的值改 MTU 会造成 PMTU 黑洞——两者都比直接报错危险。
            missing = [p for p in spec.required_params if p not in merged]
            if missing:
                if action_id == "mtu.optimize" and "target_mtu" in missing:
                    raise ValueError(
                        "mtu.optimize 需要 target_mtu 参数（1200-1500），当前为 None；"
                        "该参数应由 mtu 检测项的实测结果提供"
                    )
                raise ValueError(
                    f"动作 {action_id} 缺少必需参数 {', '.join(missing)}；"
                    f"请以 ('{action_id}', {{...}}) 的形式传入"
                )
            try:
                action = REGISTRY.get(action_id, merged)
            except (ValueError, KeyError) as exc:
                # 参数存在但取值非法（如 DNS 地址写错、MTU 越界）：同样是硬失败，
                # 否则用户会以为动作执行了而实际什么都没做。
                raise ValueError(f"动作 {action_id} 的参数不合法：{exc}") from exc

            # 可用性探针：本机不支持或"改了也没意义"的动作在此剔除。
            # 必须放在 execute 之前——因为 execute 的规则是"任一备份失败即整轮中止"，
            # 留一个注定失败的动作会让整批修复停在原地。
            try:
                supported, reason = action.available(ctx)
            except Exception as exc:  # noqa: BLE001 - 探针自身异常不应中断规划
                supported, reason = False, f"可用性检测异常（{type(exc).__name__}: {exc}）"
            if not supported:
                plan.skipped_action_ids.append(action_id)
                plan.notes.append(f"「{action_id}」已跳过：{reason or '当前环境不支持'}")
                continue

            plan.action_ids.append(action_id)
            if merged:
                plan.params[action_id] = merged

        # 冲突剔除：保留 ACTION_ORDER 里更靠前的那条，用户选择被完整解释
        for first, second, why in conflict_pairs(plan.action_ids):
            if first not in plan.action_ids or second not in plan.action_ids:
                continue
            keep, drop = sorted((first, second), key=_order_key)
            plan.action_ids.remove(drop)
            plan.params.pop(drop, None)
            plan.skipped_action_ids.append(drop)
            plan.notes.append(f"「{drop}」与「{keep}」冲突（{why}），已保留「{keep}」")

        plan.action_ids.sort(key=_order_key)

        if self.dry_run:
            plan.notes.append("演练模式：只做预览与备份，不会执行任何修改")
        return plan

    @staticmethod
    def _normalize_refs(action_ids: Iterable[ActionRef]) -> list[tuple[str, dict[str, Any]]]:
        if isinstance(action_ids, str):
            raise ValueError(
                "action_ids 必须是列表而不是单个字符串；"
                "传单个动作请写成 ['dns.flush_cache']"
            )
        out: list[tuple[str, dict[str, Any]]] = []
        for ref in action_ids:
            if isinstance(ref, str):
                out.append((ref, {}))
                continue
            if isinstance(ref, (tuple, list)) and len(ref) == 2:
                aid, params = ref
                if not isinstance(aid, str):
                    raise ValueError(f"动作 id 必须是字符串，收到 {aid!r}")
                if params is None:
                    out.append((aid, {}))
                elif isinstance(params, dict):
                    out.append((aid, dict(params)))
                else:
                    raise ValueError(
                        f"动作 {aid} 的参数必须是字典，收到 {type(params).__name__}"
                    )
                continue
            raise ValueError(
                f"无法识别的动作描述: {ref!r}；应为 'action_id' 或 ('action_id', {{...}})"
            )
        return out

    # ------------------------------------------------------------------ #
    # 预览
    # ------------------------------------------------------------------ #
    def preview_all(self, plan: RepairPlan, ctx: Any) -> list[ChangePreview]:
        """为每个动作生成"将要改什么"。

        单个动作的 preview 失败（网卡被拔、netsh 报错）不应拖垮整份清单：
        用一条说明性 ChangePreview 占位，并保留失败原因，让用户知道该项为何不可执行。
        """
        previews: list[ChangePreview] = []
        for action_id in plan.action_ids:
            try:
                action = REGISTRY.get(action_id, plan.params.get(action_id))
                previews.append(action.preview(ctx))
            except Exception as exc:  # noqa: BLE001 - 逐项隔离，UI 需要完整清单
                previews.append(ChangePreview(
                    target=action_id,
                    before="无法读取当前状态",
                    after="该项无法执行",
                    note=f"预览失败：{type(exc).__name__}: {exc}",
                ))
        return previews

    # ------------------------------------------------------------------ #
    # 执行
    # ------------------------------------------------------------------ #
    def execute(self, plan: RepairPlan, ctx: Any, *,
                progress: ProgressCb | None = None) -> RepairReport:
        report = RepairReport(
            started_at=pw.now(),
            dry_run=self.dry_run,
        )
        actions = plan.action_ids
        total = len(actions)

        # --- 1) 建会话 -------------------------------------------------
        note = "、".join(actions) if actions else "无动作"
        report.note = f"本次计划包含 {total} 个动作：{note}"
        session = self.store.begin(kind="修复前自动备份", note=report.note)
        report.session_id = session.session_id
        report.session_path = session.path

        # --- 2) 全部备份，任一失败即中止 --------------------------------
        # 备份前强制刷新网卡快照：备份的语义是"记录被修改那一刻的真实状态"。
        # ctx 的网卡缓存可能来自几分钟前的体检，用它备份会让回滚回到一个
        # 用户早已不处于的过去（mtu.optimize 的首次闭环实测就撞上了这一点）。
        #
        # 这里只容忍"没有这个方法"这一种情况，用 getattr 探测而不是
        # try/except AttributeError：后者会把 refresh_adapters() **内部**
        # 抛出的 AttributeError（例如采集链路里写错属性名）一起静默吞掉，
        # 备份便继续用陈旧快照，正好把这条不变量悄悄退回原状。
        refresh = getattr(ctx, "refresh_adapters", None)
        if refresh is not None:
            refresh()

        for index, action_id in enumerate(actions):
            self._emit(progress, index, total, action_id, "backup")
            try:
                action = REGISTRY.get(action_id, plan.params.get(action_id))
                action.backup(self.store, session, ctx)
            except Exception as exc:  # noqa: BLE001 - 备份失败必须整轮中止
                report.aborted = True
                report.abort_reason = (
                    f"动作「{action_id}」备份失败，因备份失败未做任何修改："
                    f"{type(exc).__name__}: {exc}"
                )
                report.rollback_hint = (
                    "没有任何动作被应用，系统未被修改，无需回滚。"
                    f"备份会话 {session.session_id} 已保留（仅含部分快照），"
                    f"建议排查失败原因后重试。"
                )
                report.finished_at = pw.now()
                return report

        # --- 3) 备份落盘 ------------------------------------------------
        self.store.save(session)

        if self.dry_run:
            report.finished_at = pw.now()
            report.rollback_hint = (
                f"演练模式：未执行任何修改。备份会话 {session.session_id} 已创建，"
                f"路径 {session.path}（可用于确认备份链路完整，但无需回滚）"
            )
            return report

        if not actions:
            report.finished_at = pw.now()
            report.rollback_hint = (
                f"本次没有可执行的动作，未做任何修改；"
                f"备份会话 {session.session_id} 仅作审计记录（无备份项）"
            )
            return report

        # --- 4) 逐条 apply + verify ------------------------------------
        failures = 0
        for index, action_id in enumerate(actions):
            action = REGISTRY.get(action_id, plan.params.get(action_id))
            result = ActionResult(action_id=action_id, started_at=pw.now())

            self._emit(progress, index, total, action_id, "apply")
            try:
                applied = action.apply(ctx)
            except Exception as exc:  # noqa: BLE001 - 单条失败不中断整轮
                result.state = ActionState.FAILED
                result.message = "执行失败"
                result.error = f"{type(exc).__name__}: {exc}"
                result.finished_at = pw.now()
                report.results.append(result)
                failures += 1
                continue

            # 部分动作会直接返回 SKIPPED，此时不再 verify（没有改动可校验）
            if applied.state is ActionState.SKIPPED:
                applied.action_id = action_id
                report.results.append(applied)
                continue

            self._emit(progress, index, total, action_id, "verify")
            applied.action_id = action_id
            try:
                verified, message = action.verify(ctx)
                applied.verified = bool(verified)
                applied.detail.append(f"校验：{message}")
                if not verified:
                    # 命令成功了但读回不对：如实记为失败，不掩饰
                    applied.state = ActionState.FAILED
                    applied.error = f"校验未通过：{message}"
                    failures += 1
            except Exception as exc:  # noqa: BLE001 - 校验失败是失败，不是崩溃
                applied.verified = False
                applied.state = ActionState.FAILED
                applied.error = f"校验阶段异常：{type(exc).__name__}: {exc}"
                failures += 1
            report.results.append(applied)

        # --- 5) 收尾 ---------------------------------------------------
        report.finished_at = pw.now()
        report.partial = failures > 0
        if report.partial:
            report.rollback_hint = (
                f"本轮有 {failures} 个动作未能完成或校验未通过，"
                f"建议回滚本次备份会话 {session.session_id} 以恢复原状。"
                f"备份路径：{session.path}"
            )
        else:
            report.rollback_hint = (
                f"全部动作已完成并通过校验。若需撤销，可回滚备份会话 "
                f"{session.session_id}（路径：{session.path}）"
            )
        return report

    @staticmethod
    def _emit(progress: ProgressCb | None, index: int, total: int,
              action_id: str, phase: str) -> None:
        if progress is None:
            return
        progress(index, total, action_id, phase)

    # ------------------------------------------------------------------ #
    # 回滚
    # ------------------------------------------------------------------ #
    def rollback(self, session_id: str, ctx: Any) -> RollbackReport:
        """反序恢复整个备份会话。

        反序的原因：后备份的状态是"最新被覆盖前"的状态，先恢复它才是正确顺序。
        例如先改 DNS（备份 A）再改 MTU（备份 B），恢复时必须先 B 再 A。

        单项失败不中断：恢复尽可能多的状态，优于因第一项失败而全部放弃。
        """
        report = RollbackReport(session_id=session_id, started_at=pw.now())
        try:
            session = self.store.load(session_id)
        except FileNotFoundError as exc:
            report.error = str(exc)
            report.finished_at = pw.now()
            return report

        if not session.items:
            report.finished_at = pw.now()
            report.error = "该会话没有备份项（可能只包含无状态动作），无可恢复内容"
            return report

        # 提权状态算一次即可：items 可能有十几项，每项都去问一次系统没必要。
        # 非管理员时会话里需要写 HKLM / 跑 netsh 的项会被标为 SKIPPED 并说明原因，
        # 而不是标成"失败"——后者会让用户以为备份文件坏了。
        elevated = pw.is_elevated()
        for item in reversed(session.items):
            report.results.append(rollback_item(self.store, session, ctx, item,
                                                elevated=elevated))

        report.finished_at = pw.now()
        # 只有全部恢复成功（或本就不需要恢复）才标记还原。部分失败时保持"未还原"，
        # 用户才能看到它还能在提权后重试一次，而不是被误标为已完成。
        if elevated and report.fail_count == 0:
            self.store.mark_restored(session)
            report.marked_restored = True
        return report


# --------------------------------------------------------------------------- #
# 手工备份
# --------------------------------------------------------------------------- #
def create_manual_backup(store: BackupStore, ctx: Any) -> BackupSession:
    """不执行任何修改，只把"当前可修复项涉及的状态"全部抓一份快照。

    用途：用户在做危险操作（改注册表、装驱动）之前，"先存一份能退回去的现场"。
    与修复前自动备份走同一套 capture 调用，所以恢复能力完全一致。

    单项采集失败不中止整体：手工备份的价值在于"尽量多存一点"，
    但每个失败都必须写进会话 note，让用户知道哪一项没存下来。
    """
    session = store.begin(kind="手工备份", note="用户主动创建的系统状态快照")
    failures: list[str] = []
    captured: list[str] = []
    # 不同动作会备份同一个底层对象（tcp.reset_stack 与 adapter.reset_stack 都备份
    # tcpip / winsock2，hosts 两个动作都备份 hosts）。手工备份若不去重，同一份
    # 状态会被采集成多个条目，回滚时就重复执行同一条恢复命令。
    seen_keys: set[str] = set()

    for action_id in REGISTRY.ids():
        spec = REGISTRY.spec(action_id)
        if spec is None or spec.parameterized:
            # 需要参数的动作（mtu.optimize）无法在不知道目标值的情况下构造；
            # 但 MTU 的当前值本身就是需要备份的状态，这里单独处理。
            continue
        try:
            action = REGISTRY.get(action_id)
            before_count = len(session.items)
            keys = action.backup(store, session, ctx)
            # backup() 内部已经把条目追加进 session.items，因此去重必须在事后修剪。
            # 只修剪「本次调用新追加的那一段」，否则会把早先动作合法的同类条目一起删掉。
            newly_added = session.items[before_count:]
            kept: list[Any] = []
            for item in newly_added:
                if item.key in seen_keys:
                    continue  # 与更早的动作重复，丢弃这一份
                seen_keys.add(item.key)
                kept.append(item)
                if item.key not in captured:
                    captured.append(item.key)
            session.items = session.items[:before_count] + kept
        except Exception as exc:  # noqa: BLE001 - 手工备份要尽力而为，逐项记录
            failures.append(f"{action_id}: {type(exc).__name__}: {exc}")

    store.save(session)

    # mtu.optimize 无参构造会拒绝执行（刻意的），所以它的"当前 MTU"备份在此单独做：
    # 手工备份的目的不是改 MTU，而是记录当前值以便将来核对。
    try:
        primary = ctx.primary
        if primary is not None and primary.mtu:
            store.capture_state(
                session,
                key=f"mtu:{primary.interface_guid}",
                kind="mtu",
                label=f"{primary.name} 的 MTU（手工备份记录）",
                payload={
                    "interface_guid": primary.interface_guid,
                    "interface_index": primary.if_index,
                    "alias": primary.name,
                    "mtu": int(primary.mtu),
                },
            )
            captured.append(f"mtu:{primary.interface_guid}")
    except Exception as exc:  # noqa: BLE001
        failures.append(f"mtu.snapshot: {type(exc).__name__}: {exc}")

    if failures:
        session.note = (
            f"手工备份（部分项目未成功，共 {len(captured)} 项）：\n" + "\n".join(failures)
        )
    else:
        session.note = f"手工备份成功，共 {len(captured)} 项状态快照"

    store.save(session)
    return session


__all__ = [
    "ActionRef",
    "ProgressCb",
    "RepairEngine",
    "RepairPlan",
    "RepairReport",
    "RollbackReport",
    "create_manual_backup",
]
