"""English language pack.

Conventions mirror app/i18n_zh.py: every user-facing string goes through
core.i18n.t(), and result objects carry *keys* that the UI layer translates.
Placeholder sets must match the Chinese catalog key-for-key
(tests/test_i18n.py enforces this).
"""
from __future__ import annotations

CATALOG: dict[str, str] = {
    # ------------------------------------------------------------------ #
    # Application shell
    # ------------------------------------------------------------------ #
    "app.name": "LanPulse",
    "app.brand": "LANPULSE",
    "app.tagline": "Network Checkup & One-click Fix",

    "nav.overview": "Overview",
    "nav.dns": "DNS Tuning",
    "nav.hosts": "HOSTS",
    "nav.repair": "One-click Fix",
    "nav.backup": "Backups & Rollback",
    "nav.diagnose": "Diagnostics",
    "nav.report": "Reports & Logs",
    "nav.settings": "Settings",

    "side.admin": "Running with administrator rights",
    "side.unprivileged": "Running without elevation\nSome repairs unavailable",

    # ------------------------------------------------------------------ #
    # Severity / risk
    # ------------------------------------------------------------------ #
    "sev.ok": "OK",
    "sev.info": "Notice",
    "sev.warn": "Warning",
    "sev.critical": "Critical",
    "sev.skip": "Skipped",

    "risk.low": "Low risk",
    "risk.medium": "Medium risk",
    "risk.high": "High risk",

    # ------------------------------------------------------------------ #
    # Common words
    # ------------------------------------------------------------------ #
    "common.none": "None",
    "common.unknown": "Unknown",
    "common.empty": "(empty)",
    "common.truncated": "… (truncated)",

    # List separators: full-width punctuation in Chinese, half-width + space in English
    "sep.summary": "; ",
    "sep.list": ", ",

    "status.ready": "Ready",
    "status.scanning": "Running checkup…",
    "status.scan_done": "Checkup complete | {n} checks | score {score}",
    "status.score": "Score {score}",
    "status.rolling_back": "Rolling back…",
    "status.task_failed": "Task failed",
    "status.detecting": "Checking: {name}",
    "status.summarizing": "Summarizing results…",
    "status.creating_backup": "Creating backup…",
    "status.phase_backup": "Backup",
    "status.phase_apply": "Apply",
    "status.phase_verify": "Verify",
    "status.progress": "{phase}: {action}",
    "status.yes": "Yes",
    "status.no": "No",
    "status.on": "On",
    "status.off": "Off",
    "status.enabled": "Enabled",
    "status.disabled": "Disabled",
    "status.success": "Succeeded",
    "status.failed": "Failed",
    "status.available": "Available",
    "status.listening": "Listening",
    "status.no_listener": "Nothing listening",
    "status.not_configured": "Not configured",
    "status.not_run": "Not run",
    "status.not_measured": "Not measured",
    "status.no_response": "No response",
    "status.unreachable": "Unreachable",
    "status.connectable": "Reachable",
    "status.unset": "Not set",
    "status.empty_paren": "(empty)",
    "status.empty_all_proxy": "(empty, everything goes through the proxy)",
    "status.direct_access": "Direct access",
    "status.direct_unset": "Not set (direct)",

    "value.static_manual": "Manually configured (static)",
    "value.static": "Static",
    "value.dhcp": "DHCP",
    "value.dhcp_auto": "Assigned automatically (DHCP)",
    "value.dhcp_issued": "Provided by DHCP",
    "value.manual_specified": "Manually specified",
    "value.overseas_only": "Overseas only",
    "value.private": "Private address",
    "value.public": "Public address",
    "value.no_ip": "No IP",
    "value.no_dns": "No DNS",
    "value.no_primary_adapter": "(no primary adapter detected)",
    "value.empty": "—",
    "value.bytes": "{n} bytes",
    "value.bytes_signed": "{n:+d} bytes",
    "value.seconds": "{n} s",
    "value.ms": "{n}ms",
    "value.dnsapi": "Windows DnsQuery API",
    "value.getaddrinfo": "socket.getaddrinfo fallback",
    "value.remote": "Remote",
    "value.inconsistent": "Mismatched",
    "value.consistent": "Matched",
    "value.inbound_unknown": "Inbound policy unknown",
    "value.not_from_adapter": "Not read from the adapter",
    "value.not_read": "Not read",
    "value.netsh_subifaces": "netsh subinterface table",
    "value.mtu_source_adapter": "{name} (Get-NetAdapter)",

    "grade.excellent": "Excellent",
    "grade.normal": "Normal",
    "grade.slow": "Slow",
    "grade.very_slow": "Very slow",
    "grade.high_latency": "High latency",
    "grade.icmp_blocked": "ICMP blocked or unreachable",

    # ------------------------------------------------------------------ #
    # Buttons
    # ------------------------------------------------------------------ #
    "btn.scan": "Start network checkup",
    "btn.scanning": "Running checkup…",
    "btn.repair": "One-click Fix",
    "btn.apply_plan": "Apply selected plan",
    "btn.restore_dhcp": "Restore automatic DNS",
    "btn.reload": "Reload",
    "btn.advanced_edit": "Advanced edit",
    "btn.exit_edit": "Exit editing",
    "btn.discard_edit": "Discard changes",
    "btn.save_hosts": "Save (auto-backup)",
    "btn.clean_hosts": "Clean abnormal entries",
    "btn.clean_hosts_n": "Clean abnormal entries ({n})",
    "btn.restore_default": "Restore system default",
    "btn.select_none": "Select none",
    "btn.select_safe": "Low risk only",
    "btn.dry_run": "Dry run first",
    "btn.execute": "Run fixes",
    "btn.execute_high": "Run fixes ({n} high-risk included)",
    "btn.open_backup_dir": "Open backup folder",
    "btn.new_backup": "Create backup now",
    "btn.rollback_session": "Restore to this backup",
    "btn.rollback_to": "Restore state of {time}",
    "btn.no_restorable": "Nothing restorable in this backup",
    "btn.export_html": "Export HTML report",
    "btn.export_json": "Export JSON",
    "btn.export_text": "Export TXT",
    "btn.refresh": "Refresh",
    "btn.yes": "Yes",
    "btn.no": "Cancel",
    "btn.close": "Close",
    "btn.confirm_save": "Save",
    "btn.confirm_execute": "Run",
    "btn.confirm_rollback": "Roll back",
    "btn.restart_admin": "Restart as administrator",
    "btn.env_check": "Environment check",

    # ------------------------------------------------------------------ #
    # Dashboard
    # ------------------------------------------------------------------ #
    "page.dashboard.headline_empty": "No checkup yet",
    "page.dashboard.metrics_title": "Current network status",
    "page.dashboard.metrics_sub": "Taken from the most recent checkup snapshot",
    "page.dashboard.problems_title": "Issues found",
    "page.dashboard.problems_empty": "Issues that need attention will be listed here after a checkup",
    "page.dashboard.problems_ok": "No network issues need attention ✓",
    "page.dashboard.entry_title": "Quick actions",
    "page.dashboard.entry.dns.title": "DNS tuning center",
    "page.dashboard.entry.dns.desc": "Inspect current DNS, test speed, switch to public DNS "
                                     "or restore automatic assignment",
    "page.dashboard.entry.hosts.title": "HOSTS manager",
    "page.dashboard.entry.hosts.desc": "View and edit HOSTS visually; spot blocked and hijacked entries",
    "page.dashboard.entry.backup.title": "Backups & Rollback",
    "page.dashboard.entry.backup.desc": "Snapshots taken before every system change, "
                                        "restorable at any time",
    "page.dashboard.entry.report.title": "Diagnostic reports",
    "page.dashboard.entry.report.desc": "Export HTML / JSON / TXT reports with all evidence "
                                        "from this checkup",
    "page.dashboard.footnote": "All detection and repair runs locally; nothing is uploaded. "
                               "Every system change is backed up beforehand and can be "
                               "restored from Backups & Rollback.",
    "page.dashboard.all_ok": "{n} checks ran, all healthy",
    "page.dashboard.has_problems": "{n} checks ran, {k} issues found",
    "page.dashboard.hostname": "Host name",
    "page.dashboard.admin": "Administrator",
    "page.dashboard.elevated": "Elevated",
    "page.dashboard.not_elevated": "Standard user (some repairs unavailable)",
    "page.dashboard.gauge.ok": "Network looks healthy",
    "page.dashboard.gauge.info": "Mostly healthy",
    "page.dashboard.gauge.warn": "Issues present",
    "page.dashboard.gauge.critical": "Needs attention",
    "page.dashboard.gauge.skip": "Limited by permissions",
    "page.dashboard.gauge.waiting": "Waiting for checkup",
    "page.dashboard.fix_tip": "Applies fixes based on the checkup; the full change list and an "
                              "automatic backup are shown before anything runs",

    "widget.health_score": "HEALTH SCORE",
    "widget.waiting_sample": "Waiting for samples",

    # ------------------------------------------------------------------ #
    # DNS page
    # ------------------------------------------------------------------ #
    "page.dns.subtitle": "Your DNS resolver decides which route every site takes — "
                         "the first place to look when pages won't open",
    "page.dns.current_title": "Current DNS configuration",
    "page.dns.current_sub": "Read from the adapter currently carrying your traffic",
    "page.dns.current_hint": "Current DNS servers appear here after a checkup",
    "page.dns.section_plans": "Choose a plan",
    "page.dns.apply_servers": "DNS for the active adapter will be set to {servers}. "
                              "The current configuration is backed up first and can be "
                              "restored from Backups & Rollback.",
    "page.dns.apply_dhcp": "DNS will be restored to automatic assignment by DHCP. "
                           "The current configuration is backed up first.",
    "page.dns.plan_dhcp_servers": "Assigned automatically by the router / DHCP server",
    "page.dns.not_included": "This checkup did not include the DNS check",
    "page.dns.no_servers": "Not configured or assigned automatically",
    "page.dns.iface": "Active adapter",
    "page.dns.advice": "· {text}",

    # ------------------------------------------------------------------ #
    # HOSTS page
    # ------------------------------------------------------------------ #
    "hosts.warn": "⚠ Editing HOSTS directly is risky: a bad entry can make some sites "
                  "unreachable. The current file is backed up before saving and can be "
                  "restored from Backups & Rollback.",
    "hosts.tip": "Cleaning removes only blocked and hijacked entries; every other line is "
                 "kept byte-for-byte. Restoring the default replaces the whole file with the "
                 "system template, so all custom entries are lost.",
    "hosts.col_line": "Line",
    "hosts.col_ip": "IP address",
    "hosts.col_domains": "Hostnames",
    "hosts.col_verdict": "Verdict",
    "hosts.read_error": "Cannot read the HOSTS file: {err}",
    "hosts.status_ok": "File looks healthy: {n} valid mappings, no suspicious entries.",
    "hosts.status_warn": "{n} valid mappings, of which {blocked} block a hostname "
                         "(typical of ad blockers or cracks). If a site won't open, check here first.",
    "hosts.status_critical": "{hijacked} suspected hijack entries and {blocked} blocked entries "
                             "found. Clean them now and run a full antivirus scan.",
    "hosts.risk.normal": "Normal",
    "hosts.risk.blocked": "Blocked",
    "hosts.risk.hijacked": "Suspected hijack",
    "hosts.note.blocked": "Blocks this hostname (common with ad filters or cracks)",
    "hosts.note.hijacked": "Critical hostname ({domains}) points to {ip}; {effect}",
    "hosts.note.hijack_blocked": "it will be blocked",
    "hosts.note.hijack_hijack": "it may be hijacked",
    "hosts.empty": "This HOSTS file has no custom mappings at all (only comments and blank "
                   "lines), which is usually the normal default state.",
    "hosts.unchanged": "Nothing changed, no need to save.",
    "hosts.judge": "{label} | {note}",

    # ------------------------------------------------------------------ #
    # Repair page
    # ------------------------------------------------------------------ #
    "page.repair.subtitle": "Items are pre-selected from the checkup; adjust them as you like. "
                            "High-risk items start unchecked",
    "page.repair.pledge": "🔒 Everything that will be modified is backed up first, and both the "
                          "backup location and contents stay visible on this machine. A failing "
                          "step never stops the others, and you can always roll back to the state "
                          "before this run from Backups & Rollback.",
    "page.repair.empty": "Run a network checkup first; suggested fixes will be listed here.",
    "page.repair.nothing": "This checkup found nothing that needs fixing ✓",
    "page.repair.selected": "{n} item(s) selected",
    "page.repair.selected_high": "{n} item(s) selected, {high} of them high risk",
    "page.repair.none_selected": "No fix selected yet",
    "page.repair.state.pending": "Pending",
    "page.repair.state.applied": "✓ Applied",
    "page.repair.state.skipped": "Skipped",
    "page.repair.state.failed": "✗ Failed",
    "page.repair.state.rolled_back": "Rolled back",
    "page.repair.state.rollback_failed": "Rollback failed",
    "page.repair.state.unverified": "Applied (verification failed)",
    "page.repair.state.with_message": "{text} | {message}",
    "page.repair.preview": "{target}: {before}  →  {after}",
    "page.repair.unknown_action": "Unknown action ({id})",
    "page.repair.unknown_action_desc": "This action is not registered in core/action_ids.py. "
                                       "A version mismatch is likely — do not run it.",
    "page.repair.dry_tip": "Runs the full backup and preview flow without changing any setting",
    "page.repair.confirm_head": "{n} fix(es) will be applied:",
    "page.repair.confirm_item": "  • [{risk}] {title}",
    "page.repair.confirm_backup": "A backup session is created beforehand (location: {path}).",
    "page.repair.confirm_high": "Note: {n} of them are high-risk and may need a reboot "
                                "to take full effect.",
    "page.repair.confirm_ask": "Continue?",
    "page.repair.confirm_title": "Confirm applying fixes",

    # ------------------------------------------------------------------ #
    # Backup page
    # ------------------------------------------------------------------ #
    "backup.warn": "Rollback restores only the items recorded in the backup; changes you made "
                   "to the system afterwards are left untouched.",
    "backup.pick_hint": "Select a backup on the left to see details",
    "backup.count": "{n} backup session(s)",
    "backup.col_time": "Time",
    "backup.col_kind": "Type",
    "backup.col_summary": "Contents",
    "backup.restored_suffix": " (restored)",
    "backup.no_changes": "(no persistent state changed)",
    "backup.not_restorable": "This session recorded no restorable state and exists only as an "
                             "audit trail",
    "backup.empty_title": "No backups yet.",
    "backup.empty_hint": "A backup is created automatically before every repair. You can also "
                         "click Create backup now to snapshot the current network configuration.",
    "backup.created": "Created",
    "backup.host": "Host",
    "backup.privilege": "Privilege at backup",
    "backup.privilege_admin": "Administrator",
    "backup.privilege_user": "Standard user",
    "backup.restored_once": "Already restored once at {time}",
    "backup.items": "Backed-up items ({n})",
    "backup.no_persist": "This operation touched no persistent configuration and is recorded "
                         "for audit purposes only.",
    "backup.dir": "Folder: {path}",
    "backup.confirm_title": "Confirm rollback",
    "backup.confirm_body": "{n} configuration item(s) will be restored to the state of {time}:\n\n"
                           "{items}",
    "backup.confirm_more": "\n  …",
    "backup.confirm_tail": "The network may drop briefly during rollback. Continue?",
    "backup.open_fail_title": "Cannot open folder",
    "backup.new_tip": "Snapshot the current network configuration before changing anything",

    # ------------------------------------------------------------------ #
    # Diagnose page
    # ------------------------------------------------------------------ #
    "page.diagnose.col_check": "Check",
    "page.diagnose.col_status": "Status",
    "page.diagnose.col_summary": "Conclusion",
    "page.diagnose.col_duration": "Time",
    "page.diagnose.pick": "Select any check on the left to see details",
    "page.diagnose.meta": "{n} checks | {host} | {time}",
    "page.diagnose.chip_tip": "{label}: {n}",
    "page.diagnose.section_metrics": "Metrics",
    "page.diagnose.section_advice": "Recommendations",
    "page.diagnose.section_evidence": "Raw evidence",
    "page.diagnose.error": "Check failed: {err}",

    # ------------------------------------------------------------------ #
    # Report page
    # ------------------------------------------------------------------ #
    "report.export_title": "Export this machine's report",
    "report.export_sub": "The report contains only local network configuration and results — "
                         "no personal data — so it is safe to share with a technician",
    "report.not_yet": "No checkup yet",
    "report.tip_html": "Single-file web page with full evidence; good for sending to others",
    "report.tip_json": "Structured data for tooling or archiving",
    "report.tip_text": "Plain text, easy to paste into a ticket",
    "report.audit_title": "Operation audit trail",
    "report.filter.all": "All events",
    "report.filter.repair": "Repairs",
    "report.filter.rollback": "Rollbacks",
    "report.filter.backup": "Backups",
    "report.col_time": "Time",
    "report.col_event": "Event",
    "report.col_target": "Operation",
    "report.col_result": "Result",
    "report.count": " | {n} record(s)",
    "report.ok": "Succeeded",
    "report.fail": "Failed",
    "report.summary": "Latest checkup: {time} | host {host} | {n} checks | "
                      "score {score} | {k} issues found",
    "report.summary_unelevated": " | running without elevation, some checks skipped",

    # ------------------------------------------------------------------ #
    # Settings page
    # ------------------------------------------------------------------ #
    "settings.section.general": "General",
    "settings.section.scan": "Detection",
    "settings.section.backup": "Backups",
    "settings.section.safety": "Safety",
    "settings.section.report": "Reports",
    "settings.section.data": "Data management",
    "settings.language.title": "Interface language",
    "settings.language.desc": "Applies immediately, no restart needed",
    "settings.language.auto": "Follow system",
    "action.needs_restart": "⚠ Takes effect after a restart; rollback is only valid before restarting",
    "settings.region.title": "Network region",
    "settings.region.desc": "Chooses which probe targets and DNS plans are used",
    "settings.region.auto": "Detect automatically",
    "settings.region.auto_hint": "The region is inferred from time zone, system language and "
                                 "measured latency.",
    "settings.region.detected": "Detected as “{region}”",
    "settings.region.basis": "Based on: {basis}",
    "settings.region.basis.timezone": "system time zone {tz}",
    "settings.region.basis.latency_cn": "latency pointing to mainland China (China anchor {cn} ms)",
    "settings.region.basis.latency_not_cn": "latency pointing outside mainland China "
                                            "(global anchor {gl} ms)",
    "settings.region.basis.locale": "system language",
    "settings.region.basis.none": "no time zone or latency available; fell back to the "
                                  "most lenient profile",
    "settings.region.shared_tz": "Mainland China, Hong Kong and Macau share one time zone, so "
                                 "the time zone alone cannot separate them — this result relies "
                                 "on the system region code. If it is wrong, pick a region above.",
    "settings.region.fixed_hint": "Pinned to “{region}”; probe targets and DNS plans for that "
                                  "region are used.",
    "settings.autoscan.title": "Checkup on startup",
    "settings.autoscan.desc": "Run a full checkup automatically when the app opens",
    "settings.probe.title": "Allow network probes",
    "settings.probe.desc": "When off, only local configuration is read and no network request "
                           "is made (connectivity and MTU measuring are skipped)",
    "settings.timeout.title": "Probe timeout multiplier",
    "settings.timeout.desc": "Raise it on slow networks so normal slowness is not reported "
                             "as a fault",
    "settings.backupkeep.title": "Backups to keep",
    "settings.backupkeep.desc": "Older sessions beyond this count are pruned automatically",
    "settings.highrisk.title": "Extra confirmation for high-risk actions",
    "settings.highrisk.desc": "Ask once more before running a high-risk repair",
    "settings.reportfmt.title": "Default report format",
    "settings.reportfmt.desc": "Format used by the export buttons on the report page",
    "settings.reportfmt.html": "HTML (single-file page)",
    "settings.reportfmt.json": "JSON (structured data)",
    "settings.reportfmt.text": "TXT (plain text)",
    "settings.evidence.title": "Include raw evidence in reports",
    "settings.evidence.desc": "Turning this off gives a shorter report but hides raw command "
                              "output when troubleshooting",
    "settings.open_data": "Open data folder",
    "settings.open_settings": "Open config file",
    "settings.reset": "Reset to defaults",
    "settings.reset.confirm.title": "Reset to defaults",
    "settings.reset.confirm.body": "All settings will return to their defaults, including "
                                   "interface language and network region.\n\nContinue?",
    "lang.zh": "Chinese",
    "lang.en": "English",

    # ------------------------------------------------------------------ #
    # Audit events
    # ------------------------------------------------------------------ #
    "audit.scan": "Network checkup",
    "audit.export_target": "{fmt} report",
    "audit.backup": "Manual backup",
    "audit.hosts_edit": "Manual HOSTS edit",
    "audit.hosts_edit_detail": "Saved with backup, session {session}",
    "audit.repair": "One-click Fix",
    "audit.rollback": "Rollback",
    "audit.counts": "{ok} succeeded, {fail} failed",

    # ------------------------------------------------------------------ #
    # Message boxes
    # ------------------------------------------------------------------ #
    "msg.scan_first": "Run a network checkup first",
    "msg.busy": "Another task is running, please wait",
    "msg.need_admin": "This operation needs administrator rights. "
                      "Click “Restart as administrator” first",
    "msg.need_admin_hosts": "Editing HOSTS requires administrator rights",
    "msg.hosts_save_title": "Confirm saving HOSTS",
    "msg.hosts_save_body": "The edited content will overwrite the HOSTS file.\n\n"
                           "The current file is backed up first and can be restored from "
                           "Backups & Rollback.\nWrong content can make some sites unreachable."
                           "\n\nSave now?",
    "msg.backup_done": "Backup snapshot created",
    "msg.hosts_saved": "HOSTS saved; the original file was backed up",
    "msg.task_failed_title": "Task failed",
    "msg.task_failed_body": "The operation could not complete:\n\n{err}\n\n"
                            "If this keeps happening, export a diagnostic report from "
                            "Reports & Logs.",
    "msg.dryrun_title": "Dry run complete",
    "msg.dryrun_body": "The dry run changed no system settings.\n\n"
                       "Backup session created: {session}\n"
                       "{n} action(s), all passed the backup stage.\n\n"
                       "If everything looks right, click Run fixes.",
    "msg.repair_title": "Repair complete",
    "msg.repair_head": "Done: {ok} item(s) succeeded",
    "msg.repair_fail": ", {fail} failed",
    "msg.repair_partial": "⚠ Some actions did not succeed. Consider rolling back this session "
                          "from Backups & Rollback.",
    "msg.repair_session": "Backup session: {session}",
    "msg.rollback_title": "Rollback result",
    "msg.rollback_head": "Rollback done: {ok} item(s) restored",
    "msg.rollback_partial": "Some items could not be restored; see details below and in the log.",
    "msg.export_ok_title": "Export succeeded",
    "msg.export_ok_body": "Report saved to:\n{path}",
    "msg.export_fail_title": "Export failed",
    "msg.export_fail_body": "Could not generate the report:\n{err}",
    "msg.elevate_cancelled_title": "Cancelled",
    "msg.elevate_cancelled_body": "Administrator rights were not granted; the app continues in "
                                  "read-only mode.\nCheckups, report export and backup viewing "
                                  "still work.",
    "msg.unavailable": "Unavailable",
    "msg.elevate_unavailable": "The elevation module is unavailable: {err}",
    "msg.env_unavailable": "The environment check module is unavailable: {err}",
    "msg.env_fail": "Environment check failed",
    "msg.env_title": "Environment check",
    "msg.env_heading": "Runtime environment check",
    "msg.exit_title": "Task in progress",
    "msg.exit_body": "A task is still running. Quitting now may interrupt a system change and "
                     "leave a half-applied configuration behind.\n\nQuit anyway?",
    "msg.no_report": "No checkup result yet — run one first",

    "err.open_failed": "Cannot open the file",

    # ------------------------------------------------------------------ #
    # Metric names
    # ------------------------------------------------------------------ #
    "metric.link_speed": "Link speed",
    "metric.adapter_count": "Adapters",
    "metric.primary_adapter": "Active adapter",
    "metric.ipv4": "IPv4 address",
    "metric.gateway": "Default gateway",
    "metric.ping_target": "Direct IPv4 {target}",
    "metric.loss_rate": "Internet packet loss",
    "metric.tcp_target": "TCP {host}:{port}",
    "metric.dns_resolve": "DNS lookup",
    "metric.total_budget": "Round budget",
    "metric.probe_domains": "Probe hostnames",
    "metric.avg_resolve_ms": "Average lookup time",
    "metric.min_max_ms": "Fastest / slowest",
    "metric.resolve_via": "Lookup method",
    "metric.interface": "Active adapter",
    "metric.dns_count": "DNS server count",
    "metric.config_mode": "Configuration mode",
    "metric.loopback_dns": "Local DNS listener",
    "metric.dns_route": "DNS route",
    "metric.dns_owner": "DNS owner",
    "metric.dhcp_issued": "Provided by DHCP",
    "metric.return_code": "Command exit code",
    "metric.is_admin": "Administrator",
    "metric.profile_firewall": "{profile} firewall",
    "metric.route_count": "Default routes",
    "metric.adapter_gateway": "Gateway reported by adapter",
    "metric.active_gateway": "Effective gateway",
    "metric.multi_gateway": "Multiple default gateways",
    "metric.gateway_latency": "Gateway latency",
    "metric.gateway_loss": "Gateway packet loss",
    "metric.file_path": "File path",
    "metric.file_size": "File size",
    "metric.total_lines": "Total lines",
    "metric.mapping_lines": "Valid mappings",
    "metric.blocked_records": "Blocked entries",
    "metric.hijack_records": "Hijacked entries",
    "metric.suspicious_total": "Suspicious entries",
    "metric.up_adapters": "Connected adapters",
    "metric.current_adapter": "Current adapter",
    "metric.acquire_mode": "Address source",
    "metric.address_type": "Address type",
    "metric.gateway_same_subnet": "Gateway on same subnet",
    "metric.ipv4_dns_count": "IPv4 DNS servers",
    "metric.configured_mtu": "Configured MTU",
    "metric.measured_mtu": "Measured path MTU",
    "metric.probe_target": "Probe target",
    "metric.probe_attempts": "Probes run",
    "metric.mtu_gap": "Configured vs measured gap",
    "metric.registry_path": "Registry path",
    "metric.proxy_enable": "Proxy switch",
    "metric.proxy_server": "Proxy server",
    "metric.proxy_override": "Bypass list",
    "metric.auto_config_url": "Auto-config script",
    "metric.winhttp_proxy": "WinHTTP proxy",
    "metric.pac_reachable": "Auto-config script reachable",
    "metric.local_proxy": "Local proxy {host}:{port}",
    "metric.remote_proxy": "Proxy server {host}:{port}",
    "metric.consistency": "WinHTTP vs WinINET consistency",
    "metric.tcp_global_rc": "tcp global command exit code",
    "metric.ip_global_rc": "ip global command exit code",
    "metric.autotuning": "Receive window auto-tuning",
    "metric.ecn": "ECN",
    "metric.rss": "RSS receive-side scaling",
    "metric.timestamps": "TCP timestamps",
    "metric.scaling_heuristics": "Window scaling heuristics",
    "metric.param_count": "Parameter count",

    # ------------------------------------------------------------------ #
    # DNS vendors / regions / plans
    # ------------------------------------------------------------------ #
    "dns.vendor.aliyun": "Alibaba Cloud Public DNS",
    "dns.vendor.tencent": "Tencent DNSPod",
    "dns.vendor.dns114": "114DNS",
    "dns.vendor.baidu": "Baidu DNS",
    "dns.vendor.bytedance": "ByteDance DNS",
    "dns.vendor.chinatelecom": "China Telecom DNS",
    "dns.vendor.chinamobile": "China Mobile DNS",
    "dns.vendor.google": "Google Public DNS",
    "dns.vendor.cloudflare": "Cloudflare",
    "dns.vendor.quad9": "Quad9",
    "dns.vendor.opendns": "OpenDNS",
    "dns.vendor.adguard": "AdGuard DNS",
    "dns.vendor.controld": "Control D",
    "dns.vendor.yandex": "Yandex DNS",
    "dns.vendor.korea": "Korean public DNS",
    "dns.vendor.jp": "Japanese public DNS",
    "dns.vendor.hk": "Hong Kong public DNS",
    "dns.vendor.mo": "Macau public DNS",
    "dns.vendor.tw": "HiNet DNS (Taiwan)",
    "dns.vendor.sg": "Singapore public DNS",
    "dns.vendor.in": "Indian public DNS",
    "dns.vendor.au": "Australian public DNS",
    "dns.vendor.eu": "European public DNS",
    "dns.vendor.na": "North American public DNS",
    "dns.vendor.custom": "Custom / ISP",

    "dns.owner.aliyun": "Alibaba Public DNS",
    "dns.owner.tencent": "Tencent DNSPod",
    "dns.owner.dns114": "114DNS",
    "dns.owner.baidu": "Baidu Public DNS",
    "dns.owner.google": "Google Public DNS (overseas)",
    "dns.owner.cloudflare": "Cloudflare DNS (overseas)",
    "dns.owner.quad9": "Quad9 (overseas)",
    "dns.owner.opendns": "OpenDNS (overseas)",
    "dns.owner.chinatelecom": "China Telecom / 360 Public DNS",
    "dns.owner.ct": "China Telecom Public DNS",
    "dns.owner.bytedance": "ByteDance Public DNS",
    "dns.owner.onedns": "OneDNS",
    "dns.owner.loopback": "LAN DNS (router or ISP)",
    "dns.owner.custom": "Custom / ISP DNS",

    "dns.plan.ali_tencent.name": "Alibaba + Tencent",
    "dns.plan.ali_tencent.tag": "Recommended · fastest in China",
    "dns.plan.ali_tencent.desc": "Most accurate CDN resolution inside China with low latency; "
                                 "domains are not resolved to overseas nodes. A good fit for "
                                 "most home broadband.",
    "dns.plan.dns114.name": "114 DNS",
    "dns.plan.dns114.tag": "Stable · long-established",
    "dns.plan.dns114.desc": "Carrier-grade DNS with wide coverage and very stable availability; "
                            "pollution resistance is only average.",
    "dns.plan.global_public.name": "Cloudflare + Google",
    "dns.plan.global_public.tag": "Overseas · use with care",
    "dns.plan.global_public.desc": "Best privacy, but inside China resolution may be scheduled "
                                   "to overseas nodes, making real access slower.",
    "dns.plan.quad9.name": "Quad9",
    "dns.plan.quad9.tag": "Secure · blocks malicious domains",
    "dns.plan.quad9.desc": "Blocks known malicious domains automatically and protects privacy "
                           "well; direct connections from China are slower.",
    "dns.plan.opendns.name": "OpenDNS",
    "dns.plan.opendns.tag": "Content filtering",
    "dns.plan.opendns.desc": "Offers content filtering and parental controls; direct connections "
                             "from China are slower.",
    "dns.plan.hk_local.name": "Hong Kong local DNS",
    "dns.plan.hk_local.tag": "Local · Hong Kong",
    "dns.plan.hk_local.desc": "Hong Kong ISP DNS resolves fastest locally; may slow down "
                              "once traffic leaves the region.",
    "dns.plan.mo_local.name": "Macau local DNS",
    "dns.plan.mo_local.tag": "Local · Macau",
    "dns.plan.mo_local.desc": "Macau has only two fixed-line carriers, CTM and MTel, so local DNS resolves most accurately; international traffic usually exits via Hong Kong and may slow down outside the region.",
    "dns.plan.tw_local.name": "HiNet DNS",
    "dns.plan.tw_local.tag": "Local · Taiwan",
    "dns.plan.tw_local.desc": "Best local resolution in Taiwan with nearby CDN nodes; "
                              "traffic to mainland sites may take a detour.",
    "dns.plan.jp_local.name": "Japanese local DNS",
    "dns.plan.jp_local.tag": "Local · Japan",
    "dns.plan.jp_local.desc": "Japanese public DNS resolves local sites and CDN nodes more "
                              "accurately.",
    "dns.plan.kr_local.name": "Korean local DNS",
    "dns.plan.kr_local.tag": "Local · Korea",
    "dns.plan.kr_local.desc": "Korean public DNS resolves Korean sites faster and more "
                              "accurately.",
    "dns.plan.sg_local.name": "Singapore local DNS",
    "dns.plan.sg_local.tag": "Local · Singapore",
    "dns.plan.sg_local.desc": "Singapore ISP DNS keeps resolution inside Southeast Asia.",
    "dns.plan.in_local.name": "Indian local DNS",
    "dns.plan.in_local.tag": "Local · India",
    "dns.plan.in_local.desc": "Indian public DNS keeps resolution in South Asia; "
                              "international routes vary in quality.",
    "dns.plan.au_local.name": "Australian local DNS",
    "dns.plan.au_local.tag": "Local · Australia",
    "dns.plan.au_local.desc": "Australian public DNS resolves closer within Oceania; "
                              "cross-ocean access still depends on upstream routes.",
    "dns.plan.eu_local.name": "EU public DNS",
    "dns.plan.eu_local.tag": "Privacy-first · inside the EU",
    "dns.plan.eu_local.desc": "Servers are located inside the EU and bound by GDPR, so "
                              "query-log retention policies are more transparent.",
    "dns.plan.na_local.name": "North American public DNS",
    "dns.plan.na_local.tag": "Local · North America",
    "dns.plan.na_local.desc": "North American public DNS resolves closer within the Americas.",
    "dns.plan.dhcp.name": "Automatic (router-assigned)",
    "dns.plan.dhcp.tag": "Fallback",
    "dns.plan.dhcp.desc": "Restores automatic assignment by the router / DHCP. Pick this on a "
                          "company or campus network, or when using your ISP's DNS.",

    "region.cn": "Mainland China",
    "region.hk": "Hong Kong, China",
    "region.mo": "Macau, China",
    "region.tw": "Taiwan, China",
    "region.jp": "Japan",
    "region.kr": "South Korea",
    "region.sg": "Singapore / Southeast Asia",
    "region.in": "India / South Asia",
    "region.au": "Australia / New Zealand",
    "region.na": "North America",
    "region.eu": "Europe",
    "region.other": "Other regions",

    "probe.aliyun": "Alibaba Cloud DNS",
    "probe.tencent": "Tencent DNS",
    "probe.cloudflare": "Cloudflare",
    "probe.google": "Google DNS",
    "probe.quad9": "Quad9",
    "probe.tw": "HiNet DNS",
    "probe.korea": "Korean public DNS",
    "probe.jp": "Japanese public DNS",
    "probe.sg": "Singapore public DNS",
    "probe.in": "Indian public DNS",
    "probe.au": "Australian public DNS",

    "env.vpn_active": "VPN / tunnel adapter detected",
    "env.proxy": "System proxy enabled",
    "env.ipv6_only": "Only an IPv6 address was obtained",
    "env.captive_portal": "Web login required (captive portal)",

    # ------------------------------------------------------------------ #
    # Check: registry fallback
    # ------------------------------------------------------------------ #
    "check.registry.summary_failed": "Check did not complete",
    "check.registry.detail_failed": "This check failed and was skipped.\nReason: {err}",

    # ------------------------------------------------------------------ #
    # Check: adapter
    # ------------------------------------------------------------------ #
    "check.adapter.title": "Adapter and link status",
    "check.adapter.category": "Link",
    "check.adapter.summary_none": "No network adapter found",
    "check.adapter.detail_none": "The system reports no usable network adapters. On a virtual "
                                 "machine or a fresh install, make sure the adapter driver is "
                                 "installed correctly.",
    "check.adapter.problem.all_down": "All network adapters are disconnected",
    "check.adapter.problem.virtual_only": "Only virtual or tunnel adapters are connected; the "
                                          "physical adapter is not",
    "check.adapter.problem.no_ipv4": "Connected adapters have no usable IPv4 address or default "
                                     "gateway",
    "check.adapter.problem.apipa": "The adapter got the APIPA address {ip}, meaning DHCP did not "
                                   "assign an address, so internet access is unavailable",
    "check.adapter.summary_ok": "Adapter link is healthy and connected",
    "check.adapter.advice.device_manager": "Check Device Manager for a warning icon on the "
                                           "network adapter",
    "check.adapter.advice.check_cable": "Check the cable / Wi-Fi switch and confirm the router "
                                        "has power",
    "check.adapter.advice.physical_disabled": "Check whether the physical adapter is disabled or "
                                              "a virtual adapter took over the route",
    "check.adapter.advice.apipa": "Use “Reacquire IP address” under One-click Fix, or confirm "
                                  "DHCP is enabled on the router",
    "check.adapter.note.adapter_count": "{up} connected / {virtual} virtual",
    "check.adapter.detail.line": "• {name} | {status} | {ip}{virtual}",
    "check.adapter.detail.virtual": " | virtual",

    # ------------------------------------------------------------------ #
    # Check: ip
    # ------------------------------------------------------------------ #
    "check.ip.title": "IP address configuration",
    "check.ip.category": "Link",
    "check.ip.summary_none": "No usable network connection; cannot obtain an IPv4 address",
    "check.ip.detail_none": "All adapters are disconnected, or connected without an IPv4 address.",
    "check.ip.note.up_adapters": "{n} in total",
    "check.ip.problem.no_ipv4": "Adapter “{name}” has no IPv4 address",
    "check.ip.problem.apipa": "The adapter got the APIPA address {ip}, meaning DHCP did not "
                              "assign an address, so internet access is unavailable",
    "check.ip.problem.invalid_prefix": "Subnet prefix {n} is invalid; the subnet cannot be "
                                       "determined",
    "check.ip.problem.gw_diff": "Gateway {gw} and this host {ip}/{prefix} (subnet {net}) are not "
                                "on the same subnet; traffic may not get out",
    "check.ip.summary_ok": "IPv4 configuration is healthy: {ip}/{prefix} ({mode}), gateway on the "
                           "same subnet",
    "check.ip.advice.connect": "Plug in the cable or turn on Wi-Fi, and confirm the router has "
                               "power",
    "check.ip.advice.regain": "Click “Reacquire IP address”, or confirm DHCP is enabled on the "
                              "router",
    "check.ip.advice.apipa": "First confirm DHCP is enabled on the router; if it still fails, "
                             "reset the lease with “Reacquire IP address”",
    "check.ip.advice.invalid_prefix": "Set the adapter to obtain an IP automatically, or re-enter "
                                      "it to match the router subnet",
    "check.ip.advice.gw_diff": "Check whether the subnet mask is wrong; home networks should use "
                               "255.255.255.0 (/24)",
    "check.ip.note.apipa": "APIPA automatic private address",
    "check.ip.note.network": "Subnet {net}",
    "check.ip.note.prefix_invalid": "Abnormal prefix length",
    "check.ip.note.nat": "Outbound traffic is NAT-translated",
    "check.ip.note.public_direct": "Holds a public address directly",
    "check.ip.detail.line": "• {name} | {status} | {ip}/{prefix} | {mode} | gateway {gw}",

    # ------------------------------------------------------------------ #
    # Check: gateway
    # ------------------------------------------------------------------ #
    "check.gateway.title": "Default gateway and routing",
    "check.gateway.category": "Link",
    "check.gateway.summary_skip": "Cannot read the routing table; gateway check skipped",
    "check.gateway.detail_skip": "`route print -4` returned {rc}, output: {out}",
    "check.gateway.problem.no_route": "There is no 0.0.0.0 default route; this host can only reach "
                                      "devices on the same subnet",
    "check.gateway.problem.multi_route": "{n} default routes exist; traffic may take the wrong "
                                         "adapter (VPN / virtual adapter taking over)",
    "check.gateway.problem.gw_slow": "Gateway latency {ms}ms is high; the local link quality is "
                                     "poor",
    "check.gateway.problem.gw_mid": "Gateway latency {ms}ms is slightly above what wired networks "
                                    "normally show",
    "check.gateway.problem.gw_icmp": "Gateway {gw} did not answer ping (most routers block ICMP by "
                                     "default; that is normal and not a link failure)",
    "check.gateway.summary_ok": "Default gateway {gw} is configured correctly",
    "check.gateway.summary_ok_extra": "Default gateway {gw} is configured correctly, plus {n} "
                                      "backup default route(s)",
    "check.gateway.summary_ok_nogw": "The routing table has no parseable default gateway, but the "
                                     "adapter reports one",
    "check.gateway.advice.no_route": "Check whether the adapter received a gateway; reacquire the "
                                     "IP address if needed",
    "check.gateway.advice.high_metric": "The default route metric is high; if another adapter is "
                                        "also online, confirm the egress is correct",
    "check.gateway.advice.multi_route": "Disconnect unused VPNs or virtual adapters, or adjust "
                                        "adapter metrics",
    "check.gateway.advice.gw_slow": "On wired networks check the cable and connector; on Wi-Fi "
                                    "move closer to the router or use 5GHz",
    "check.gateway.note.route_count": "0.0.0.0/0 entries in route print -4",
    "check.gateway.note.route_count_fail": "The command did not return successfully",
    "check.gateway.note.route": "metric {metric} | interface {interface}",
    "check.gateway.note.multi": "{gw}(metric {metric})",
    "check.gateway.note.loss": "loss {loss}%",
    "check.gateway.note.icmp": "Routers commonly block ICMP; this is not a link failure",
    "check.gateway.detail.route": "• Default route → {gw} | interface {interface} | metric {metric}",
    "check.gateway.detail.no_route": "• No 0.0.0.0 default route found",

    # ------------------------------------------------------------------ #
    # Check: dns_server
    # ------------------------------------------------------------------ #
    "check.dns_server.title": "DNS server configuration",
    "check.dns_server.category": "DNS",
    "check.dns_server.problem.no_dns": "Adapter “{interface}” has no IPv4 DNS server configured, "
                                       "so only hostnames hard-coded in HOSTS can be resolved",
    "check.dns_server.problem.invalid_addr": "The DNS configuration contains an invalid address "
                                             "{ip}",
    "check.dns_server.problem.loopback": "DNS points to the local loopback address {ip}, but "
                                         "nothing is listening on port 53, so lookups fail "
                                         "immediately",
    "check.dns_server.problem.too_many": "{n} DNS servers are configured; too many slows down "
                                         "failover when a lookup fails",
    "check.dns_server.problem.overseas": "All DNS servers are overseas; direct lookups from China "
                                         "often take over 100ms",
    "check.dns_server.summary_ok": "DNS configuration is healthy ({mode}): {head}",
    "check.dns_server.advice.restore_dhcp": "Set DNS to automatic; on a company or campus network "
                                            "ask IT for the internal DNS addresses",
    "check.dns_server.advice.invalid_addr": "Set DNS to automatic, or enter a public server "
                                            "(223.5.5.5)",
    "check.dns_server.advice.loopback": "Leftover entries usually come from uninstalled proxy or "
                                        "accelerator software; switching to automatic fixes it",
    "check.dns_server.advice.too_many": "Two commonly used DNS servers are enough",
    "check.dns_server.advice.overseas": "If pages feel slow, try Alibaba 223.5.5.5 or Tencent "
                                        "119.29.29.29",
    "check.dns_server.note.loopback_on": "a service answers on {ip}:53",
    "check.dns_server.note.loopback_off": "nothing answers on {ip}:53",
    "check.dns_server.note.overseas": "direct lookups to overseas DNS from China can exceed 100ms",
    "check.dns_server.note.owner_custom": "{n} of them are not well-known public DNS",
    "check.dns_server.note.owner_known": "all are well-known public DNS",
    "check.dns_server.note.dhcp": "Assigned by the router and refreshed when joining a new network",
    "check.dns_server.detail.owner": "• {ip} → {owner}",
    "check.dns_server.detail.iface": "• {name}: {servers}",
    "check.dns_server.owner_pair": "{ip}={owner}",
    "check.dns_server.owner_pair_full": "{ip} ({owner})",

    # ------------------------------------------------------------------ #
    # Check: dns_resolve
    # ------------------------------------------------------------------ #
    "check.dns_resolve.title": "Domain resolution and response speed",
    "check.dns_resolve.category": "DNS",
    "check.dns_resolve.summary_skip": "No DNS query could be issued within the time budget; check "
                                      "skipped",
    "check.dns_resolve.detail_skip": "The whole {budget} s budget was used up without producing a "
                                     "judgeable sample.",
    "check.dns_resolve.summary_ok": "DNS resolution is healthy: {n} hostnames averaged {ms}ms "
                                    "({grade})",
    "check.dns_resolve.summary_ok_noms": "{n} hostnames resolved successfully",
    "check.dns_resolve.problem.all_fail": "All {n} probe hostnames failed to resolve; domains are "
                                          "unreachable although direct IP traffic may still work",
    "check.dns_resolve.problem.avg_very_slow": "Average lookup time is {ms}ms, which severely "
                                               "slows page loads",
    "check.dns_resolve.problem.avg_slow": "Average lookup time is {ms}ms, slower than normal "
                                          "(should be < {limit}ms)",
    "check.dns_resolve.problem.partial": "{n} hostnames failed to resolve; a single DNS record may "
                                         "be broken",
    "check.dns_resolve.problem.hijacked": "{n} hostnames resolved to invalid addresses (possible "
                                          "HOSTS blocking or DNS hijacking): {names}",
    "check.dns_resolve.advice.flush": "Try “Flush DNS cache” first; if it still fails, switch to a "
                                      "public DNS (223.5.5.5)",
    "check.dns_resolve.advice.switch_public": "Switching to a public DNS usually improves this "
                                              "immediately",
    "check.dns_resolve.advice.try_ali_tencent": "Compare with Alibaba 223.5.5.5 / Tencent "
                                                "119.29.29.29",
    "check.dns_resolve.advice.check_hosts": "Check the HOSTS file for blocking entries; if there "
                                            "are none, DNS is being hijacked",
    "check.dns_resolve.note.probe_domains": "{ok} succeeded / {fail} failed",
    "check.dns_resolve.detail.ok": "• {name} → {ips} ({ms}ms)",
    "check.dns_resolve.detail.fail": "• {name} → lookup failed: {err}",
    "check.dns_resolve.no_a_record": "(no A record)",
    "err.resolve_timeout": "lookup timed out (>{sec}s)",
    "err.dnsquery_rc": "DnsQuery returned {rc} ({text})",
    "err.dnsapi_unavailable": "dnsapi is unavailable",
    "err.no_a_record": "No A record returned",

    "rc.0": "Success",
    "rc.9003": "Domain does not exist (NXDOMAIN)",
    "rc.9002": "DNS server failure (SERVFAIL)",
    "rc.9501": "No such record",
    "rc.1460": "Operation timed out",
    "rc.11001": "Host not found",
    "rc.11002": "Cannot resolve; server did not respond",
    "rc.11003": "Non-recoverable error",
    "rc.11004": "No data record",
    "rc.unknown": "Unknown error",

    # ------------------------------------------------------------------ #
    # Check: hosts
    # ------------------------------------------------------------------ #
    "check.hosts.title": "HOSTS file",
    "check.hosts.category": "Resolution",
    "check.hosts.summary_read_error": "Cannot read the HOSTS file: {err}",
    "check.hosts.detail_read_error": "Path {path}\nReason: {err}\n"
                                     "Usually caused by security software locking the file or "
                                     "changed permissions; name resolution will fall back to "
                                     "plain DNS lookups.",
    "check.hosts.advice.admin_notepad": "Open Notepad as administrator and inspect "
                                        "%SystemRoot%\\System32\\drivers\\etc\\hosts",
    "check.hosts.problem.hijacked": "{n} entries rewrite major-site hostnames ({names}), which "
                                    "makes those sites fail to open or land on the wrong address",
    "check.hosts.problem.blocked": "{n} hostnames are blocked (a common ad-blocker or crack "
                                   "technique, not a system fault, but those sites are blocked)",
    "check.hosts.problem.near_empty": "The HOSTS file is nearly empty; it may have been cleared or "
                                      "replaced (the system default contains at least localhost)",
    "check.hosts.problem.zero": "The HOSTS file is 0 bytes and has been emptied",
    "check.hosts.summary_ok": "HOSTS is healthy: {n} custom mappings, no blocked or hijacked "
                              "entries",
    "check.hosts.advice.clean": "Clean the abnormal entries from HOSTS; if you did install an ad "
                                "blocker or crack, review those entries yourself",
    "check.hosts.advice.blocked": "If a site will not open and it is not a network problem, check "
                                  "whether it is blocked here",
    "check.hosts.advice.restore": "Use “Restore default HOSTS” to rebuild it; the original file is "
                                  "backed up first",
    "check.hosts.note.mapping_lines": "Commented-out or blank lines are not counted",
    "check.hosts.note.blocked": "Mapped to a blackhole such as 0.0.0.0 / 127.0.0.1",
    "check.hosts.note.hijacked": "A major-site hostname was rewritten",
    "check.hosts.reason.blackhole": "Mapped to the blackhole address {ip}, which blocks the "
                                    "hostname",
    "check.hosts.reason.watched": "Hits the major-site hostname {name}, which should never appear "
                                  "in HOSTS",
    "check.hosts.detail.suspicious_head": "Suspicious entries (showing at most {n}):",
    "check.hosts.detail.suspicious_line": "  {line}: {raw}  | {reason}",
    "check.hosts.detail.more": "  …and {n} more",
    "check.hosts.detail.none": "No suspicious entries found.",
    "check.hosts.detail.entries_head": "All {n} valid mappings:",
    "check.hosts.detail.entry": "  {line}: {ip} {hosts}",

    # ------------------------------------------------------------------ #
    # Check: proxy
    # ------------------------------------------------------------------ #
    "check.proxy.title": "System proxy settings",
    "check.proxy.category": "Proxy",
    "check.proxy.summary_skip": "Cannot read system proxy settings (registry not accessible); "
                                "check skipped",
    "check.proxy.detail_skip": "Reading HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\"
                               "Internet Settings failed. This key is normally readable by any "
                               "account, so failure usually means security software protects it.",
    "check.proxy.summary_direct": "No system proxy in use; the network is direct (normal)",
    "check.proxy.summary_auto_only": "The system proxy is off; only the auto-config script is used",
    "check.proxy.summary_ok": "The system proxy is enabled and its service is listening; "
                              "configuration is healthy",
    "check.proxy.problem.pac_fail": "The PAC auto-config script is unreachable: {url}",
    "check.proxy.problem.dead": "The system proxy points to local {addrs}, but nothing is listening "
                                "on that port; the browser sends every request there and cannot "
                                "reach the internet at all",
    "check.proxy.problem.empty": "The system proxy switch is on but the proxy server address is "
                                 "empty, so the browser cannot send any request",
    "check.proxy.problem.local_alive": "A local proxy {addrs} is in use (the proxy app is running, "
                                       "which is normal)",
    "check.proxy.problem.remote": "A remote proxy {addrs} is in use; if you cannot get online, "
                                  "confirm that proxy service is reachable",
    "check.proxy.problem.pac_lost": "The PAC auto-config script is unreachable; the proxy rules may "
                                    "no longer be valid",
    "check.proxy.advice.pac": "If PAC is not needed, clear the checkbox under Internet Options → "
                              "Connections → LAN settings",
    "check.proxy.advice.dead": "If the proxy app exited unexpectedly, start it again, or use "
                               "“Disable leftover system proxy” to go direct",
    "check.proxy.advice.empty": "Use “Disable leftover system proxy” to switch back to a direct "
                                "connection",
    "check.proxy.advice.consistency": "“Browser works but the command line does not” is usually "
                                      "caused by this mismatch",
    "check.proxy.note.endpoints": "{n} endpoint(s)",
    "check.proxy.note.proxy_running": "The proxy app is running",
    "check.proxy.note.proxy_dead": "The proxy app exited but the system proxy was not cleared",
    "check.proxy.note.remote": "Not a local proxy; no connectivity probe was made",
    "check.proxy.note.consistency": "Windows Update and some command-line tools use WinHTTP and "
                                    "may ignore the browser proxy",
    "check.proxy.detail.enable": "• Proxy switch: {value}",
    "check.proxy.detail.server": "• Proxy server: {value}",
    "check.proxy.detail.override": "• Bypass list: {value}",
    "check.proxy.detail.pac": "• Auto-config script: {value}",
    "check.proxy.detail.winhttp": "• WinHTTP: {value}",
    "check.proxy.detail.endpoints": "• Parsed endpoints: {list}",
    "err.file_missing": "File not found: {path}",
    "err.connect_failed": "Cannot connect to {host}:{port} ({err})",
    "err.unsupported_protocol": "Unsupported protocol: {url}",

    # ------------------------------------------------------------------ #
    # Check: tcp
    # ------------------------------------------------------------------ #
    "check.tcp.title": "TCP/IP stack parameters",
    "check.tcp.category": "Protocol stack",
    "check.tcp.summary_broken": "Cannot read TCP/IP stack state; the stack may be damaged",
    "check.tcp.detail_broken": "{reason}.\nBoth commands normally print a complete global parameter "
                               "table; a failure or an empty table usually means the Winsock or "
                               "stack registry entries are broken.",
    "check.tcp.reason.cmd_rc": "`netsh int ip show global` returned {rc}",
    "check.tcp.reason.parse_fail": "`netsh int tcp show global` produced empty or unparseable "
                                   "output",
    "check.tcp.advice.reset": "Run “Reset TCP/IP stack” first, reboot, then check again",
    "check.tcp.note.autotuning_unknown": "The parameter was not found in the output",
    "check.tcp.note.autotuning_ok": "Lets the window grow with the bandwidth-delay product",
    "check.tcp.note.autotuning_bad": "Restricted; throughput drops on high-latency links",
    "check.tcp.note.ecn": "Explicit congestion notification; being off is a normal default and "
                          "does not affect internet access",
    "check.tcp.note.rss": "Spreads packet reception across cores; disabling caps high bandwidth",
    "check.tcp.note.timestamps": "RFC1323 timestamps for RTT measurement and sequence-wrap "
                                 "protection",
    "check.tcp.note.scaling": "disabled is the recommended value (Windows default)",
    "check.tcp.note.param_count": "Taken from netsh int tcp show global",
    "check.tcp.problem.autotuning_bad": "Receive window auto-tuning is set to {value}; download "
                                        "speed drops noticeably on high-latency links "
                                        "(long-distance or international)",
    "check.tcp.problem.autotuning_unknown": "The receive window auto-tuning level could not be "
                                            "identified in the command output",
    "check.tcp.advice.autotuning": "Restore it to normal: that is the Windows default, and most "
                                   "“optimization guides” that change it make things worse",
    "check.tcp.advice.heuristics": "Window scaling heuristics is enabled; current Windows versions "
                                   "no longer use this parameter, so changing it has no effect — "
                                   "nothing to do",
    "check.tcp.advice.rss": "Disabling RSS caps bandwidth above 1 Gbps; ignore it if it was turned "
                            "off to save power",
    "check.tcp.summary_ok": "Stack parameters are healthy (receive window auto-tuning {auto})",
    "check.tcp.summary_ok_scaling": "Stack parameters are healthy (receive window auto-tuning "
                                    "{auto}, window scaling heuristics {scaling})",
    "check.tcp.detail.kv": "• {key}: {value}",
    "check.tcp.detail.heuristics": "Window scaling heuristics:",

    # ------------------------------------------------------------------ #
    # Check: mtu
    # ------------------------------------------------------------------ #
    "check.mtu.title": "MTU and fragmentation",
    "check.mtu.category": "Protocol stack",
    "check.mtu.summary_not_measured": "Path MTU not measured ({reason}); configured MTU is {value}",
    "check.mtu.detail_not_measured": "Could not complete the path MTU measurement: {reason}\n"
                                     "Current configured value: {value}.\n"
                                     "Measuring needs the target to echo ICMP, and many public "
                                     "addresses and firewalls drop echo packets. That is normal "
                                     "and does not indicate a network fault.",
    "check.mtu.problem.cfg_gt_pmtu": "Configured MTU {cfg} is larger than the measured path MTU "
                                     "{pmtu} (gap {gap} bytes), so large packets are silently "
                                     "dropped — a PMTU black hole risk",
    "check.mtu.problem.cfg_lt_pmtu": "Configured MTU {cfg} is smaller than the measured path MTU "
                                     "{pmtu}; link utilization is slightly lower but usability is "
                                     "unaffected",
    "check.mtu.problem.no_cfg": "No configured MTU could be read; the measured path MTU is {pmtu}",
    "check.mtu.summary_ok": "MTU is healthy: configured {cfg}, measured path {pmtu} "
                            "(gap {gap:+d} bytes, within the {tol}-byte tolerance)",
    "check.mtu.advice.probe": "For an exact result, probe with ping -f -l against your gateway or "
                              "your own server",
    "check.mtu.advice.optimize": "Set the adapter MTU to the measured value; PPPoE is usually 1492 "
                                 "and VPNs often 1420 or lower",
    "check.mtu.advice.raise": "Optional: raise MTU back to the measured value for better bulk "
                              "throughput",
    "check.mtu.note.probe_target": "Probe target {target}",
    "check.mtu.note.attempts": "budget {n} probes / {sec} s",
    "check.mtu.note.gap": "threshold {n} bytes",
    "check.mtu.note.target_unused": "Not measured when ICMP is blocked or unreachable",
    "check.mtu.detail.ok": "• Probe target: {target}\n"
                           "• {n} DF probes, largest non-fragmentable payload {payload} bytes\n"
                           "• Path MTU = payload + {overhead} (20 IP + 8 ICMP) = {mtu}",
    "check.mtu.skip.budget": "The probe time budget was used up",
    "check.mtu.skip.no_icmp": "{ip} did not answer ICMP",
    "check.mtu.skip.no_target": "None of the probe targets responded",
    "check.mtu.skip.too_small": "A payload of {n} bytes already fails (path MTU < 1428)",

    # ------------------------------------------------------------------ #
    # Check: firewall
    # ------------------------------------------------------------------ #
    "check.firewall.title": "Windows Firewall",
    "check.firewall.category": "Security",
    "check.firewall.summary_denied": "Administrator rights are needed to read the full firewall "
                                     "state; check skipped",
    "check.firewall.reason.denied": "The command reported access denied",
    "check.firewall.reason.rc": "The command returned {rc} without valid output",
    "check.firewall.hint.user": "Running as a standard user; reading the global firewall state "
                                "needs administrator rights.",
    "check.firewall.hint.admin": "Running as administrator but the read still failed; security "
                                 "software has probably taken over the firewall.",
    "check.firewall.detail_denied": "{reason}. {hint}\n"
                                    "This does not mean the firewall is misconfigured — the tool "
                                    "simply has no evidence to judge from.\n"
                                    "Output excerpt: {out}",
    "check.firewall.advice.denied": "Re-run the checkup as administrator, or check Windows "
                                    "Security → Firewall & network protection yourself",
    "check.firewall.summary_unparsed": "Cannot parse the firewall state output; check skipped",
    "check.firewall.detail_unparsed": "The output of `netsh advfirewall show allprofiles` contains "
                                      "no recognizable configuration block.\nOutput excerpt: {out}",
    "check.firewall.summary_no_state": "No profile on/off state could be identified in the output; "
                                       "check skipped",
    "check.firewall.detail_no_state": "The output of `netsh advfirewall show allprofiles` has no "
                                      "parseable State line.\nOutput excerpt: {out}",
    "check.firewall.summary_all_off": "The firewall is off for all three network profiles: "
                                      "{profiles}",
    "check.firewall.summary_part_off": "The firewall is off for some network profiles: {profiles}",
    "check.firewall.summary_ok": "The Windows Firewall is on for all three profiles",
    "check.firewall.advice.all_off": "A disabled firewall exposes shared ports on public Wi-Fi; "
                                     "turn it back on",
    "check.firewall.advice.part_off": "If you do not need inbound connections on “{profiles}”, "
                                      "turn the firewall back on",
    "check.firewall.detail.line": "• {label}: {state} | {policy}",
    "check.firewall.detail.note": "Note: a disabled firewall does not break internet access; this "
                                  "is a hardening item.",
    "profile.domain": "Domain network",
    "profile.private": "Private network",
    "profile.public": "Public network",

    # ------------------------------------------------------------------ #
    # Check: connectivity
    # ------------------------------------------------------------------ #
    "check.connectivity.title": "Internet connectivity and latency",
    "check.connectivity.category": "Connectivity",
    "check.connectivity.summary_ok": "Internet connectivity is healthy: ping {ping}, HTTPS "
                                     "{handshake}",
    "check.connectivity.ping_no_icmp": "target does not answer ICMP (a common policy, does not "
                                       "affect the verdict)",
    "check.connectivity.ping_text": "{ms}ms ({grade})",
    "check.connectivity.ping_detail": "average {avg}ms (min {min} / max {max}, loss {loss}%)",
    "check.connectivity.ping_detail_fail": "unreachable (loss {loss}%)",
    "check.connectivity.handshake_text": "slowest handshake {ms}ms",
    "check.connectivity.handshake_none": "no successful target",
    "check.connectivity.handshake_ms": "handshake {ms}ms",
    "check.connectivity.problem.ping_loss": "Public ping loss is {loss}%; the link is unstable",
    "check.connectivity.problem.budget": "HTTPS connectivity could not be probed within the time "
                                         "budget; the conclusion is incomplete",
    "check.connectivity.problem.tcp_all_fail": "None of the {n} HTTPS targets could be connected; "
                                               "the internet is unusable right now",
    "check.connectivity.problem.tcp_partial": "Some targets could not be connected over HTTPS: "
                                              "{names} (the rest are fine, so it may be a "
                                              "single-site or CDN problem)",
    "check.connectivity.problem.latency_high": "Internet latency {ms}ms is high; pages will feel "
                                               "noticeably slow",
    "check.connectivity.problem.latency_mid": "Internet latency {ms}ms is slightly above the usual "
                                              "level",
    "check.connectivity.problem.handshake_slow": "HTTPS handshakes are generally above {fast}ms "
                                                 "(slowest {slow}ms); check DNS and line quality",
    "check.connectivity.problem.handshake_fair": "HTTPS handshakes are {fast}~{slow}ms — slow but "
                                                 "acceptable",
    "check.connectivity.problem.dns_fail": "Domain resolution failed; the browser will report a "
                                           "DNS error",
    "check.connectivity.advice.wifi": "On Wi-Fi switch to 5GHz or move closer to the router; on "
                                      "wired check the cable quality",
    "check.connectivity.advice.proxy_firewall": "IP works but all HTTPS fails: check the system "
                                                "proxy and firewall outbound rules first",
    "check.connectivity.advice.wan": "Both IP and HTTPS fail: check the router WAN port and "
                                     "whether the broadband bill is overdue",
    "check.connectivity.advice.dns": "Try “Flush DNS cache” first; if it still fails, switch to a "
                                     "public DNS",
    "check.connectivity.note.ping": "loss {loss}% | {grade}",
    "check.connectivity.note.dns": "{name} took {ms}ms",
    "check.connectivity.detail.ping": "• Direct IPv4 {target}: {text}",
    "check.connectivity.detail.tcp_ok": "• TCP {host}:{port}: handshake {ms}ms",
    "check.connectivity.detail.tcp_fail": "• TCP {host}:{port}: failed ({err})",
    "check.connectivity.detail.dns_ok": "• DNS lookup {name}: {ms}ms → {addrs}",
    "check.connectivity.detail.dns_fail": "• DNS lookup {name}: failed ({err})",
    "check.connectivity.detail.elapsed": "• This check took {sec} s (budget {budget} s)",
    "check.connectivity.no_a_record": "no A record",

    # ------------------------------------------------------------------ #
    # Repair action metadata
    # ------------------------------------------------------------------ #
    "action.dns.flush_cache.title": "Flush the DNS resolver cache",
    "action.dns.flush_cache.description": "Clears the local DNS cache, fixing access problems "
                                          "caused by stale results or hijack leftovers. It "
                                          "changes no configuration and can be repeated anytime.",
    "action.dns.set_public.title": "Switch to a public DNS server",
    "action.dns.set_public.description": "Points the active adapter's DNS at public servers "
                                         "(Alibaba 223.5.5.5 / Tencent 119.29.29.29 by default). "
                                         "The original configuration is fully backed up and can "
                                         "be restored in one click.",
    "action.dns.restore_dhcp.title": "Restore automatic DNS",
    "action.dns.restore_dhcp.description": "Puts the adapter's DNS back under router / DHCP "
                                           "control — the right choice on a company or campus "
                                           "network.",
    "action.hosts.clean_bad_lines.title": "Clean abnormal HOSTS entries",
    "action.hosts.clean_bad_lines.description": "Removes suspicious mappings that were not written "
                                                "by you (blocks pointing at 0.0.0.0 / loopback, or "
                                                "entries that clash with critical system hostnames). "
                                                "The whole file is backed up before rewriting.",
    "action.hosts.restore_default.title": "Restore the default HOSTS template",
    "action.hosts.restore_default.description": "Overwrites the current file with the Windows "
                                                "default hosts file. Every custom entry you added "
                                                "is lost, so it is unselected by default and always "
                                                "needs a second confirmation.",
    "action.tcp.autotuning.title": "Restore TCP receive window auto-tuning",
    "action.tcp.autotuning.description": "Sets the TCP autotuning level back to normal. Turning it "
                                         "off manually makes throughput collapse on high-latency "
                                         "links.",
    "action.tcp.heuristics.title": "Disable the window scaling heuristics limit",
    "action.tcp.heuristics.description": "Window scaling heuristics were deprecated after Windows "
                                         "10 1803 and changing them has no effect. The item is "
                                         "kept only for older systems; on current Windows it is "
                                         "skipped automatically.",
    "action.tcp.reset_stack.title": "Reset the TCP/IP stack",
    "action.tcp.reset_stack.description": "Equivalent to netsh int ip reset + winsock reset, used "
                                          "to repair a damaged stack. A reboot is required for it "
                                          "to take full effect, so it is unselected by default.",
    "action.proxy.reset.title": "Disable the leftover system proxy",
    "action.proxy.reset.description": "Clears the WinINET proxy settings and goes back to a direct "
                                      "connection. Common after a proxy app exits unexpectedly.",
    "action.proxy.restore_auto.title": "Restore automatic proxy detection",
    "action.proxy.restore_auto.description": "Returns “Automatically detect settings” to its "
                                             "system default of enabled.",
    "action.adapter.renew_dhcp.title": "Reacquire IP address (DHCP renewal)",
    "action.adapter.renew_dhcp.description": "Runs release + renew on the active adapter, fixing "
                                             "169.254 addresses, expired leases and similar issues. "
                                             "The network drops for 3-10 seconds while it runs.",
    "action.adapter.reset_stack.title": "Reset the Winsock catalog and firewall rules",
    "action.adapter.reset_stack.description": "netsh winsock reset clears third-party network filter "
                                              "driver registrations (some security suites need "
                                              "their components reinstalled) and requires a "
                                              "reboot. Unselected by default.",
    "action.mtu.optimize.title": "Correct MTU from the measured value",
    "action.mtu.optimize.description": "Writes only when a better MTU was actually measured and "
                                       "differs from the current one; it never guesses a fixed "
                                       "value.",
    "action.firewall.ensure_enabled.title": "Re-enable Windows Firewall",
    "action.firewall.ensure_enabled.description": "Turns the firewall back on when a profile is "
                                                  "found unexpectedly disabled.",
    "action.netbios.disable_public.title": "Disable NetBIOS over TCP/IP on public adapters",
    "action.netbios.disable_public.description": "Reduces the exposure created by LAN name "
                                                 "broadcasting without affecting normal DHCP / "
                                                 "DNS internet access.",

    # ------------------------------------------------------------------ #
    # Repair actions: shared / base
    # ------------------------------------------------------------------ #
    "repair.result.failed": "Action failed",
    "repair.phase.backup": "Backup",
    "repair.phase.apply": "Apply",
    "repair.phase.verify": "Verify",
    "repair.restart_note": "This operation needs a restart to take full effect",
    "repair.elevation_required": "Administrator rights are required to change system settings. "
                                 "Restart the app as administrator and retry this fix",
    "repair.registry_snapshot_label": "{label} (registry export unavailable; structured state "
                                      "recorded instead)",
    "repair.detail.verify": "Verification: {message}",
    "repair.error.verify_failed": "Verification failed: {message}",
    "repair.error.verify_exception": "Verification raised an error: {err}",

    "err.action_duplicate": "Duplicate repair action registration: {id}",
    "err.action_unregistered": "Action {id} is not registered in core/action_ids.py; add its "
                              "metadata to the authoritative list first",
    "err.action_no_impl": "Repair action not implemented: {id}; implemented: {list}",
    "err.action_missing_param": "Action {id} requires the constructor arguments {list}; pass them "
                                "via plan([( '{id}', {{...}} )])",
    "err.action_unknown_param": "Action {id} does not accept {list}; available: {allowed}",
    "err.no_primary": "No active internet adapter found (none connected with a default gateway or "
                      "valid IPv4); verify the network connection first",
    "err.primary_virtual": "The active adapter “{name}” is identified as a virtual/tunnel adapter; "
                          "it is left untouched to avoid breaking VPN or VM configuration",
    "err.primary_no_guid": "Adapter “{name}” has no InterfaceGuid, so its registry configuration "
                          "cannot be located safely",
    "err.run_failed": "{what} failed (exit code {rc}). Command: {cmd}\nSystem output: {out}",
    "err.run_failed_text": "{what} failed (exit code 0, but the system output contains the error "
                          "“{marker}”). Command: {cmd}\nSystem output: {out}",
    "err.dns_list_empty": "The DNS server list is empty",
    "err.alias_empty": "The adapter alias is empty; cannot run netsh",
    "err.alias_invalid": "The adapter alias contains illegal characters; refusing to build the "
                         "command: {value}",
    "err.reg_backup_path_empty": "The registry backup path is empty",
    "err.firewall_parse": "Cannot parse the on/off state of firewall profiles {list} from netsh "
                          "output; aborted to avoid producing a wrong backup. Raw output:\n{out}",
    "err.unknown_firewall_profile": "Unknown firewall profile: {profile}",

    "what.dns_primary": "setting the preferred DNS for “{alias}”",
    "what.dns_index": "setting DNS #{index} for “{alias}” ({server})",
    "what.dns_dhcp": "restoring automatic DNS for “{alias}”",
    "what.dns_read": "reading the DNS configuration of “{alias}”",
    "what.mtu_set": "setting the MTU of “{alias}” to {mtu}",
    "what.firewall_read": "reading the firewall configuration",
    "what.firewall_set": "setting firewall “{profile}” to {state}",
    "what.tcp_read": "reading global TCP parameters",
    "what.tcp_set": "setting TCP parameter {name}={value}",
    "what.reg_import": "importing the registry backup {path}",
    "what.winhttp_direct": "restoring direct WinHTTP access",
    "what.heuristics_read": "reading window scaling heuristics",
    "what.heuristics_set": "setting window scaling heuristics to disabled",
    "what.heuristics_restore": "restoring window scaling heuristics to {level}",

    # ------------------------------------------------------------------ #
    # Repair action: dns
    # ------------------------------------------------------------------ #
    "preview.dns_flush.target": "Local DNS resolver cache",
    "preview.dns_flush.before": "About {n} records are currently cached",
    "preview.dns_flush.before_unknown": "The number of cached records is unknown",
    "preview.dns_flush.after": "The cache is cleared and lookups query the DNS server again",
    "preview.dns_flush.note": "Changes no network configuration; safe to repeat",
    "msg.dns_flush.failed": "Failed to flush the DNS cache",
    "msg.dns_flush.done": "DNS cache flushed",
    "err.dns_flush_rc": "ipconfig /flushdns returned {rc}: {out}",
    "err.dns_cache_read": "Failed to read the DNS cache (exit code {rc}): {out}",
    "msg.dns_cache_read_ok": "The cache is empty and the DNS client responds normally",
    "msg.no_rollback_needed": "This action changes no persistent configuration, so there is "
                              "nothing to roll back",
    "err.dns_servers_required": "The DNS server list is empty: at least one IPv4 address is "
                                "required",
    "err.dns_server_invalid": "Invalid DNS server address: {value}; only dotted-decimal IPv4 is "
                              "accepted",
    "value.dns_auto_unknown": "Automatic (the DHCP-provided servers were not recorded)",
    "value.dns_not_configured": "Not configured",
    "value.dns_from_dhcp": "{servers} (provided by DHCP)",
    "value.dns_manual": "{servers} (manual)",
    "preview.dns_target": "{adapter} / DNS servers",
    "preview.dns_set_after": "{servers} (manual, static)",
    "preview.dns_set_note": "The original DNS configuration is fully backed up and restorable in "
                            "one click from the backup page; IPv6 DNS is unaffected",
    "label.dns_config": "DNS configuration of {adapter}",
    "msg.dns_set_done": "DNS for “{adapter}” is now {servers}",
    "msg.dns_verify_ok": "DNS read back as {actual}, matching the target",
    "msg.dns_verify_fail": "DNS read back as {actual}, which does not match the target {expected}",
    "value.dns_empty": "empty",
    "preview.dns_dhcp_after_keep": "Automatic (keeps the DHCP-provided DNS)",
    "preview.dns_dhcp_after_set": "Automatic (switches to DHCP-provided DNS)",
    "preview.dns_dhcp_after_suffix": ", DNS suffix registered per DHCP options",
    "preview.dns_dhcp_note": "The original DNS configuration is fully backed up; if it is already "
                             "automatic, nothing changes",
    "msg.dns_dhcp_done": "DNS for “{adapter}” is now automatic",
    "msg.dns_dhcp_ok": "Confirmed to be automatic via DHCP",
    "msg.dns_dhcp_switched": "The configuration source is now automatic (no servers handed out "
                             "yet)",
    "msg.dns_still_manual": "Still manually configured: {servers}",

    # ------------------------------------------------------------------ #
    # Repair action: hosts
    # ------------------------------------------------------------------ #
    "preview.hosts.target": "HOSTS file ({path})",
    "preview.hosts.clean.before_none": "{n} valid mappings, no suspicious entries",
    "preview.hosts.clean.after_none": "Unchanged (this action is skipped at run time)",
    "preview.hosts.clean.note_none": "Nothing is written when there is nothing to clean",
    "preview.hosts.clean.sample": "line {line} {ip} {hosts}",
    "preview.hosts.clean.sample_more": "; …{n} lines in total",
    "preview.hosts.clean.before": "{n} valid mappings, {k} of them suspicious: {sample}",
    "preview.hosts.clean.after": "These {k} lines are deleted; the remaining {rest} mappings and "
                                 "all comments are kept as-is",
    "preview.hosts.clean.note": "Only suspicious line numbers are removed; comments, blank lines, "
                                "line endings and BOM are preserved byte-for-byte. The whole file "
                                "is backed up and restorable in one click",
    "label.hosts_raw": "Original HOSTS file",
    "msg.hosts_clean_none": "Nothing to clean",
    "err.hosts_safety_count": "Safety check failed: {n} lines were parsed as removable, but the "
                              "file only has {maps} valid mappings ({lines} lines total). This "
                              "usually means the HOSTS format is abnormal or parsing went wrong, "
                              "so the run was aborted to avoid deleting the whole file.",
    "err.hosts_line_mismatch": "HOSTS line splitting is inconsistent ({a} vs {b}); the file may "
                               "contain unusual control characters, so the run was aborted to "
                               "avoid deleting the wrong lines",
    "err.hosts_empty_result": "Safety check failed: cleaning would leave nothing in the file, which "
                              "points at a line-number mapping bug. Aborted; the original file is "
                              "untouched",
    "err.hosts_still_suspicious": "{n} suspicious entries are still parsed after cleaning; the "
                                  "line mapping may be inconsistent, so writing was aborted (the "
                                  "original file is untouched)",
    "msg.hosts_clean_done": "Deleted {n} abnormal entries; everything else is untouched",
    "detail.hosts_removed": "Removed line {line}: {raw} | {reason}",
    "detail.hosts_removed_more": "…and {n} more of the same kind",
    "err.hosts_missing": "The HOSTS file does not exist: {path}",
    "err.hosts_still_suspicious_verify": "{n} suspicious entries remain",
    "err.hosts_empty_file": "HOSTS became an empty file",
    "msg.hosts_verify_note": " (the file has few lines: {n}; verify it is complete)",
    "msg.hosts_verify_ok": "Confirmed 0 suspicious entries; {n} valid mappings remain{note}",
    "preview.hosts.restore.before": "{n} valid mappings currently",
    "preview.hosts.restore.before_detail": ": {detail}",
    "preview.hosts.restore.detail_more": " and {n} more",
    "preview.hosts.restore.after": "Only the system default template (all comments, no mappings); "
                                   "every custom entry is lost",
    "preview.hosts.restore.note": "This cannot be undone from the undo stack, but it can be rolled "
                                  "back on the backup page. The current file is fully backed up "
                                  "first.",
    "msg.hosts_restore_done": "HOSTS restored to the system default template ({n} mappings cleared)",
    "detail.hosts_restore_written": "Wrote the Windows default template (CRLF line endings, UTF-8 "
                                    "without BOM)",
    "detail.hosts_restore_cleared": "Custom mappings were cleared; roll back this session on the "
                                    "backup page to get them back",
    "err.hosts_restore_left": "{n} valid mappings are still parsed from the template; the write "
                              "may not have taken effect",
    "err.hosts_restore_empty": "HOSTS is an empty file; the default template was not written",
    "msg.hosts_restore_verify_ok": "Confirmed to be the system default template ({n} lines, 0 "
                                   "mappings)",
    "err.hosts_text_type": "new_text must be a string, got {type}",
    "err.hosts_text_empty": "Refusing to write: the new content is an empty file. Overwriting "
                            "would leave HOSTS with no lines at all, which usually means the input "
                            "was truncated or mis-encoded",
    "err.hosts_text_zero": "Refusing to write: the new content is 0 bytes",
    "err.hosts_text_blank": "Refusing to write: the new content is only whitespace and has nothing "
                            "worth keeping",
    "kind.hosts_edit": "Manual HOSTS edit",
    "note.hosts_edit": "The original HOSTS content is backed up before writing",
    "msg.hosts_saved_detail": "HOSTS written ({lines} lines, {maps} mappings)",
    "detail.hosts_before": "Before writing there were {n} valid mappings",
    "detail.hosts_still_suspicious": "Note: the new content still contains {n} suspicious entries",

    # ------------------------------------------------------------------ #
    # Repair action: adapter
    # ------------------------------------------------------------------ #
    "preview.adapter_renew.target": "{adapter} / IPv4 address and lease",
    "preview.adapter_renew.before": "{ip}{flag}, address source={source}",
    "preview.adapter_renew.apipa_flag": " (APIPA invalid address)",
    "preview.adapter_renew.source_dhcp": "DHCP",
    "preview.adapter_renew.source_static": "static or unknown",
    "preview.adapter_renew.after": "Requests an address from the DHCP server again; the resulting "
                                   "IP may differ from the current one",
    "preview.adapter_renew.note": "The network drops for about 3-10 seconds, which is expected; the "
                                  "old address and gateway are fully backed up",
    "label.ip_lease": "IP lease information of {adapter}",
    "detail.ipconfig_rc": "ipconfig /{command} \"{alias}\" -> exit code {rc}",
    "detail.release_warn": "Warning: release returned {rc}; continuing with renew (some adapters "
                           "cannot release a lease)",
    "msg.renew_failed": "Failed to reacquire an IP address; the network may still be unusable",
    "err.renew_failed": "ipconfig /renew returned {rc}: {out}\n"
                        "Previous address {ip}; check the cable / Wi-Fi connection and the router's "
                        "DHCP service",
    "msg.renew_adapter_missing": "Cannot locate the adapter after reacquiring an address",
    "err.renew_adapter_missing": "No adapter found by GUID {guid} or alias {alias}",
    "msg.renew_no_ip": "The network came back, but the adapter still has no IPv4 address",
    "err.renew_no_ip": "renew succeeded but the adapter has no IPv4 address; check whether DHCP is "
                       "enabled on the router",
    "msg.renew_apipa": "Still a 169.254 invalid address after renewal; DHCP did not respond",
    "err.renew_apipa": "Current address {ip}; check the router's DHCP service and the cable "
                       "connection",
    "msg.renew_done": "The network is back and the IP changed from {old} to {new}; if you still "
                      "cannot get online, check the router DHCP and gateway configuration",
    "detail.new_ip": "New address {ip}/{prefix}, gateway {gateway}",
    "detail.ip_changed": "The address changed; the old address {old} is recorded in the backup",
    "msg.verify_no_adapter": "No connected adapter found",
    "msg.verify_no_ip": "“{name}” currently has no IPv4 address",
    "msg.verify_apipa": "“{name}” still has the APIPA address {ip}; DHCP assigned no valid address",
    "msg.verify_ip_ok": "“{name}” obtained the valid address {ip}, gateway {gateway}",
    "preview.adapter_reset.target": "Winsock catalog and IPv4 stack",
    "preview.adapter_reset.before": "Current Winsock LSP registrations and IP stack parameters",
    "preview.adapter_reset.after": "Winsock catalog rebuilt and IP stack parameters reset; "
                                   "third-party LSPs are removed, so affected security suites may "
                                   "need their network components reinstalled",
    "preview.adapter_reset.note": "{restart}; the registry is fully backed up and can be rolled "
                                  "back from the backup page before rebooting",
    "label.winsock_params": "WinSock2 parameters registry",
    "label.tcpip_params": "TCP/IP parameters registry",
    "detail.cmd_rc": "{command} -> exit code {rc}",
    "msg.adapter_reset_failed": "The network component reset was not fully applied",
    "err.adapter_reset_failed": "netsh winsock reset returned {winsock_rc}: {winsock_out}\n"
                                "netsh int ip reset returned {ip_rc}: {ip_out}",
    "msg.adapter_reset_done": "Winsock and the IP stack were reset; a reboot is required for full "
                              "effect",
    "detail.adapter_reset_snapshot": "Registry snapshots were recorded around the reset; affected "
                                     "security suites' LSP components should be reinstalled",
    "err.winsock_catalog": "`netsh winsock show catalog` returned {rc} after the reset: {out}",
    "msg.winsock_catalog_ok": "Applied; a reboot is required (the Winsock catalog is only rebuilt "
                              "on restart)",

    # ------------------------------------------------------------------ #
    # Repair action: firewall
    # ------------------------------------------------------------------ #
    "preview.firewall.target": "Windows Firewall (domain / private / public)",
    "preview.firewall.before": "{pairs}",
    "preview.firewall.keep": "Keep all profiles on; nothing to change",
    "preview.firewall.keep_note": "No command runs when all three profiles are already on",
    "preview.firewall.off_note": "Currently off: {profiles}; after enabling you may need to allow "
                                 "specific programs through the firewall",
    "label.firewall_states": "Firewall profile on/off states",
    "msg.firewall_all_on": "All three firewall profiles are already on; nothing to change",
    "detail.firewall_set": "{profile}: {before} -> ON",
    "msg.firewall_enabled": "Firewall enabled: {profiles}",
    "detail.firewall_hint": "Tip: if a program is blocked, allow it under “Allow an app through "
                            "Windows Defender Firewall”",
    "msg.firewall_verify_fail": "Some profiles are still off: {profiles}",
    "msg.firewall_verify_ok": "All three profiles (domain / private / public) are ON",

    # ------------------------------------------------------------------ #
    # Repair action: mtu
    # ------------------------------------------------------------------ #
    "err.mtu_required": "mtu.optimize requires the target_mtu parameter (1200-1500), currently "
                        "None; it must come from the measured result of the MTU check",
    "err.mtu_type": "mtu.optimize target_mtu must be an integer, got {type}: {value}",
    "err.mtu_range": "mtu.optimize target_mtu must be between {min} and {max}, got {value}; values "
                     "outside that range break the link, so this is refused (no clamping)",
    "preview.mtu.after_same": "{value} (same as current; this action is skipped at run time)",
    "preview.mtu.after_atypical": "{value} (an atypical value — verify the measurement is reliable)",
    "preview.mtu.target": "{adapter} / MTU",
    "preview.mtu.before": "{value} (ifIndex={index})",
    "preview.mtu.before_fail": "Read failed",
    "preview.mtu.note": "Written with store=persistent and kept across reboots; the original value "
                        "is backed up and restorable in one click",
    "err.mtu_read": "Cannot read the current MTU of “{adapter}” (got {value}); without the original "
                    "value rollback is impossible, so the run was aborted",
    "label.mtu": "MTU of {adapter}",
    "msg.mtu_already": "MTU is already {value}; nothing to change",
    "msg.mtu_done": "MTU of “{adapter}” changed from {old} to {new}",
    "err.mtu_no_target": "Cannot determine the target adapter (apply did not record it)",
    "err.mtu_adapter_missing": "Target adapter not found (GUID={guid}, ifIndex={index})",
    "msg.mtu_verify_ok": "Read back “{name}” MTU={value} (ifIndex={index})",
    "msg.mtu_verify_fail": "Read back “{name}” MTU={value}, expected {expected} "
                           "(ifIndex={index})",

    # ------------------------------------------------------------------ #
    # Repair action: netbios
    # ------------------------------------------------------------------ #
    "err.netbios_guid_empty": "The adapter GUID is empty; cannot locate the NetBIOS registry key",
    "err.netbios_read": "Failed to read the NetBIOS configuration ({path}): {err}",
    "preview.netbios.before_unset": "Not configured (equivalent to DHCP-controlled, usually "
                                    "enabled)",
    "preview.netbios.value_dhcp": "0 (DHCP-controlled)",
    "preview.netbios.value_on": "1 (enabled)",
    "preview.netbios.value_off": "2 (disabled)",
    "preview.netbios.after": "{value} (disabled)",
    "preview.netbios.note_public": "Affects LAN name broadcasting only — not internet access, DNS "
                                   "or modern SMB file sharing; the current address looks public",
    "preview.netbios.note_private": "Affects LAN name broadcasting only — not internet access, DNS "
                                    "or modern SMB file sharing; the current address is private, "
                                    "so be careful if you reach shares by name in Network "
                                    "Neighborhood",
    "label.netbios": "NetBIOS adapter configuration",
    "label.netbios_snapshot": "NetBIOS adapter configuration (the registry key did not exist)",
    "msg.netbios_already": "NetBIOS is already disabled on this adapter; nothing to change",
    "msg.netbios_done": "NetBIOS over TCP/IP disabled on “{adapter}”",
    "detail.netbios_value": "NetbiosOptions: {before} -> {after}",
    "detail.netbios_path": "Registry key: HKLM\\{path}",
    "detail.netbios_takes_effect": "This takes effect on the current connection immediately; no "
                                   "reboot needed",
    "msg.netbios_verify_ok": "Read back NetbiosOptions={value} (disabled)",
    "msg.netbios_verify_missing": "The registry value does not exist on read-back; security "
                                  "software may have blocked the write",
    "msg.netbios_verify_fail": "Read back NetbiosOptions={value}, expected {expected}",

    # ------------------------------------------------------------------ #
    # Repair action: proxy
    # ------------------------------------------------------------------ #
    "err.reg_read": "Failed to read the registry value {name}: {err}",
    "err.wininet_load": "Failed to load wininet.dll: {err}",
    "err.wininet_option": "{label} returned failure (GetLastError={err})",
    "err.wininet_call": "{label} raised an error: {err}",
    "msg.wininet_refreshed": "The system was notified to refresh the proxy settings",
    "value.proxy_direct": "Direct (no proxy)",
    "value.proxy_enabled": "{parts} (proxy enabled)",
    "preview.proxy_reset.target": "System proxy (WinINET: HKCU Internet Settings)",
    "preview.proxy_reset.after": "Direct (ProxyEnable=0, ProxyServer deleted)",
    "preview.proxy_reset.after_keep": "Direct (ProxyEnable=0, ProxyServer deleted); the exception "
                                      "list {keep} is kept",
    "preview.proxy_reset.note": "WinHTTP proxy and auto-detect settings are untouched; the original "
                                "values are fully backed up and restorable in one click",
    "label.proxy_settings": "System proxy settings (Internet Settings)",
    "detail.proxy_enable": "ProxyEnable: {before} -> 0",
    "detail.proxy_server_deleted": "ProxyServer: {before} -> deleted",
    "detail.proxy_server_absent": "ProxyServer: was not present",
    "detail.proxy_override_kept": "Kept ProxyOverride={value}",
    "detail.proxy_refresh": "Proxy refresh: {message}",
    "detail.proxy_refresh_failed": "Proxy refresh failed (this change is unaffected): {message}",
    "msg.proxy_enable_not_zero": "ProxyEnable still reads non-zero after writing 0",
    "err.proxy_enable_readback": "ProxyEnable read back as {value}",
    "msg.proxy_reset_done": "The system proxy is off; the browser connects directly",
    "msg.proxy_verify_enable": "ProxyEnable read back as {value}, expected 0",
    "msg.proxy_verify_server": "ProxyServer still exists: {value}",
    "msg.proxy_verify_ok": "ProxyEnable=0 and ProxyServer cleared",
    "preview.proxy_auto.target": "System proxy (WinINET static proxy + WinHTTP proxy settings)",
    "preview.proxy_auto.before": "WinINET: {wininet}; WinHTTP: {winhttp}",
    "preview.proxy_auto.after": "WinINET static proxy off; WinHTTP back to direct access",
    "preview.proxy_auto.note": "The binary “Automatically detect settings” switch "
                              "(DefaultConnectionSettings) is left untouched",
    "label.winhttp_proxy": "WinHTTP proxy configuration",
    "detail.proxy_auto_enable": "ProxyEnable: {before} -> 0 (static proxy disabled)",
    "detail.proxy_auto_unchanged": "Auto-detect (DefaultConnectionSettings byte 9, bit 3) was not "
                                   "changed: editing that binary directly can corrupt connection "
                                   "settings after a version upgrade, so it is left as-is.",
    "msg.proxy_auto_done": "Static proxy disabled and WinHTTP restored to direct access "
                           "(auto-detect switch untouched)",
    "msg.proxy_auto_verify_fail": "WinHTTP is still not direct: {text}",
    "msg.proxy_auto_verify_ok": "WinINET is direct and WinHTTP uses direct access",
    "value.winhttp_read_failed": "(read failed, exit code {rc}) {out}",

    # ------------------------------------------------------------------ #
    # Repair action: tcp
    # ------------------------------------------------------------------ #
    "err.autotuning_parse": "Cannot parse the current autotuning level from `netsh int tcp show "
                            "global`; raw output: {values}",
    "preview.autotuning.target": "TCP receive window auto-tuning level",
    "preview.autotuning.note": "Changes a global parameter only; the stack is not reset and no "
                               "reboot is needed",
    "label.autotuning": "TCP auto-tuning level",
    "msg.autotuning_done": "TCP auto-tuning level set to {value}",
    "msg.autotuning_verify_ok": "Read back autotuning = {value}",
    "msg.autotuning_verify_fail": "Read back autotuning = {value}, expected {expected}",
    "msg.heuristics_unreadable": "Cannot read window scaling heuristics; skipping this item: {err}",
    "msg.heuristics_missing": "Window scaling heuristics was not found in the output; nothing to "
                              "fix",
    "msg.heuristics_ineffective": "Current Windows versions no longer use window scaling "
                                  "heuristics (the system itself states that changing these "
                                  "settings has no effect), so nothing needs fixing",
    "preview.heuristics.target": "TCP window scaling heuristics (wsh)",
    "preview.heuristics.read_failed": "Read failed ({err})",
    "preview.heuristics.note": "This setting no longer affects behavior on current Windows and is "
                               "recorded for state consistency; older systems may gain throughput "
                               "on high-latency links",
    "err.heuristics_parse": "Cannot parse the window scaling heuristics level from `netsh int tcp "
                            "show heuristics`; aborted so rollback stays possible. Raw output: "
                            "{values}",
    "label.heuristics": "TCP window scaling heuristics level",
    "msg.heuristics_already": "Window scaling heuristics is already {value}; nothing to change",
    "msg.heuristics_done": "Window scaling heuristics set to {value} (was {before})",
    "detail.heuristics_note": "Note: Windows 10/11 no longer actually use this parameter (the "
                              "system says changing window scaling heuristics settings will have "
                              "no effect); this item only keeps older systems and state "
                              "consistent",
    "msg.heuristics_verify_ok": "Read back window scaling heuristics = {value}",
    "msg.heuristics_verify_fail": "Read back window scaling heuristics = {value}, expected "
                                  "{expected}",
    "preview.tcp_reset.target": "TCP/IP stack and Winsock catalog",
    "preview.tcp_reset.before": "Current stack state (including third-party LSP / filter driver "
                                "registrations)",
    "preview.tcp_reset.after": "Stack parameters reset to system defaults and the Winsock catalog "
                               "rebuilt; third-party LSP registrations are cleared, so affected "
                               "security suites may need their components reinstalled",
    "msg.tcp_reset_failed": "The stack reset was not fully applied",
    "err.tcp_reset_failed": "netsh int ip reset returned {ip_rc}: {ip_out}\n"
                            "netsh winsock reset returned {winsock_rc}: {winsock_out}",
    "msg.tcp_reset_done": "The TCP/IP stack and Winsock were reset; a reboot is required for full "
                          "effect",
    "detail.tcp_reset_rollback": "⚠ Rollback can only restore registry parameters; the applied "
                                 "stack state can only be overwritten by the backup after a reboot",
    "err.tcp_show_global": "After the stack reset, `netsh int ip show global` returned {rc}: {out}",
    "msg.tcp_reset_verify_ok": "Applied; a reboot is required (this process cannot observe the "
                               "result)",

    # ------------------------------------------------------------------ #
    # Rollback
    # ------------------------------------------------------------------ #
    "msg.rollback_item_failed": "Failed to restore “{label}”",
    "msg.rollback_item_done": "Restored “{label}”",
    "msg.rollback_needs_admin": "“{label}” needs administrator rights to restore, and the app is "
                                "running as a standard user. Restart it as administrator and retry "
                                "the rollback; the backup file itself is intact and can be restored "
                                "manually from the backup folder",
    "msg.rollback_dhcp_skip": "“{label}” is not rolled back automatically: a DHCP renewal would "
                              "drop the network again. The backup recorded address {ip} and gateway "
                              "{gateway}; verify manually whether they need restoring",
    "detail.rollback_dhcp_hint": "To restore the address, set a static IP in the adapter properties "
                                 "with the values above",
    "msg.rollback_winhttp_skip": "“{label}” only recorded display text and exported no importable "
                                 "registry snapshot; check the WinHTTP proxy manually using the "
                                 "raw output in the backup folder",
    "msg.rollback_unknown_kind": "Unknown backup kind “{kind}” (key={key})",
    "err.rollback_unknown_kind": "The backup item type does not match any rollback implementation; "
                                 "refusing to guess a restore method",
    "err.hosts_backup_missing": "The HOSTS backup file does not exist: {path}",
    "err.hosts_backup_corrupted": "The backup file is corrupted; refusing to restore: {path}\n"
                                  "expected sha256={expected}\nactual sha256={actual}\n"
                                  "Check whether another program modified this file",
    "detail.hosts_restored": "Restored HOSTS from {path} (sha256 verified)",
    "msg.hosts_restored": "Restored the original HOSTS file ({n} bytes)",
    "err.rollback_adapter_missing": "No adapter with GUID {guid} was found; it may have been "
                                    "disabled or removed, so its DNS configuration cannot be "
                                    "restored",
    "detail.dns_dhcp_restored": "Was automatic via DHCP; restored: {alias}",
    "msg.dns_dhcp_restored": "DNS for “{alias}” is back to automatic",
    "err.rollback_dns_empty": "The backup recorded static DNS but the server list is empty ({key}), "
                              "so it cannot be restored from here; set it manually in the adapter "
                              "properties",
    "detail.dns_static_restored": "Was a static list; restored: {alias} -> {servers}",
    "msg.dns_static_restored": "DNS for “{alias}” restored to {servers}",
    "err.reg_backup_missing": "The registry backup file does not exist: {path}",
    "detail.reg_imported": "Imported {path}",
    "msg.reg_restored": "Imported the registry backup ({hive})",
    "err.rollback_mtu_invalid": "The MTU value in the backup is invalid: {value}",
    "err.rollback_mtu_no_target": "The backup has neither an adapter GUID nor an alias; cannot "
                                  "locate the adapter to restore",
    "detail.rollback_mtu_fallback": "Warning: adapter {guid} was not found by GUID; falling back to "
                                    "the backup alias “{alias}”",
    "msg.mtu_restored": "MTU of “{alias}” restored to {value}",
    "err.rollback_firewall_empty": "The firewall backup has no profile states; cannot restore",
    "msg.firewall_restored": "Firewall restored: {profiles}",
    "err.rollback_tcp_empty": "The backup has no original TCP parameter value ({key})",
    "msg.autotuning_restored": "TCP autotuninglevel restored to {level}",
    "msg.heuristics_restored": "TCP window scaling heuristics restored to {level}",
    "err.rollback_tcp_unknown": "Cannot determine the TCP parameter name from the backup key: {key}",
    "err.rollback_netbios_guid": "The backup has no adapter GUID ({key}); cannot locate the NetBIOS "
                                 "configuration",
    "detail.netbios_already_original": "Neither the value nor the key exists; treated as already "
                                       "original",
    "msg.netbios_original": "NetBIOS configuration is back to its original state (it did not exist)",
    "err.netbios_delete": "Failed to delete NetbiosOptions ({path}): {err}",
    "detail.netbios_deleted": "Deleted {path}\\NetbiosOptions (it did not exist before)",
    "msg.netbios_unset": "NetBIOS configuration is back to “not set”",
    "err.rollback_netbios_snapshot": "This NetBIOS backup contains no restorable registry snapshot "
                                     "({key}, hive={hive}); import the .reg file from the backup "
                                     "folder manually",
    "msg.rollback_nothing": "This backup session has no items from that action; nothing to roll "
                            "back",
    "msg.rollback_partial": "Some backup items failed to restore ({n} succeeded)",
    "msg.rollback_done": "Restored {n} backup item(s)",

    # ------------------------------------------------------------------ #
    # Repair engine
    # ------------------------------------------------------------------ #
    "note.plan.duplicate": "“{id}” was submitted twice and merged into one",
    "note.plan.servers_override": "dns.set_public received both params.servers and servers; the "
                                  "servers argument wins",
    "note.plan.no_impl": "“{id}” has no repair implementation and was skipped",
    "note.plan.skipped": "“{id}” skipped: {reason}",
    "note.plan.unsupported": "not supported in this environment",
    "note.plan.probe_error": "availability probe raised an error ({err})",
    "note.plan.conflict": "“{drop}” conflicts with “{keep}” ({why}); “{keep}” was kept",
    "note.plan.dry_run": "Dry-run mode: preview and backup only, no changes are made",
    "err.servers_type": "servers must be a list, got {type}",
    "err.servers_empty": "servers cannot be an empty list: at least one DNS server address is "
                         "required",
    "err.missing_param": "Action {id} is missing the required parameters {list}; pass them as "
                         "('{id}', {{...}})",
    "err.invalid_param": "Action {id} has invalid parameters: {err}",
    "err.action_ids_type": "action_ids must be a list, not a single string; "
                           "write ['dns.flush_cache'] for one action",
    "err.action_id_type": "Action ids must be strings, got {value}",
    "err.action_params_type": "Parameters for action {id} must be a dict, got {type}",
    "err.action_ref": "Unrecognized action description: {value}; expected 'action_id' or "
                      "('action_id', {{...}})",
    "preview.unreadable": "Cannot read the current state",
    "preview.unavailable": "This item cannot run",
    "note.preview_failed": "Preview failed: {err}",
    "note.session_plan": "This plan contains {n} action(s): {list}",
    "note.session_empty": "no actions",
    "kind.auto_backup": "Automatic pre-repair backup",
    "err.backup_failed": "Backup for action “{id}” failed; nothing was modified because of it: "
                         "{err}",
    "hint.aborted": "No action was applied and the system is unchanged, so no rollback is needed. "
                    "Backup session {session} was kept (partial snapshots only); investigate the "
                    "failure and retry.",
    "hint.dry_run": "Dry-run mode: no changes were made. Backup session {session} was created at "
                    "{path} (useful to confirm the backup path works; no rollback needed)",
    "hint.no_actions": "There were no actions to run and nothing was modified; backup session "
                       "{session} is an audit record only (no items)",
    "hint.partial": "{n} action(s) did not complete or failed verification this round. Rolling back "
                    "backup session {session} is recommended to restore the original state. Backup "
                    "path: {path}",
    "hint.all_done": "All actions completed and passed verification. To undo them, roll back backup "
                     "session {session} (path: {path})",
    "err.session_empty": "This session has no backup items (it may only contain stateless actions), "
                         "so there is nothing to restore",
    "kind.manual_backup": "Manual backup",
    "note.manual_backup": "System state snapshot created by the user",
    "label.mtu_snapshot": "MTU of {adapter} (manual backup record)",
    "note.manual_partial": "Manual backup (some items failed, {n} captured):\n{list}",
    "note.manual_ok": "Manual backup succeeded with {n} state snapshot(s)",

    # ------------------------------------------------------------------ #
    # Report rendering
    # ------------------------------------------------------------------ #
    "report.html.title": "LanPulse Network Checkup Report · {host}",
    "report.html.heading": "Network checkup report",
    "report.html.host": "Host name",
    "report.html.os": "Operating system",
    "report.html.time": "Checked at",
    "report.html.elevated": "Administrator",
    "report.html.duration": "Duration",
    "report.html.id": "Report ID",
    "report.html.status": "Overall status · {label}",
    "report.html.overview": "Result overview",
    "report.html.details": "Detailed results ({n} checks)",
    "report.html.empty": "There are no results in this report.",
    "report.html.footnote_privacy": "This report was generated locally and no data was uploaded. "
                                    "It contains no external links, scripts or images, so it opens "
                                    "fine offline.",
    "report.html.footnote_snapshot": "The report is a snapshot taken when it was exported; network "
                                     "configuration changes over time, so a new checkup may reach "
                                     "different conclusions.",
    "report.html.backup_dir": "Configuration backup folder: {path} "
                              "(pre-repair originals are stored here per session and can be "
                              "inspected or restored manually)",
    "report.html.no_backup": "No backup has been produced yet — the folder is only created before a "
                             "repair runs.",
    "report.html.footer": "LanPulse · Report {id} · Generated at {time}",
    "report.html.escaped_error": "This check failed, so its conclusion is unavailable:\n{err}",
    "report.metric.header_name": "Metric",
    "report.metric.header_value": "Value",
    "report.metric.header_note": "Notes",
    "report.advice.label": "Recommended actions",
    "report.evidence.summary": "Raw evidence ({n} characters)",
    "report.evidence.unserializable": "[Evidence could not be serialized to JSON: {err}]",
    "report.elevated_yes": "Yes (administrator)",
    "report.elevated_no": "No (standard user)",
    "report.text.title": " LanPulse Network Checkup Report",
    "report.text.host": " Host name    : {value}",
    "report.text.os": " OS           : {value}",
    "report.text.time": " Checked at   : {value}",
    "report.text.elevated": " Administrator: {value}",
    "report.text.duration": " Duration     : {value}",
    "report.text.id": " Report ID    : {value}",
    "report.text.score": " Health score : {score} / 100      Overall status: {label}",
    "report.text.counts": " Result counts: healthy {ok} | notice {info} | warning {warn} | "
                          "critical {crit} | skipped {skip}",
    "report.text.item": "[{idx}] {sev} | {title} ({category} / {id})",
    "report.text.summary": "  Summary: {text}",
    "report.text.error_head": "  ! This check failed, so its conclusion is unavailable:",
    "report.text.detail_head": "  Details:",
    "report.text.advice_head": "  Recommendations:",
    "report.text.notes_head": " Notes:",
    "report.text.note_privacy": "   This report was generated locally and no data was uploaded.",
    "report.text.note_snapshot": "   The report is a snapshot from export time; a new checkup may "
                                 "reach different conclusions.",
    "report.text.backup_dir": "   Configuration backup folder: {path}",
    "report.text.generated_at": "   Generated at {value}",
    "report.text.truncated": "\n… (truncated; see the JSON / HTML report for the full content)",
    "report.text.seconds": "{n:.1f} s",
    "report.text.minutes": "{n} min {sec} s",
    "report.plan.empty": "There is nothing to change.\n\nNo item on this system needs automatic "
                         "repair, so nothing will be modified.",
    "report.plan.head": "{n} change(s) will be applied:",
    "report.plan.item": "{idx}. {target}",
    "report.plan.before": "Before",
    "report.plan.after": "After",
    "report.plan.note": "Note",
    "report.plan.footnote": "The current configuration is backed up first; restore it with one "
                            "click from the Backups & Rollback page.",
    "report.plan.footnote2": "If a change is not what you expect, cancel and review the raw "
                             "evidence of that check first.",
    "err.report_format": "Unsupported report format: {fmt} (choose html / json / text)",
    "report.file_prefix": "LanPulseReport",

    # ---- 界面骨架与环境提示 ----
    'env.admin_ok': 'Running as administrator',
    'env.admin_limited': 'Limited privileges\nsome repairs unavailable',
    'btn.elevate': 'Restart as administrator',
    'btn.selfcheck': 'Environment check',
    'dns.vendor.unknown': 'Custom / ISP',
    'settings.region.saved': 'Region setting saved',
    'settings.region.rerun_hint': 'Takes effect on the next checkup; current view shows the previous result',
    'settings.cleaned': 'Cleaned {n} old backup session(s)',
    "status.checking": 'Checking: {name}',

    # ---- v1.1.0 新增：场景化诊断 / 根因分析 / 网页分层 / 劫持检测 / 缓冲膨胀 ----
    'check.web_timing.title': 'Web page load speed',
    'check.web_timing.category': 'Web',
    'check.web_timing.summary_skipped': 'Network probing disabled',
    'check.dns_hijack.title': 'DNS tampering check',
    'check.dns_hijack.category': 'Security',
    'check.dns_hijack.summary_skipped': 'Network probing disabled',
    'check.dns_hijack.summary_no_dns': 'No manual DNS configured',
    'check.bufferbloat.title': 'Lag under download load',
    'check.bufferbloat.category': 'Experience',
    'check.bufferbloat.summary_skipped': 'Network probing disabled',
    'check.bufferbloat.summary_unmeasurable': 'Latency unmeasurable',
    'check.bufferbloat.summary_no_load': 'Could not create download load',
    'metric.web_target': 'Test site',
    'metric.web_dns': 'DNS lookup',
    'metric.web_tcp': 'TCP connect',
    'metric.web_tls': 'TLS handshake',
    'metric.web_ttfb': 'First byte',
    'metric.web_cert': 'Cert validity',
    'metric.hijack_query': 'Resolution compare',
    'metric.bufferbloat_idle': 'Idle latency',
    'metric.bufferbloat_loaded': 'Loaded latency',
    'metric.bufferbloat_delta': 'Latency increase',
    'metric.bufferbloat_grade': 'Grade',
    'metric.grade_good': 'Good',
    'metric.grade_fair': 'Fair',
    'metric.grade_poor': 'Slow',
    'metric.grade_unknown': 'N/A',
    'scenario.slow.name': 'Slow internet',
    'scenario.slow.desc': 'Pages load slowly, downloads crawl, videos buffer',
    'scenario.disconnect.name': 'Frequent disconnects',
    'scenario.disconnect.desc': 'Drops out now and then; a router restart fixes it',
    'scenario.web.name': "Websites won't open",
    'scenario.web.desc': 'Some or all sites fail, but chat apps still work',
    'scenario.gaming.name': 'Gaming / video lag',
    'scenario.gaming.desc': 'Bandwidth is fine but games lag and calls stutter',
    'scenario.security.name': 'Check for tampering',
    'scenario.security.desc': 'Sites look altered or redirect to ad pages',
    'scenario.full.name': 'Full checkup',
    'scenario.full.desc': 'Run all 14 checks (about 10-15 seconds)',
    'rootcause.dhcp_failed.title': 'The router did not assign an IP address',
    'rootcause.dhcp_failed.impact': 'The address is a 169.254 placeholder, so there is no internet',
    'rootcause.dhcp_failed.advice': 'Run "Renew IP address"; if it still fails, restart the router',
    'rootcause.hosts_hijack.title': 'Suspicious entries in the HOSTS file',
    'rootcause.hosts_hijack.impact': 'Specific sites resolve to the wrong address and may be blocked or hijacked',
    'rootcause.hosts_hijack.advice': 'Clean the entries and run a full antivirus scan',
    'rootcause.dns_hijack.title': 'DNS responses are being tampered with',
    'rootcause.dns_hijack.impact': 'A domain resolves to the wrong IP, so sites fail or lead to fake pages',
    'rootcause.dns_hijack.advice': 'Switch to a trusted public DNS and review the HOSTS file',
    'rootcause.proxy_residual.title': 'A dead system proxy was left behind',
    'rootcause.proxy_residual.impact': 'Every web request goes to a closed port, which looks like a total outage',
    'rootcause.proxy_residual.advice': 'Clear the leftover system proxy setting',
    'rootcause.gateway_poor.title': 'The link to the router is poor',
    'rootcause.gateway_poor.impact': 'Packet loss or high latency makes the whole connection unstable',
    'rootcause.gateway_poor.advice': 'On Wi-Fi try 5 GHz or move closer; on Ethernet check the cable and port',
    'rootcause.dns_slow.title': 'DNS lookups are slow',
    'rootcause.dns_slow.impact': 'Every new site waits on resolution first, which feels like a stall',
    'rootcause.dns_slow.advice': 'Flush the DNS cache or switch to a faster public DNS',
    'rootcause.web_break.title': 'Web access breaks at a specific layer',
    'rootcause.web_break.impact': 'Layered timing has already pinpointed the stage, so no guesswork is needed',
    'rootcause.web_break.advice': 'Act on the layered figures below',
    'rootcause.mtu_mismatch.title': 'MTU mismatch (large packets are dropped)',
    'rootcause.mtu_mismatch.impact': 'Small packets pass while large ones vanish: home pages open but video and downloads stall',
    'rootcause.mtu_mismatch.advice': 'Set MTU to the measured value',
    'rootcause.bufferbloat.title': 'Latency rises sharply under download load',
    'rootcause.bufferbloat.impact': 'Bandwidth is fine but latency spikes, which gaming and video calls feel first',
    'rootcause.bufferbloat.advice': 'Enable SQM / QoS on the router, or limit large background transfers',
    'rootcause.firewall_off.title': 'Windows Firewall is turned off',
    'rootcause.firewall_off.impact': 'This is a security risk and does not cause the current connectivity problem',
    'rootcause.firewall_off.advice': 'Turn the firewall back on',

    # ---- 场景页 ----
    'scenario.intro': 'Pick whatever matches your situation; only the relevant checks will run',
    'scenario.checks_count': '{n} checks',
    'scenario.advanced_hint': 'Want every check individually? Use the Diagnostics page',
    'scenario.btn_full': 'Run full checkup',

    # ---- 根因分析展示 ----
    'nav.scenario': 'Scenarios',
    'dashboard.no_problems': 'No network problems found ✓',
    'dashboard.other_issues': 'Other issues ({n}, not covered above)',
    'dashboard.confidence': 'Confidence: {level}',
    'rootcause.confidence.high': 'High',
    'rootcause.confidence.medium': 'Medium',
    'rootcause.confidence.low': 'Low',

    # ---- UI 骨架文案（v1.1.0 补齐）----
    'dashboard.not_scanned': 'Not scanned yet',
    'dashboard.metrics_title': 'Current network state',
    'dashboard.metrics_desc': 'Taken from the most recent scan',
    'dashboard.problems_title': 'Findings',
    'dashboard.entries_title': 'Quick actions',
    'dashboard.scanning': 'Scanning…',
    'dashboard.no_problems': 'No network problems found ✓',
    'dashboard.footer': 'All checks and repairs run locally with zero upload. Every change is backed up first and can be rolled back at any time.',
    'dashboard.all_ok': 'All {n} checks passed',
    'dashboard.with_problems': '{n} checks, {m} issues found',
    'dashboard.confidence': 'Confidence: {level}',
    'dashboard.other_issues': 'Other issues ({n}, not covered above)',
    'btn.one_click_fix': 'One-click fix',
    'btn.manual_backup': 'Create backup now',
    'btn.discard': 'Discard',
    'btn.restore_hosts': 'Restore default',
    'btn.execute_repair': 'Run repair',
    'diagnose.pick_one': 'Select a row on the left to see details',
    'diagnose.metrics': 'Metrics',
    'diagnose.advice': 'Advice',
    'diagnose.evidence': 'Raw evidence',
    'backup.restore_btn': 'Restore to {ts}',
    'backup.rollback_hint': 'Rollback only restores the items recorded in this backup; later unrelated changes are untouched.',
    'dns.subtitle': 'DNS decides the route to every site you visit — the first thing to check when pages fail to open',
    'dns.current_title': 'Current DNS configuration',
    'dns.current_desc': 'Read from the adapter currently carrying your traffic',
    'dns.choose_plan': 'Choose a plan',
    'hosts.no_change': 'No changes to save.',
    'repair.subtitle': 'Preselected from the scan; adjust as you like — high-risk items start unchecked',
    'repair.empty_hint': 'Run a scan first and the suggested fixes will appear here.',
    'scenario.intro': 'Pick whatever matches your situation; only the relevant checks will run',
    'scenario.checks_count': '{n} checks',
    'scenario.advanced_hint': 'Want every check individually? Use the Diagnostics page',
    'scenario.btn_full': 'Run full checkup',
    'nav.scenario': 'Scenarios',

    # ---- UI 骨架补充 ----
    'backup.restore_default': 'Restore to this backup',
    'repair.nothing_to_fix': 'Nothing to fix from this scan ✓',

    # ---- 仪表盘细节 ----
    'dashboard.hostname': 'Host',
    'dashboard.privilege': 'Privileges',
    'dashboard.elevated_yes': 'Administrator',
    'dashboard.elevated_no': 'Standard user (some repairs unavailable)',
    'gauge.waiting': 'Waiting',
    'gauge.waiting_sample': 'Waiting for samples',
    'dashboard.entry_dns': 'DNS tuning',
    'dashboard.entry_dns_desc': 'Inspect current DNS, test speed, switch to public resolvers, or fall back to DHCP',
    'dashboard.entry_hosts': 'HOSTS manager',
    'dashboard.entry_hosts_desc': 'View and edit HOSTS with blocked and hijacked entries flagged',
    'dashboard.entry_backup': 'Backups & rollback',
    'dashboard.entry_backup_desc': 'Every snapshot taken before a change lives here; restore in one click',
    'dashboard.entry_report': 'Reports',
    'dashboard.entry_report_desc': 'Export HTML / JSON / TXT with the full evidence of this scan',
    'dashboard.severity_ok': 'Network looks healthy',
    'dashboard.severity_info': 'Mostly fine',
    'dashboard.severity_warn': 'Issues found',
    'dashboard.severity_critical': 'Needs attention',
    'dashboard.severity_skip': 'Limited by environment',

    # ---- 诊断页表头与状态 ----
    'diagnose.col_check': 'Check',
    'diagnose.col_state': 'State',
    'diagnose.col_result': 'Result',
    'diagnose.col_time': 'Time',

    'diagnose.meta': '{n} checks | {host} | {ts}',

    # ---- Update check ----
    # These strings have a specific job: explain why a tool that promises
    # "zero upload" still makes an outbound request. Be concrete — "only a
    # version file" — never vague, or every other promise looks doubtful.
    'update.consent.title': 'Check for updates',
    'update.consent.body': 'LanPulse can check for new versions from time to time. Turn this on?',
    'update.consent.detail': (
        'The check only requests a version file from the official site. '
        'Nothing about you is sent: no account, no device ID, no usage statistics. '
        'You can turn it off in Settings at any time.'
    ),
    'update.consent.yes': 'Enable',
    'update.consent.no': 'No thanks',
    'update.available': 'Version v{version} is available',
    'update.view': 'View',
    'update.check_now': 'Check now',
    'update.checking': 'Checking…',
    'update.up_to_date': "You're up to date",
    'settings.update.title': 'Check for updates',
    'settings.update.desc': 'Requests only a version file from the official site; nothing is uploaded',
}

__all__ = ["CATALOG"]
