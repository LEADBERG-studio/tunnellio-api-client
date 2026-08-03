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

    $TestScript = Join-Path $env:TEMP "tunnellio-build-tests-$(Get-Random).py"
    $TestCode = @"
import sys
from pathlib import Path

sys.path[:0] = ['src', '.']

import tests.test_cli as cli_tests
import tests.test_config as config_tests
import tests.test_planner as planner_tests
import tests.test_client as client_tests
import tests.test_oauth as oauth_tests
import tests.test_bridge as bridge_tests
import tests.test_errors as errors_tests
import tests.test_modes as modes_tests

cli_tests.test_parser_allows_empty_argv()
cli_tests.test_connect_flags_are_optional_until_explicitly_set()
cli_tests.test_status_can_filter_by_name()
cli_tests.test_show_config_can_target_name()
cli_tests.test_stop_all_defaults()
cli_tests.test_apply_explicit_overrides_updates_connect_section()
cli_tests.test_prepare_execution_config_updates_default_config_first(Path('test-artifacts/build-script-default'))
cli_tests.test_prepare_execution_config_keeps_client_config_when_overwrite_disabled(Path('test-artifacts/build-script-client'))
cli_tests.test_connect_parser_accepts_new_server_contract_flags()
cli_tests.test_apply_explicit_overrides_updates_new_contract_fields()
cli_tests.test_connect_parser_accepts_transport_flag()
cli_tests.test_apply_explicit_overrides_maps_transport_to_config()
cli_tests.test_bridge_parser_accepts_basic_flags()
cli_tests.test_bridge_parser_does_not_require_token()
cli_tests.test_connect_parser_accepts_tcp_bridge_password()
cli_tests.test_bridge_parser_accepts_tcp_bridge_password()
cli_tests.test_runtime_connection_snapshot_contains_auth_and_runtime_contracts(Path("test-artifacts/build-script-snapshot"))
config_tests.test_build_launch_config_template_contains_all_sections()
config_tests.test_normalize_launch_config_backfills_defaults()
config_tests.test_save_launch_config_persists_default_path_metadata(Path("test-artifacts/build-script-save"))
planner_tests.test_split_selector()
planner_tests.test_split_selector_rejects_invalid_value()
planner_tests.test_build_launch_payload_for_new_domain()
planner_tests.test_existing_unbound_domain_requires_key()
planner_tests.test_build_plan_returns_session_and_auth_contracts()
planner_tests.test_build_plan_rejects_requested_auth_mode_mismatch()
planner_tests.test_tcp_bridge_new_domain_omits_key_payload()
planner_tests.test_tcp_bridge_build_plan_returns_keyless_profile()
planner_tests.test_tcp_bridge_session_open_payload_omits_key_id_when_keyless()
planner_tests.test_keyless_bridge_plan_calls_public_endpoint()
planner_tests.test_keyless_bridge_plan_with_generated_subdomain()
planner_tests.test_tcp_bridge_password_in_launch_payload()
planner_tests.test_tcp_bridge_password_in_keyless_plan()
planner_tests.test_password_required_profile_parses()
bridge_tests.test_send_and_recv_frame_roundtrip()
bridge_tests.test_auth_tag_computes_hmac_sha256()
bridge_tests.test_bidirectional_copy_transfers_data()
bridge_tests.test_launch_bridge_handshake_without_secret()
bridge_tests.test_launch_bridge_handshake_with_secret()
bridge_tests.test_launch_bridge_with_hello_template_and_password()
client_tests.test_build_ssl_context_insecure()
client_tests.test_build_ssl_context_windows_uses_truststore_when_available()
client_tests.test_build_ssl_context_windows_falls_back_when_missing()
client_tests.test_fetch_oauth_authorization_server_uses_discovery_url()
client_tests.test_fetch_oauth_protected_resource_uses_resource_url()
client_tests.test_authorize_oauth_code_uses_post_json()
client_tests.test_exchange_oauth_token_unwraps_enveloped_response()
client_tests.test_introspect_oauth_token_unwraps_enveloped_response()
client_tests.test_open_session_unwraps_session_payload()
client_tests.test_heartbeat_session_includes_resume_token()
client_tests.test_close_session_includes_resume_token()
oauth_tests.test_generate_pkce_pair()
oauth_tests.test_build_authorize_url()
oauth_tests.test_token_record_from_response_and_roundtrip(Path('test-artifacts/build-script-oauth-record'))
oauth_tests.test_token_record_requires_access_token()
oauth_tests.test_build_token_storage_name()
errors_tests.test_plan_required_code_is_not_an_auth_failure()
errors_tests.test_plan_wording_on_403_is_detected_without_a_dedicated_code()
errors_tests.test_unauthorized_is_still_an_auth_error()
errors_tests.test_plain_forbidden_is_still_an_auth_error()
errors_tests.test_is_plan_limit_matrix()
errors_tests.test_plan_required_payload_keeps_the_server_code()
errors_tests.test_other_errors_are_unchanged()
modes_tests.test_api_token_unlocks_every_mode()
modes_tests.test_api_token_alone_still_unlocks_every_mode()
modes_tests.test_ssh_key_only_leaves_three_modes()
modes_tests.test_no_credentials_leaves_the_two_keyless_modes()
modes_tests.test_the_three_fallback_modes_never_need_an_api_token()
modes_tests.test_only_ssh_stable_needs_an_ssh_key()
modes_tests.test_resolve_ssh_stable()
modes_tests.test_resolve_tcp_stable()
modes_tests.test_resolve_tcp_random()
modes_tests.test_connection_mode_is_honoured_when_transport_is_absent()
modes_tests.test_bridge_command_is_always_tokenless()
modes_tests.test_api_flows_still_require_a_token()
modes_tests.test_auto_transport_is_treated_as_api_until_it_resolves()
modes_tests.test_is_random_domain()
modes_tests.test_describe_modes_is_human_readable()
modes_tests.test_offline_ssh_plan_needs_no_api_client()
modes_tests.test_offline_ssh_plan_rejects_a_missing_domain()
planner_tests.test_plan_required_meta_does_not_abort_the_plan()
planner_tests.test_plan_required_capabilities_fall_back_to_placeholders()
planner_tests.test_plan_limits_do_not_block_a_full_connect()
planner_tests.test_unknown_capabilities_allow_random_ephemeral()
planner_tests.test_known_capabilities_still_gate_random_ephemeral()
planner_tests.test_unknown_capabilities_skip_lifetime_validation()
planner_tests.test_rejected_token_still_fails()
planner_tests.test_keyless_bridge_profile_saves_without_meta()
print('manual tests passed')
"@
    Set-Content -Path $TestScript -Value $TestCode -Encoding UTF8
    try {
        & $Python $TestScript
    } finally {
        Remove-Item $TestScript -ErrorAction SilentlyContinue
    }
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
