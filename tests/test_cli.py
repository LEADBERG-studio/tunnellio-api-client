import json
import shutil
from pathlib import Path

from tunnellio.cli import build_parser, _apply_explicit_overrides, _prepare_execution_config, _write_runtime_connection_snapshot
from tunnellio.planner import Planner, PlanOptions
from tests.test_planner import DummyClient, DummyConfig



def test_parser_allows_empty_argv() -> None:
    parser = build_parser()
    args = parser.parse_args([])
    assert args.command is None
    assert args.config is None
    assert args.config_overwrite == 'ask'



def test_connect_flags_are_optional_until_explicitly_set() -> None:
    parser = build_parser()
    args = parser.parse_args(['connect'])
    assert args.command == 'connect'
    assert args.run is None
    assert args.watch is None
    assert args.name is None
    assert args.local_port is None



def test_status_can_filter_by_name() -> None:
    parser = build_parser()
    args = parser.parse_args(['status', '--name', 'prod-api'])
    assert args.command == 'status'
    assert args.name == 'prod-api'
    assert args.pid is None



def test_show_config_can_target_name() -> None:
    parser = build_parser()
    args = parser.parse_args(['show-config', '--name', 'prod-api'])
    assert args.command == 'show-config'
    assert args.name == 'prod-api'
    assert args.output is None



def test_stop_all_defaults() -> None:
    parser = build_parser()
    args = parser.parse_args(['stop', '--all'])
    assert args.command == 'stop'
    assert args.all is True
    assert args.force is None
    assert args.grace_seconds is None



def test_apply_explicit_overrides_updates_connect_section() -> None:
    parser = build_parser()
    args = parser.parse_args([
        '--token', 'abc',
        '--verbose',
        'connect',
        '--run',
        '--watch',
        '--domain', 'existing:mcp',
        '--local-port', '8080',
        '--name', 'prod-api',
    ])
    base = {
        'command': 'connect',
        'global': {'token': None, 'verbose': False},
        'connect': {
            'run': False,
            'watch': False,
            'domainSelector': None,
            'localPort': 3000,
            'name': None,
        },
    }
    updated = _apply_explicit_overrides(base, args)
    assert updated['global']['token'] == 'abc'
    assert updated['global']['verbose'] is True
    assert updated['connect']['run'] is True
    assert updated['connect']['watch'] is True
    assert updated['connect']['domainSelector'] == 'existing:mcp'
    assert updated['connect']['localPort'] == 8080
    assert updated['connect']['name'] == 'prod-api'



def test_prepare_execution_config_updates_default_config_first(tmp_path: Path) -> None:
    shutil.rmtree(tmp_path, ignore_errors=True)
    tmp_path.mkdir(parents=True, exist_ok=True)
    parser = build_parser()
    args = parser.parse_args([
        '--state-dir', str(tmp_path),
        '--token', 'tok-default',
        'connect',
        '--run',
        '--watch',
        '--domain', 'existing:mcp',
        '--local-port', '9090',
    ])
    config_payload, config_path, config_written = _prepare_execution_config(args)
    assert config_written is True
    assert config_path is not None and config_path.exists()
    assert config_payload['connect']['localPort'] == 9090
    assert config_payload['connect']['name'] is not None
    assert config_payload['connect']['name'].startswith('tunnel-')



def test_prepare_execution_config_keeps_client_config_when_overwrite_disabled(tmp_path: Path) -> None:
    shutil.rmtree(tmp_path, ignore_errors=True)
    tmp_path.mkdir(parents=True, exist_ok=True)
    config_path = tmp_path / 'client.json'
    config_path.write_text(
        '{\n'
        '  "schemaVersion": 1,\n'
        '  "command": "connect",\n'
        '  "global": {"token": "tok-a", "stateDir": "' + str(tmp_path).replace('\\', '\\\\') + '"},\n'
        '  "connect": {"run": true, "watch": true, "name": "prod-api", "domainSelector": "existing:old", "localPort": 3000}\n'
        '}\n',
        encoding='utf-8',
    )
    parser = build_parser()
    args = parser.parse_args([
        '--config', str(config_path),
        '--config-overwrite', 'no',
        'connect',
        '--domain', 'existing:new',
        '--local-port', '7777',
    ])
    config_payload, returned_path, config_written = _prepare_execution_config(args)
    assert returned_path is None
    assert config_written is False
    assert config_payload['connect']['domainSelector'] == 'existing:new'
    assert config_payload['connect']['localPort'] == 7777
    saved = config_path.read_text(encoding='utf-8')
    assert 'existing:old' in saved
    assert 'existing:new' not in saved


def test_connect_parser_accepts_new_server_contract_flags() -> None:
    parser = build_parser()
    args = parser.parse_args([
        'connect',
        '--requested-auth-mode', 'oauth',
        '--connection-mode', 'cloud_proxy',
        '--oauth-client-policy', 'shared',
        '--runtime-name', 'prod-api',
        '--use-discovery',
        '--session-strategy', 'open_then_launch',
        '--enable-pkce',
    ])
    assert args.requested_auth_mode == 'oauth'
    assert args.connection_mode == 'cloud_proxy'
    assert args.oauth_client_policy == 'shared'
    assert args.runtime_name == 'prod-api'
    assert args.use_discovery is True
    assert args.session_strategy == 'open_then_launch'
    assert args.enable_pkce is True


def test_apply_explicit_overrides_updates_new_contract_fields() -> None:
    parser = build_parser()
    args = parser.parse_args([
        'connect',
        '--requested-auth-mode', 'oauth',
        '--connection-mode', 'cloud_proxy',
        '--oauth-client-policy', 'shared',
        '--runtime-name', 'prod-api',
        '--use-discovery',
        '--session-strategy', 'open_then_launch',
        '--enable-pkce',
    ])
    base = {
        'command': 'connect',
        'global': {},
        'connect': {
            'requestedAuthMode': None,
            'connectionMode': None,
            'oauthClientPolicy': None,
            'runtimeName': None,
            'useDiscovery': False,
            'sessionStrategy': None,
            'enablePkce': False,
        },
    }
    updated = _apply_explicit_overrides(base, args)
    assert updated['connect']['requestedAuthMode'] == 'oauth'
    assert updated['connect']['connectionMode'] == 'cloud_proxy'
    assert updated['connect']['oauthClientPolicy'] == 'shared'
    assert updated['connect']['runtimeName'] == 'prod-api'
    assert updated['connect']['useDiscovery'] is True
    assert updated['connect']['sessionStrategy'] == 'open_then_launch'
    assert updated['connect']['enablePkce'] is True


def test_connect_parser_accepts_transport_flag() -> None:
    parser = build_parser()
    args = parser.parse_args(['connect', '--transport', 'tcp-bridge'])
    assert args.transport == 'tcp-bridge'

    args_ssh = parser.parse_args(['connect', '--transport', 'ssh'])
    assert args_ssh.transport == 'ssh'

    args_auto = parser.parse_args(['connect', '--transport', 'auto'])
    assert args_auto.transport == 'auto'


def test_apply_explicit_overrides_maps_transport_to_config() -> None:
    parser = build_parser()
    args = parser.parse_args([
        'connect',
        '--transport', 'tcp-bridge',
        '--domain', 'new:demo-bridge',
    ])
    base = {
        'command': 'connect',
        'global': {},
        'connect': {
            'transport': None,
            'domainSelector': None,
        },
    }
    updated = _apply_explicit_overrides(base, args)
    assert updated['connect']['transport'] == 'tcp-bridge'
    assert updated['connect']['domainSelector'] == 'new:demo-bridge'


def test_bridge_parser_accepts_basic_flags() -> None:
    parser = build_parser()
    args = parser.parse_args([
        'bridge',
        '--domain', 'new:my-app',
        '--local-port', '3000',
        '--run',
        '--name', 'my-bridge',
    ])
    assert args.command == 'bridge'
    assert args.domain_selector == 'new:my-app'
    assert args.local_port == 3000
    assert args.run is True
    assert args.name == 'my-bridge'


def test_bridge_parser_does_not_require_token() -> None:
    parser = build_parser()
    args = parser.parse_args(['bridge', '--local-port', '3000'])
    assert args.command == 'bridge'
    assert args.token is None
    assert args.local_port == 3000


def test_oauth_login_parser_accepts_required_flags() -> None:
    parser = build_parser()
    args = parser.parse_args([
        'oauth-login',
        '--domain', 'existing:demo',
        '--client-id', 'client-1',
        '--redirect-uri', 'http://localhost:3333/callback',
        '--scopes', 'proxy.connect proxy.inspect',
        '--enable-pkce',
    ])
    assert args.command == 'oauth-login'
    assert args.domain_selector == 'existing:demo'
    assert args.client_id == 'client-1'
    assert args.redirect_uri == 'http://localhost:3333/callback'
    assert args.enable_pkce is True



def test_oauth_refresh_parser_accepts_token_reference() -> None:
    parser = build_parser()
    args = parser.parse_args(['oauth-refresh', '--token-name', 'demo-token'])
    assert args.command == 'oauth-refresh'
    assert args.token_name == 'demo-token'



def test_runtime_connection_snapshot_contains_auth_and_runtime_contracts(tmp_path: Path) -> None:
    planner = Planner(DummyClient(), DummyConfig())
    result = planner.build_plan(
        PlanOptions(
            key_selector='existing:work',
            domain_selector='existing:demo',
            requested_auth_mode='oauth',
            connection_mode='cloud_proxy',
            runtime_name='prod-api',
            enable_pkce=True,
        )
    )
    target = tmp_path / 'prod-api.config.json'
    status_path = tmp_path / 'prod-api.json'
    stop_path = tmp_path / 'prod-api.stop'
    _write_runtime_connection_snapshot(
        target,
        runtime_name='prod-api',
        execution_config={'command': 'connect'},
        result=result,
        status_path=status_path,
        stop_path=stop_path,
    )
    payload = json.loads(target.read_text(encoding='utf-8'))
    assert payload['auth']['authMode'] == 'oauth'
    assert payload['runtime']['name'] == 'prod-api'
    assert payload['transport']['publicUrl'] == 'https://demo.tunnellio.site'
    assert payload['session']['resumeToken'] == 'resume_123'
