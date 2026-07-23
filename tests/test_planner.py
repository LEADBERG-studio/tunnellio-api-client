from pathlib import Path

from tunnellio.errors import InteractiveInputRequiredError, ValidationError
from tunnellio.models import Capabilities
from tunnellio.planner import PlanOptions, Planner, _split_selector


class DummyClient:
    def fetch_capabilities(self):
        return {
            'keys': {
                'maxCount': 10,
                'canCreate': True,
                'canDelete': True,
                'minLifetimeDays': 1,
                'maxLifetimeDays': 365,
                'defaultLifetimeDays': 30,
            },
            'domains': {
                'canCreate': True,
                'canDelete': True,
                'supportsRandomEphemeral': True,
                'minLifetimeDays': 1,
                'maxLifetimeDays': 365,
                'defaultLifetimeDays': 30,
            },
            'ephemeral': {
                'enabled': True,
                'deleteOnDisconnect': True,
                'fallbackLifetimeHours': 24,
            },
        }

    def list_keys(self):
        return [
            {
                'id': 1,
                'name': 'work',
                'fingerprint': 'SHA256:test',
                'createdAt': '2026-07-22T18:20:00+00:00',
                'expiresAt': None,
                'lastUsedAt': None,
                'status': 'active',
            }
        ]

    def list_domains(self):
        return [
            {
                'id': 2,
                'hostname': 'demo',
                'fqdn': 'demo.tunnellio.site',
                'publicUrl': 'https://demo.tunnellio.site',
                'keyId': None,
                'localPort': 3000,
                'note': '',
                'createdAt': '2026-07-22T18:25:00+00:00',
                'expiresAt': None,
                'lastUsedAt': None,
                'mode': 'persistent',
                'status': 'active',
            }
        ]


class DummyConfig:
    profiles_dir = Path('.')



def test_split_selector() -> None:
    assert _split_selector('existing:work', label='key') == ('existing', 'work')



def test_split_selector_rejects_invalid_value() -> None:
    try:
        _split_selector('existing', label='key')
    except ValidationError as exc:
        assert 'selector' in exc.details
    else:
        raise AssertionError('ValidationError was not raised')



def test_build_launch_payload_for_new_domain() -> None:
    planner = Planner(DummyClient(), DummyConfig())
    capabilities = Capabilities.from_api(DummyClient().fetch_capabilities())
    options = PlanOptions(
        key_selector='existing:work',
        domain_selector='new:demo-app',
        local_host='127.0.0.1',
        local_port=4040,
        domain_lifetime_days=30,
        note='test',
    )
    payload = planner.build_launch_payload(options, capabilities)
    assert payload['domainMode'] == 'new'
    assert payload['domain']['hostname'] == 'demo-app'
    assert payload['key']['mode'] == 'existing'
    assert payload['key']['keyId'] == 1
    assert payload['local']['port'] == 4040



def test_existing_unbound_domain_requires_key() -> None:
    planner = Planner(DummyClient(), DummyConfig())
    capabilities = Capabilities.from_api(DummyClient().fetch_capabilities())
    options = PlanOptions(domain_selector='existing:demo')
    try:
        planner.build_launch_payload(options, capabilities)
    except InteractiveInputRequiredError as exc:
        assert 'missing' in exc.details
    else:
        raise AssertionError('InteractiveInputRequiredError was not raised')
