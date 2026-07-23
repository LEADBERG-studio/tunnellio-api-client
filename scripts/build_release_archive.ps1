param(
    [string]$Version = "",
    [string]$Ref = "HEAD"
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

& git rev-parse --verify $Ref *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Git ref not found: $Ref"
}

$ArchivePath = Join-Path $Root ("artifacts\tunnellio-source-v$Version.zip")
if (Test-Path $ArchivePath) {
    Remove-Item $ArchivePath -Force
}

& git archive --format=zip "--output=$ArchivePath" $Ref
if ($LASTEXITCODE -ne 0) {
    throw "git archive failed for ref $Ref"
}

Write-Host "Source archive ready: $ArchivePath"
Write-Host "Archived git ref: $Ref"
