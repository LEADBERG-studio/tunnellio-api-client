from pathlib import Path

from tunnellio.errors import ValidationError
from tunnellio.modes import (
    MODE_API,
    MODE_SSH_STABLE,
    MODE_TCP_RANDOM,
    MODE_TCP_STABLE,
    available_modes,
    describe_modes,
    is_random_domain,
    requires_api_token,
    requires_ssh_key,
    resolve_mode,
)
from tunnellio.planner import PlanOptions, Planner


class DummyConfig:
    profiles_dir = Path('.')


def test_api_token_unlocks_every_mode() -> None:
    modes = available_modes(has_api_token=True, has_ssh_key=True)
    assert modes == (MODE_API, MODE_SSH_STABLE, MODE_TCP_STABLE, MODE_TCP_RANDOM)


def test_api_token_alone_still_unlocks_every_mode() -> None:
    modes = available_modes(has_api_token=True, has_ssh_key=False)
    assert MODE_API in modes
    assert MODE_TCP_STABLE in modes
    assert MODE_TCP_RANDOM in modes


def test_ssh_key_only_leaves_three_modes() -> None:
    modes = available_modes(has_api_token=False, has_ssh_key=True)
    assert modes == (MODE_SSH_STABLE, MODE_TCP_STABLE, MODE_TCP_RANDOM)
    assert MODE_API not in modes


def test_no_credentials_leaves_the_two_keyless_modes() -> None:
    modes = available_modes(has_api_token=False, has_ssh_key=False)
    assert modes == (MODE_TCP_STABLE, MODE_TCP_RANDOM)


def test_the_three_fallback_modes_never_need_an_api_token() -> None:
    for mode in (MODE_SSH_STABLE, MODE_TCP_STABLE, MODE_TCP_RANDOM):
        assert requires_api_token(mode) is False
    assert requires_api_token(MODE_API) is True


def test_only_ssh_stable_needs_an_ssh_key() -> None:
    assert requires_ssh_key(MODE_SSH_STABLE) is True
    for mode in (MODE_TCP_STABLE, MODE_TCP_RANDOM, MODE_API):
        assert requires_ssh_key(mode) is False


def test_resolve_ssh_stable() -> None:
    decision = resolve_mode(command='connect', transport='ssh', domain_selector='existing:mcp')
    assert decision.mode == MODE_SSH_STABLE
    assert decision.requires_api_token is False


def test_resolve_tcp_stable() -> None:
    decision = resolve_mode(command='connect', transport='tcp-bridge', domain_selector='existing:mcp')
    assert decision.mode == MODE_TCP_STABLE
    assert decision.requires_api_token is False


def test_resolve_tcp_random() -> None:
    for selector in ('random', 'ephemeral', 'ephemeral_random', None, ''):
        decision = resolve_mode(command='connect', transport='tcp-bridge', domain_selector=selector)
        assert decision.mode == MODE_TCP_RANDOM, selector
        assert decision.requires_api_token is False


def test_connection_mode_is_honoured_when_transport_is_absent() -> None:
    decision = resolve_mode(command='connect', connection_mode='tcp_bridge', domain_selector='existing:mcp')
    assert decision.mode == MODE_TCP_STABLE


def test_bridge_command_is_always_tokenless() -> None:
    assert resolve_mode(command='bridge', domain_selector='existing:mcp').mode == MODE_TCP_STABLE
    assert resolve_mode(command='bridge', domain_selector=None).mode == MODE_TCP_RANDOM
    assert resolve_mode(command='bridge').requires_api_token is False


def test_api_flows_still_require_a_token() -> None:
    # Creating a domain, registering a key, cloud proxy and random SSH all go
    # through the Integration API and must keep demanding a credential.
    assert resolve_mode(command='connect', transport='ssh', domain_selector='new:mcp').requires_api_token is True
    assert resolve_mode(command='connect', transport='ssh', domain_selector='random').requires_api_token is True
    assert resolve_mode(command='connect', connection_mode='cloud_proxy', domain_selector='existing:mcp').requires_api_token is True
    assert resolve_mode(command='meta').requires_api_token is True
    assert resolve_mode(command='oauth-login', domain_selector='existing:mcp').requires_api_token is True


def test_auto_transport_is_treated_as_api_until_it_resolves() -> None:
    decision = resolve_mode(command='connect', transport='auto', domain_selector='existing:mcp')
    assert decision.mode == MODE_API


def test_is_random_domain() -> None:
    assert is_random_domain(None) is True
    assert is_random_domain('') is True
    assert is_random_domain('random') is True
    assert is_random_domain('ephemeral_random:') is True
    assert is_random_domain('existing:mcp') is False
    assert is_random_domain('new:mcp') is False


def test_describe_modes_is_human_readable() -> None:
    lines = describe_modes(has_api_token=False, has_ssh_key=False)
    assert len(lines) == 2
    assert all(': ' in line for line in lines)


def test_offline_ssh_plan_needs_no_api_client() -> None:
    """The whole point: a reserved domain plus a key is enough on its own."""
    planner = Planner(None, DummyConfig())
    result = planner.build_offline_ssh_plan(
        PlanOptions(domain_selector='existing:my-mcp', local_port=8765, mode='connect')
    )
    profile = result.connection_profile
    assert profile.public_url == 'https://my-mcp.tunnellio.site'
    assert profile.requires_api_token is False
    assert profile.requires_ssh_key is True
    assert result.meta is None
    assert '-R' in profile.ssh_args
    assert 'my-mcp:80:127.0.0.1:8765' in profile.ssh_args
    assert profile.ssh_args[-1] == 'tunnel@tunnellio.site'


def test_offline_ssh_plan_rejects_a_missing_domain() -> None:
    planner = Planner(None, DummyConfig())
    try:
        planner.build_offline_ssh_plan(PlanOptions(local_port=3000, mode='connect'))
    except ValidationError:
        pass
    else:
        raise AssertionError('ValidationError was not raised')
