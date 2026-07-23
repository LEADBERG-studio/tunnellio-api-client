param(
    [string]$Version = ""
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

$ArchivePath = Join-Path $Root ("artifacts\tunnellio-source-v$Version.zip")
if (Test-Path $ArchivePath) { Remove-Item $ArchivePath -Force }

$SourceItems = @(
    "README.md",
    "CHANGELOG.md",
    "pyproject.toml",
    "requirements-build.txt",
    "tunnellio.spec",
    "config.example.json",
    "LOCAL_E2E_TESTS.md",
    "run_local_e2e.ps1",
    "HELPER_CONTRACT.md",
    "TECHNICAL_PLAN.md",
    "TECHNICAL_REQUIREMENTS.md",
    "docs",
    "scripts",
    "src",
    "tests",
    "live_test_suite.py",
    "local_e2e_tests.py",
    "enable_insecure_tls.py"
)

Compress-Archive -Path $SourceItems -DestinationPath $ArchivePath -Force
Write-Host "Source archive ready: $ArchivePath"
