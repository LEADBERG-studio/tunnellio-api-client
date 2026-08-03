from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any


class ExitCode(IntEnum):
    SUCCESS = 0
    GENERIC = 1
    VALIDATION = 2
    AUTH = 3
    API = 4
    CONFLICT = 5
    OAUTH = 6
    SESSION = 7
    HEALTH = 8


@dataclass(slots=True)
class TunnellioError(Exception):
    code: str
    message: str
    details: dict[str, Any] | None = field(default=None)
    exit_code: ExitCode = field(default=ExitCode.GENERIC)

    def __str__(self) -> str:
        return self.message

    def to_payload(self) -> dict[str, Any]:
        error: dict[str, Any] = {
            'code': self.code,
            'message': self.message,
        }
        if self.details:
            error['details'] = self.details
        return {'ok': False, 'error': error}


class ValidationError(TunnellioError):
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(
            code='validation_error',
            message=message,
            details=details,
            exit_code=ExitCode.VALIDATION,
        )


class AuthError(TunnellioError):
    def __init__(self, message: str = 'Authentication failed.', details: dict[str, Any] | None = None):
        super().__init__(
            code='unauthorized',
            message=message,
            details=details,
            exit_code=ExitCode.AUTH,
        )


class PlanRequiredError(TunnellioError):
    """The credential is valid, but the account plan does not cover this endpoint.

    This is deliberately NOT an ``AuthError``. The token authenticated
    successfully; the server simply declined to serve one advisory endpoint.
    Callers that only need discovery data can degrade gracefully instead of
    aborting the whole launch, and integrators can tell a real credential
    failure apart from a plan limit.
    """

    def __init__(
        self,
        message: str = 'This endpoint is not included in the current plan.',
        details: dict[str, Any] | None = None,
        code: str = 'plan_required',
    ):
        super().__init__(
            code=code,
            message=message,
            details=details,
            exit_code=ExitCode.API,
        )


class ApiError(TunnellioError):
    def __init__(self, message: str = 'API request failed.', details: dict[str, Any] | None = None):
        super().__init__(
            code='api_error',
            message=message,
            details=details,
            exit_code=ExitCode.API,
        )


class ConflictError(TunnellioError):
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(
            code='conflict',
            message=message,
            details=details,
            exit_code=ExitCode.CONFLICT,
        )


class OAuthFlowError(TunnellioError):
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(
            code='oauth_flow_error',
            message=message,
            details=details,
            exit_code=ExitCode.OAUTH,
        )


class RequestedAuthModeMismatchError(TunnellioError):
    def __init__(self, requested: str, actual: str, details: dict[str, Any] | None = None):
        merged = {'requestedAuthMode': requested, 'actualAuthMode': actual}
        if details:
            merged.update(details)
        super().__init__(
            code='requested_auth_mode_mismatch',
            message='The server returned a different auth mode than requested.',
            details=merged,
            exit_code=ExitCode.VALIDATION,
        )


class SessionError(TunnellioError):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(
            code=code,
            message=message,
            details=details,
            exit_code=ExitCode.SESSION,
        )


class SessionResumeError(SessionError):
    def __init__(self, details: dict[str, Any] | None = None):
        super().__init__('session_resume_failed', 'Session resume failed.', details)


class SessionHeartbeatError(SessionError):
    def __init__(self, details: dict[str, Any] | None = None):
        super().__init__('session_heartbeat_failed', 'Session heartbeat failed.', details)


class HealthProbeError(TunnellioError):
    def __init__(self, message: str = 'Health probe failed.', details: dict[str, Any] | None = None):
        super().__init__(
            code='health_probe_failed',
            message=message,
            details=details,
            exit_code=ExitCode.HEALTH,
        )


class InteractiveInputRequiredError(TunnellioError):
    def __init__(self, missing: list[str], choices: dict[str, list[str]] | None = None):
        super().__init__(
            code='interactive_input_required',
            message='More input is required.',
            details={
                'missing': missing,
                'choices': choices or {},
            },
            exit_code=ExitCode.VALIDATION,
        )


PLAN_REQUIRED_CODES = frozenset(
    {
        'plan_required',
        'plan_upgrade_required',
        'feature_not_in_plan',
        'subscription_required',
    }
)


def is_plan_limit(*, code: str, message: str, status: int | None) -> bool:
    """Tell a plan/tier refusal apart from a rejected credential.

    Both arrive as HTTP 403, but they mean opposite things: one says the token
    is wrong, the other says the token is fine and the feature is not included.
    """
    if code in PLAN_REQUIRED_CODES:
        return True
    return status == 403 and 'plan' in message.lower()


def error_from_api(
    *,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    status: int | None = None,
) -> TunnellioError:
    if is_plan_limit(code=code, message=message, status=status):
        return PlanRequiredError(message, details, code=code or 'plan_required')
    if code in {'unauthorized', 'forbidden'} or status in {401, 403}:
        return AuthError(message, details)
    if code in {
        'validation_error',
        'interactive_input_required',
        'key_not_found',
        'domain_not_found',
        'requested_auth_mode_mismatch',
    }:
        if code == 'requested_auth_mode_mismatch' and details:
            return RequestedAuthModeMismatchError(
                str(details.get('requestedAuthMode')),
                str(details.get('actualAuthMode')),
                details,
            )
        return ValidationError(message, details)
    if code in {'conflict', 'domain_not_available'} or status == 409:
        return ConflictError(message, details)
    if code.startswith('oauth_'):
        return OAuthFlowError(message, details)
    if code.startswith('session_'):
        return SessionError(code, message, details)
    if code.startswith('health_'):
        return HealthProbeError(message, details)
    return TunnellioError(code=code, message=message, details=details, exit_code=ExitCode.API)
