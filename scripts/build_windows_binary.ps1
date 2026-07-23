param(
    [string]$Python = "python",
    [string]$Version = "",
    [switch]$SkipTests,
    [switch]$Clean
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

if ($Clean) {
    if (Test-Path build) { Remove-Item build -Recurse -Force }
    if (Test-Path dist) { Remove-Item dist -Recurse -Force }
    if (Test-Path artifacts) { Remove-Item artifacts -Recurse -Force }
}

& $Python -m pip install --upgrade pip
& $Python -m pip install -e .
& $Python -m pip install -r requirements-build.txt

if (-not $SkipTests) {
    & $Python -m compileall src tests local_e2e_tests.py

    $ManualTestCode = @'
import sys
from pathlib import Path

sys.path[:0] = ["src", "."]

import tests.test_cli as cli_tests
import tests.test_config as config_tests
import tests.test_planner as planner_tests
import tests.test_client as client_tests

cli_tests.test_parser_allows_empty_argv()
cli_tests.test_connect_flags_are_optional_until_explicitly_set()
cli_tests.test_status_can_filter_by_name()
cli_tests.test_show_config_can_target_name()
cli_tests.test_stop_all_defaults()
cli_tests.test_apply_explicit_overrides_updates_connect_section()
cli_tests.test_prepare_execution_config_updates_default_config_first(Path("test-artifacts/build-script-default"))
cli_tests.test_prepare_execution_config_keeps_client_config_when_overwrite_disabled(Path("test-artifacts/build-script-client"))
config_tests.test_build_launch_config_template_contains_all_sections()
config_tests.test_normalize_launch_config_backfills_defaults()
config_tests.test_save_launch_config_persists_default_path_metadata(Path("test-artifacts/build-script-save"))
planner_tests.test_split_selector()
planner_tests.test_split_selector_rejects_invalid_value()
planner_tests.test_build_launch_payload_for_new_domain()
planner_tests.test_existing_unbound_domain_requires_key()
client_tests.test_build_ssl_context_insecure()
client_tests.test_build_ssl_context_windows_uses_truststore_when_available()
client_tests.test_build_ssl_context_windows_falls_back_when_missing()
print("manual tests passed")
'@

    & $Python -c $ManualTestCode
}

& $Python -m PyInstaller --clean tunnellio.spec

$StageDir = Join-Path $Root ("artifacts\tunnellio-windows-x64-v$Version")
New-Item -ItemType Directory -Force -Path $StageDir | Out-Null
Copy-Item "dist\tunnellio.exe" (Join-Path $StageDir "tunnellio.exe") -Force
Copy-Item README.md (Join-Path $StageDir "README.md") -Force
Copy-Item config.example.json (Join-Path $StageDir "config.example.json") -Force
Copy-Item LOCAL_E2E_TESTS.md (Join-Path $StageDir "LOCAL_E2E_TESTS.md") -Force
Copy-Item run_local_e2e.ps1 (Join-Path $StageDir "run_local_e2e.ps1") -Force
Copy-Item docs\* (Join-Path $StageDir "docs") -Recurse -Force

Write-Host "Build complete: $StageDir"
Write-Host "Next step: .\scripts\build_release_archive.ps1 -Version $Version"
