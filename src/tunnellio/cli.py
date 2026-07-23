from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from typing import Sequence

from .client import ApiClient
from .config import DEFAULT_LOCAL_HOST, DEFAULT_LOCAL_PORT, load_runtime_config
from .errors import ExitCode, TunnellioError, ValidationError
from .models import Capabilities, Meta, PlanResult
from .output import OutputWriter
from .planner import PlanOptions, Planner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='tunnellio')
    parser.add_argument('--token')
    parser.add_argument('--base-url')
    parser.add_argument('--state-dir')
    parser.add_argument('--insecure-tls', action='store_true')
    parser.add_argument('--verbose', action='store_true')

    subparsers = parser.add_subparsers(dest='command', required=True)

    meta_parser = subparsers.add_parser('meta')
    meta_parser.add_argument('--output', choices=['json', 'text'], default='json')

    capabilities_parser = subparsers.add_parser('capabilities')
    capabilities_parser.add_argument('--output', choices=['json', 'text'], default='json')

    for command_name in ('plan', 'connect'):
        sub = subparsers.add_parser(command_name)
        sub.add_argument('--output', choices=['json', 'text'], default='json' if command_name == 'plan' else 'text')
        sub.add_argument('--key', dest='key_selector')
        sub.add_argument('--public-key-path')
        sub.add_argument('--domain', dest='domain_selector')
        sub.add_argument('--key-lifetime-days', type=int)
        sub.add_argument('--domain-lifetime-days', type=int)
        sub.add_argument('--note')
        sub.add_argument('--local-host', default=DEFAULT_LOCAL_HOST)
        sub.add_argument('--local-port', type=int, default=DEFAULT_LOCAL_PORT)
        sub.add_argument('--save-profile', action='store_true')
        if command_name == 'connect':
            sub.add_argument('--run', action='store_true')

    return parser


def log_progress(enabled: bool, message: str) -> None:
    if not enabled:
        return
    stamp = time.strftime('%H:%M:%S')
    print(f'[tunnellio-cli {stamp}] {message}', file=sys.stderr, flush=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    writer = OutputWriter(getattr(args, 'output', 'json'))

    if args.verbose:
        os.environ['TUNNELLIO_VERBOSE'] = '1'

    try:
        log_progress(args.verbose, 'Loading runtime config')
        config = load_runtime_config(
            token=args.token,
            base_url=args.base_url,
            state_dir=args.state_dir,
            insecure_tls=args.insecure_tls,
        )
        client = ApiClient(config)

        if args.command == 'meta':
            log_progress(args.verbose, 'Fetching API metadata')
            writer.write_meta(Meta.from_api(client.fetch_meta()))
            return int(ExitCode.SUCCESS)

        if args.command == 'capabilities':
            log_progress(args.verbose, 'Fetching capabilities')
            writer.write_capabilities(Capabilities.from_api(client.fetch_capabilities()))
            return int(ExitCode.SUCCESS)

        planner = Planner(client, config)
        options = PlanOptions(
            key_selector=args.key_selector,
            domain_selector=args.domain_selector,
            local_host=args.local_host,
            local_port=args.local_port,
            public_key_path=args.public_key_path,
            key_lifetime_days=args.key_lifetime_days,
            domain_lifetime_days=args.domain_lifetime_days,
            note=args.note,
            save_profile=args.save_profile,
            mode=args.command,
        )
        log_progress(args.verbose, f'Building {args.command} plan')
        result = planner.build_plan(options)

        if args.command == 'connect' and args.run:
            log_progress(args.verbose, 'Launching SSH bridge')
            execution = _run_launch_command(client, result, verbose=args.verbose)
            writer.write_exec_result(result, execution)
        else:
            writer.write_plan(result)
        return int(ExitCode.SUCCESS)
    except TunnellioError as exc:
        writer.write_error(exc)
        return int(exc.exit_code)
    except KeyboardInterrupt:
        writer.write_error(ValidationError('Interrupted by user.'))
        return int(ExitCode.GENERIC)


def _run_launch_command(
    client: ApiClient,
    result: PlanResult,
    *,
    verbose: bool = False,
) -> dict[str, int | str | bool | None]:
    if not result.connection_profile.ssh_args:
        raise ValidationError('Connection profile did not contain sshArgs for execution.')

    expanded_args = [os.path.expanduser(arg) if '~' in arg else arg for arg in result.connection_profile.ssh_args]
    log_progress(verbose, f'SSH args: {expanded_args}')
    process = subprocess.Popen(expanded_args)
    interrupted = False
    try:
        return_code = process.wait()
    except KeyboardInterrupt:
        interrupted = True
        process.send_signal(signal.SIGINT)
        return_code = process.wait()

    session_completed = False
    if result.session is not None and result.session.delete_on_disconnect:
        log_progress(verbose, f'Completing ephemeral session {result.session.id}')
        client.complete_session(result.session.id)
        session_completed = True

    execution: dict[str, int | str | bool | None] = {
        'pid': process.pid,
        'returnCode': return_code,
        'interrupted': interrupted,
        'sessionId': result.session.id if result.session else None,
        'sessionCompleted': session_completed,
    }
    return execution


if __name__ == '__main__':
    raise SystemExit(main())
