param(
    [string]$Version = "",
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not $Version) {
    $VersionMatch = Select-String -Path "pyproject.toml" -Pattern '^version\s*=\s*"([^"]+)"'
    if (-not $VersionMatch) {
        throw "Version not found in pyproject.toml"
    }
    $Version = $VersionMatch.Matches[0].Groups[1].Value
}

$StageDir = Join-Path $Root ("artifacts\tunnellio-windows-x64-v$Version")
if (-not (Test-Path $StageDir)) {
    throw "Stage directory not found: $StageDir. Run .\scripts\build_windows_binary.ps1 first."
}

$ArchivePath = Join-Path $Root ("artifacts\tunnellio-windows-x64-v$Version.zip")
if (Test-Path $ArchivePath) { Remove-Item $ArchivePath -Force }
Compress-Archive -Path (Join-Path $StageDir '*') -DestinationPath $ArchivePath -Force
Write-Host "Archive ready: $ArchivePath"
