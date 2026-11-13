"""中文语言包。

约定：
  * 所有面向用户的字符串都走 core.i18n.t()；
  * 检测/修复结果对象（CheckResult / Metric / ChangePreview / ActionResult）
    里存的是 **key**，由 app/ui/i18n_ui.tr_or_raw() 在渲染时翻译；
  * 含 {占位符} 的 key 在两种语言里的占位符集合必须一致（tests/test_i18n.py 校验）。
"""
from __future__ import annotations

CATALOG: dict[str, str] = {
    # ------------------------------------------------------------------ #
    # 应用外壳
    # ------------------------------------------------------------------ #
    "app.name": "LanPulse",
    "app.brand": "LANPULSE",
    "app.tagline": "网络体检与一键修复",

    "nav.overview": "总览",
    "nav.dns": "DNS 优化",
    "nav.hosts": "HOSTS 管理",
    "nav.repair": "一键修复",
    "nav.backup": "备份与回滚",
    "nav.diagnose": "诊断详情",
    "nav.report": "报告与日志",
    "nav.settings": "设置",

    "side.admin": "已获得管理员权限",
    "side.unprivileged": "普通权限运行\n部分修复不可用",

    # ------------------------------------------------------------------ #
    # 严重度 / 风险
    # ------------------------------------------------------------------ #
    "sev.ok": "正常",
    "sev.info": "提示",
    "sev.warn": "异常",
    "sev.critical": "严重",
    "sev.skip": "跳过",

    "risk.low": "低风险",
    "risk.medium": "中风险",
    "risk.high": "高风险",

    # ------------------------------------------------------------------ #
    # 通用词
    # ------------------------------------------------------------------ #
    "common.none": "无",
    "common.unknown": "未知",
    "common.empty": "（空）",
    "common.truncated": "…（已截断）",

    # 列表分隔符：中文用全角标点，英文用半角 + 空格
    "sep.summary": "；",
    "sep.list": "、",

    "status.ready": "就绪",
    "status.scanning": "正在体检…",
    "status.scan_done": "体检完成｜{n} 项｜健康分 {score}",
    "status.score": "健康分 {score}",
    "status.rolling_back": "正在回滚…",
    "status.task_failed": "任务失败",
    "status.detecting": "正在检测：{name}",
    "status.summarizing": "正在汇总结果…",
    "status.creating_backup": "正在创建备份…",
    "status.phase_backup": "备份",
    "status.phase_apply": "执行",
    "status.phase_verify": "校验",
    "status.progress": "{phase}：{action}",
    "status.yes": "是",
    "status.no": "否",
    "status.on": "开启",
    "status.off": "关闭",
    "status.enabled": "已启用",
    "status.disabled": "未启用",
    "status.success": "成功",
    "status.failed": "失败",
    "status.available": "可用",
    "status.listening": "监听中",
    "status.no_listener": "无进程监听",
    "status.not_configured": "未配置",
    "status.not_run": "未执行",
    "status.not_measured": "未测出",
    "status.no_response": "无响应",
    "status.unreachable": "不通",
    "status.connectable": "可连接",
    "status.unset": "未设置",
    "status.empty_paren": "（空）",
    "status.empty_all_proxy": "（空，全部走代理）",
    "status.direct_access": "直接访问",
    "status.direct_unset": "未设置（直连）",

    "value.static_manual": "静态手工指定",
    "value.static": "静态",
    "value.dhcp": "DHCP",
    "value.dhcp_auto": "DHCP 自动获取",
    "value.dhcp_issued": "DHCP 自动下发",
    "value.manual_specified": "手动指定",
    "value.overseas_only": "仅境外",
    "value.private": "私有地址",
    "value.public": "公网地址",
    "value.no_ip": "无 IP",
    "value.no_dns": "无 DNS",
    "value.no_primary_adapter": "（未识别主网卡）",
    "value.empty": "—",
    "value.bytes": "{n} 字节",
    "value.bytes_signed": "{n:+d} 字节",
    "value.seconds": "{n} 秒",
    "value.ms": "{n}ms",
    "value.dnsapi": "Windows DnsQuery API",
    "value.getaddrinfo": "socket.getaddrinfo 回退",
    "value.remote": "远程",
    "value.inconsistent": "不一致",
    "value.consistent": "一致",
    "value.inbound_unknown": "入站策略未知",
    "value.not_from_adapter": "未从网卡读取到",
    "value.not_read": "未读取到",
    "value.netsh_subifaces": "netsh 子接口表",
    "value.mtu_source_adapter": "{name}（Get-NetAdapter）",

    "grade.excellent": "优秀",
    "grade.normal": "正常",
    "grade.slow": "偏慢",
    "grade.very_slow": "极慢",
    "grade.high_latency": "高延迟",
    "grade.icmp_blocked": "目标禁 ICMP 或不可达",

    # ------------------------------------------------------------------ #
    # 按钮
    # ------------------------------------------------------------------ #
    "btn.scan": "开始网络体检",
    "btn.scanning": "正在体检…",
    "btn.repair": "一键修复",
    "btn.apply_plan": "应用所选方案",
    "btn.restore_dhcp": "恢复自动获取",
    "btn.reload": "重新读取",
    "btn.advanced_edit": "高级编辑",
    "btn.exit_edit": "退出编辑",
    "btn.discard_edit": "放弃修改",
    "btn.save_hosts": "保存（自动备份）",
    "btn.clean_hosts": "清理异常记录",
    "btn.clean_hosts_n": "清理异常记录（{n}）",
    "btn.restore_default": "恢复系统默认",
    "btn.select_none": "全不选",
    "btn.select_safe": "只选低风险",
    "btn.dry_run": "先演练",
    "btn.execute": "执行修复",
    "btn.execute_high": "执行修复（含 {n} 项高风险）",
    "btn.open_backup_dir": "打开备份目录",
    "btn.new_backup": "手动创建备份",
    "btn.rollback_session": "恢复到此次备份状态",
    "btn.rollback_to": "恢复到 {time} 的状态",
    "btn.no_restorable": "该备份无可恢复内容",
    "btn.export_html": "导出 HTML 报告",
    "btn.export_json": "导出 JSON",
    "btn.export_text": "导出 TXT",
    "btn.refresh": "刷新",
    "btn.yes": "是",
    "btn.no": "取消",
    "btn.close": "关闭",
    "btn.confirm_save": "确认保存",
    "btn.confirm_execute": "确认执行",
    "btn.confirm_rollback": "确认回滚",
    "btn.restart_admin": "以管理员身份重启",
    "btn.env_check": "环境自检",

    # ------------------------------------------------------------------ #
    # 仪表盘
    # ------------------------------------------------------------------ #
    "page.dashboard.headline_empty": "尚未体检",
    "page.dashboard.metrics_title": "当前网络状态",
    "page.dashboard.metrics_sub": "数据来自最近一次体检的快照",
    "page.dashboard.problems_title": "发现的问题",
    "page.dashboard.problems_empty": "体检后这里会列出需要处理的项",
    "page.dashboard.problems_ok": "没有发现需要处理的网络问题 ✓",
    "page.dashboard.entry_title": "功能入口",
    "page.dashboard.entry.dns.title": "DNS 优化中心",
    "page.dashboard.entry.dns.desc": "查看当前 DNS、测速、切换公共 DNS 或恢复自动获取",
    "page.dashboard.entry.hosts.title": "HOSTS 管理",
    "page.dashboard.entry.hosts.desc": "可视化查看与编辑 HOSTS，识别屏蔽与劫持记录",
    "page.dashboard.entry.backup.title": "备份与回滚",
    "page.dashboard.entry.backup.desc": "所有系统修改前的快照都在这里，可随时一键还原",
    "page.dashboard.entry.report.title": "诊断报告",
    "page.dashboard.entry.report.desc": "导出 HTML / JSON / TXT 报告，记录本次体检全部证据",
    "page.dashboard.footnote": "所有检测与修复均在本机完成，不联网上传任何数据。"
                               "每项系统修改前都会自动备份，可在「备份与回滚」中随时还原。",
    "page.dashboard.all_ok": "共检测 {n} 项，全部正常",
    "page.dashboard.has_problems": "共检测 {n} 项，发现 {k} 个问题",
    "page.dashboard.hostname": "主机名",
    "page.dashboard.admin": "管理员权限",
    "page.dashboard.elevated": "已提权",
    "page.dashboard.not_elevated": "普通权限（部分修复不可用）",
    "page.dashboard.gauge.ok": "网络状态良好",
    "page.dashboard.gauge.info": "基本正常",
    "page.dashboard.gauge.warn": "存在问题",
    "page.dashboard.gauge.critical": "需要处理",
    "page.dashboard.gauge.skip": "检测受限",
    "page.dashboard.gauge.waiting": "等待检测",
    "page.dashboard.fix_tip": "根据体检结果执行修复；执行前会展示完整改动清单并自动备份",

    "widget.health_score": "HEALTH SCORE",
    "widget.waiting_sample": "等待采样",

    # ------------------------------------------------------------------ #
    # DNS 页
    # ------------------------------------------------------------------ #
    "page.dns.subtitle": "域名解析服务决定你访问网站走哪条路，是“网页打不开”的首要排查点",
    "page.dns.current_title": "当前 DNS 配置",
    "page.dns.current_sub": "读取自当前承载上网流量的网卡",
    "page.dns.current_hint": "体检后显示当前 DNS 服务器",
    "page.dns.section_plans": "选择方案",
    "page.dns.apply_servers": "将把当前上网网卡的 DNS 改为 {servers}。"
                              "修改前会自动备份原配置，可在「备份与回滚」中还原。",
    "page.dns.apply_dhcp": "将把 DNS 恢复为由 DHCP 自动下发。修改前会自动备份原配置。",
    "page.dns.plan_dhcp_servers": "由路由器 / DHCP 服务器自动下发",
    "page.dns.not_included": "本次体检未包含 DNS 检测项",
    "page.dns.no_servers": "未配置或自动获取",
    "page.dns.iface": "作用网卡",
    "page.dns.advice": "· {text}",

    # ------------------------------------------------------------------ #
    # HOSTS 页
    # ------------------------------------------------------------------ #
    "hosts.warn": "⚠ 直接编辑 HOSTS 存在风险：错误内容可能导致部分网站无法访问。"
                  "保存前会自动备份当前文件，可在「备份与回滚」中还原。",
    "hosts.tip": "清理只移除「屏蔽」与「劫持」两类记录，其余行原样保留；"
                 "恢复默认会把整个文件替换为系统模板，自定义记录将全部丢失。",
    "hosts.col_line": "行",
    "hosts.col_ip": "IP 地址",
    "hosts.col_domains": "域名",
    "hosts.col_verdict": "判定",
    "hosts.read_error": "无法读取 HOSTS 文件：{err}",
    "hosts.status_ok": "文件正常：{n} 条有效映射，未发现可疑记录。",
    "hosts.status_warn": "{n} 条有效映射，其中 {blocked} 条为屏蔽记录"
                         "（常见于广告过滤 / 破解补丁），若对应网站打不开可清理。",
    "hosts.status_critical": "发现 {hijacked} 条疑似劫持记录，{blocked} 条屏蔽记录，"
                             "建议立即清理并全盘杀毒。",
    "hosts.risk.normal": "正常",
    "hosts.risk.blocked": "屏蔽",
    "hosts.risk.hijacked": "疑似劫持",
    "hosts.note.blocked": "屏蔽该域名（广告过滤或破解补丁常见做法）",
    "hosts.note.hijacked": "关键域名（{domains}）被指向 {ip}，{effect}",
    "hosts.note.hijack_blocked": "会被屏蔽",
    "hosts.note.hijack_hijack": "可能被劫持",
    "hosts.empty": "此 HOSTS 文件没有任何自定义映射（仅含注释与空行），这通常是正常的默认状态。",
    "hosts.unchanged": "内容未变化，无需保存。",
    "hosts.judge": "{label}｜{note}",

    # ------------------------------------------------------------------ #
    # 修复页
    # ------------------------------------------------------------------ #
    "page.repair.subtitle": "根据体检结果自动勾选，你可以逐项调整；高危项默认不勾选",
    "page.repair.pledge": "🔒 执行前会自动备份所有将被修改的配置，备份位置与内容完全对本机可见。"
                          "任一步骤失败都不会中断其它步骤，且随时可在「备份与回滚」还原到本次执行前。",
    "page.repair.empty": "先做一次网络体检，系统会在这里列出建议的修复项。",
    "page.repair.nothing": "本次体检未发现需要修复的问题，无需执行修复 ✓",
    "page.repair.selected": "已选 {n} 项",
    "page.repair.selected_high": "已选 {n} 项，其中 {high} 项为高风险",
    "page.repair.none_selected": "尚未选择任何修复项",
    "page.repair.state.pending": "待执行",
    "page.repair.state.applied": "✓ 已生效",
    "page.repair.state.skipped": "已跳过",
    "page.repair.state.failed": "✗ 失败",
    "page.repair.state.rolled_back": "已回滚",
    "page.repair.state.rollback_failed": "回滚失败",
    "page.repair.state.unverified": "已执行（校验未通过）",
    "page.repair.state.with_message": "{text}｜{message}",
    "page.repair.preview": "{target}：{before}  →  {after}",
    "page.repair.unknown_action": "未知动作（{id}）",
    "page.repair.unknown_action_desc": "该动作未在 core/action_ids.py 中登记，"
                                       "可能为版本不一致，请勿执行。",
    "page.repair.dry_tip": "完整走一遍备份与预览流程，但不会修改任何系统设置",
    "page.repair.confirm_head": "即将执行 {n} 项修复：",
    "page.repair.confirm_item": "  • [{risk}] {title}",
    "page.repair.confirm_backup": "执行前会自动创建备份会话（位置：{path}）。",
    "page.repair.confirm_high": "注意：其中 {n} 项为高风险操作，可能需要重启计算机才能完全生效。",
    "page.repair.confirm_ask": "是否继续？",
    "page.repair.confirm_title": "确认执行修复",

    # ------------------------------------------------------------------ #
    # 备份页
    # ------------------------------------------------------------------ #
    "backup.warn": "回滚只会还原备份中记录的项目，不会影响备份之后你对系统做的其它修改。",
    "backup.pick_hint": "选择左侧备份查看详情",
    "backup.count": "共 {n} 个备份会话",
    "backup.col_time": "时间",
    "backup.col_kind": "类型",
    "backup.col_summary": "内容",
    "backup.restored_suffix": "（已还原）",
    "backup.no_changes": "（无持久化状态变更）",
    "backup.not_restorable": "该会话未记录可恢复的状态，仅作为操作审计留痕",
    "backup.empty_title": "还没有任何备份。",
    "backup.empty_hint": "每次执行修复前系统会自动创建备份；"
                         "你也可以点右上角「手动创建备份」先存一份当前网络配置快照。",
    "backup.created": "创建时间",
    "backup.host": "主机",
    "backup.privilege": "备份时权限",
    "backup.privilege_admin": "管理员",
    "backup.privilege_user": "普通用户",
    "backup.restored_once": "已于 {time} 还原过一次",
    "backup.items": "备份内容（{n} 项）",
    "backup.no_persist": "本次操作不涉及持久化配置，仅记录审计留痕。",
    "backup.dir": "目录：{path}",
    "backup.confirm_title": "确认回滚",
    "backup.confirm_body": "将把以下 {n} 项配置恢复到 {time} 的状态：\n\n{items}",
    "backup.confirm_more": "\n  …",
    "backup.confirm_tail": "回滚过程中网络可能短暂中断。是否继续？",
    "backup.open_fail_title": "无法打开目录",
    "backup.new_tip": "在修改任何设置前，先手动存一份当前网络配置快照",

    # ------------------------------------------------------------------ #
    # 诊断页
    # ------------------------------------------------------------------ #
    "page.diagnose.col_check": "检测项",
    "page.diagnose.col_status": "状态",
    "page.diagnose.col_summary": "结论",
    "page.diagnose.col_duration": "耗时",
    "page.diagnose.pick": "选择左侧任一项查看详情",
    "page.diagnose.meta": "共 {n} 项｜{host}｜{time}",
    "page.diagnose.chip_tip": "{label} {n} 项",
    "page.diagnose.section_metrics": "指标",
    "page.diagnose.section_advice": "建议",
    "page.diagnose.section_evidence": "原始证据",
    "page.diagnose.error": "执行异常：{err}",

    # ------------------------------------------------------------------ #
    # 报告页
    # ------------------------------------------------------------------ #
    "report.export_title": "导出本机体检报告",
    "report.export_sub": "报告仅包含本机网络配置与检测结论，不含任何个人数据，可安全分享给维修人员",
    "report.not_yet": "尚未体检",
    "report.tip_html": "单文件网页，含完整证据，适合发给他人",
    "report.tip_json": "结构化数据，适合程序处理或存档",
    "report.tip_text": "纯文本，适合粘贴进工单",
    "report.audit_title": "操作审计流水",
    "report.filter.all": "全部事件",
    "report.filter.repair": "修复执行",
    "report.filter.rollback": "回滚",
    "report.filter.backup": "备份",
    "report.col_time": "时间",
    "report.col_event": "事件",
    "report.col_target": "操作",
    "report.col_result": "结果",
    "report.count": "｜{n} 条记录",
    "report.ok": "成功",
    "report.fail": "失败",
    "report.summary": "最近一次体检：{time}｜主机 {host}｜共 {n} 项检测｜"
                      "健康分 {score}｜发现 {k} 个问题",
    "report.summary_unelevated": "｜以普通权限运行，部分项目未检测",

    # ------------------------------------------------------------------ #
    # 设置页
    # ------------------------------------------------------------------ #
    "settings.section.general": "通用",
    "settings.section.scan": "检测",
    "settings.section.backup": "备份",
    "settings.section.safety": "安全",
    "settings.section.report": "报告",
    "settings.section.data": "数据管理",
    "settings.language.title": "界面语言",
    "settings.language.desc": "切换后立即生效，无需重启程序",
    "settings.language.auto": "跟随系统",
    "action.needs_restart": "⚠ 需重启才能生效；回滚只在重启前有效",
    "settings.region.title": "网络区域",
    "settings.region.desc": "决定检测时使用哪一组探测目标与推荐 DNS",
    "settings.region.auto": "自动识别",
    "settings.region.auto_hint": "根据时区、系统语言与实测延迟自动判断当前区域。",
    "settings.region.detected": "当前识别为「{region}」",
    "settings.region.basis": "依据：{basis}",
    "settings.region.basis.timezone": "系统时区 {tz}",
    "settings.region.basis.latency_cn": "实测延迟倾向中国大陆（国内锚点 {cn} ms）",
    "settings.region.basis.latency_not_cn": "实测延迟倾向境外（全球锚点 {gl} ms）",
    "settings.region.basis.locale": "系统语言",
    "settings.region.basis.none": "无法获取时区与延迟，已回退到最宽松的剖面",
    "settings.region.shared_tz": "中国大陆、香港、澳门共用同一时区，仅凭时区无法区分，"
                                "此处的判断依赖系统地区码。识别不对可直接在上方手动选择。",
    "settings.region.fixed_hint": "已固定为「{region}」，检测目标与推荐方案都使用该区域。",
    "settings.autoscan.title": "启动时自动体检",
    "settings.autoscan.desc": "打开软件后自动跑一次完整检测",
    "settings.probe.title": "允许联网探测",
    "settings.probe.desc": "关闭后只读取本机配置，不做任何网络请求（会跳过连通性与 MTU 实测）",
    "settings.timeout.title": "探测超时倍数",
    "settings.timeout.desc": "网络较慢的地区可调大，避免正常慢速被误判为故障",
    "settings.backupkeep.title": "备份保留数量",
    "settings.backupkeep.desc": "超过该数量的旧备份会话会被自动清理",
    "settings.highrisk.title": "高风险动作额外确认",
    "settings.highrisk.desc": "执行高危修复前要求再次确认",
    "settings.reportfmt.title": "默认报告格式",
    "settings.reportfmt.desc": "在报告页点导出时使用的默认格式",
    "settings.reportfmt.html": "HTML（单文件网页）",
    "settings.reportfmt.json": "JSON（结构化数据）",
    "settings.reportfmt.text": "TXT（纯文本）",
    "settings.evidence.title": "报告包含原始证据",
    "settings.evidence.desc": "关闭后报告更精简，但排障时看不到原始命令输出",
    "settings.open_data": "打开数据目录",
    "settings.open_settings": "打开配置文件",
    "settings.reset": "恢复默认设置",
    "settings.reset.confirm.title": "恢复默认设置",
    "settings.reset.confirm.body": "将把全部设置恢复为默认值，包括界面语言与网络区域。\n\n是否继续？",
    "lang.zh": "中文",
    "lang.en": "English",

    # ------------------------------------------------------------------ #
    # 审计事件
    # ------------------------------------------------------------------ #
    "audit.scan": "网络体检",
    "audit.export_target": "{fmt} 报告",
    "audit.backup": "手动备份",
    "audit.hosts_edit": "HOSTS 手工编辑",
    "audit.hosts_edit_detail": "已保存并备份，会话 {session}",
    "audit.repair": "一键修复",
    "audit.rollback": "回滚备份",
    "audit.counts": "成功 {ok}，失败 {fail}",

    # ------------------------------------------------------------------ #
    # 消息框
    # ------------------------------------------------------------------ #
    "msg.scan_first": "请先完成一次网络体检",
    "msg.busy": "正在执行其它任务，请稍候",
    "msg.need_admin": "该操作需要管理员权限，请先点「以管理员身份重启」",
    "msg.need_admin_hosts": "修改 HOSTS 需要管理员权限",
    "msg.hosts_save_title": "确认保存 HOSTS",
    "msg.hosts_save_body": "将用编辑后的内容覆盖 HOSTS 文件。\n\n"
                           "保存前会自动备份当前文件，可在「备份与回滚」中还原。\n"
                           "错误的内容可能导致部分网站无法访问。\n\n是否保存？",
    "msg.backup_done": "已创建备份快照",
    "msg.hosts_saved": "HOSTS 已保存，原始文件已备份",
    "msg.task_failed_title": "任务失败",
    "msg.task_failed_body": "操作未能完成：\n\n{err}\n\n"
                            "若反复出现，请到「报告与日志」导出诊断报告。",
    "msg.dryrun_title": "演练完成",
    "msg.dryrun_body": "演练未修改任何系统设置。\n\n已创建备份会话：{session}\n"
                       "共 {n} 项动作，全部通过备份阶段校验。\n\n"
                       "确认无误后可直接点「执行修复」。",
    "msg.repair_title": "修复完成",
    "msg.repair_head": "执行完成：成功 {ok} 项",
    "msg.repair_fail": "，失败 {fail} 项",
    "msg.repair_partial": "⚠ 部分动作未成功，建议到「备份与回滚」回滚本次会话。",
    "msg.repair_session": "备份会话：{session}",
    "msg.rollback_title": "回滚结果",
    "msg.rollback_head": "回滚完成：成功 {ok} 项",
    "msg.rollback_partial": "部分项目未能还原，详情见下方与 report 日志。",
    "msg.export_ok_title": "导出成功",
    "msg.export_ok_body": "报告已保存到：\n{path}",
    "msg.export_fail_title": "导出失败",
    "msg.export_fail_body": "无法生成报告：\n{err}",
    "msg.elevate_cancelled_title": "已取消",
    "msg.elevate_cancelled_body": "未获得管理员权限，软件将以只读模式继续运行。\n"
                                  "体检、报告导出、备份查看仍然可用。",
    "msg.unavailable": "不可用",
    "msg.elevate_unavailable": "提权模块不可用：{err}",
    "msg.env_unavailable": "环境自检模块不可用：{err}",
    "msg.env_fail": "自检失败",
    "msg.env_title": "环境自检",
    "msg.env_heading": "运行环境自检",
    "msg.exit_title": "任务进行中",
    "msg.exit_body": "仍有任务在执行，立即退出可能中断系统修改并留下未完成的配置。\n\n确定退出？",
    "msg.no_report": "还没有体检结果，先做一次体检",

    "err.open_failed": "无法打开文件",

    # ------------------------------------------------------------------ #
    # 指标名（值/说明可以是 key，也可以是渲染后的文本）
    # ------------------------------------------------------------------ #
    "metric.link_speed": "链路速率",
    "metric.adapter_count": "适配器总数",
    "metric.primary_adapter": "当前上网网卡",
    "metric.ipv4": "IPv4 地址",
    "metric.gateway": "默认网关",
    "metric.ping_target": "IPv4 直连 {target}",
    "metric.loss_rate": "外网丢包率",
    "metric.tcp_target": "TCP {host}:{port}",
    "metric.dns_resolve": "DNS 解析",
    "metric.total_budget": "整轮预算",
    "metric.probe_domains": "探测域名数",
    "metric.avg_resolve_ms": "平均解析耗时",
    "metric.min_max_ms": "最快/最慢",
    "metric.resolve_via": "解析方式",
    "metric.interface": "所在网卡",
    "metric.dns_count": "DNS 服务器数量",
    "metric.config_mode": "配置方式",
    "metric.loopback_dns": "本机 DNS 监听",
    "metric.dns_route": "DNS 线路",
    "metric.dns_owner": "DNS 归属",
    "metric.dhcp_issued": "DHCP 下发",
    "metric.return_code": "命令返回码",
    "metric.is_admin": "当前是否管理员",
    "metric.profile_firewall": "{profile}防火墙",
    "metric.route_count": "默认路由条数",
    "metric.adapter_gateway": "网卡上报网关",
    "metric.active_gateway": "生效网关",
    "metric.multi_gateway": "多默认网关",
    "metric.gateway_latency": "网关延迟",
    "metric.gateway_loss": "网关丢包率",
    "metric.file_path": "文件路径",
    "metric.file_size": "文件大小",
    "metric.total_lines": "总行数",
    "metric.mapping_lines": "有效映射行",
    "metric.blocked_records": "屏蔽型记录",
    "metric.hijack_records": "劫持型记录",
    "metric.suspicious_total": "可疑记录合计",
    "metric.up_adapters": "已连接网卡",
    "metric.current_adapter": "当前网卡",
    "metric.acquire_mode": "获取方式",
    "metric.address_type": "地址类型",
    "metric.gateway_same_subnet": "网关同网段",
    "metric.ipv4_dns_count": "IPv4 DNS 服务器",
    "metric.configured_mtu": "当前配置 MTU",
    "metric.measured_mtu": "实测路径 MTU",
    "metric.probe_target": "测试目标地址",
    "metric.probe_attempts": "探测次数",
    "metric.mtu_gap": "配置与实测差值",
    "metric.registry_path": "注册表路径",
    "metric.proxy_enable": "代理开关",
    "metric.proxy_server": "代理服务器",
    "metric.proxy_override": "绕过列表",
    "metric.auto_config_url": "自动配置脚本",
    "metric.winhttp_proxy": "WinHTTP 代理",
    "metric.pac_reachable": "自动配置脚本可达",
    "metric.local_proxy": "本地代理 {host}:{port}",
    "metric.remote_proxy": "代理服务器 {host}:{port}",
    "metric.consistency": "WinHTTP 与 WinINET 一致性",
    "metric.tcp_global_rc": "tcp 全局参数命令返回码",
    "metric.ip_global_rc": "ip 全局参数命令返回码",
    "metric.autotuning": "接收窗口自动调节",
    "metric.ecn": "ECN",
    "metric.rss": "RSS 接收端缩放",
    "metric.timestamps": "TCP 时间戳",
    "metric.scaling_heuristics": "窗口缩放启发式",
    "metric.param_count": "参数条目数",

    # ------------------------------------------------------------------ #
    # DNS 归属 / 区域 / 方案
    # ------------------------------------------------------------------ #
    "dns.vendor.aliyun": "阿里云公共 DNS",
    "dns.vendor.tencent": "腾讯 DNSPod",
    "dns.vendor.dns114": "114DNS",
    "dns.vendor.baidu": "百度 DNS",
    "dns.vendor.bytedance": "字节跳动 DNS",
    "dns.vendor.chinatelecom": "中国电信 DNS",
    "dns.vendor.chinamobile": "中国移动 DNS",
    "dns.vendor.google": "Google Public DNS",
    "dns.vendor.cloudflare": "Cloudflare",
    "dns.vendor.quad9": "Quad9",
    "dns.vendor.opendns": "OpenDNS",
    "dns.vendor.adguard": "AdGuard DNS",
    "dns.vendor.controld": "Control D",
    "dns.vendor.yandex": "Yandex DNS",
    "dns.vendor.korea": "韩国公共 DNS",
    "dns.vendor.jp": "日本公共 DNS",
    "dns.vendor.hk": "香港公共 DNS",
    "dns.vendor.mo": "澳门公共 DNS",
    "dns.vendor.tw": "台湾中华电信 DNS",
    "dns.vendor.sg": "新加坡公共 DNS",
    "dns.vendor.in": "印度公共 DNS",
    "dns.vendor.au": "澳洲公共 DNS",
    "dns.vendor.eu": "欧洲公共 DNS",
    "dns.vendor.na": "北美公共 DNS",
    "dns.vendor.custom": "自定义 / 运营商",

    "dns.owner.aliyun": "阿里公共 DNS",
    "dns.owner.tencent": "腾讯 DNSPod",
    "dns.owner.dns114": "114DNS",
    "dns.owner.baidu": "百度公共 DNS",
    "dns.owner.google": "Google Public DNS（境外）",
    "dns.owner.cloudflare": "Cloudflare DNS（境外）",
    "dns.owner.quad9": "Quad9（境外）",
    "dns.owner.opendns": "OpenDNS（境外）",
    "dns.owner.chinatelecom": "电信/360 公共 DNS",
    "dns.owner.ct": "电信公共 DNS",
    "dns.owner.bytedance": "字节跳动公共 DNS",
    "dns.owner.onedns": "OneDNS",
    "dns.owner.loopback": "内网 DNS（路由器或运营商）",
    "dns.owner.custom": "自定义/运营商 DNS",

    "dns.plan.ali_tencent.name": "阿里 + 腾讯",
    "dns.plan.ali_tencent.tag": "推荐 · 国内最快",
    "dns.plan.ali_tencent.desc": "国内 CDN 解析最准，延迟低，不会被解析到海外节点。"
                                "适合绝大多数家庭宽带。",
    "dns.plan.dns114.name": "114 DNS",
    "dns.plan.dns114.tag": "稳定 · 老牌",
    "dns.plan.dns114.desc": "运营商级 DNS，覆盖广、可用性非常稳定，抗污染能力一般。",
    "dns.plan.global_public.name": "Cloudflare + Google",
    "dns.plan.global_public.tag": "境外 · 需谨慎",
    "dns.plan.global_public.desc": "隐私保护最好，但国内解析可能被调度到海外节点，"
                                   "实际访问反而变慢。",
    "dns.plan.quad9.name": "Quad9",
    "dns.plan.quad9.tag": "安全 · 拦截恶意域名",
    "dns.plan.quad9.desc": "自动拦截已知恶意域名，隐私保护较好；国内直连延迟偏高。",
    "dns.plan.opendns.name": "OpenDNS",
    "dns.plan.opendns.tag": "内容过滤",
    "dns.plan.opendns.desc": "提供内容过滤与家长控制；国内直连延迟偏高。",
    "dns.plan.hk_local.name": "香港本地 DNS",
    "dns.plan.hk_local.tag": "本地 · 香港",
    "dns.plan.hk_local.desc": "香港本地运营商 DNS，港内访问解析更快；离港后可能变慢。",
    "dns.plan.mo_local.name": "澳门本地 DNS",
    "dns.plan.mo_local.tag": "本地 · 澳门",
    "dns.plan.mo_local.desc": "澳门只有 CTM 与 MTel 两家固网运营商，本地 DNS 解析最准；国际访问通常经香港出口，离澳后可能变慢。",
    "dns.plan.tw_local.name": "中华电信 DNS",
    "dns.plan.tw_local.tag": "本地 · 台湾",
    "dns.plan.tw_local.desc": "台湾本地解析最准，岛内 CDN 就近；访问大陆站点时可能绕行。",
    "dns.plan.jp_local.name": "日本本地 DNS",
    "dns.plan.jp_local.tag": "本地 · 日本",
    "dns.plan.jp_local.desc": "日本本地公共 DNS，日文站点与本地 CDN 解析更准。",
    "dns.plan.kr_local.name": "韩国本地 DNS",
    "dns.plan.kr_local.tag": "本地 · 韩国",
    "dns.plan.kr_local.desc": "韩国本地公共 DNS，韩文站点解析更快、更准。",
    "dns.plan.sg_local.name": "新加坡本地 DNS",
    "dns.plan.sg_local.tag": "本地 · 新加坡",
    "dns.plan.sg_local.desc": "新加坡本地运营商 DNS，东南亚区域内解析更近。",
    "dns.plan.in_local.name": "印度本地 DNS",
    "dns.plan.in_local.tag": "本地 · 印度",
    "dns.plan.in_local.desc": "印度本地公共 DNS，南亚区域解析更近；国际线路质量波动较大。",
    "dns.plan.au_local.name": "澳洲本地 DNS",
    "dns.plan.au_local.tag": "本地 · 澳洲",
    "dns.plan.au_local.desc": "澳洲本地公共 DNS，大洋洲解析更近；跨洋访问仍取决于上游线路。",
    "dns.plan.eu_local.name": "欧盟公共 DNS",
    "dns.plan.eu_local.tag": "隐私优先 · 欧盟境内",
    "dns.plan.eu_local.desc": "服务器位于欧盟境内，受 GDPR 约束，查询日志留存政策更透明。",
    "dns.plan.na_local.name": "北美公共 DNS",
    "dns.plan.na_local.tag": "本地 · 北美",
    "dns.plan.na_local.desc": "北美本地公共 DNS，美洲范围内解析更近。",
    "dns.plan.dhcp.name": "自动获取（路由器下发）",
    "dns.plan.dhcp.tag": "回退方案",
    "dns.plan.dhcp.desc": "恢复为由路由器 / DHCP 自动分配。"
                          "接入公司、校园网或使用运营商 DNS 时选这个。",

    "region.cn": "中国大陆",
    "region.hk": "中国香港",
    "region.mo": "中国澳门",
    "region.tw": "中国台湾",
    "region.jp": "日本",
    "region.kr": "韩国",
    "region.sg": "新加坡 / 东南亚",
    "region.in": "印度 / 南亚",
    "region.au": "澳大利亚 / 新西兰",
    "region.na": "北美",
    "region.eu": "欧洲",
    "region.other": "其他地区",

    "probe.aliyun": "阿里云 DNS",
    "probe.tencent": "腾讯 DNS",
    "probe.cloudflare": "Cloudflare",
    "probe.google": "Google DNS",
    "probe.quad9": "Quad9",
    "probe.tw": "中华电信 DNS",
    "probe.korea": "韩国公共 DNS",
    "probe.jp": "日本公共 DNS",
    "probe.sg": "新加坡公共 DNS",
    "probe.in": "印度公共 DNS",
    "probe.au": "澳洲公共 DNS",

    "env.vpn_active": "检测到 VPN / 隧道虚拟网卡",
    "env.proxy": "系统代理已启用",
    "env.ipv6_only": "仅获取到 IPv6 地址",
    "env.captive_portal": "需要网页登录（认证门户）",

    # ------------------------------------------------------------------ #
    # 检测单元：注册表兜底
    # ------------------------------------------------------------------ #
    "check.registry.summary_failed": "检测未完成",
    "check.registry.detail_failed": "该检测项执行失败，已跳过。\n原因：{err}",

    # ------------------------------------------------------------------ #
    # 检测单元：adapter
    # ------------------------------------------------------------------ #
    "check.adapter.title": "网卡与链路状态",
    "check.adapter.category": "链路",
    "check.adapter.summary_none": "未发现任何网络适配器",
    "check.adapter.detail_none": "系统没有报告可用的网络适配器。若为虚拟机或刚重装系统，"
                                 "请先确认网卡驱动已正确安装。",
    "check.adapter.problem.all_down": "所有网络适配器均处于断开状态",
    "check.adapter.problem.virtual_only": "只有虚拟或隧道适配器处于连接状态，物理网卡未连接",
    "check.adapter.problem.no_ipv4": "已连接的网卡没有可用的 IPv4 地址或默认网关",
    "check.adapter.problem.apipa": "网卡拿到的是 APIPA 地址 {ip}，"
                                   "说明 DHCP 未能分配地址，当前无法正常上网",
    "check.adapter.summary_ok": "网卡链路正常，已连接到网络",
    "check.adapter.advice.device_manager": "在设备管理器中检查网络适配器是否有黄色感叹号",
    "check.adapter.advice.check_cable": "检查网线 / Wi-Fi 开关，确认路由器已通电",
    "check.adapter.advice.physical_disabled": "确认物理网卡是否被禁用，或是否有虚拟网卡抢占了路由",
    "check.adapter.advice.apipa": "点击「一键修复」中的重新获取 IP 地址，或检查路由器 DHCP 是否开启",
    "check.adapter.note.adapter_count": "已连接 {up} / 虚拟 {virtual}",
    "check.adapter.detail.line": "• {name}｜{status}｜{ip}{virtual}",
    "check.adapter.detail.virtual": "｜虚拟",

    # ------------------------------------------------------------------ #
    # 检测单元：ip
    # ------------------------------------------------------------------ #
    "check.ip.title": "IP 地址配置",
    "check.ip.category": "链路",
    "check.ip.summary_none": "没有可用的网络连接，无法获取 IPv4 地址",
    "check.ip.detail_none": "所有网卡都未连接，或已连接但没有 IPv4 地址。",
    "check.ip.note.up_adapters": "共 {n} 块",
    "check.ip.problem.no_ipv4": "网卡「{name}」没有 IPv4 地址",
    "check.ip.problem.apipa": "网卡拿到的是 APIPA 地址 {ip}，说明 DHCP 未分配地址，当前无法上网",
    "check.ip.problem.invalid_prefix": "子网前缀 {n} 不合法，无法判断网段归属",
    "check.ip.problem.gw_diff": "网关 {gw} 与本机 {ip}/{prefix}（网段 {net}）不在同一网段，"
                                "流量可能发不出去",
    "check.ip.summary_ok": "IPv4 配置正常：{ip}/{prefix}（{mode}），网关同网段",
    "check.ip.advice.connect": "插好网线或打开 Wi-Fi，确认路由器已通电",
    "check.ip.advice.regain": "点击「重新获取 IP 地址」，或检查路由器 DHCP 是否开启",
    "check.ip.advice.apipa": "先确认路由器 DHCP 已开启；仍失败时用「重新获取 IP 地址」重置租约",
    "check.ip.advice.invalid_prefix": "把网卡 IP 改为自动获取，或按路由器网段重新填写",
    "check.ip.advice.gw_diff": "核对掩码是否填错；家用网络应为 255.255.255.0（/24）",
    "check.ip.note.apipa": "APIPA 自动专用地址",
    "check.ip.note.network": "网段 {net}",
    "check.ip.note.prefix_invalid": "前缀长度异常",
    "check.ip.note.nat": "内网出口经 NAT 转换",
    "check.ip.note.public_direct": "直接持有公网地址",
    "check.ip.detail.line": "• {name}｜{status}｜{ip}/{prefix}｜{mode}｜网关 {gw}",

    # ------------------------------------------------------------------ #
    # 检测单元：gateway
    # ------------------------------------------------------------------ #
    "check.gateway.title": "默认网关与路由",
    "check.gateway.category": "链路",
    "check.gateway.summary_skip": "无法读取路由表，已跳过网关检测",
    "check.gateway.detail_skip": "`route print -4` 返回码 {rc}，输出：{out}",
    "check.gateway.problem.no_route": "路由表里没有 0.0.0.0 默认路由，本机只能访问同网段设备",
    "check.gateway.problem.multi_route": "存在 {n} 条默认路由，"
                                         "流量可能走错网卡（VPN / 虚拟网卡抢占）",
    "check.gateway.problem.gw_slow": "网关延迟 {ms}ms 偏高，内网链路质量差",
    "check.gateway.problem.gw_mid": "网关延迟 {ms}ms，略高于有线网络常见水平",
    "check.gateway.problem.gw_icmp": "网关 {gw} 未响应 ping"
                                     "（多数路由器默认禁 ICMP，属正常配置，不代表链路故障）",
    "check.gateway.summary_ok": "默认网关 {gw} 配置正常",
    "check.gateway.summary_ok_extra": "默认网关 {gw} 配置正常，另有 {n} 条备用默认路由",
    "check.gateway.summary_ok_nogw": "路由表无可解析的默认网关，但网卡已上报网关",
    "check.gateway.advice.no_route": "检查网卡是否拿到网关；必要时重新获取 IP 地址",
    "check.gateway.advice.high_metric": "默认路由 metric 偏高，"
                                        "若有其它网卡在同时联网请确认出口是否正确",
    "check.gateway.advice.multi_route": "断开不用的 VPN 或虚拟网卡，或调整网卡跃点数",
    "check.gateway.advice.gw_slow": "有线网络请检查网线/水晶头；无线请靠近路由器或换 5GHz 频段",
    "check.gateway.note.route_count": "route print -4 中的 0.0.0.0/0",
    "check.gateway.note.route_count_fail": "命令未成功返回",
    "check.gateway.note.route": "metric {metric}｜出接口 {interface}",
    "check.gateway.note.multi": "{gw}(metric {metric})",
    "check.gateway.note.loss": "丢包 {loss}%",
    "check.gateway.note.icmp": "网关禁 ICMP 属正常，不代表链路故障",
    "check.gateway.detail.route": "• 默认路由 → {gw}｜出接口 {interface}｜metric {metric}",
    "check.gateway.detail.no_route": "• 未发现 0.0.0.0 默认路由",

    # ------------------------------------------------------------------ #
    # 检测单元：dns_server
    # ------------------------------------------------------------------ #
    "check.dns_server.title": "DNS 服务器配置",
    "check.dns_server.category": "DNS",
    "check.dns_server.problem.no_dns": "网卡「{interface}」没有配置任何 IPv4 DNS 服务器，"
                                       "除 HOSTS 里写死的域名外都无法解析",
    "check.dns_server.problem.invalid_addr": "DNS 配置里有无效地址 {ip}",
    "check.dns_server.problem.loopback": "DNS 指向本机回环地址 {ip}，"
                                         "但本机 53 端口没有 DNS 服务在监听，解析请求会直接失败",
    "check.dns_server.problem.too_many": "配置了 {n} 个 DNS 服务器，"
                                         "过多会拖慢解析失败时的切换",
    "check.dns_server.problem.overseas": "DNS 全部为境外公共服务器，"
                                         "国内直连时单次解析常在 100ms 以上",
    "check.dns_server.summary_ok": "DNS 配置正常（{mode}）：{head}",
    "check.dns_server.advice.restore_dhcp": "把 DNS 改为自动获取；"
                                            "若接的是公司/校园网，向网管确认内网 DNS 地址",
    "check.dns_server.advice.invalid_addr": "把 DNS 改为自动获取，或填公共 DNS（223.5.5.5）",
    "check.dns_server.advice.loopback": "DNS 残留多见于卸载过的代理/加速软件；改为自动获取即可恢复",
    "check.dns_server.advice.too_many": "保留 2 个常用 DNS 即可",
    "check.dns_server.advice.overseas": "如感觉网页打开慢，可换成阿里 223.5.5.5 或腾讯 119.29.29.29",
    "check.dns_server.note.loopback_on": "{ip}:53 有服务",
    "check.dns_server.note.loopback_off": "{ip}:53 无服务",
    "check.dns_server.note.overseas": "国内直连境外 DNS 单次解析可能 100ms 以上",
    "check.dns_server.note.owner_custom": "其中 {n} 个非已知公共 DNS",
    "check.dns_server.note.owner_known": "全部为已知公共 DNS",
    "check.dns_server.note.dhcp": "由路由器分配，接入新网络时会自动更新",
    "check.dns_server.detail.owner": "• {ip} → {owner}",
    "check.dns_server.detail.iface": "• {name}：{servers}",
    "check.dns_server.owner_pair": "{ip}={owner}",
    "check.dns_server.owner_pair_full": "{ip}（{owner}）",

    # ------------------------------------------------------------------ #
    # 检测单元：dns_resolve
    # ------------------------------------------------------------------ #
    "check.dns_resolve.title": "域名解析与响应速度",
    "check.dns_resolve.category": "DNS",
    "check.dns_resolve.summary_skip": "未能在时间预算内发出任何 DNS 查询，本项已跳过",
    "check.dns_resolve.detail_skip": "整轮预算 {budget} 秒已被耗尽，没有产出可判定的样本。",
    "check.dns_resolve.summary_ok": "域名解析正常：{n} 个域名平均耗时 {ms}ms（{grade}）",
    "check.dns_resolve.summary_ok_noms": "{n} 个域名解析成功",
    "check.dns_resolve.problem.all_fail": "{n} 个探测域名全部解析失败，"
                                          "域名打不开但 IP 直连可能正常",
    "check.dns_resolve.problem.avg_very_slow": "平均解析耗时 {ms}ms，已严重拖慢网页打开",
    "check.dns_resolve.problem.avg_slow": "平均解析耗时 {ms}ms，偏慢（正常应 < {limit}ms）",
    "check.dns_resolve.problem.partial": "{n} 个域名解析失败，可能是单条 DNS 记录异常",
    "check.dns_resolve.problem.hijacked": "{n} 个域名被解析到无效地址"
                                          "（疑似被 HOSTS 屏蔽或 DNS 劫持）：{names}",
    "check.dns_resolve.advice.flush": "先试「清空 DNS 缓存」；仍失败改用公共 DNS（223.5.5.5）",
    "check.dns_resolve.advice.switch_public": "切换为公共 DNS 通常可立刻改善",
    "check.dns_resolve.advice.try_ali_tencent": "可换成阿里 223.5.5.5 / 腾讯 119.29.29.29 对比效果",
    "check.dns_resolve.advice.check_hosts": "检查 HOSTS 文件是否存在屏蔽记录；如无则说明 DNS 被劫持",
    "check.dns_resolve.note.probe_domains": "成功 {ok} / 失败 {fail}",
    "check.dns_resolve.detail.ok": "• {name} → {ips}（{ms}ms）",
    "check.dns_resolve.detail.fail": "• {name} → 解析失败：{err}",
    "check.dns_resolve.no_a_record": "（无 A 记录）",
    "err.resolve_timeout": "解析超时（>{sec}s）",
    "err.dnsquery_rc": "DnsQuery 返回码 {rc}（{text}）",
    "err.dnsapi_unavailable": "dnsapi 不可用",
    "err.no_a_record": "未返回任何 A 记录",

    "rc.0": "成功",
    "rc.9003": "域名不存在（NXDOMAIN）",
    "rc.9002": "DNS 服务器故障（SERVFAIL）",
    "rc.9501": "无此记录",
    "rc.1460": "操作超时",
    "rc.11001": "无法解析主机",
    "rc.11002": "无法解析，服务器未响应",
    "rc.11003": "非恢复性错误",
    "rc.11004": "无数据记录",
    "rc.unknown": "未知错误",

    # ------------------------------------------------------------------ #
    # 检测单元：hosts
    # ------------------------------------------------------------------ #
    "check.hosts.title": "HOSTS 文件",
    "check.hosts.category": "解析",
    "check.hosts.summary_read_error": "HOSTS 文件无法读取：{err}",
    "check.hosts.detail_read_error": "路径 {path}\n原因：{err}\n"
                                     "常见于安全软件锁定或文件权限被改；"
                                     "域名解析将退化为纯 DNS 查询。",
    "check.hosts.advice.admin_notepad": "用管理员权限打开记事本检查 "
                                        "%SystemRoot%\\System32\\drivers\\etc\\hosts",
    "check.hosts.problem.hijacked": "发现 {n} 条大站域名被改写的记录（{names}），"
                                    "会导致对应网站打不开或跳到错误地址",
    "check.hosts.problem.blocked": "做了 {n} 条域名屏蔽"
                                   "（这是广告拦截/破解补丁的常见做法，不是系统故障，"
                                   "但会屏蔽对应站点）",
    "check.hosts.problem.near_empty": "HOSTS 文件几乎为空，可能被清空或替换"
                                      "（系统默认至少含 localhost 记录）",
    "check.hosts.problem.zero": "HOSTS 文件是 0 字节，已被清空",
    "check.hosts.summary_ok": "HOSTS 正常：{n} 条自定义映射，未发现屏蔽或劫持记录",
    "check.hosts.advice.clean": "清理 HOSTS 中的异常记录；"
                                "若你确实装了广告拦截/破解补丁，请自行核对这些条目",
    "check.hosts.advice.blocked": "若某个网站打不开且不是网络问题，先看这里是否屏蔽了它",
    "check.hosts.advice.restore": "用「恢复默认 HOSTS」还原；本操作会先备份原文件",
    "check.hosts.note.mapping_lines": "被 # 注释或空行不计入",
    "check.hosts.note.blocked": "映射到 0.0.0.0 / 127.0.0.1 等黑洞地址",
    "check.hosts.note.hijacked": "常见大站域名被改写",
    "check.hosts.reason.blackhole": "映射到黑洞地址 {ip}，等于屏蔽该域名",
    "check.hosts.reason.watched": "命中常见大站域名 {name}，正常不应出现在 HOSTS 里",
    "check.hosts.detail.suspicious_head": "可疑记录（最多展示 {n} 条）：",
    "check.hosts.detail.suspicious_line": "  {line}: {raw}  ｜{reason}",
    "check.hosts.detail.more": "  ……另有 {n} 条",
    "check.hosts.detail.none": "未发现可疑记录。",
    "check.hosts.detail.entries_head": "全部有效映射 {n} 条：",
    "check.hosts.detail.entry": "  {line}: {ip} {hosts}",

    # ------------------------------------------------------------------ #
    # 检测单元：proxy
    # ------------------------------------------------------------------ #
    "check.proxy.title": "系统代理设置",
    "check.proxy.category": "代理",
    "check.proxy.summary_skip": "无法读取系统代理设置（注册表不可访问），本项已跳过",
    "check.proxy.detail_skip": "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\"
                               "Internet Settings 读取失败。"
                               "该键通常任何账户都可读，失败多为注册表被安全软件保护。",
    "check.proxy.summary_direct": "未使用系统代理，网络直连（正常）",
    "check.proxy.summary_auto_only": "系统代理已关闭，仅使用自动配置脚本",
    "check.proxy.summary_ok": "系统代理已启用且对应服务在监听，配置正常",
    "check.proxy.problem.pac_fail": "PAC 自动配置脚本不可访问：{url}",
    "check.proxy.problem.dead": "系统代理指向本机 {addrs}，但该端口没有任何程序在监听；"
                                "浏览器会把全部请求发给这个死端口，表现为完全无法上网",
    "check.proxy.problem.empty": "系统代理开关已启用，但代理服务器地址为空，"
                                 "浏览器无法发出任何请求",
    "check.proxy.problem.local_alive": "正在使用本地代理 {addrs}"
                                       "（代理软件运行中，属正常状态）",
    "check.proxy.problem.remote": "使用远程代理 {addrs}，若无法上网请确认该代理服务可用",
    "check.proxy.problem.pac_lost": "PAC 自动配置脚本不可访问，代理规则可能已失效",
    "check.proxy.advice.pac": "若不需要 PAC，可在「Internet 选项 → 连接 → 局域网设置」中取消勾选",
    "check.proxy.advice.dead": "如果是代理软件意外退出：重新打开它，"
                               "或用「关闭残留的系统代理」改回直连",
    "check.proxy.advice.empty": "用「关闭残留的系统代理」把设置改回直连",
    "check.proxy.advice.consistency": "如遇「浏览器能用、命令行不能用」，多为这两处不一致所致",
    "check.proxy.note.endpoints": "{n} 个端点",
    "check.proxy.note.proxy_running": "代理软件正在运行",
    "check.proxy.note.proxy_dead": "代理软件已退出但系统代理未清除",
    "check.proxy.note.remote": "非本机代理，未做连通性探测",
    "check.proxy.note.consistency": "系统更新、部分命令行工具走 WinHTTP，"
                                    "可能不遵循浏览器代理",
    "check.proxy.detail.enable": "• 代理开关：{value}",
    "check.proxy.detail.server": "• 代理服务器：{value}",
    "check.proxy.detail.override": "• 绕过列表：{value}",
    "check.proxy.detail.pac": "• 自动配置脚本：{value}",
    "check.proxy.detail.winhttp": "• WinHTTP：{value}",
    "check.proxy.detail.endpoints": "• 解析出的端点：{list}",
    "err.file_missing": "文件不存在：{path}",
    "err.connect_failed": "无法连接 {host}:{port}（{err}）",
    "err.unsupported_protocol": "不支持的协议：{url}",

    # ------------------------------------------------------------------ #
    # 检测单元：tcp
    # ------------------------------------------------------------------ #
    "check.tcp.title": "TCP/IP 协议栈参数",
    "check.tcp.category": "协议栈",
    "check.tcp.summary_broken": "TCP/IP 协议栈状态无法读取，协议栈可能已损坏",
    "check.tcp.detail_broken": "{reason}。\n"
                               "正常情况下这两条命令都会输出完整的全局参数表；"
                               "返回失败或空表通常意味着 Winsock/协议栈注册项异常。",
    "check.tcp.reason.cmd_rc": "`netsh int ip show global` 返回码 {rc}",
    "check.tcp.reason.parse_fail": "`netsh int tcp show global` 输出为空或无法解析",
    "check.tcp.advice.reset": "先执行「重置 TCP/IP 协议栈」，重启后再体检一次",
    "check.tcp.note.autotuning_unknown": "未从输出中识别到该参数",
    "check.tcp.note.autotuning_ok": "允许窗口随带宽时延积自动放大",
    "check.tcp.note.autotuning_bad": "被限制，高延迟链路吞吐会下降",
    "check.tcp.note.ecn": "拥塞显式通知，关闭属常见默认值，不影响正常上网",
    "check.tcp.note.rss": "多核分担收包，关闭会限制高带宽上限",
    "check.tcp.note.timestamps": "RFC1323 时间戳，用于 RTT 测量与防序号回绕",
    "check.tcp.note.scaling": "disabled 为推荐值（Windows 默认）",
    "check.tcp.note.param_count": "取自 netsh int tcp show global",
    "check.tcp.problem.autotuning_bad": "接收窗口自动调节被设为 {value}，"
                                        "高延迟链路（跨省/出国）下载速度会明显下降",
    "check.tcp.problem.autotuning_unknown": "未能从命令输出中识别出接收窗口自动调节级别",
    "check.tcp.advice.autotuning": "恢复为 normal：这是 Windows 默认值，"
                                   "绝大多数『优化教程』改它都是负优化",
    "check.tcp.advice.heuristics": "窗口缩放启发式为 enabled；"
                                   "但当前 Windows 版本已不再使用该参数，"
                                   "修改它不会产生任何效果，无需处理",
    "check.tcp.advice.rss": "RSS 关闭会限制千兆以上带宽上限；若为省电而关可忽略",
    "check.tcp.summary_ok": "协议栈参数正常（接收窗口自动调节 {auto}）",
    "check.tcp.summary_ok_scaling": "协议栈参数正常（接收窗口自动调节 {auto}，"
                                    "窗口缩放启发式 {scaling}）",
    "check.tcp.detail.kv": "• {key}：{value}",
    "check.tcp.detail.heuristics": "窗口缩放启发式：",

    # ------------------------------------------------------------------ #
    # 检测单元：mtu
    # ------------------------------------------------------------------ #
    "check.mtu.title": "MTU 与分片",
    "check.mtu.category": "协议栈",
    "check.mtu.summary_not_measured": "路径 MTU 未实测（{reason}），当前配置 MTU {value}",
    "check.mtu.detail_not_measured": "未能完成路径 MTU 实测：{reason}\n"
                                     "当前配置值：{value}。\n"
                                     "实测依赖目标回显 ICMP，很多公网地址与防火墙会丢弃 echo 包，"
                                     "这属于正常现象，不代表网络异常。",
    "check.mtu.problem.cfg_gt_pmtu": "配置 MTU {cfg} 大于实测路径 MTU {pmtu}（差 {gap} 字节），"
                                     "大包会被静默丢弃，存在 PMTU 黑洞风险",
    "check.mtu.problem.cfg_lt_pmtu": "配置 MTU {cfg} 小于实测路径 MTU {pmtu}，"
                                     "链路利用率略低但不影响可用性",
    "check.mtu.problem.no_cfg": "未读到网卡配置 MTU，实测路径 MTU 为 {pmtu}",
    "check.mtu.summary_ok": "MTU 正常：配置 {cfg}，实测路径 {pmtu}"
                            "（差 {gap:+d} 字节，在 {tol} 字节容差内）",
    "check.mtu.advice.probe": "如需精确结果，可对局域网网关或自己的服务器做 ping -f -l 探测",
    "check.mtu.advice.optimize": "把网卡 MTU 调整为实测值；"
                                 "PPPoE 拨号常见 1492，VPN 常见 1420 以下",
    "check.mtu.advice.raise": "可选：把 MTU 调回实测值以获得更好的大文件吞吐",
    "check.mtu.note.probe_target": "探测目标 {target}",
    "check.mtu.note.attempts": "预算 {n} 次 / {sec} 秒",
    "check.mtu.note.gap": "阈值 {n} 字节",
    "check.mtu.note.target_unused": "ICMP 被禁或无法到达时不做实测",
    "check.mtu.detail.ok": "• 探测目标：{target}\n"
                           "• 共 {n} 次 DF 探测，最大不分片 payload {payload} 字节\n"
                           "• 路径 MTU = payload + {overhead}（IP 头 20 + ICMP 头 8）= {mtu}",
    "check.mtu.skip.budget": "已用满探测时间预算",
    "check.mtu.skip.no_icmp": "{ip} 无 ICMP 响应",
    "check.mtu.skip.no_target": "所有探测目标均无响应",
    "check.mtu.skip.too_small": "payload {n} 字节即无法通过（路径 MTU < 1428）",

    # ------------------------------------------------------------------ #
    # 检测单元：firewall
    # ------------------------------------------------------------------ #
    "check.firewall.title": "Windows 防火墙",
    "check.firewall.category": "安全",
    "check.firewall.summary_denied": "需要管理员权限才能读取完整防火墙状态，本项已跳过",
    "check.firewall.reason.denied": "命令返回访问被拒",
    "check.firewall.reason.rc": "命令返回码 {rc}，未拿到有效输出",
    "check.firewall.hint.user": "当前以普通用户身份运行，读取防火墙全局状态需要管理员权限。",
    "check.firewall.hint.admin": "已以管理员身份运行，但仍读取失败；多为安全软件接管了防火墙。",
    "check.firewall.detail_denied": "{reason}。{hint}\n"
                                    "这不代表防火墙异常，只是本工具拿不到判断依据。\n"
                                    "输出片段：{out}",
    "check.firewall.advice.denied": "以管理员身份重新运行体检，"
                                    "或打开「Windows 安全中心 → 防火墙和网络保护」自查",
    "check.firewall.summary_unparsed": "无法解析防火墙状态输出，本项已跳过",
    "check.firewall.detail_unparsed": "`netsh advfirewall show allprofiles` "
                                      "的输出未包含可识别的配置块。\n输出片段：{out}",
    "check.firewall.summary_no_state": "未能从输出中识别出各配置文件的开关状态，本项已跳过",
    "check.firewall.detail_no_state": "`netsh advfirewall show allprofiles` 输出中"
                                      "没有可解析的 State/状态 行。\n输出片段：{out}",
    "check.firewall.summary_all_off": "三个网络配置文件的防火墙全部关闭：{profiles}",
    "check.firewall.summary_part_off": "部分网络配置文件的防火墙已关闭：{profiles}",
    "check.firewall.summary_ok": "Windows 防火墙三个配置文件均处于开启状态",
    "check.firewall.advice.all_off": "在公共 Wi-Fi 下关闭防火墙会暴露共享端口，建议重新开启",
    "check.firewall.advice.part_off": "如果不需要在「{profiles}」环境下接收入站连接，建议开启",
    "check.firewall.detail.line": "• {label}：{state}｜{policy}",
    "check.firewall.detail.note": "说明：防火墙关闭不会导致上不了网，属于安全加固项。",
    "profile.domain": "域网络",
    "profile.private": "专用网络",
    "profile.public": "公用网络",

    # ------------------------------------------------------------------ #
    # 检测单元：connectivity
    # ------------------------------------------------------------------ #
    "check.connectivity.title": "外网连通性与延迟",
    "check.connectivity.category": "连通性",
    "check.connectivity.summary_ok": "外网连通正常：ping {ping}，HTTPS {handshake}",
    "check.connectivity.ping_no_icmp": "目标不回 ICMP（常见策略，不影响判定）",
    "check.connectivity.ping_text": "{ms}ms（{grade}）",
    "check.connectivity.ping_detail": "平均 {avg}ms"
                                      "（最低 {min} / 最高 {max}，丢包 {loss}%）",
    "check.connectivity.ping_detail_fail": "不通（丢包 {loss}%）",
    "check.connectivity.handshake_text": "握手最慢 {ms}ms",
    "check.connectivity.handshake_none": "无成功目标",
    "check.connectivity.handshake_ms": "握手 {ms}ms",
    "check.connectivity.problem.ping_loss": "公网 ping 丢包 {loss}%，链路不稳定",
    "check.connectivity.problem.budget": "未能在时间预算内完成 HTTPS 连接探测，本项结论不完整",
    "check.connectivity.problem.tcp_all_fail": "{n} 个 HTTPS 目标全部无法建立连接，"
                                               "当前无法正常上网",
    "check.connectivity.problem.tcp_partial": "部分目标无法建立 HTTPS 连接：{names}"
                                              "（其余正常，可能是单站点或 CDN 问题）",
    "check.connectivity.problem.latency_high": "外网延迟 {ms}ms 偏高，网页会明显变慢",
    "check.connectivity.problem.latency_mid": "外网延迟 {ms}ms，略高于常见水平",
    "check.connectivity.problem.handshake_slow": "HTTPS 握手普遍在 {fast}ms 以上"
                                                 "（最慢 {slow}ms），建议检查 DNS 与线路质量",
    "check.connectivity.problem.handshake_fair": "HTTPS 握手 {fast}~{slow}ms，"
                                                 "握手偏慢但可接受",
    "check.connectivity.problem.dns_fail": "域名解析失败，浏览器会报 DNS 错误",
    "check.connectivity.advice.wifi": "无线环境先换 5GHz 或靠近路由器；有线检查网线质量",
    "check.connectivity.advice.proxy_firewall": "IP 层能通但 HTTPS 全断："
                                                "优先检查系统代理与防火墙出站规则",
    "check.connectivity.advice.wan": "IP 层与 HTTPS 双双不通：检查路由器 WAN 口与宽带是否欠费",
    "check.connectivity.advice.dns": "先用「清空 DNS 缓存」，仍失败则切换公共 DNS",
    "check.connectivity.note.ping": "丢包 {loss}%｜{grade}",
    "check.connectivity.note.dns": "{name} 耗时 {ms}ms",
    "check.connectivity.detail.ping": "• IPv4 直连 {target}：{text}",
    "check.connectivity.detail.tcp_ok": "• TCP {host}:{port}：握手 {ms}ms",
    "check.connectivity.detail.tcp_fail": "• TCP {host}:{port}：失败（{err}）",
    "check.connectivity.detail.dns_ok": "• DNS 解析 {name}：{ms}ms → {addrs}",
    "check.connectivity.detail.dns_fail": "• DNS 解析 {name}：失败（{err}）",
    "check.connectivity.detail.elapsed": "• 本项总耗时 {sec} 秒（预算 {budget} 秒）",
    "check.connectivity.no_a_record": "无 A 记录",

    # ------------------------------------------------------------------ #
    # 修复动作元数据
    # ------------------------------------------------------------------ #
    "action.dns.flush_cache.title": "清空 DNS 解析缓存",
    "action.dns.flush_cache.description": "清除本机 DNS 缓存，解决域名解析结果过期、劫持残留导致的访问异常。"
                                         "该操作不影响任何配置，可随时重做。",
    "action.dns.set_public.title": "切换至公共 DNS 服务器",
    "action.dns.set_public.description": "将当前上网网卡的 DNS 改为公共 DNS"
                                        "（默认阿里 223.5.5.5 / 腾讯 119.29.29.29）。"
                                        "原 DNS 配置会完整备份，可一键还原。",
    "action.dns.restore_dhcp.title": "DNS 恢复为自动获取",
    "action.dns.restore_dhcp.description": "把网卡 DNS 改回由路由器 / DHCP 自动下发，"
                                           "适合接入公司或校园网的场景。",
    "action.hosts.clean_bad_lines.title": "清理 HOSTS 中的异常记录",
    "action.hosts.clean_bad_lines.description": "移除非本机写入的可疑映射（指向 0.0.0.0 / "
                                                "回环地址的屏蔽项、与系统关键域名冲突的记录）。"
                                                "原文件整份备份后才会改写。",
    "action.hosts.restore_default.title": "HOSTS 恢复为系统默认模板",
    "action.hosts.restore_default.description": "用 Windows 原始默认 hosts 覆盖当前文件。"
                                                "会丢失用户自己添加的全部自定义记录，"
                                                "因此默认不勾选，且执行前强制二次确认。",
    "action.tcp.autotuning.title": "恢复 TCP 接收窗口自动调节",
    "action.tcp.autotuning.description": "把 TCP autotuning 级别恢复为 normal。"
                                         "被手动关掉会导致高延迟链路吞吐骤降。",
    "action.tcp.heuristics.title": "关闭启发式窗口缩放限制",
    "action.tcp.heuristics.description": "窗口缩放启发式在 Windows 10 1803 之后已被系统废弃，"
                                         "修改不会产生实际效果。保留此项仅为兼容旧系统；"
                                         "在现行 Windows 上执行会被自动跳过。",
    "action.tcp.reset_stack.title": "重置 TCP/IP 协议栈",
    "action.tcp.reset_stack.description": "等价于 netsh int ip reset + winsock reset，"
                                          "用于修复协议栈损坏。会要求重启计算机才能完全生效，"
                                          "因此默认不勾选。",
    "action.proxy.reset.title": "关闭残留的系统代理",
    "action.proxy.reset.description": "清除 WinINET 代理设置并恢复为直连。"
                                      "常见于代理软件异常退出后无法上网。",
    "action.proxy.restore_auto.title": "恢复自动检测代理设置",
    "action.proxy.restore_auto.description": "把“自动检测设置”恢复为系统默认开启状态。",
    "action.adapter.renew_dhcp.title": "重新获取 IP 地址（DHCP 续租）",
    "action.adapter.renew_dhcp.description": "对当前上网网卡执行 release + renew，"
                                             "修复 169.254 开头的无效地址、租约失效等问题。"
                                             "执行期间网络会短暂中断 3-10 秒。",
    "action.adapter.reset_stack.title": "重置 Winsock 目录与防火墙规则",
    "action.adapter.reset_stack.description": "netsh winsock reset 会清空第三方网络过滤驱动注册"
                                              "（部分安全软件需重装组件），并需要重启。默认不勾选。",
    "action.mtu.optimize.title": "按实测结果修正 MTU",
    "action.mtu.optimize.description": "仅当实测出更优 MTU 且与当前值不同时才会写入，"
                                       "不会盲目改成固定值。",
    "action.firewall.ensure_enabled.title": "重新启用 Windows 防火墙",
    "action.firewall.ensure_enabled.description": "当检测到防火墙域配置被意外关闭时，恢复为开启状态。",
    "action.netbios.disable_public.title": "在公网网卡上禁用 NetBIOS over TCP/IP",
    "action.netbios.disable_public.description": "降低局域网名称广播带来的暴露面，"
                                                 "不影响正常的 DHCP / DNS 上网。",

    # ------------------------------------------------------------------ #
    # 修复动作：通用 / base
    # ------------------------------------------------------------------ #
    "repair.result.failed": "执行失败",
    "repair.phase.backup": "备份",
    "repair.phase.apply": "执行",
    "repair.phase.verify": "校验",
    "repair.restart_note": "该操作需要重启计算机才能完全生效",
    "repair.elevation_required": "需要管理员权限才能修改系统配置，"
                                 "请以管理员身份重新运行后再修复此项",
    "repair.registry_snapshot_label": "{label}（注册表导出不可用，已记录结构化状态）",
    "repair.detail.verify": "校验：{message}",
    "repair.error.verify_failed": "校验未通过：{message}",
    "repair.error.verify_exception": "校验阶段异常：{err}",

    "err.action_duplicate": "修复动作重复登记: {id}",
    "err.action_unregistered": "动作 {id} 未在 core/action_ids.py 中登记，"
                              "请先在权威清单里补充元数据",
    "err.action_no_impl": "未实现的修复动作: {id}；已实现: {list}",
    "err.action_missing_param": "动作 {id} 需要构造参数 {list}，"
                                "请通过 plan([( '{id}', {{...}} )]) 传入",
    "err.action_unknown_param": "动作 {id} 不接受参数 {list}，可用参数: {allowed}",
    "err.no_primary": "未找到当前上网网卡"
                      "（没有已连接且带默认网关/有效 IPv4 的适配器），请先确认网络连接正常",
    "err.primary_virtual": "当前上网网卡「{name}」被识别为虚拟/隧道适配器，"
                          "为避免破坏 VPN 或虚拟机配置，不对其执行修复",
    "err.primary_no_guid": "网卡「{name}」缺少 InterfaceGuid，无法安全定位注册表配置项",
    "err.run_failed": "{what}失败（返回码 {rc}）。命令：{cmd}\n系统输出：{out}",
    "err.run_failed_text": "{what}失败（返回码为 0，但系统输出含错误「{marker}」）。"
                          "命令：{cmd}\n系统输出：{out}",
    "err.dns_list_empty": "DNS 服务器列表为空",
    "err.alias_empty": "网卡别名为空，无法执行 netsh 命令",
    "err.alias_invalid": "网卡别名包含非法字符，拒绝拼接命令：{value}",
    "err.reg_backup_path_empty": "注册表备份路径为空",
    "err.firewall_parse": "无法从 netsh 输出解析防火墙配置文件 {list} 的开关状态，"
                          "为避免生成错误备份已中止。原始输出：\n{out}",
    "err.unknown_firewall_profile": "未知的防火墙配置文件: {profile}",

    "what.dns_primary": "设置「{alias}」的首选 DNS",
    "what.dns_index": "设置「{alias}」的第 {index} 个 DNS（{server}）",
    "what.dns_dhcp": "把「{alias}」的 DNS 恢复为自动获取",
    "what.dns_read": "读取「{alias}」的 DNS 配置",
    "what.mtu_set": "设置「{alias}」的 MTU 为 {mtu}",
    "what.firewall_read": "读取防火墙配置",
    "what.firewall_set": "设置防火墙「{profile}」为 {state}",
    "what.tcp_read": "读取 TCP 全局参数",
    "what.tcp_set": "设置 TCP 参数 {name}={value}",
    "what.reg_import": "导入注册表备份 {path}",
    "what.winhttp_direct": "恢复 WinHTTP 直连",
    "what.heuristics_read": "读取窗口缩放启发式参数",
    "what.heuristics_set": "设置窗口缩放启发式为 disabled",
    "what.heuristics_restore": "恢复窗口缩放启发式为 {level}",

    # ------------------------------------------------------------------ #
    # 修复动作：dns
    # ------------------------------------------------------------------ #
    "preview.dns_flush.target": "本机 DNS 解析缓存",
    "preview.dns_flush.before": "当前缓存约 {n} 条记录",
    "preview.dns_flush.before_unknown": "当前缓存条目数未知",
    "preview.dns_flush.after": "缓存清空，后续域名解析重新向 DNS 服务器查询",
    "preview.dns_flush.note": "不修改任何网络配置，可反复执行",
    "msg.dns_flush.failed": "清空 DNS 缓存失败",
    "msg.dns_flush.done": "DNS 缓存已清空",
    "err.dns_flush_rc": "ipconfig /flushdns 返回码 {rc}：{out}",
    "err.dns_cache_read": "读取 DNS 缓存失败（返回码 {rc}）：{out}",
    "msg.dns_cache_read_ok": "缓存已清空，DNS 客户端可正常响应",
    "msg.no_rollback_needed": "该动作不修改任何持久化配置，无需回滚",
    "err.dns_servers_required": "DNS 服务器列表为空：至少需要一个 IPv4 地址",
    "err.dns_server_invalid": "非法的 DNS 服务器地址: {value}，只接受 IPv4 点分十进制",
    "value.dns_auto_unknown": "自动获取（DHCP 下发的服务器未记录）",
    "value.dns_not_configured": "未配置",
    "value.dns_from_dhcp": "{servers}（由 DHCP 自动下发）",
    "value.dns_manual": "{servers}（手动配置）",
    "preview.dns_target": "{adapter} / DNS 服务器",
    "preview.dns_set_after": "{servers}（手动配置，静态）",
    "preview.dns_set_note": "原 DNS 配置会完整备份，可在备份页一键还原；IPv6 DNS 不受影响",
    "label.dns_config": "{adapter} 的 DNS 配置",
    "msg.dns_set_done": "已将「{adapter}」的 DNS 设置为 {servers}",
    "msg.dns_verify_ok": "读回 DNS 为 {actual}，与目标一致",
    "msg.dns_verify_fail": "读回 DNS 为 {actual}，与目标 {expected} 不一致",
    "value.dns_empty": "空",
    "preview.dns_dhcp_after_keep": "自动获取（沿用 DHCP 下发的 DNS）",
    "preview.dns_dhcp_after_set": "自动获取（改为由 DHCP 下发）",
    "preview.dns_dhcp_after_suffix": "，DNS 后缀按 DHCP 选项注册",
    "preview.dns_dhcp_note": "原 DNS 配置会完整备份；若当前已是自动获取，执行后无变化",
    "msg.dns_dhcp_done": "「{adapter}」的 DNS 已改为自动获取",
    "msg.dns_dhcp_ok": "已确认为 DHCP 自动获取",
    "msg.dns_dhcp_switched": "配置源已切换为自动获取（当前未下发服务器）",
    "msg.dns_still_manual": "仍为手动配置：{servers}",

    # ------------------------------------------------------------------ #
    # 修复动作：hosts
    # ------------------------------------------------------------------ #
    "preview.hosts.target": "HOSTS 文件（{path}）",
    "preview.hosts.clean.before_none": "{n} 条有效映射，未发现可疑记录",
    "preview.hosts.clean.after_none": "内容不变（执行时该动作会被跳过）",
    "preview.hosts.clean.note_none": "没有需要清理的记录时不会写入文件",
    "preview.hosts.clean.sample": "第 {line} 行 {ip} {hosts}",
    "preview.hosts.clean.sample_more": "；…共 {n} 行",
    "preview.hosts.clean.before": "{n} 条有效映射，其中 {k} 条可疑：{sample}",
    "preview.hosts.clean.after": "删除这 {k} 行，剩余 {rest} 条映射与全部注释原样保留",
    "preview.hosts.clean.note": "仅删除可疑行号，注释、空行、行尾格式、BOM 均按字节保留；"
                                "原文件整份备份，可一键还原",
    "label.hosts_raw": "HOSTS 文件原文",
    "msg.hosts_clean_none": "未发现需要清理的记录",
    "err.hosts_safety_count": "安全检查未通过：解析出 {n} 行需删除，"
                              "但文件只有 {maps} 条有效映射（总行数 {lines}）。"
                              "这通常说明 HOSTS 格式异常或解析出错，为避免误删整份文件已中止。",
    "err.hosts_line_mismatch": "HOSTS 行切分结果不一致（{a} vs {b}），"
                               "文件可能包含非常规控制字符，为避免删错行已中止",
    "err.hosts_empty_result": "安全检查未通过：清理后文件将不剩任何内容，"
                              "疑似行号映射错误，已中止（原文件未修改）",
    "err.hosts_still_suspicious": "清理后仍解析出 {n} 条可疑记录，"
                                  "行号映射可能不一致，已中止写入（原文件未被修改）",
    "msg.hosts_clean_done": "已删除 {n} 条异常记录，其余内容原样保留",
    "detail.hosts_removed": "删除第 {line} 行：{raw}｜{reason}",
    "detail.hosts_removed_more": "…另有 {n} 条同类记录",
    "err.hosts_missing": "HOSTS 文件不存在：{path}",
    "err.hosts_still_suspicious_verify": "仍存在 {n} 条可疑记录",
    "err.hosts_empty_file": "HOSTS 变成空文件",
    "msg.hosts_verify_note": "（文件行数较少：{n} 行，请自行核对是否完整）",
    "msg.hosts_verify_ok": "已确认可疑记录为 0；剩余 {n} 条有效映射{note}",
    "preview.hosts.restore.before": "当前 {n} 条有效映射",
    "preview.hosts.restore.before_detail": "：{detail}",
    "preview.hosts.restore.detail_more": " 等 {n} 条",
    "preview.hosts.restore.after": "仅系统默认模板（全部为注释，无任何映射），"
                                   "用户自定义记录全部丢失",
    "preview.hosts.restore.note": "此操作不可通过撤销恢复，但可在备份页回滚。"
                                  "执行前会把当前文件整份备份。",
    "msg.hosts_restore_done": "HOSTS 已恢复为系统默认模板（清除 {n} 条映射）",
    "detail.hosts_restore_written": "已写入 Windows 默认模板（CRLF 行尾，UTF-8 无 BOM）",
    "detail.hosts_restore_cleared": "用户自定义映射已清除；如需找回请在备份页回滚本次会话",
    "err.hosts_restore_left": "模板中仍解析出 {n} 条有效映射，写入可能未生效",
    "err.hosts_restore_empty": "HOSTS 为空文件，默认模板未写入",
    "msg.hosts_restore_verify_ok": "已确认为系统默认模板（{n} 行，0 条映射）",
    "err.hosts_text_type": "new_text 必须是字符串，收到 {type}",
    "err.hosts_text_empty": "拒绝写入：新内容为空文件。覆盖后 HOSTS 将不含任何行，"
                            "这通常意味着输入被截断或编码错误",
    "err.hosts_text_zero": "拒绝写入：新内容字节数为 0",
    "err.hosts_text_blank": "拒绝写入：新内容只包含空白字符，没有可保留的内容",
    "kind.hosts_edit": "手工编辑 HOSTS",
    "note.hosts_edit": "写入前自动备份 HOSTS 原文",
    "msg.hosts_saved_detail": "HOSTS 已写入（{lines} 行，{maps} 条映射）",
    "detail.hosts_before": "写入前有 {n} 条有效映射",
    "detail.hosts_still_suspicious": "注意：新内容里仍有 {n} 条可疑记录",

    # ------------------------------------------------------------------ #
    # 修复动作：adapter
    # ------------------------------------------------------------------ #
    "preview.adapter_renew.target": "{adapter} / IPv4 地址与租约",
    "preview.adapter_renew.before": "{ip}{flag}，地址来源={source}",
    "preview.adapter_renew.apipa_flag": "（APIPA 无效地址）",
    "preview.adapter_renew.source_dhcp": "DHCP",
    "preview.adapter_renew.source_static": "静态或未知",
    "preview.adapter_renew.after": "重新向 DHCP 服务器申请地址；成功后可能得到与当前不同的 IP",
    "preview.adapter_renew.note": "执行期间网络会中断约 3-10 秒，属预期行为；"
                                  "原地址与网关会完整备份",
    "label.ip_lease": "{adapter} 的 IP 租约信息",
    "detail.ipconfig_rc": "ipconfig /{command} \"{alias}\" -> 返回码 {rc}",
    "detail.release_warn": "警告：release 返回 {rc}，继续尝试 renew（部分网卡不支持释放租约）",
    "msg.renew_failed": "重新获取 IP 地址失败，网络可能仍不可用",
    "err.renew_failed": "ipconfig /renew 返回码 {rc}：{out}\n"
                        "原地址 {ip}；请检查网线 / Wi-Fi 连接与路由器 DHCP 服务",
    "msg.renew_adapter_missing": "重新获取地址后无法定位该网卡",
    "err.renew_adapter_missing": "按 GUID {guid} 与别名 {alias} 均未找到网卡",
    "msg.renew_no_ip": "网络已恢复，但网卡仍未获得 IPv4 地址",
    "err.renew_no_ip": "renew 返回成功但网卡无 IPv4 地址，请检查路由器 DHCP 是否开启",
    "msg.renew_apipa": "重新获取后仍是 169.254 开头的无效地址，DHCP 未响应",
    "err.renew_apipa": "当前地址 {ip}；请检查路由器 DHCP 服务与网线连接",
    "msg.renew_done": "网络已恢复，IP 从 {old} 变为 {new}；"
                      "若仍无法上网请检查路由器 DHCP 与网关配置",
    "detail.new_ip": "新地址 {ip}/{prefix}，网关 {gateway}",
    "detail.ip_changed": "地址已变化，旧地址 {old} 记录在备份中",
    "msg.verify_no_adapter": "未找到任何已连接的网卡",
    "msg.verify_no_ip": "「{name}」当前没有 IPv4 地址",
    "msg.verify_apipa": "「{name}」仍为 APIPA 地址 {ip}，DHCP 未分配有效地址",
    "msg.verify_ip_ok": "「{name}」已获得有效地址 {ip}，网关 {gateway}",
    "preview.adapter_reset.target": "Winsock 目录与 IPv4 协议栈",
    "preview.adapter_reset.before": "当前 Winsock LSP 注册与 IP 协议栈参数",
    "preview.adapter_reset.after": "Winsock 目录重建、IP 协议栈参数复位；第三方 LSP 被移除，"
                                   "相关安全软件可能需重装网络组件",
    "preview.adapter_reset.note": "{restart}；注册表会整份备份，重启前可用备份页回滚",
    "label.winsock_params": "WinSock2 参数注册表",
    "label.tcpip_params": "TCP/IP 参数注册表",
    "detail.cmd_rc": "{command} -> 返回码 {rc}",
    "msg.adapter_reset_failed": "网络组件重置未完全下发",
    "err.adapter_reset_failed": "netsh winsock reset 返回码 {winsock_rc}：{winsock_out}\n"
                                "netsh int ip reset 返回码 {ip_rc}：{ip_out}",
    "msg.adapter_reset_done": "Winsock 与 IP 协议栈已重置，需要重启计算机才能完全生效",
    "detail.adapter_reset_snapshot": "已在 reset 前后记录注册表快照；"
                                     "相关安全软件的 LSP 组件建议重装",
    "err.winsock_catalog": "重置后 `netsh winsock show catalog` 返回 {rc}：{out}",
    "msg.winsock_catalog_ok": "已下发，需重启生效（Winsock 目录仅重启后重建完成）",

    # ------------------------------------------------------------------ #
    # 修复动作：firewall
    # ------------------------------------------------------------------ #
    "preview.firewall.target": "Windows 防火墙（域 / 专用 / 公用）",
    "preview.firewall.before": "{pairs}",
    "preview.firewall.keep": "保持全部开启，无需修改",
    "preview.firewall.keep_note": "三个配置文件都已开启时不会执行任何命令",
    "preview.firewall.off_note": "当前关闭的是 {profiles}；开启后可能需要在防火墙里为特定程序放行",
    "label.firewall_states": "防火墙配置文件开关状态",
    "msg.firewall_all_on": "三个防火墙配置文件均已开启，无需修改",
    "detail.firewall_set": "{profile}: {before} -> ON",
    "msg.firewall_enabled": "防火墙已开启：{profiles}",
    "detail.firewall_hint": "提示：如有程序被防火墙拦下，可在「允许应用通过防火墙」中放行",
    "msg.firewall_verify_fail": "仍有配置文件未开启：{profiles}",
    "msg.firewall_verify_ok": "域 / 专用 / 公用 三个配置文件均为 ON",

    # ------------------------------------------------------------------ #
    # 修复动作：mtu
    # ------------------------------------------------------------------ #
    "err.mtu_required": "mtu.optimize 需要 target_mtu 参数（1200-1500），当前为 None；"
                        "该参数应由 mtu 检测项的实测结果提供",
    "err.mtu_type": "mtu.optimize 的 target_mtu 必须是整数，收到 {type}: {value}",
    "err.mtu_range": "mtu.optimize 的 target_mtu 必须在 {min}-{max} 之间，收到 {value}；"
                     "超出该范围会破坏链路，拒绝执行（不做钳位）",
    "preview.mtu.after_same": "{value}（与当前相同，执行时该动作会被跳过）",
    "preview.mtu.after_atypical": "{value}（非典型值，请确认实测过程可靠）",
    "preview.mtu.target": "{adapter} / MTU",
    "preview.mtu.before": "{value}（ifIndex={index}）",
    "preview.mtu.before_fail": "读取失败",
    "preview.mtu.note": "使用 store=persistent 写入，重启后保留；原值会备份，可一键还原",
    "err.mtu_read": "无法读取「{adapter}」的当前 MTU（读到 {value}），"
                    "没有原值就无法回滚，已中止",
    "label.mtu": "{adapter} 的 MTU",
    "msg.mtu_already": "当前 MTU 已是 {value}，无需修改",
    "msg.mtu_done": "「{adapter}」的 MTU 已从 {old} 改为 {new}",
    "err.mtu_no_target": "无法确定目标网卡（apply 未记录目标网卡）",
    "err.mtu_adapter_missing": "未找到目标网卡（GUID={guid}，ifIndex={index}）",
    "msg.mtu_verify_ok": "读回「{name}」MTU={value}（ifIndex={index}）",
    "msg.mtu_verify_fail": "读回「{name}」MTU={value}，期望 {expected}（ifIndex={index}）",

    # ------------------------------------------------------------------ #
    # 修复动作：netbios
    # ------------------------------------------------------------------ #
    "err.netbios_guid_empty": "网卡 GUID 为空，无法定位 NetBIOS 注册表项",
    "err.netbios_read": "读取 NetBIOS 配置失败（{path}）：{err}",
    "preview.netbios.before_unset": "未配置（等同由 DHCP 决定，通常为启用）",
    "preview.netbios.value_dhcp": "0（由 DHCP 决定）",
    "preview.netbios.value_on": "1（启用）",
    "preview.netbios.value_off": "2（已禁用）",
    "preview.netbios.after": "{value}（禁用）",
    "preview.netbios.note_public": "仅影响局域网名字广播，不影响上网、DNS 与现代 SMB 文件共享；"
                                   "当前地址看起来是公网地址",
    "preview.netbios.note_private": "仅影响局域网名字广播，不影响上网、DNS 与现代 SMB 文件共享；"
                                    "当前是内网地址，若依赖「网上邻居」按名字访问共享请谨慎",
    "label.netbios": "NetBIOS 网卡配置",
    "label.netbios_snapshot": "NetBIOS 网卡配置（原注册表项不存在）",
    "msg.netbios_already": "该网卡的 NetBIOS 已是禁用状态，无需修改",
    "msg.netbios_done": "已在「{adapter}」上禁用 NetBIOS over TCP/IP",
    "detail.netbios_value": "NetbiosOptions: {before} -> {after}",
    "detail.netbios_path": "注册表项：HKLM\\{path}",
    "detail.netbios_takes_effect": "该改动对当前连接即时生效，无需重启",
    "msg.netbios_verify_ok": "读回 NetbiosOptions={value}（已禁用）",
    "msg.netbios_verify_missing": "读回时注册表值不存在，写入可能被安全软件拦截",
    "msg.netbios_verify_fail": "读回 NetbiosOptions={value}，期望 {expected}",

    # ------------------------------------------------------------------ #
    # 修复动作：proxy
    # ------------------------------------------------------------------ #
    "err.reg_read": "读取注册表项 {name} 失败：{err}",
    "err.wininet_load": "加载 wininet.dll 失败：{err}",
    "err.wininet_option": "{label} 返回失败（GetLastError={err}）",
    "err.wininet_call": "{label} 调用异常：{err}",
    "msg.wininet_refreshed": "已通知系统刷新代理设置",
    "value.proxy_direct": "直连（未启用代理）",
    "value.proxy_enabled": "{parts}（已启用代理）",
    "preview.proxy_reset.target": "系统代理（WinINET：HKCU Internet Settings）",
    "preview.proxy_reset.after": "直连（ProxyEnable=0，ProxyServer 删除）",
    "preview.proxy_reset.after_keep": "直连（ProxyEnable=0，ProxyServer 删除）；"
                                      "保留例外列表 {keep}",
    "preview.proxy_reset.note": "不改动 WinHTTP 代理与自动检测设置；原值会完整备份，可一键还原",
    "label.proxy_settings": "系统代理设置（Internet Settings）",
    "detail.proxy_enable": "ProxyEnable: {before} -> 0",
    "detail.proxy_server_deleted": "ProxyServer: {before} -> 已删除",
    "detail.proxy_server_absent": "ProxyServer: 原本就不存在",
    "detail.proxy_override_kept": "保留 ProxyOverride={value}",
    "detail.proxy_refresh": "代理设置刷新：{message}",
    "detail.proxy_refresh_failed": "代理设置刷新失败（不影响本次修改）：{message}",
    "msg.proxy_enable_not_zero": "写入 ProxyEnable=0 后读回仍不为 0",
    "err.proxy_enable_readback": "读回 ProxyEnable={value}",
    "msg.proxy_reset_done": "系统代理已关闭，浏览器将直接连接网络",
    "msg.proxy_verify_enable": "ProxyEnable 读回为 {value}，期望 0",
    "msg.proxy_verify_server": "ProxyServer 仍存在：{value}",
    "msg.proxy_verify_ok": "ProxyEnable=0 且 ProxyServer 已清除",
    "preview.proxy_auto.target": "系统代理（WinINET 静态代理 + WinHTTP 代理配置）",
    "preview.proxy_auto.before": "WinINET：{wininet}；WinHTTP：{winhttp}",
    "preview.proxy_auto.after": "WinINET 静态代理关闭；WinHTTP 恢复为直接访问",
    "preview.proxy_auto.note": "不改动「自动检测设置」的二进制开关"
                              "（DefaultConnectionSettings），该位保持原样",
    "label.winhttp_proxy": "WinHTTP 代理配置",
    "detail.proxy_auto_enable": "ProxyEnable: {before} -> 0（静态代理已关闭）",
    "detail.proxy_auto_unchanged": "自动检测设置（DefaultConnectionSettings 第 9 字节 bit3）"
                                   "未改动：直接编辑该二进制在版本升级后可能损坏连接配置，"
                                   "故保持原样。",
    "msg.proxy_auto_done": "已关闭静态代理并恢复 WinHTTP 直连（自动检测开关未改动）",
    "msg.proxy_auto_verify_fail": "WinHTTP 仍非直连：{text}",
    "msg.proxy_auto_verify_ok": "WinINET 直连，WinHTTP 为直接访问",
    "value.winhttp_read_failed": "（读取失败，返回码 {rc}）{out}",

    # ------------------------------------------------------------------ #
    # 修复动作：tcp
    # ------------------------------------------------------------------ #
    "err.autotuning_parse": "无法从 `netsh int tcp show global` 解析出当前的 autotuning 级别，"
                            "原始输出：{values}",
    "preview.autotuning.target": "TCP 接收窗口自动调节级别",
    "preview.autotuning.note": "只改全局参数，不重置协议栈，无需重启",
    "label.autotuning": "TCP 自动调谐级别",
    "msg.autotuning_done": "TCP 自动调谐级别已设为 {value}",
    "msg.autotuning_verify_ok": "读回 autotuning = {value}",
    "msg.autotuning_verify_fail": "读回 autotuning = {value}，期望 {expected}",
    "msg.heuristics_unreadable": "无法读取窗口缩放启发式参数，跳过该项：{err}",
    "msg.heuristics_missing": "当前输出中未识别到窗口缩放启发式参数，该项无需修复",
    "msg.heuristics_ineffective": "当前 Windows 版本已不再实际使用窗口缩放启发式"
                                  "（系统自带说明：更改窗口缩放启发设置将没有任何效果），"
                                  "该项无需修复",
    "preview.heuristics.target": "TCP 窗口缩放启发式（wsh）",
    "preview.heuristics.read_failed": "读取失败（{err}）",
    "preview.heuristics.note": "该设置在新版 Windows 上不再影响行为，仅记录状态；"
                               "旧版系统可改善高延迟吞吐",
    "err.heuristics_parse": "无法从 `netsh int tcp show heuristics` 解析出窗口缩放启发式级别，"
                            "已中止以免无法回滚。原始输出：{values}",
    "label.heuristics": "TCP 窗口缩放启发式级别",
    "msg.heuristics_already": "窗口缩放启发式已是 {value}，无需修改",
    "msg.heuristics_done": "窗口缩放启发式已设为 {value}（原值 {before}）",
    "detail.heuristics_note": "说明：Windows 10/11 已不再实际使用该参数"
                              "（系统提示 changing window scaling heuristics settings "
                              "will have no effect），本项仅为对齐旧系统与状态一致性",
    "msg.heuristics_verify_ok": "读回窗口缩放启发式 = {value}",
    "msg.heuristics_verify_fail": "读回窗口缩放启发式 = {value}，期望 {expected}",
    "preview.tcp_reset.target": "TCP/IP 协议栈与 Winsock 目录",
    "preview.tcp_reset.before": "当前协议栈状态（含第三方 LSP / 过滤驱动注册）",
    "preview.tcp_reset.after": "协议栈参数复位为系统默认，Winsock 目录重建；"
                               "第三方 LSP 注册被清除，相关安全软件可能需重装组件",
    "msg.tcp_reset_failed": "协议栈重置未完全下发",
    "err.tcp_reset_failed": "netsh int ip reset 返回码 {ip_rc}：{ip_out}\n"
                            "netsh winsock reset 返回码 {winsock_rc}：{winsock_out}",
    "msg.tcp_reset_done": "TCP/IP 协议栈与 Winsock 已重置，需要重启计算机才能完全生效",
    "detail.tcp_reset_rollback": "⚠ 回滚只能恢复注册表参数，"
                                 "已生效的协议栈状态需重启后才能被备份覆盖",
    "err.tcp_show_global": "协议栈重置后 `netsh int ip show global` 返回 {rc}：{out}",
    "msg.tcp_reset_verify_ok": "已下发，需重启生效（当前进程无法观测生效结果）",

    # ------------------------------------------------------------------ #
    # 回滚
    # ------------------------------------------------------------------ #
    "msg.rollback_item_failed": "恢复「{label}」失败",
    "msg.rollback_item_done": "已恢复「{label}」",
    "msg.rollback_needs_admin": "「{label}」需要管理员权限才能还原，当前以普通用户身份运行。"
                                "请右键以管理员身份启动后重试回滚；"
                                "备份文件本身完好，可在备份目录中手工还原",
    "msg.rollback_dhcp_skip": "「{label}」不自动回滚：DHCP 续租会再次断开网络。"
                              "备份记录的原地址为 {ip}，网关 {gateway}，请手工核对是否需要还原",
    "detail.rollback_dhcp_hint": "如需恢复地址，请在网卡属性中改为静态 IP 并填入上述值",
    "msg.rollback_winhttp_skip": "「{label}」仅记录了展示文本，未导出可导入的注册表快照；"
                                 "请使用备份目录中的原始输出人工核对 WinHTTP 代理",
    "msg.rollback_unknown_kind": "未知的备份类型「{kind}」（key={key}）",
    "err.rollback_unknown_kind": "备份项类型与回滚实现不匹配，拒绝猜测恢复方式",
    "err.hosts_backup_missing": "HOSTS 备份文件不存在：{path}",
    "err.hosts_backup_corrupted": "备份文件已损坏，拒绝恢复：{path}\n"
                                  "期望 sha256={expected}\n实际 sha256={actual}\n"
                                  "请检查该文件是否被其它程序修改",
    "detail.hosts_restored": "已从 {path} 恢复 HOSTS（sha256 校验通过）",
    "msg.hosts_restored": "已恢复 HOSTS 原文（{n} 字节）",
    "err.rollback_adapter_missing": "未找到 GUID 为 {guid} 的网卡，"
                                    "该网卡可能已被禁用或移除，无法恢复其 DNS 配置",
    "detail.dns_dhcp_restored": "原本为 DHCP 自动获取，已恢复：{alias}",
    "msg.dns_dhcp_restored": "「{alias}」的 DNS 已恢复为自动获取",
    "err.rollback_dns_empty": "备份记录了静态 DNS 但服务器列表为空（{key}），"
                              "无法据此恢复；请手工在网卡属性中设置",
    "detail.dns_static_restored": "原本为静态列表，已恢复：{alias} -> {servers}",
    "msg.dns_static_restored": "「{alias}」的 DNS 已恢复为 {servers}",
    "err.reg_backup_missing": "注册表备份文件不存在：{path}",
    "detail.reg_imported": "已导入 {path}",
    "msg.reg_restored": "已导入注册表备份（{hive}）",
    "err.rollback_mtu_invalid": "备份中的 MTU 值无效：{value}",
    "err.rollback_mtu_no_target": "备份中既无网卡 GUID 也无别名，无法定位要恢复的网卡",
    "detail.rollback_mtu_fallback": "警告：未按 GUID 找到网卡 {guid}，退化为按备份别名「{alias}」恢复",
    "msg.mtu_restored": "「{alias}」的 MTU 已恢复为 {value}",
    "err.rollback_firewall_empty": "防火墙备份中没有配置文件状态，无法恢复",
    "msg.firewall_restored": "防火墙已恢复：{profiles}",
    "err.rollback_tcp_empty": "备份中没有 TCP 参数原值（{key}）",
    "msg.autotuning_restored": "TCP autotuninglevel 已恢复为 {level}",
    "msg.heuristics_restored": "TCP 窗口缩放启发式已恢复为 {level}",
    "err.rollback_tcp_unknown": "无法从备份 key 判断 TCP 参数名：{key}",
    "err.rollback_netbios_guid": "备份中没有网卡 GUID（{key}），无法定位 NetBIOS 配置项",
    "detail.netbios_already_original": "注册表值与键均不存在，视为已回到原始状态",
    "msg.netbios_original": "NetBIOS 配置已回到原状（原本不存在）",
    "err.netbios_delete": "删除 NetbiosOptions 失败（{path}）：{err}",
    "detail.netbios_deleted": "已删除 {path}\\NetbiosOptions（原本不存在）",
    "msg.netbios_unset": "NetBIOS 配置已回到「未设置」状态",
    "err.rollback_netbios_snapshot": "该 NetBIOS 备份不含可恢复的注册表快照"
                                     "（{key}，hive={hive}）；"
                                     "请用备份目录中的 .reg 文件人工导入",
    "msg.rollback_nothing": "本次备份会话中没有该动作产生的备份项，无可回滚内容",
    "msg.rollback_partial": "部分备份项恢复失败（成功 {n} 项）",
    "msg.rollback_done": "已恢复 {n} 项备份",

    # ------------------------------------------------------------------ #
    # 修复编排 engine
    # ------------------------------------------------------------------ #
    "note.plan.duplicate": "「{id}」重复提交，已合并为一条",
    "note.plan.servers_override": "dns.set_public 同时收到 params.servers 与 servers 参数，"
                                  "以 servers 为准",
    "note.plan.no_impl": "「{id}」没有修复实现，已跳过",
    "note.plan.skipped": "「{id}」已跳过：{reason}",
    "note.plan.unsupported": "当前环境不支持",
    "note.plan.probe_error": "可用性检测异常（{err}）",
    "note.plan.conflict": "「{drop}」与「{keep}」冲突（{why}），已保留「{keep}」",
    "note.plan.dry_run": "演练模式：只做预览与备份，不会执行任何修改",
    "err.servers_type": "servers 必须是列表，收到 {type}",
    "err.servers_empty": "servers 不能为空列表：至少需要一个 DNS 服务器地址",
    "err.missing_param": "动作 {id} 缺少必需参数 {list}；"
                         "请以 ('{id}', {{...}}) 的形式传入",
    "err.invalid_param": "动作 {id} 的参数不合法：{err}",
    "err.action_ids_type": "action_ids 必须是列表而不是单个字符串；"
                           "传单个动作请写成 ['dns.flush_cache']",
    "err.action_id_type": "动作 id 必须是字符串，收到 {value}",
    "err.action_params_type": "动作 {id} 的参数必须是字典，收到 {type}",
    "err.action_ref": "无法识别的动作描述: {value}；"
                      "应为 'action_id' 或 ('action_id', {{...}})",
    "preview.unreadable": "无法读取当前状态",
    "preview.unavailable": "该项无法执行",
    "note.preview_failed": "预览失败：{err}",
    "note.session_plan": "本次计划包含 {n} 个动作：{list}",
    "note.session_empty": "无动作",
    "kind.auto_backup": "修复前自动备份",
    "err.backup_failed": "动作「{id}」备份失败，因备份失败未做任何修改：{err}",
    "hint.aborted": "没有任何动作被应用，系统未被修改，无需回滚。"
                    "备份会话 {session} 已保留（仅含部分快照），建议排查失败原因后重试。",
    "hint.dry_run": "演练模式：未执行任何修改。备份会话 {session} 已创建，"
                    "路径 {path}（可用于确认备份链路完整，但无需回滚）",
    "hint.no_actions": "本次没有可执行的动作，未做任何修改；"
                       "备份会话 {session} 仅作审计记录（无备份项）",
    "hint.partial": "本轮有 {n} 个动作未能完成或校验未通过，"
                    "建议回滚本次备份会话 {session} 以恢复原状。备份路径：{path}",
    "hint.all_done": "全部动作已完成并通过校验。若需撤销，"
                     "可回滚备份会话 {session}（路径：{path}）",
    "err.session_empty": "该会话没有备份项（可能只包含无状态动作），无可恢复内容",
    "kind.manual_backup": "手工备份",
    "note.manual_backup": "用户主动创建的系统状态快照",
    "label.mtu_snapshot": "{adapter} 的 MTU（手工备份记录）",
    "note.manual_partial": "手工备份（部分项目未成功，共 {n} 项）：\n{list}",
    "note.manual_ok": "手工备份成功，共 {n} 项状态快照",

    # ------------------------------------------------------------------ #
    # 报告渲染
    # ------------------------------------------------------------------ #
    "report.html.title": "LanPulse 网络体检报告 · {host}",
    "report.html.heading": "网络体检报告",
    "report.html.host": "主机名",
    "report.html.os": "操作系统",
    "report.html.time": "检测时间",
    "report.html.elevated": "管理员权限",
    "report.html.duration": "检测耗时",
    "report.html.id": "报告编号",
    "report.html.status": "总体状态 · {label}",
    "report.html.overview": "结果概览",
    "report.html.details": "检测明细（共 {n} 项）",
    "report.html.empty": "本次没有任何检测结果。",
    "report.html.footnote_privacy": "本报告仅在本机生成，未上传任何数据。"
                                    "报告不包含任何外部链接、脚本或图片，断网状态下可正常查看。",
    "report.html.footnote_snapshot": "报告内容是导出时刻的状态快照，"
                                     "网络配置随环境变化，重新体检可能得到不同结论。",
    "report.html.backup_dir": "配置备份目录：{path}"
                              "（修复前的原始状态按会话保存在此，可直接打开核对或手工还原）",
    "report.html.no_backup": "本次尚未产生任何备份 —— 该目录只会在执行修复前自动创建。",
    "report.html.footer": "LanPulse · 报告编号 {id} · 生成于 {time}",
    "report.html.escaped_error": "该检测项执行失败，结论不可用：\n{err}",
    "report.metric.header_name": "指标",
    "report.metric.header_value": "值",
    "report.metric.header_note": "说明",
    "report.advice.label": "建议处理",
    "report.evidence.summary": "原始证据（{n} 字符）",
    "report.evidence.unserializable": "[证据无法序列化为 JSON: {err}]",
    "report.elevated_yes": "是（管理员）",
    "report.elevated_no": "否（普通用户）",
    "report.text.title": " LanPulse 网络体检报告",
    "report.text.host": " 主机名       : {value}",
    "report.text.os": " 操作系统     : {value}",
    "report.text.time": " 检测时间     : {value}",
    "report.text.elevated": " 管理员权限   : {value}",
    "report.text.duration": " 检测耗时     : {value}",
    "report.text.id": " 报告编号     : {value}",
    "report.text.score": " 健康分       : {score} / 100      总体状态: {label}",
    "report.text.counts": " 结果统计: 正常 {ok} | 提示 {info} | 异常 {warn} | "
                          "严重 {crit} | 跳过 {skip}",
    "report.text.item": "[{idx}] {sev} | {title}（{category} / {id}）",
    "report.text.summary": "  摘要: {text}",
    "report.text.error_head": "  ! 该检测项执行失败，结论不可用:",
    "report.text.detail_head": "  详情:",
    "report.text.advice_head": "  建议:",
    "report.text.notes_head": " 说明:",
    "report.text.note_privacy": "   本报告仅在本机生成，未上传任何数据。",
    "report.text.note_snapshot": "   报告内容是导出时刻的状态快照，重新体检可能得到不同结论。",
    "report.text.backup_dir": "   配置备份目录: {path}",
    "report.text.generated_at": "   生成于 {value}",
    "report.text.truncated": "\n…（已截断，完整内容见 JSON / HTML 报告）",
    "report.text.seconds": "{n:.1f} 秒",
    "report.text.minutes": "{n} 分 {sec} 秒",
    "report.plan.empty": "没有需要执行的修改。\n\n当前系统未发现需要自动修复的项目，无需做任何改动。",
    "report.plan.head": "将要执行 {n} 项修改：",
    "report.plan.item": "{idx}. {target}",
    "report.plan.before": "修改前",
    "report.plan.after": "修改后",
    "report.plan.note": "说明",
    "report.plan.footnote": "执行前会自动备份当前配置；如需还原，可在「备份与回滚」页面一键回滚。",
    "report.plan.footnote2": "若某项修改与你预期不符，请取消并先查看该检测项的原始证据。",
    "err.report_format": "不支持的报告格式: {fmt}（可选 html / json / text）",
    "report.file_prefix": "LanPulse报告",

    # ---- 界面骨架与环境提示 ----
    'env.admin_ok': '已获得管理员权限',
    'env.admin_limited': '普通权限运行\n部分修复不可用',
    'btn.elevate': '以管理员身份重启',
    'btn.selfcheck': '环境自检',
    'dns.vendor.unknown': '自定义 / 运营商',
    'settings.region.saved': '区域设置已保存',
    'settings.region.rerun_hint': '重新体检后生效；当前显示的是上次结果',
    'settings.cleaned': '已清理 {n} 个旧备份会话',
    "status.checking": '正在检测：{name}',

    # ---- v1.1.0 新增：场景化诊断 / 根因分析 / 网页分层 / 劫持检测 / 缓冲膨胀 ----
    'check.web_timing.title': '网页打开速度',
    'check.web_timing.category': '网页',
    'check.web_timing.summary_skipped': '已关闭联网探测',
    'check.dns_hijack.title': 'DNS 解析是否被篡改',
    'check.dns_hijack.category': '安全',
    'check.dns_hijack.summary_skipped': '已关闭联网探测',
    'check.dns_hijack.summary_no_dns': '未配置手动 DNS',
    'check.bufferbloat.title': '下载时延卡顿',
    'check.bufferbloat.category': '体验',
    'check.bufferbloat.summary_skipped': '已关闭联网探测',
    'check.bufferbloat.summary_unmeasurable': '无法测量延迟',
    'check.bufferbloat.summary_no_load': '无法产生有效下载负载',
    'metric.web_target': '测试站点',
    'metric.web_dns': 'DNS 解析',
    'metric.web_tcp': 'TCP 连接',
    'metric.web_tls': 'TLS 握手',
    'metric.web_ttfb': '首字节响应',
    'metric.web_cert': '证书剩余',
    'metric.hijack_query': '解析对比',
    'metric.bufferbloat_idle': '空闲延迟',
    'metric.bufferbloat_loaded': '下载时延迟',
    'metric.bufferbloat_delta': '延迟增量',
    'metric.bufferbloat_grade': '评级',
    'metric.grade_good': '优秀',
    'metric.grade_fair': '一般',
    'metric.grade_poor': '偏慢',
    'metric.grade_unknown': '未测',
    'scenario.slow.name': '上网很慢',
    'scenario.slow.desc': '网页加载慢、下载慢、视频缓冲久',
    'scenario.disconnect.name': '经常断网',
    'scenario.disconnect.desc': '偶尔掉线、需要重启路由器才能恢复',
    'scenario.web.name': '网页打不开',
    'scenario.web.desc': '某些或全部网站无法访问，但 QQ 等能上',
    'scenario.gaming.name': '游戏 / 视频卡顿',
    'scenario.gaming.desc': '网速够快，但游戏延迟高、视频会议卡',
    'scenario.security.name': '检查是否被劫持',
    'scenario.security.desc': '怀疑网站被篡改、跳转到广告页',
    'scenario.full.name': '完整体检',
    'scenario.full.desc': '运行全部 14 项检测（约 10-15 秒）',
    'rootcause.dhcp_failed.title': '路由器没有分配 IP 地址',
    'rootcause.dhcp_failed.impact': '拿到的是 169.254 开头的无效地址，无法上网',
    'rootcause.dhcp_failed.advice': '执行「重新获取 IP 地址」，仍失败请重启路由器',
    'rootcause.hosts_hijack.title': 'HOSTS 文件存在可疑记录',
    'rootcause.hosts_hijack.impact': '特定网站会被指向错误地址，可能被屏蔽或劫持',
    'rootcause.hosts_hijack.advice': '清理异常记录，并对电脑做一次杀毒扫描',
    'rootcause.dns_hijack.title': 'DNS 解析结果被篡改',
    'rootcause.dns_hijack.impact': '同一域名解析到错误的 IP，导致网站打不开或跳到假站',
    'rootcause.dns_hijack.advice': '切换到可信公共 DNS，并检查 HOSTS 文件',
    'rootcause.proxy_residual.title': '代理软件退出后残留了系统代理',
    'rootcause.proxy_residual.impact': '所有网页请求都被发往一个已关闭的端口，表现为完全无法上网',
    'rootcause.proxy_residual.advice': '关闭残留的系统代理设置',
    'rootcause.gateway_poor.title': '到路由器的这一段链路质量差',
    'rootcause.gateway_poor.impact': '丢包或延迟高，整条网络都不稳定',
    'rootcause.gateway_poor.advice': '无线环境先换 5GHz 或靠近路由器；有线检查网线与网口',
    'rootcause.dns_slow.title': 'DNS 解析速度慢',
    'rootcause.dns_slow.impact': '每次打开新网站都要先等解析，表现为“点开就卡一下”',
    'rootcause.dns_slow.advice': '清空 DNS 缓存，或切换到更快的公共 DNS',
    'rootcause.web_break.title': '网页访问在某一层中断',
    'rootcause.web_break.impact': '分层计时已定位到具体环节，不必逐项排查',
    'rootcause.web_break.advice': '按下方分层数据对应处理',
    'rootcause.mtu_mismatch.title': 'MTU 不匹配（大包被丢弃）',
    'rootcause.mtu_mismatch.impact': '小包能通、大包被丢，表现为“能开首页但视频和下载卡死”',
    'rootcause.mtu_mismatch.advice': '按实测值修正 MTU',
    'rootcause.bufferbloat.title': '下载时延迟明显升高',
    'rootcause.bufferbloat.impact': '带宽没跑满但延迟飙升，游戏与视频会议最容易感知',
    'rootcause.bufferbloat.advice': '在路由器启用 SQM / QoS，或限制后台大流量任务',
    'rootcause.firewall_off.title': 'Windows 防火墙处于关闭状态',
    'rootcause.firewall_off.impact': '这是安全风险，不会导致当前无法上网',
    'rootcause.firewall_off.advice': '建议重新启用防火墙',

    # ---- 场景页 ----
    'scenario.intro': '先选一个最接近你遇到的情况，系统会只跑相关的检查项',
    'scenario.checks_count': '{n} 项检查',
    'scenario.advanced_hint': '想逐项查看全部检测？用「诊断详情」页可以选择任意单项',
    'scenario.btn_full': '运行完整体检',

    # ---- 根因分析展示 ----
    'nav.scenario': '场景',
    'dashboard.no_problems': '没有发现需要处理的网络问题 ✓',
    'dashboard.other_issues': '其它异常（{n} 项，未归入上述原因）',
    'dashboard.confidence': '置信度 {level}',
    'rootcause.confidence.high': '高',
    'rootcause.confidence.medium': '中',
    'rootcause.confidence.low': '低',

    # ---- UI 骨架文案（v1.1.0 补齐）----
    'dashboard.not_scanned': '尚未体检',
    'dashboard.metrics_title': '当前网络状态',
    'dashboard.metrics_desc': '数据来自最近一次体检的快照',
    'dashboard.problems_title': '发现的问题',
    'dashboard.entries_title': '功能入口',
    'dashboard.scanning': '正在体检…',
    'dashboard.no_problems': '没有发现需要处理的网络问题 ✓',
    'dashboard.footer': '所有检测与修复均在本机完成，不联网上传任何数据。每项系统修改前都会自动备份，可在「备份与回滚」中随时还原。',
    'dashboard.all_ok': '共检测 {n} 项，全部正常',
    'dashboard.with_problems': '共检测 {n} 项，发现 {m} 个问题',
    'dashboard.confidence': '置信度 {level}',
    'dashboard.other_issues': '其它异常（{n} 项，未归入上述原因）',
    'btn.one_click_fix': '一键修复',
    'btn.manual_backup': '手动创建备份',
    'btn.discard': '放弃修改',
    'btn.restore_hosts': '恢复系统默认',
    'btn.execute_repair': '执行修复',
    'diagnose.pick_one': '选择左侧任一项查看详情',
    'diagnose.metrics': '指标',
    'diagnose.advice': '建议',
    'diagnose.evidence': '原始证据',
    'backup.restore_btn': '恢复到 {ts} 的状态',
    'backup.rollback_hint': '回滚只会还原备份中记录的项目，不会影响备份之后你对系统做的其它修改。',
    'dns.subtitle': '域名解析服务决定你访问网站走哪条路，是「网页打不开」的首要排查点',
    'dns.current_title': '当前 DNS 配置',
    'dns.current_desc': '读取自当前承载上网流量的网卡',
    'dns.choose_plan': '选择方案',
    'hosts.no_change': '内容未变化，无需保存。',
    'repair.subtitle': '根据体检结果自动勾选，你可以逐项调整；高危项默认不勾选',
    'repair.empty_hint': '先做一次网络体检，系统会在这里列出建议的修复项。',
    'scenario.intro': '先选一个最接近你遇到的情况，系统会只跑相关的检查项',
    'scenario.checks_count': '{n} 项检查',
    'scenario.advanced_hint': '想逐项查看全部检测？用「诊断详情」页可以选择任意单项',
    'scenario.btn_full': '运行完整体检',
    'nav.scenario': '场景',

    # ---- UI 骨架补充 ----
    'backup.restore_default': '恢复到此次备份状态',
    'repair.nothing_to_fix': '本次体检未发现需要修复的问题，无需执行修复 ✓',

    # ---- 仪表盘细节 ----
    'dashboard.hostname': '主机名',
    'dashboard.privilege': '管理员权限',
    'dashboard.elevated_yes': '已提权',
    'dashboard.elevated_no': '普通权限（部分修复不可用）',
    'gauge.waiting': '等待检测',
    'gauge.waiting_sample': '等待采样',
    'dashboard.entry_dns': 'DNS 优化中心',
    'dashboard.entry_dns_desc': '查看当前 DNS、测速、切换公共 DNS 或恢复自动获取',
    'dashboard.entry_hosts': 'HOSTS 管理',
    'dashboard.entry_hosts_desc': '可视化查看与编辑 HOSTS，识别屏蔽与劫持记录',
    'dashboard.entry_backup': '备份与回滚',
    'dashboard.entry_backup_desc': '所有系统修改前的快照都在这里，可随时一键还原',
    'dashboard.entry_report': '诊断报告',
    'dashboard.entry_report_desc': '导出 HTML / JSON / TXT 报告，记录本次体检全部证据',
    'dashboard.severity_ok': '网络状态良好',
    'dashboard.severity_info': '基本正常',
    'dashboard.severity_warn': '存在问题',
    'dashboard.severity_critical': '需要处理',
    'dashboard.severity_skip': '检测受限',

    # ---- 诊断页表头与状态 ----
    'diagnose.col_check': '检测项',
    'diagnose.col_state': '状态',
    'diagnose.col_result': '结论',
    'diagnose.col_time': '耗时',

    'diagnose.meta': '共 {n} 项｜{host}｜{ts}',

    # ---- 更新检查 ----
    # 这一组文案承担一个特殊职责：向用户解释"为什么一个号称零上传的软件
    # 会发网络请求"。措辞必须具体到"只请求一个版本号文件"，不能含糊成
    # "检查更新需要联网"——含糊会让用户怀疑前面所有承诺。
    'update.consent.title': '检查更新',
    'update.consent.body': 'LanPulse 可以每隔一段时间检查是否有新版本，要开启吗？',
    'update.consent.detail': (
        '检查时只会向官方网站请求一个版本号文件，不发送任何你的信息：'
        '没有账号、没有设备标识、没有使用统计。随时可以在设置里关闭。'
    ),
    'update.consent.yes': '开启检查',
    'update.consent.no': '不用了',
    'update.available': '发现新版本 v{version}',
    'update.view': '查看',
    'update.check_now': '立即检查',
    'update.checking': '正在检查…',
    'update.up_to_date': '已是最新版本',
    'settings.update.title': '检查更新',
    'settings.update.desc': '仅向官网请求一个版本号文件，不上传任何信息',
}

__all__ = ["CATALOG"]
