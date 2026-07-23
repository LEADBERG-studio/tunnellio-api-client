# Testing guide

## Fast checks
```powershell
python -m compileall src tests local_e2e_tests.py
python -c "import sys; sys.path[:0]=['src','.']; import tests.test_cli as cli_tests; import tests.test_planner as planner_tests; import tests.test_client as client_tests; cli_tests.test_plan_defaults(); cli_tests.test_connect_defaults(); cli_tests.test_meta_defaults(); cli_tests.test_verbose_flag(); planner_tests.test_split_selector(); planner_tests.test_split_selector_rejects_invalid_value(); planner_tests.test_build_launch_payload_for_new_domain(); planner_tests.test_existing_unbound_domain_requires_key(); client_tests.test_build_ssl_context_insecure(); client_tests.test_build_ssl_context_windows_uses_truststore_when_available(); client_tests.test_build_ssl_context_windows_falls_back_when_missing(); print('manual tests passed')"
```

## CLI smoke test
```powershell
python -m tunnellio.cli --token YOUR_TOKEN --base-url https://api.tunnellio.ru --verbose meta
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
