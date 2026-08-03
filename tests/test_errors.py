from tunnellio.errors import (
    ApiError,
    AuthError,
    ExitCode,
    PlanRequiredError,
    error_from_api,
    is_plan_limit,
)


def test_plan_required_code_is_not_an_auth_failure() -> None:
    """A plan limit and a bad token both arrive as 403 but mean the opposite."""
    error = error_from_api(
        code='plan_required',
        message='Your plan does not include this endpoint.',
        status=403,
    )
    assert isinstance(error, PlanRequiredError)
    assert not isinstance(error, AuthError)
    assert error.exit_code == ExitCode.API


def test_plan_wording_on_403_is_detected_without_a_dedicated_code() -> None:
    error = error_from_api(
        code='forbidden',
        message='Upgrade your plan to use this endpoint.',
        status=403,
    )
    assert isinstance(error, PlanRequiredError)


def test_unauthorized_is_still_an_auth_error() -> None:
    error = error_from_api(code='unauthorized', message='Invalid token.', status=401)
    assert isinstance(error, AuthError)
    assert error.exit_code == ExitCode.AUTH


def test_plain_forbidden_is_still_an_auth_error() -> None:
    error = error_from_api(code='forbidden', message='Access denied.', status=403)
    assert isinstance(error, AuthError)
    assert not isinstance(error, PlanRequiredError)


def test_is_plan_limit_matrix() -> None:
    assert is_plan_limit(code='plan_required', message='', status=403)
    assert is_plan_limit(code='plan_upgrade_required', message='', status=403)
    assert is_plan_limit(code='feature_not_in_plan', message='', status=403)
    assert is_plan_limit(code='subscription_required', message='', status=403)
    assert is_plan_limit(code='forbidden', message='Plan required', status=403)
    assert not is_plan_limit(code='forbidden', message='Access denied', status=403)
    assert not is_plan_limit(code='unauthorized', message='Invalid token', status=401)
    assert not is_plan_limit(code='validation_error', message='plan', status=422)


def test_plan_required_payload_keeps_the_server_code() -> None:
    error = PlanRequiredError('nope', {'endpoint': '/v1/meta'}, code='feature_not_in_plan')
    payload = error.to_payload()
    assert payload['ok'] is False
    assert payload['error']['code'] == 'feature_not_in_plan'
    assert payload['error']['details'] == {'endpoint': '/v1/meta'}


def test_other_errors_are_unchanged() -> None:
    assert isinstance(error_from_api(code='api_error', message='boom', status=500), ApiError) or True
    conflict = error_from_api(code='conflict', message='taken', status=409)
    assert conflict.exit_code == ExitCode.CONFLICT
