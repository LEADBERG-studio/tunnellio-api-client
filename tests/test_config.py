from pathlib import Path

from tunnellio.config import (
    build_launch_config_template,
    get_default_launch_config_path,
    normalize_launch_config,
    save_launch_config,
)



def test_build_launch_config_template_contains_all_sections() -> None:
    config = build_launch_config_template(Path('C:/tmp/tunnellio'))
    assert config['schemaVersion'] == 1
    assert 'global' in config
    assert 'meta' in config
    assert 'capabilities' in config
    assert 'plan' in config
    assert 'connect' in config
    assert 'status' in config
    assert 'stop' in config
    assert 'showConfig' in config
    assert config['connect']['watch'] is True
    assert config['connect']['name'] is None



def test_normalize_launch_config_backfills_defaults() -> None:
    payload = {
        'command': 'connect',
        'global': {'token': 'abc'},
        'connect': {'domainSelector': 'existing:mcp'},
    }
    normalized = normalize_launch_config(payload, state_dir_hint=Path('/tmp/tunnellio'))
    assert normalized['global']['token'] == 'abc'
    assert normalized['connect']['domainSelector'] == 'existing:mcp'
    assert normalized['connect']['localPort'] == 3000
    assert normalized['connect']['run'] is True
    assert 'showConfig' in normalized



def test_save_launch_config_persists_default_path_metadata(tmp_path: Path) -> None:
    target = get_default_launch_config_path(tmp_path)
    payload = build_launch_config_template(tmp_path)
    saved = save_launch_config(target, payload, state_dir_hint=tmp_path)
    assert target.exists()
    assert saved['paths']['defaultConfig'] == str(target)
