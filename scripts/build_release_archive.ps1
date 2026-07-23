param(
    [string]$Version = "",
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not $Version) {
    $Version = & $Python -c "import re, pathlib; text=pathlib.Path('pyproject.toml').read_text(encoding='utf-8'); m=re.search(r'^version\s*=\s*\"([^\"]+)\"', text, re.M); print(m.group(1))"
}

$StageDir = Join-Path $Root ("artifacts\tunnellio-windows-x64-v$Version")
if (-not (Test-Path $StageDir)) {
    throw "Stage directory not found: $StageDir. Run .\scripts\build_windows_binary.ps1 first."
}

$ArchivePath = Join-Path $Root ("artifacts\tunnellio-windows-x64-v$Version.zip")
if (Test-Path $ArchivePath) { Remove-Item $ArchivePath -Force }
Compress-Archive -Path (Join-Path $StageDir '*') -DestinationPath $ArchivePath -Force
Write-Host "Archive ready: $ArchivePath"
