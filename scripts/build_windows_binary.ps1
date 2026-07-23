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
    $Version = & $Python -c "import re, pathlib; text=pathlib.Path('pyproject.toml').read_text(encoding='utf-8'); m=re.search(r'^version\s*=\s*\"([^\"]+)\"', text, re.M); print(m.group(1))"
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
    & $Python -c "import sys; sys.path[:0]=['src','.']; import tests.test_cli as cli_tests; import tests.test_planner as planner_tests; import tests.test_client as client_tests; cli_tests.test_plan_defaults(); cli_tests.test_connect_defaults(); cli_tests.test_meta_defaults(); cli_tests.test_verbose_flag(); planner_tests.test_split_selector(); planner_tests.test_split_selector_rejects_invalid_value(); planner_tests.test_build_launch_payload_for_new_domain(); planner_tests.test_existing_unbound_domain_requires_key(); client_tests.test_build_ssl_context_insecure(); client_tests.test_build_ssl_context_windows_uses_truststore_when_available(); client_tests.test_build_ssl_context_windows_falls_back_when_missing(); print('manual tests passed')"
}

& $Python -m PyInstaller --clean tunnellio.spec

$StageDir = Join-Path $Root ("artifacts\tunnellio-windows-x64-v$Version")
New-Item -ItemType Directory -Force -Path $StageDir | Out-Null
Copy-Item "dist\tunnellio.exe" (Join-Path $StageDir "tunnellio.exe") -Force
Copy-Item README.md (Join-Path $StageDir "README.md") -Force
Copy-Item LOCAL_E2E_TESTS.md (Join-Path $StageDir "LOCAL_E2E_TESTS.md") -Force
Copy-Item run_local_e2e.ps1 (Join-Path $StageDir "run_local_e2e.ps1") -Force
Copy-Item docs\* (Join-Path $StageDir "docs") -Recurse -Force

Write-Host "Build complete: $StageDir"
Write-Host "Next step: .\scripts\build_release_archive.ps1 -Version $Version"
