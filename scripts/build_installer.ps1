# =============================================================================
#  LanPulse 一键构建脚本
#
#  用法（在任意目录执行都可以，脚本自己定位仓库根）：
#      powershell -ExecutionPolicy Bypass -File scripts\build_installer.ps1
#
#  可选参数：
#      -Fresh        强制重跑 PyInstaller（即使 dist\LanPulse\LanPulse.exe 已存在）
#      -SkipZip      只出 Setup.exe，不打绿色包
#      -SkipSetup    只打绿色包，不编译 Setup.exe
#
#  流程： 清理 -> PyInstaller -> 绿色包 zip -> Inno Setup -> release\
#
#  说明：
#    * 全程不需要管理员权限。Inno Setup 的“编译”只是读写文件，
#      只有“安装 Inno Setup 本身”才可能需要提权——脚本会检测并给出提示。
#    * 不依赖 7-Zip：压缩用 .NET 的 ZipFile（PowerShell 5.1 自带）。
#    * 版本号唯一来源是 installer\LanPulse.iss 里的 MyAppVersion，
#      脚本用正则读它来拼产物名，避免版本号两处漂移。
# =============================================================================

[CmdletBinding()]
param(
    [switch]$Fresh,
    [switch]$SkipZip,
    [switch]$SkipSetup
)

$ErrorActionPreference = 'Stop'
$ProgressPreference    = 'SilentlyContinue'

# 让中文输出在 PowerShell 5.1 的 GBK 控制台里也不乱码
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

# --------------------------------------------------------------------------- #
# 基础工具
# --------------------------------------------------------------------------- #
$script:RepoRoot = Split-Path -Parent $PSScriptRoot

function Write-Step([string]$Text) {
    Write-Host ''
    Write-Host ('=' * 72) -ForegroundColor DarkCyan
    Write-Host "  $Text" -ForegroundColor Cyan
    Write-Host ('=' * 72) -ForegroundColor DarkCyan
}

function Write-Ok([string]$Text)   { Write-Host "  [OK]   $Text" -ForegroundColor Green }
function Write-Info([string]$Text) { Write-Host "  [..] $Text" -ForegroundColor Gray }
function Write-Warn([string]$Text) { Write-Host "  [!!] $Text" -ForegroundColor Yellow }

function Fail([string]$Reason, [string]$Hint) {
    Write-Host ''
    Write-Host "  [FAIL] $Reason" -ForegroundColor Red
    if ($Hint) { Write-Host "         $Hint" -ForegroundColor Red }
    Write-Host ''
    exit 1
}

function Get-FileSizeMB([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return 'n/a' }
    $bytes = (Get-Item -LiteralPath $Path).Length
    return ('{0:N2} MB' -f ($bytes / 1MB))
}

function Assert-LastExit([string]$What) {
    if ($LASTEXITCODE -ne 0) {
        Fail "$What 失败（退出码 $LASTEXITCODE）" '请查看上方输出定位具体错误。'
    }
}

# --------------------------------------------------------------------------- #
# 0. 定位工具
# --------------------------------------------------------------------------- #
function Resolve-Python {
    $venv = Join-Path $script:RepoRoot '.venv\Scripts\python.exe'
    if (Test-Path -LiteralPath $venv) { return $venv }
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    Fail '找不到 Python 解释器。' '请安装 Python 3.12 并在项目根创建 .venv，或把 python 加入 PATH。'
}

# Inno Setup 的编译器。按“最可能命中、最不需要提权”的顺序找。
function Resolve-Iscc {
    $cmd = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }

    $candidates = @()

    # 已安装的 Inno Setup 会在卸载项里留下 InstallLocation
    foreach ($hive in @('HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall',
                        'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall',
                        'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall')) {
        $key = Join-Path $hive 'Inno Setup 6_is1'
        if (Test-Path $key) {
            $base = (Get-ItemProperty -Path $key -Name InstallLocation -ErrorAction SilentlyContinue).InstallLocation
            if ($base) { $candidates += (Join-Path $base 'ISCC.exe') }
        }
    }

    if ($env:ProgramFiles)      { $candidates += (Join-Path $env:ProgramFiles 'Inno Setup 6\ISCC.exe') }
    if (${env:ProgramFiles(x86)}) { $candidates += (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe') }
    if ($env:LOCALAPPDATA) {
        $candidates += (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe')
        # 本项目实测使用的 portable 解压位置（无管理员权限时的装法）
        $candidates += (Join-Path $env:LOCALAPPDATA 'LanPulseBuildTools\InnoSetup\ISCC.exe')
    }

    # 非系统盘的常见安装位置。装在 D:\Tools 之类的地方是为了不占用 C 盘；
    # 这里按盘符探测，避免每换一台机器都要改脚本。
    foreach ($drive in @('D:', 'E:', 'F:')) {
        $candidates += "${drive}\Tools\InnoSetup6\ISCC.exe"
        $candidates += "${drive}\Tools\Inno Setup 6\ISCC.exe"
        $candidates += "${drive}\InnoSetup6\ISCC.exe"
    }

    # 环境变量显式指定优先于盘符猜测（放在最后，避免覆盖更可靠的来源）
    if ($env:INNO_SETUP_HOME) {
        $candidates += (Join-Path $env:INNO_SETUP_HOME 'ISCC.exe')
    }

    foreach ($p in $candidates) {
        if ($p -and (Test-Path -LiteralPath $p)) { return $p }
    }
    return $null
}

function Get-IsccUnavailableHint {
    return @'
未找到 Inno Setup 6 编译器 (ISCC.exe)。安装方式任选其一：

  1) winget（需联网，可能要求管理员）：
       winget install --id JRSoftware.InnoSetup -e

  2) 便携解压（不需要管理员权限）：
       下载 https://jrsoftware.org/isdl.php 里的 innosetup-6.x.exe
       innosetup-6.x.exe /PORTABLE=1 /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /DIR="%LOCALAPPDATA%\NetPulseBuildTools\InnoSetup"
       脚本会自动在该位置找到 ISCC.exe。

  3) 官方安装包（需要管理员）：
       innosetup-6.x.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART

绿色包（-SkipSetup）不需要 Inno Setup，可直接用 scripts\build_portable.ps1。
'@
}

# --------------------------------------------------------------------------- #
# 1. 读取版本号（唯一来源：installer\LanPulse.iss）
# --------------------------------------------------------------------------- #
function Get-AppVersion {
    $iss = Join-Path $script:RepoRoot 'installer\LanPulse.iss'
    if (-not (Test-Path -LiteralPath $iss)) {
        Fail "找不到 Inno 脚本：$iss" '版本号从该文件的 #define MyAppVersion 读取。'
    }
    $m = Select-String -LiteralPath $iss -Pattern '^\s*#define\s+MyAppVersion\s+"([^"]+)"' |
         Select-Object -First 1
    if (-not $m) {
        Fail '无法从 installer\LanPulse.iss 解析 MyAppVersion。' '请确认其中存在形如 #define MyAppVersion "1.0.0" 的行。'
    }
    return $m.Matches[0].Groups[1].Value
}

# --------------------------------------------------------------------------- #
# 2. 清理
# --------------------------------------------------------------------------- #
function Invoke-Clean {
    Write-Step '步骤 1/4  清理'

    $releaseDir = Join-Path $script:RepoRoot 'release'
    if (Test-Path -LiteralPath $releaseDir) {
        Get-ChildItem -LiteralPath $releaseDir -File | ForEach-Object {
            if ($_.Name -like 'LanPulse-*-Setup.exe' -or
                $_.Name -like 'LanPulse-*-portable.zip' -or
                $_.Name -eq 'SHA256SUMS.txt') {
                Write-Info "删除旧产物: $($_.FullName)"
                Remove-Item -LiteralPath $_.FullName -Force
            }
        }
    } else {
        New-Item -ItemType Directory -Path $releaseDir -Force | Out-Null
        Write-Info "创建输出目录: $releaseDir"
    }

    # PyInstaller 的工作目录，每次重建，避免增量残留导致“改了代码但包没变”
    $buildDir = Join-Path $script:RepoRoot 'build'
    if (Test-Path -LiteralPath $buildDir) {
        Write-Info "删除 PyInstaller 工作目录: $buildDir"
        Remove-Item -LiteralPath $buildDir -Recurse -Force
    }

    Write-Ok '清理完成'
}

# --------------------------------------------------------------------------- #
# 3. PyInstaller
# --------------------------------------------------------------------------- #
function Invoke-PyInstaller([string]$Python) {
    Write-Step '步骤 2/4  PyInstaller 打包'

    $exe = Join-Path $script:RepoRoot 'dist\LanPulse\LanPulse.exe'
    if ((-not $Fresh) -and (Test-Path -LiteralPath $exe)) {
        Write-Ok "已存在打包产物，跳过 PyInstaller: $exe"
        Write-Info '（需要强制重建请加 -Fresh 参数）'
        return
    }

    Write-Info "解释器: $Python"
    Push-Location $script:RepoRoot
    try {
        Write-Info '执行: python -m PyInstaller build.spec --noconfirm --clean'
        & $Python -m PyInstaller build.spec --noconfirm --clean
        Assert-LastExit 'PyInstaller'
    } finally {
        Pop-Location
    }

    if (-not (Test-Path -LiteralPath $exe)) {
        Fail "PyInstaller 报告成功，但没有生成 $exe" '请检查 build.spec 的 COLLECT name 是否仍为 LanPulse。'
    }
    Write-Ok "打包完成: $exe ($(Get-FileSizeMB $exe))"
}

# --------------------------------------------------------------------------- #
# 4. 绿色包 zip
# --------------------------------------------------------------------------- #
function New-PortableZip([string]$Version) {
    Write-Step '步骤 3/4  生成绿色压缩包'

    Add-Type -AssemblyName System.IO.Compression.FileSystem

    $src  = Join-Path $script:RepoRoot 'dist\LanPulse'
    $zip  = Join-Path $script:RepoRoot "release\LanPulse-$Version-win64-portable.zip"

    if (-not (Test-Path -LiteralPath (Join-Path $src 'LanPulse.exe'))) {
        Fail "$src\LanPulse.exe 不存在，无法打包。" '请先运行 PyInstaller 打包（去掉 -SkipSetup 之外的跳过参数，或加 -Fresh）。'
    }

    Write-Info "源目录: $src"
    Write-Info "目标:   $zip"

    # CreateFromDirectory 把目录“内容”平铺进 zip 根，
    # 解压后就是 LanPulse.exe + _internal\，不会多套一层 LanPulse\。
    if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip -Force }
    [System.IO.Compression.ZipFile]::CreateFromDirectory(
        $src,
        $zip,
        [System.IO.Compression.CompressionLevel]::Optimal,
        $false
    )

    # 给绿色包补上说明文档（用户解压第一眼要看到怎么用、怎么卸）
    $extras = @(
        @{ Path = (Join-Path $script:RepoRoot 'installer\README.txt'); Entry = 'README.txt' },
        @{ Path = (Join-Path $script:RepoRoot 'installer\LICENSE.txt'); Entry = 'LICENSE.txt' }
    )
    $archive = [System.IO.Compression.ZipFile]::Open($zip, [System.IO.Compression.ZipArchiveMode]::Update)
    try {
        foreach ($x in $extras) {
            if (-not (Test-Path -LiteralPath $x.Path)) {
                Fail "缺少 $($x.Path)" '绿色包需要在 installer\ 下提供 README.txt 与 LICENSE.txt。'
            }
            [void][System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
                $archive, $x.Path, $x.Entry,
                [System.IO.Compression.CompressionLevel]::Optimal
            )
            Write-Info "已加入 $($x.Entry)"
        }
    } finally {
        $archive.Dispose()
    }

    Write-Ok "绿色包完成: $zip ($(Get-FileSizeMB $zip))"
}

# --------------------------------------------------------------------------- #
# 5. Inno Setup
# --------------------------------------------------------------------------- #
function Invoke-InnoSetup([string]$Version) {
    Write-Step '步骤 4/4  编译 Setup 安装包'

    $iscc = Resolve-Iscc
    if (-not $iscc) {
        Write-Host ''
        Write-Host (Get-IsccUnavailableHint) -ForegroundColor Yellow
        Fail '找不到 Inno Setup 6 编译器 (ISCC.exe)。' '按上方任一方式安装后重新运行；或用 -SkipSetup 只出绿色包。'
    }
    Write-Info "ISCC: $iscc"

    $iss = Join-Path $script:RepoRoot 'installer\LanPulse.iss'
    Push-Location $script:RepoRoot
    try {
        & $iscc $iss
        Assert-LastExit 'Inno Setup 编译'
    } finally {
        Pop-Location
    }

    $setup = Join-Path $script:RepoRoot "release\LanPulse-$Version-Setup.exe"
    if (-not (Test-Path -LiteralPath $setup)) {
        Fail "ISCC 返回成功，但没有找到 $setup" '请检查 installer\LanPulse.iss 的 OutputDir / OutputBaseFilename。'
    }
    Write-Ok "Setup 完成: $setup ($(Get-FileSizeMB $setup))"
}

# --------------------------------------------------------------------------- #
# 6. 汇总
# --------------------------------------------------------------------------- #
function Write-Summary([string]$Version, [string[]]$Artifacts) {
    Write-Step '构建结果'

    $rows = @()
    foreach ($a in $Artifacts) {
        if (-not (Test-Path -LiteralPath $a)) { continue }
        $hash = (Get-FileHash -LiteralPath $a -Algorithm SHA256).Hash
        $rows += [pscustomobject]@{
            Name   = (Split-Path -Leaf $a)
            Size   = (Get-FileSizeMB $a)
            SHA256 = $hash
            Path   = $a
        }
    }

    foreach ($r in $rows) {
        Write-Host ''
        Write-Host "  文件:   $($r.Name)" -ForegroundColor White
        Write-Host "  路径:   $($r.Path)"
        Write-Host "  大小:   $($r.Size)"
        Write-Host "  SHA256: $($r.SHA256)" -ForegroundColor Green
    }

    # 一并写出校验文件，方便分发时附上
    $sumFile = Join-Path $script:RepoRoot 'release\SHA256SUMS.txt'
    $lines = $rows | ForEach-Object { "$($_.SHA256)  $($_.Name)" }
    $enc = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($sumFile, (($lines -join "`r`n") + "`r`n"), $enc)
    Write-Host ''
    Write-Info "校验文件: $sumFile"

    Write-Host ''
    Write-Host "  版本 $Version 构建完成。" -ForegroundColor Green
    Write-Host ''
}

# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
Write-Host ''
Write-Host '  LanPulse 构建' -ForegroundColor White
Write-Info "仓库根: $($script:RepoRoot)"

if (-not (Test-Path -LiteralPath (Join-Path $script:RepoRoot 'build.spec'))) {
    Fail "不是预期的项目结构：$($script:RepoRoot)\build.spec 不存在。" '请把脚本放在 <仓库根>\scripts\ 下。'
}

$Version = Get-AppVersion
Write-Info "版本号: $Version  (来自 installer\LanPulse.iss)"
Write-Info ('当前会话管理员: ' + ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator))
Write-Info '（构建不需要管理员权限；只有安装 Inno Setup 本身可能需要）'

$python = Resolve-Python

Invoke-Clean
Invoke-PyInstaller -Python $python

$artifacts = @()
if (-not $SkipZip) {
    New-PortableZip -Version $Version
    $artifacts += (Join-Path $script:RepoRoot "release\LanPulse-$Version-win64-portable.zip")
} else {
    Write-Warn '已跳过绿色包 (-SkipZip)'
}

if (-not $SkipSetup) {
    Invoke-InnoSetup -Version $Version
    $artifacts += (Join-Path $script:RepoRoot "release\LanPulse-$Version-Setup.exe")
} else {
    Write-Warn '已跳过 Setup 安装包 (-SkipSetup)'
}

if ($artifacts.Count -eq 0) {
    Fail '没有生成任何产物。' '请去掉 -SkipZip 与 -SkipSetup 后重试。'
}

Write-Summary -Version $Version -Artifacts $artifacts
exit 0
