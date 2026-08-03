"""Which connection modes are reachable with which credentials.

The API token is the most capable credential, but it is not the only one, and
it must never be a hard prerequisite for the modes that do not use the API at
all. Before 0.6.0 the client demanded a token up front for every ``connect``,
so a user with a perfectly good SSH key and a reserved domain was locked out,
and a plan refusal on an advisory endpoint looked like a bad credential.

The matrix:

===================  ==========  ==========  =============================
Mode                 API token   SSH key     What it does
===================  ==========  ==========  =============================
``api``              required    optional    Full API flow: managed runtime,
                                             cloud proxy, domain and key
                                             provisioning, OAuth proxy.
``ssh_stable``       not used    required    Direct SSH reverse forward to a
                                             reserved domain.
``tcp_stable``       not used    not used    Keyless TCP bridge pinned to a
                                             reserved domain.
``tcp_random``       not used    not used    Keyless TCP bridge on a
                                             server-issued random domain.
===================  ==========  ==========  =============================

So: with an API token everything works; with only an SSH key three modes
remain; with no credentials at all the two keyless bridge modes still work.
In those last three modes the API token is never read and never validated,
even if one happens to be configured.
"""

from __future__ import annotations

from dataclasses import dataclass

MODE_API = 'api'
MODE_SSH_STABLE = 'ssh_stable'
MODE_TCP_STABLE = 'tcp_stable'
MODE_TCP_RANDOM = 'tcp_random'

ALL_MODES = (MODE_API, MODE_SSH_STABLE, MODE_TCP_STABLE, MODE_TCP_RANDOM)

#: Modes that never touch the Integration API, so the token is not consulted.
TOKENLESS_MODES = frozenset({MODE_SSH_STABLE, MODE_TCP_STABLE, MODE_TCP_RANDOM})

#: Modes that cannot work without a usable SSH private key.
SSH_MODES = frozenset({MODE_SSH_STABLE})

MODE_TITLES = {
    MODE_API: 'Full API flow',
    MODE_SSH_STABLE: 'Direct SSH to a reserved domain',
    MODE_TCP_STABLE: 'Keyless TCP bridge on a reserved domain',
    MODE_TCP_RANDOM: 'Keyless TCP bridge on a random domain',
}

RANDOM_DOMAIN_SELECTORS = frozenset({'random', 'ephemeral', 'ephemeral_random'})


def requires_api_token(mode: str) -> bool:
    return str(mode) not in TOKENLESS_MODES


def requires_ssh_key(mode: str) -> bool:
    return str(mode) in SSH_MODES


def available_modes(*, has_api_token: bool, has_ssh_key: bool) -> tuple[str, ...]:
    """Modes reachable with the credentials actually on hand."""
    modes = [MODE_TCP_STABLE, MODE_TCP_RANDOM]
    if has_ssh_key:
        modes.insert(0, MODE_SSH_STABLE)
    if has_api_token:
        modes.insert(0, MODE_API)
    return tuple(modes)


def is_random_domain(domain_selector: str | None) -> bool:
    selector = str(domain_selector or '').strip()
    if not selector:
        # No selector at all means "let the server pick", which only the
        # keyless bridge endpoint can satisfy without an API call.
        return True
    if selector in RANDOM_DOMAIN_SELECTORS:
        return True
    mode, _, _value = selector.partition(':')
    return mode.strip() in RANDOM_DOMAIN_SELECTORS


RESERVED_DOMAIN_MODES = frozenset({'existing', 'id', 'existing-id'})


def is_reserved_domain(domain_selector: str | None) -> bool:
    """True only for a domain that already exists in the account."""
    selector = str(domain_selector or '').strip()
    if not selector or ':' not in selector:
        return False
    mode, _, value = selector.partition(':')
    return mode.strip() in RESERVED_DOMAIN_MODES and bool(value.strip())


def _is_tcp_bridge(transport: str | None, connection_mode: str | None) -> bool:
    normalized_transport = str(transport or '').strip().lower().replace('-', '_')
    if normalized_transport == 'tcp_bridge':
        return True
    return str(connection_mode or '').strip().lower() == 'tcp_bridge'


@dataclass(slots=True)
class ModeDecision:
    mode: str
    requires_api_token: bool
    reason: str


def resolve_mode(
    *,
    command: str,
    transport: str | None = None,
    connection_mode: str | None = None,
    domain_selector: str | None = None,
) -> ModeDecision:
    """Classify a launch so the caller knows which credentials are needed.

    Only unambiguous, keyless launches are classified as tokenless. Anything
    that may need the API (key registration, domain creation, cloud proxy,
    OAuth) falls back to ``api`` and keeps requiring a token.
    """
    normalized_command = str(command or '').strip().lower()

    if normalized_command == 'bridge':
        # The dedicated bridge command is keyless by definition.
        mode = MODE_TCP_RANDOM if is_random_domain(domain_selector) else MODE_TCP_STABLE
        return ModeDecision(mode, False, 'bridge command uses the public keyless endpoint')

    if normalized_command in {'connect', 'plan'}:
        if _is_tcp_bridge(transport, connection_mode):
            if is_random_domain(domain_selector):
                return ModeDecision(
                    MODE_TCP_RANDOM,
                    False,
                    'tcp bridge with a server-issued domain needs no API token',
                )
            return ModeDecision(
                MODE_TCP_STABLE,
                False,
                'tcp bridge on a reserved domain needs no API token',
            )
        normalized_transport = str(transport or '').strip().lower().replace('-', '_')
        if normalized_transport == 'ssh' and is_reserved_domain(domain_selector):
            # Only an already reserved domain qualifies. Creating one is an API
            # operation and still needs a token.
            return ModeDecision(
                MODE_SSH_STABLE,
                False,
                'direct SSH to a reserved domain needs no API token',
            )

    return ModeDecision(MODE_API, True, 'this flow uses the Integration API')


def describe_modes(*, has_api_token: bool, has_ssh_key: bool) -> list[str]:
    """Operator-facing summary used in error messages and diagnostics."""
    return [f'{mode}: {MODE_TITLES[mode]}' for mode in available_modes(has_api_token=has_api_token, has_ssh_key=has_ssh_key)]


__all__ = [
    'ALL_MODES',
    'MODE_API',
    'MODE_SSH_STABLE',
    'MODE_TCP_RANDOM',
    'MODE_TCP_STABLE',
    'MODE_TITLES',
    'ModeDecision',
    'SSH_MODES',
    'TOKENLESS_MODES',
    'available_modes',
    'describe_modes',
    'is_random_domain',
    'is_reserved_domain',
    'requires_api_token',
    'requires_ssh_key',
    'resolve_mode',
]
