========================================================================
 LanPulse 1.0.0  -  便携版 / Portable Edition
 网络体检与一键修复工具  /  Network Diagnostics & One-Click Repair
========================================================================

[ 中文 ]

一、如何启动
------------------------------------------------------------------------
1. 把整个文件夹解压到你喜欢的任意位置（例如 D:\Tools\LanPulse）。
   注意：必须解压，不能在压缩包里直接双击运行。
2. 双击 LanPulse.exe 启动。
3. LanPulse.exe 依赖同目录下的 _internal 文件夹，请勿把它单独拷走，
   也不要删除或重命名 _internal。

想让它出现在开始菜单/桌面？右键 LanPulse.exe -> 发送到 -> 桌面快捷方式。

二、首次运行遇到 SmartScreen 提示
------------------------------------------------------------------------
本程序是开源软件，未购买代码签名证书，因此首次运行时 Windows 可能弹出
蓝色窗口："Windows 已保护你的电脑"。

处理方法：
  1. 点击提示框中的"更多信息"（More info）；
  2. 点击随后出现的"仍要运行"（Run anyway）。

如果杀毒软件报毒，那是 PyInstaller 打包程序的常见误报。你可以：
  * 把本文件夹加入杀毒软件白名单；或
  * 自行从源码构建（项目 README 里有构建步骤）。

三、备份与日志在哪
------------------------------------------------------------------------
程序不在自己目录里写任何东西，所有用户数据都在：

  %LOCALAPPDATA%\LanPulse\
      backups\   <- 每次修改系统前的自动备份（恢复网络配置全靠它）
      logs\      <- app.log（运行日志）、audit.jsonl（操作审计）

在资源管理器地址栏粘贴 %LOCALAPPDATA%\LanPulse 并回车即可打开。
注意：备份目录请勿手工删除，删了就无法回滚此前的修复动作。

四、如何彻底卸载
------------------------------------------------------------------------
便携版不写注册表、不装服务，所以"卸载"就是删文件：

  1. 确认 LanPulse 已退出（任务栏没有它的图标）；
  2. 删除你解压出来的整个 LanPulse 文件夹；
  3. 如需连用户数据一起清掉，删除 %LOCALAPPDATA%\LanPulse。

第 3 步是可选的：里面是你的网络配置备份和运行日志。只删文件夹、
保留 %LOCALAPPDATA%\LanPulse，是完全正常的用法——方便你以后重新解压
一份继续用原有的备份。

五、系统要求
------------------------------------------------------------------------
  * Windows 10 1809（build 17763）或更高版本，64 位
  * 不需要安装 .NET / Visual C++ 运行库，依赖已随包携带
  * 体检、报告、查看备份：普通用户权限即可
  * 执行"修复"动作（改 DNS / hosts / 防火墙 / 重置协议栈）：需要管理员权限，
    程序内会提示"以管理员身份重启"


[ English ]

1. How to start
------------------------------------------------------------------------
1. Extract the whole folder anywhere you like (e.g. D:\Tools\LanPulse).
   You must extract it - running the .exe straight from inside the ZIP
   will not work.
2. Double-click LanPulse.exe.
3. LanPulse.exe needs the _internal folder next to it. Do not copy the .exe
   out on its own, and do not delete or rename _internal.

Want Start Menu / desktop shortcuts? Right-click LanPulse.exe ->
Send to -> Desktop (create shortcut).

2. SmartScreen on first launch
------------------------------------------------------------------------
This is open-source software without a code-signing certificate, so Windows
may show a blue "Windows protected your PC" dialog the first time.

To proceed:
  1. Click "More info" in that dialog;
  2. Click the "Run anyway" button that appears.

If your antivirus flags it, that is a well-known false positive for programs
packaged with PyInstaller. You can either whitelist this folder, or build it
yourself from source (see the build steps in the project README).

3. Where backups and logs live
------------------------------------------------------------------------
The program writes nothing into its own folder. All user data is under:

  %LOCALAPPDATA%\LanPulse\
      backups\   <- automatic backup taken before every system change
      logs\      <- app.log (runtime log), audit.jsonl (action audit trail)

Paste %LOCALAPPDATA%\LanPulse into the Explorer address bar to open it.
Do not delete the backups folder manually - without it, previous repairs
cannot be rolled back.

4. How to uninstall completely
------------------------------------------------------------------------
The portable edition writes no registry entries and installs no services,
so uninstalling simply means deleting files:

  1. Make sure LanPulse is closed (not in the notification area);
  2. Delete the LanPulse folder you extracted;
  3. Optionally delete %LOCALAPPDATA%\LanPulse for a clean slate.

Step 3 is optional. It holds your network configuration backups and logs.
Deleting only the program folder while keeping %LOCALAPPDATA%\LanPulse is
perfectly normal - you can extract a fresh copy later and keep using the
backups you already have.

5. System requirements
------------------------------------------------------------------------
  * Windows 10 1809 (build 17763) or later, 64-bit
  * No .NET or Visual C++ redistributable needed - everything is bundled
  * Diagnostics, reports and backup browsing: standard user is enough
  * Repair actions (DNS / hosts / firewall / stack reset) need administrator
    rights; the app offers a "restart as administrator" button.

------------------------------------------------------------------------
 License: MIT (see LICENSE.txt)
 Copyright (c) 2026 LanPulse Contributors
------------------------------------------------------------------------