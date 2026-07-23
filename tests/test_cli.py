from pathlib import Path

from tunnellio.cli import build_parser, _apply_explicit_overrides, _prepare_execution_config



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
