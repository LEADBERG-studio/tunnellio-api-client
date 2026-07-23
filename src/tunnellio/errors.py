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


def error_from_api(
    *,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    status: int | None = None,
) -> TunnellioError:
    if code in {'unauthorized', 'forbidden'} or status in {401, 403}:
        return AuthError(message, details)
    if code in {
        'validation_error',
        'interactive_input_required',
        'key_not_found',
        'domain_not_found',
    }:
        return ValidationError(message, details)
    if code in {'conflict', 'domain_not_available'} or status == 409:
        return ConflictError(message, details)
    return TunnellioError(code=code, message=message, details=details, exit_code=ExitCode.API)
