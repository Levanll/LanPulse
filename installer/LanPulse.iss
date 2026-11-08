; ============================================================================
;  LanPulse 安装脚本（Inno Setup 6）
;
;  编译：
;      ISCC.exe installer\LanPulse.iss
;  或
;      powershell -ExecutionPolicy Bypass -File scripts\build_installer.ps1
;
;  产物：..\release\LanPulse-<版本>-Setup.exe
;  源程序目录：..\dist\LanPulse\（PyInstaller 单目录产物，必须整体分发）
;
;  维护须知（改版本只改下面这一行，scripts 里的 zip 命名也从这里正则读取）：
;      #define MyAppVersion "1.0.0"
;  ---------------------------------------------------------------------------
;  为什么 AppId 必须是写死的固定 GUID：
;      Inno 用 AppId 作为"这是同一个产品"的身份证——升级时靠它找到旧的
;      卸载项并覆盖，而不是新增一条。若每次构建重新生成 GUID，用户每装一次
;      控制面板里就会多一条 LanPulse，且旧版本永远不会被清理。所以这里写死。
;
;  为什么 PrivilegesRequired=lowest 而不是 admin：
;      体检/报告/备份查看都不需要管理员权限，只有"修复"动作才要。普通用户
;      也应该能装上程序，因此默认装到用户目录；需要装到 Program Files 的
;      用户可以在向导里选择"为所有用户安装"（OverridesAllowed=dialog），
;      那时才会弹 UAC。安装目标目录用 {autopf} 自动跟随该选择。
; ============================================================================

#define MyAppName        "LanPulse"
#define MyAppVersion     "1.2.0"
#define MyAppPublisher   "LanPulse Contributors"
#define MyAppExeName     "LanPulse.exe"
#define MyAppId          "{{B7E4C2A1-9F3D-4E8B-A5C6-1D2E3F4A5B6C}"
; 程序数据根目录：%LOCALAPPDATA%\LanPulse（日志 logs、备份 backups 都在下面）
#define MyDataDirName    "LanPulse"


[Setup]
; ---- 产品标识（AppId 决定"同一产品"，切勿改）----
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppCopyright=Copyright (c) 2026 {#MyAppPublisher}

; ---- 安装位置 ----
; autopf = 提权安装时 <Program Files>\LanPulse；非提权时 %LOCALAPPDATA%\Programs\LanPulse
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
AllowNoIcons=yes

; ---- 权限 ----
; lowest：普通用户即可完成安装（装到用户目录），全程不弹 UAC。
; OverridesAllowed=dialog：向导里出现"为所有用户安装 / 仅为我安装"选择页，
; 选"所有用户"时 Setup 在启动阶段自行提权。
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; ---- 目标系统 ----
; Windows 10 1809（build 17763）是 Get-NetAdapter / netsh 相关命令行为的下限。
MinVersion=10.0.17763
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; ---- 产物 ----
OutputDir=..\release
OutputBaseFilename=LanPulse-{#MyAppVersion}-Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
SetupIconFile=LanPulse.ico
; 注意这里指向随包安装的 .ico，而不是 LanPulse.exe：
; build.spec 里 icon=None，exe 内嵌的是 PyInstaller 的默认 Python 图标。
; 直接写 {app}\LanPulse.exe 会让"应用和功能"列表里显示一个 Python 标志。
UninstallDisplayIcon={app}\LanPulse.ico
UninstallDisplayName={#MyAppName}
LicenseFile=LICENSE.txt

; ---- 版本资源 ----
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=LanPulse 安装程序 / LanPulse Setup
VersionInfoProductName={#MyAppName}
VersionInfoCopyright=Copyright (c) 2026 {#MyAppPublisher}

; ---- 运行中实例检测 ----
; 与 app/sysutil.py 里 SingleInstance 创建的命名互斥体完全一致。
; 设置后 Inno 在安装前和卸载前都会检查该互斥体：
;   * 有实例在跑 -> 交互模式弹出"请先关闭 LanPulse"，可重试；
;   * 静默模式   -> 直接以非 0 退出码中止，绝不半途覆盖正在被占用的文件。
AppMutex=LanPulse_Global_Mutex
; 覆盖安装时，若目标文件被占用，靠 Restart Manager 让系统自行关闭持有者，
; 并记录需要重启的项（本程序是窗口程序，不强制自动重启它）。
CloseApplications=yes
RestartApplications=no


[Languages]
; 中文放第一位：Inno 在系统语言不匹配时回退到列表首项。
; ChineseSimplified.isl 官方安装包并不附带（只有 29 种语言里没有中文），
; 因此仓库里自带一份，使用相对路径引用，保证任何机器上都能编译。
Name: "chinesesimplified"; MessagesFile: "ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"


[CustomMessages]
; 卸载时的两个询问。默认值（静默模式下的返回值）都是"保留"，见 [Code]。
chinesesimplified.KeepBackupsPrompt=检测到网络配置备份目录：%n%n%1%n%n卸载 LanPulse 后要保留这些备份吗？%n%n「是」保留备份（推荐）—— 你以后重新安装本程序时可以直接使用这些备份恢复网络配置。%n「否」永久删除备份，删除后无法恢复。
chinesesimplified.RemoveLogsPrompt=是否同时删除程序日志？%n%n%1%n%n日志只包含运行记录，不含任何网络配置。保留它有助于日后排查问题；删除它则不会影响任何功能。
english.KeepBackupsPrompt=Network configuration backups were found in:%n%n%1%n%nKeep these backups after uninstalling LanPulse?%n%nYes - keep them (recommended). If you install LanPulse again later you can restore your network configuration from them.%nNo - delete them permanently. This cannot be undone.
english.RemoveLogsPrompt=Do you also want to delete the program logs?%n%n%1%n%nLogs contain only runtime records, never your network configuration. Keeping them helps diagnose problems later; deleting them affects no functionality.


[Tasks]
; 桌面快捷方式：默认不勾（unchecked）。用户明确需要时自行勾选。
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked


[Files]
; 单目录产物整体复制，保持 _internal\ 的目录结构（PyInstaller onedir 必需）。
; 同一份文件用 ignoreversion：升级安装时无条件用新版本覆盖，避免"版本号
; 相同但内容不同"的文件被跳过，导致新旧 DLL 混装。
Source: "..\dist\LanPulse\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; 程序图标。build.spec 里 icon=None（exe 内嵌的是 PyInstaller 默认图标），
; 因此快捷方式与卸载项都改用这份 .ico，装完看到的是 LanPulse 自己的图标。
Source: "LanPulse.ico"; DestDir: "{app}"; Flags: ignoreversion

; 许可证随程序一起装上，便于用户随时查看。
Source: "LICENSE.txt"; DestDir: "{app}"; Flags: ignoreversion


[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\LanPulse.ico"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"; IconFilename: "{app}\LanPulse.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\LanPulse.ico"; Tasks: desktopicon


[Registry]
; App Paths：让 Win+R 输入 "LanPulse" 即可启动（ShellExecute 会查这个键）。
; 根用 HKA（自动根）：提权安装 -> HKLM，用户级安装 -> HKCU。
; 两处 Windows 都会查，因此在哪种安装模式下该功能都生效。
; uninsdeletekey 保证卸载时不留下孤儿键。
Root: HKA; Subkey: "SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{#MyAppExeName}"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExeName}"; Flags: uninsdeletekey
Root: HKA; Subkey: "SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{#MyAppExeName}"; ValueType: string; ValueName: "Path"; ValueData: "{app}"; Flags: uninsdeletekey


[Run]
; 安装完成页的"立即运行"，默认勾选。
; skipifsilent：静默安装不自动拉起程序——否则 CI/脚本安装完会多一个常驻
; 进程，后续的卸载验证会被单实例互斥体挡住。
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent


[Code]
const
  // 与 core/backup.py 的 BACKUP_ROOT_NAME / app/logging_setup.py 的 log_dir() 对齐
  BACKUP_DIR_NAME = 'backups';
  LOGS_DIR_NAME   = 'logs';

{ 卸载完成后处理用户数据。
  铁律：备份目录默认保留。用户的网络配置备份是他的东西，不是程序的一部分，
  不能因为卸载一个工具就消失——哪怕他自己后来也不记得里面有啥。
  静默卸载时两个 SuppressibleMsgBox 都返回默认值 yes/no，因此：
      * 备份 -> IDYES -> 保留
      * 日志 -> IDYES -> 保留
  即：静默卸载不动 %LOCALAPPDATA%\LanPulse 下的任何内容。 }
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataRoot, BackupDir, LogsDir: String;
begin
  if CurUninstallStep <> usPostUninstall then
    Exit;

  DataRoot := ExpandConstant('{localappdata}\{#MyDataDirName}');
  BackupDir := AddBackslash(DataRoot) + BACKUP_DIR_NAME;
  LogsDir := AddBackslash(DataRoot) + LOGS_DIR_NAME;

  if DirExists(BackupDir) then
  begin
    if SuppressibleMsgBox(
         FmtMessage(CustomMessage('KeepBackupsPrompt'), [BackupDir]),
         mbConfirmation, MB_YESNO, IDYES) = IDNO then
      DelTree(BackupDir, True, True, True);
  end;

  if DirExists(LogsDir) then
  begin
    if SuppressibleMsgBox(
         FmtMessage(CustomMessage('RemoveLogsPrompt'), [LogsDir]),
         mbConfirmation, MB_YESNO, IDYES) = IDNO then
      DelTree(LogsDir, True, True, True);
  end;
end;
