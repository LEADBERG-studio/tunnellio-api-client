# Testing guide



## Fast source checks

```powershell

python -m compileall src tests

```



## Local manual test suite

```powershell

python -c "from pathlib import Path; import sys; sys.path[:0]=['src','.']; import tests.test_client as tc; import tests.test_planner as tp; import tests.test_oauth as to; import tests.test_cli as tcli; import tests.test_config as tcfg; tc.test_build_ssl_context_insecure(); tc.test_build_ssl_context_windows_uses_truststore_when_available(); tc.test_build_ssl_context_windows_falls_back_when_missing(); tc.test_fetch_oauth_authorization_server_uses_discovery_url(); tc.test_fetch_oauth_protected_resource_uses_resource_url(); tc.test_authorize_oauth_code_uses_post_json(); tc.test_exchange_oauth_token_unwraps_enveloped_response(); tc.test_introspect_oauth_token_unwraps_enveloped_response(); tc.test_open_session_unwraps_session_payload(); tc.test_heartbeat_session_includes_resume_token(); tc.test_close_session_includes_resume_token(); tp.test_split_selector(); tp.test_split_selector_rejects_invalid_value(); tp.test_build_launch_payload_for_new_domain(); tp.test_existing_unbound_domain_requires_key(); tp.test_build_plan_returns_session_and_auth_contracts(); tp.test_build_plan_rejects_requested_auth_mode_mismatch(); to.test_generate_pkce_pair(); to.test_build_authorize_url(); to.test_token_record_from_response_and_roundtrip(Path('test-artifacts/tmp-oauth-record-doc')); to.test_token_record_requires_access_token(); to.test_refresh_roundtrip_preserves_refresh_token_when_server_omits_it(); to.test_build_token_storage_name(); tcli.test_parser_allows_empty_argv(); tcli.test_connect_flags_are_optional_until_explicitly_set(); tcli.test_status_can_filter_by_name(); tcli.test_show_config_can_target_name(); tcli.test_stop_all_defaults(); tcli.test_apply_explicit_overrides_updates_connect_section(); tcli.test_prepare_execution_config_updates_default_config_first(Path('test-artifacts/tmp-cli-default-doc')); tcli.test_prepare_execution_config_keeps_client_config_when_overwrite_disabled(Path('test-artifacts/tmp-cli-client-doc')); tcli.test_connect_parser_accepts_new_server_contract_flags(); tcli.test_apply_explicit_overrides_updates_new_contract_fields(); tcli.test_oauth_login_parser_accepts_required_flags(); tcli.test_oauth_refresh_parser_accepts_token_reference(); tcli.test_runtime_connection_snapshot_contains_auth_and_runtime_contracts(Path('test-artifacts/tmp-cli-snapshot-doc')); tcfg.test_build_launch_config_template_contains_all_sections(); tcfg.test_normalize_launch_config_backfills_defaults(); tcfg.test_save_launch_config_persists_default_path_metadata(Path('test-artifacts/tmp-config-doc')); print('full local suite passed')"

```



## CLI smoke test

```powershell

python -m tunnellio.cli --token YOUR_TOKEN --base-url https://api.tunnellio.ru --verbose meta

```



## Live contract checks

Use these when you need to verify the new server contract against a real domain.



### Live plan check

```powershell

python -m tunnellio.cli --token YOUR_TOKEN plan --output json --domain existing:test --local-port 3000 --requested-auth-mode dual --connection-mode dual --runtime-name live-test-dual

```



### Live session check

This should validate open -> status -> heartbeat -> resume -> close with the server's current session contract.

```powershell

python -c "import json, sys; sys.path[:0]=['src']; from tunnellio.config import load_runtime_config; from tunnellio.client import ApiClient; from tunnellio.planner import Planner, PlanOptions; config = load_runtime_config(token='YOUR_TOKEN', base_url='https://api.tunnellio.ru', state_dir='test-artifacts/live-session-doc', insecure_tls=False, require_token=False); client = ApiClient(config); planner = Planner(client, config); plan = planner.build_plan(PlanOptions(domain_selector='existing:test', local_port=3000, requested_auth_mode='dual', connection_mode='dual', runtime_name='live-session-doc')); opened = client.open_session(plan.session_open_payload); token = opened.get('resumeToken'); sid = opened['id']; payload = {'runtimeName': 'live-session-doc', 'publicUrl': plan.connection_profile.public_url}; result = {'opened': opened, 'status': client.get_session_status(session_id=sid), 'heartbeat': client.heartbeat_session(session_id=sid, resume_token=token, payload=payload), 'resumed': client.resume_session(session_id=sid, resume_token=token, payload=payload), 'closed': client.close_session(session_id=sid, resume_token=token, reason='testing_doc_check')}; print(json.dumps(result, indent=2, ensure_ascii=False))"

```

### Live OAuth login

```powershell

python -m tunnellio.cli --token YOUR_TOKEN --base-url https://api.tunnellio.ru --state-dir test-artifacts/live-oauth oauth-login --output json --domain existing:test --client-id YOUR_CLIENT_ID --redirect-uri http://localhost:3333/callback --scopes "proxy.connect proxy.inspect" --token-name live-test-client --use-discovery --enable-pkce

```

### Live OAuth refresh

```powershell

python -m tunnellio.cli --token YOUR_TOKEN --base-url https://api.tunnellio.ru --state-dir test-artifacts/live-oauth oauth-refresh --output json --token-name live-test-client

```

### Live OAuth introspection

```powershell

python -m tunnellio.cli --token YOUR_TOKEN --base-url https://api.tunnellio.ru --state-dir test-artifacts/live-oauth oauth-introspect --output json --token-name live-test-client

```

## API-only local e2e

```powershell

.\run_local_e2e.ps1 -Token "YOUR_TOKEN" -Mode api -VerboseOutput

```



## Full local e2e

```powershell

.\run_local_e2e.ps1 -Token "YOUR_TOKEN" -Mode full -VerboseOutput

```



## Fallback checks

If you need diagnostics for broken TLS or a problematic environment:

```powershell

.\run_local_e2e.ps1 -Token "YOUR_TOKEN" -Mode full -VerboseOutput -AllowInsecureTlsFallback -AllowInsecurePublicUrlProbe

```



## Artifacts

Each run writes into:

- `test-artifacts\<run-id>\report.json`

- `test-artifacts\<run-id>\ssh-stdout.log`

- `test-artifacts\<run-id>\ssh-stderr.log`
