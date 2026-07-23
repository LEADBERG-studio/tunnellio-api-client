from __future__ import annotations

import json
import sys
from typing import Any

from .errors import TunnellioError
from .models import Capabilities, Meta, PlanResult


class OutputWriter:
    def __init__(self, output_format: str):
        self.output_format = output_format

    def write_meta(self, meta: Meta) -> None:
        self.write_payload(meta.to_dict(), title='API metadata')

    def write_capabilities(self, capabilities: Capabilities) -> None:
        self.write_payload(capabilities.to_dict(), title='Capabilities')

    def write_plan(self, result: PlanResult) -> None:
        if self.output_format == 'json':
            print(json.dumps(result.to_dict(), indent=2))
            return

        print('Plan created successfully.')
        print(f'API: {result.meta.api_base_url} ({result.meta.api_version})')
        print(f'Key: {result.key.name} (id={result.key.id})')
        print(f'Domain: {result.domain.hostname}')
        print(f'Public URL: {result.connection_profile.public_url}')
        print(
            'SSH target: '
            f'{result.connection_profile.ssh_user}@{result.connection_profile.ssh_host}:{result.connection_profile.ssh_port}'
        )
        print(
            'Forward: '
            f'{result.connection_profile.remote_hostname} <- '
            f'{result.connection_profile.local_host}:{result.connection_profile.local_port}'
        )
        print(f'Command: {result.connection_profile.ssh_command}')
        if result.session is not None:
            print(f'Ephemeral session: {result.session.id}')
        if result.saved_profile is not None:
            print(f'Saved profile: {result.saved_profile.path}')

    def write_exec_result(self, result: PlanResult, execution: dict[str, Any]) -> None:
        if self.output_format == 'json':
            payload = result.to_dict()
            payload['execution'] = execution
            print(json.dumps(payload, indent=2))
            return

        self.write_plan(result)
        print(f"Process pid: {execution.get('pid')}")
        if execution.get('returnCode') is not None:
            print(f"Process exit code: {execution['returnCode']}")
        if execution.get('sessionCompleted'):
            print('Ephemeral session completed.')

    def write_payload(self, payload: dict[str, Any], *, title: str | None = None) -> None:
        if self.output_format == 'json':
            print(json.dumps(payload, indent=2))
            return
        if title:
            print(f'{title}:')
        print(json.dumps(payload, indent=2))

    def write_error(self, error: TunnellioError) -> None:
        if self.output_format == 'json':
            print(json.dumps(error.to_payload(), indent=2))
            return
        print(f'Error: {error.message}', file=sys.stderr)
        if error.details:
            print(json.dumps(error.details, indent=2), file=sys.stderr)
