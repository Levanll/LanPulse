# =============================================================================
#  LanPulse 绿色包构建脚本
#
#  用法（在任意目录执行都可以，脚本自己定位仓库根）：
#      powershell -ExecutionPolicy Bypass -File scripts\build_portable.ps1
#
#  可选参数：
#      -Fresh    强制重跑 PyInstaller（即使 dist\LanPulse\LanPulse.exe 已存在）
#
#  产物： release\LanPulse-<版本>-win64-portable.zip
#         （zip 根目录直接是 LanPulse.exe + _internal\ + README.txt + LICENSE.txt）
#
#  这个脚本不需要 Inno Setup、不需要管理员权限、不依赖 7-Zip。
#  需要完整发布（Setup + 绿色包）请用 scripts\build_installer.ps1。
# =============================================================================

[CmdletBinding()]
param(
    [switch]$Fresh
)

$ErrorActionPreference = 'Stop'
$ProgressPreference    = 'SilentlyContinue'

try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

$script:RepoRoot = Split-Path -Parent $PSScriptRoot

function Write-Step([string]$Text) {
    Write-Host ''
    Write-Host ('=' * 72) -ForegroundColor DarkCyan
    Write-Host "  $Text" -ForegroundColor Cyan
    Write-Host ('=' * 72) -ForegroundColor DarkCyan
}

function Write-Ok([string]$Text)   { Write-Host "  [OK]   $Text" -ForegroundColor Green }
function Write-Info([string]$Text) { Write-Host "  [..] $Text" -ForegroundColor Gray }

function Fail([string]$Reason, [string]$Hint) {
    Write-Host ''
    Write-Host "  [FAIL] $Reason" -ForegroundColor Red
    if ($Hint) { Write-Host "         $Hint" -ForegroundColor Red }
    Write-Host ''
    exit 1
}

function Get-FileSizeMB([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return 'n/a' }
    return ('{0:N2} MB' -f ((Get-Item -LiteralPath $Path).Length / 1MB))
}

function Resolve-Python {
    $venv = Join-Path $script:RepoRoot '.venv\Scripts\python.exe'
    if (Test-Path -LiteralPath $venv) { return $venv }
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    Fail '找不到 Python 解释器。' '请安装 Python 3.12 并在项目根创建 .venv，或把 python 加入 PATH。'
}

# 版本号唯一来源与 build_installer.ps1 保持一致：installer\LanPulse.iss
function Get-AppVersion {
    $iss = Join-Path $script:RepoRoot 'installer\LanPulse.iss'
    if (-not (Test-Path -LiteralPath $iss)) {
        Fail "找不到 $iss" '版本号从该文件的 #define MyAppVersion 读取。'
    }
    $m = Select-String -LiteralPath $iss -Pattern '^\s*#define\s+MyAppVersion\s+"([^"]+)"' |
         Select-Object -First 1
    if (-not $m) {
        Fail '无法从 installer\LanPulse.iss 解析 MyAppVersion。' '请确认其中存在 #define MyAppVersion "1.0.0" 这样的行。'
    }
    return $m.Matches[0].Groups[1].Value
}

# --------------------------------------------------------------------------- #
Write-Host ''
Write-Host '  LanPulse 绿色包构建' -ForegroundColor White
Write-Info "仓库根: $($script:RepoRoot)"

if (-not (Test-Path -LiteralPath (Join-Path $script:RepoRoot 'build.spec'))) {
    Fail "不是预期的项目结构：$($script:RepoRoot)\build.spec 不存在。" '请把脚本放在 <仓库根>\scripts\ 下。'
}

$Version = Get-AppVersion
Write-Info "版本号: $Version"

# --------------------------------------------------------------------------- #
# 1. PyInstaller
# --------------------------------------------------------------------------- #
Write-Step '步骤 1/3  PyInstaller 打包'

$exe = Join-Path $script:RepoRoot 'dist\LanPulse\LanPulse.exe'
if ((-not $Fresh) -and (Test-Path -LiteralPath $exe)) {
    Write-Ok "已存在打包产物，跳过 PyInstaller: $exe"
    Write-Info '（需要强制重建请加 -Fresh 参数）'
} else {
    $python = Resolve-Python
    Write-Info "解释器: $python"
    Push-Location $script:RepoRoot
    try {
        Write-Info '执行: python -m PyInstaller build.spec --noconfirm --clean'
        & $python -m PyInstaller build.spec --noconfirm --clean
        if ($LASTEXITCODE -ne 0) {
            Fail "PyInstaller 失败（退出码 $LASTEXITCODE）" '请查看上方输出定位具体错误。'
        }
    } finally {
        Pop-Location
    }
    if (-not (Test-Path -LiteralPath $exe)) {
        Fail "PyInstaller 报告成功，但没有生成 $exe" '请检查 build.spec 的 COLLECT name 是否仍为 LanPulse。'
    }
    Write-Ok "打包完成: $exe ($(Get-FileSizeMB $exe))"
}

# --------------------------------------------------------------------------- #
# 2. 生成 zip
# --------------------------------------------------------------------------- #
Write-Step '步骤 2/3  生成 zip'

Add-Type -AssemblyName System.IO.Compression.FileSystem

$src = Join-Path $script:RepoRoot 'dist\LanPulse'
$zip = Join-Path $script:RepoRoot "release\LanPulse-$Version-win64-portable.zip"

$releaseDir = Join-Path $script:RepoRoot 'release'
if (-not (Test-Path -LiteralPath $releaseDir)) {
    New-Item -ItemType Directory -Path $releaseDir -Force | Out-Null
    Write-Info "创建输出目录: $releaseDir"
}

Write-Info "源目录: $src"
Write-Info "目标:   $zip"

# CreateFromDirectory 压缩的是目录“内容”，解压后顶层就是 LanPulse.exe，
# 不会出现多套一层的 LanPulse\LanPulse.exe。README 按这个层级写。
if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip -Force }
[System.IO.Compression.ZipFile]::CreateFromDirectory(
    $src,
    $zip,
    [System.IO.Compression.CompressionLevel]::Optimal,
    $false
)

$archive = [System.IO.Compression.ZipFile]::Open($zip, [System.IO.Compression.ZipArchiveMode]::Update)
try {
    foreach ($extra in @(
        @{ Path = (Join-Path $script:RepoRoot 'installer\README.txt');  Entry = 'README.txt'  },
        @{ Path = (Join-Path $script:RepoRoot 'installer\LICENSE.txt'); Entry = 'LICENSE.txt' }
    )) {
        if (-not (Test-Path -LiteralPath $extra.Path)) {
            Fail "缺少 $($extra.Path)" '绿色包需要 installer\README.txt 与 installer\LICENSE.txt。'
        }
        [void][System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
            $archive, $extra.Path, $extra.Entry,
            [System.IO.Compression.CompressionLevel]::Optimal
        )
        Write-Info "已加入 $($extra.Entry)"
    }
} finally {
    $archive.Dispose()
}

Write-Ok "绿色包完成: $zip ($(Get-FileSizeMB $zip))"

# --------------------------------------------------------------------------- #
# 3. 汇总
# --------------------------------------------------------------------------- #
Write-Step '构建结果'

$hash = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash

Write-Host ''
Write-Host "  文件:   $(Split-Path -Leaf $zip)" -ForegroundColor White
Write-Host "  路径:   $zip"
Write-Host "  大小:   $(Get-FileSizeMB $zip)"
Write-Host "  SHA256: $hash" -ForegroundColor Green
Write-Host ''

$sumFile = Join-Path $releaseDir 'SHA256SUMS.txt'
$lines = @()
if (Test-Path -LiteralPath $sumFile) {
    # 已有条目里去掉本 zip 的旧行，其余（例如 Setup.exe 那行）原样保留，
    # 避免单独跑本脚本时把 build_installer.ps1 写的校验行冲掉。
    $lines += @(Get-Content -LiteralPath $sumFile |
                Where-Object { $_ -match '\S' -and $_ -notmatch [regex]::Escape((Split-Path -Leaf $zip)) })
}
$lines += "$hash  $(Split-Path -Leaf $zip)"
$enc = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($sumFile, (($lines -join "`r`n") + "`r`n"), $enc)
Write-Info "校验文件: $sumFile"

Write-Host ''
Write-Host "  版本 $Version 绿色包构建完成。" -ForegroundColor Green
Write-Host ''
exit 0
