from rest_framework import exceptions as drf_exceptions
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


class DomainError(Exception):
    """Base class for business-rule errors raised from service functions."""

    code = "domain_error"
    message = "A domain error occurred."
    http_status = 400

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        details: dict | None = None,
        http_status: int | None = None,
    ):
        self.message = message or self.message
        self.code = code or self.code
        self.details = details or {}
        self.http_status = http_status or self.http_status
        super().__init__(self.message)


_DRF_EXCEPTION_CODES = {
    drf_exceptions.ValidationError: "validation_error",
    drf_exceptions.AuthenticationFailed: "authentication_failed",
    drf_exceptions.NotAuthenticated: "not_authenticated",
    drf_exceptions.PermissionDenied: "permission_denied",
    drf_exceptions.NotFound: "not_found",
    drf_exceptions.MethodNotAllowed: "method_not_allowed",
    drf_exceptions.Throttled: "throttled",
    drf_exceptions.ParseError: "parse_error",
}


def _code_for_drf_exception(exc: Exception) -> str:
    for exc_class, code in _DRF_EXCEPTION_CODES.items():
        if isinstance(exc, exc_class):
            return code
    return getattr(exc, "default_code", "error")


def _flatten_message(data) -> str:
    if isinstance(data, dict):
        for value in data.values():
            return _flatten_message(value)
        return "Invalid request."
    if isinstance(data, list):
        return _flatten_message(data[0]) if data else "Invalid request."
    return str(data)


def custom_exception_handler(exc, context):
    if isinstance(exc, DomainError):
        return Response(
            {
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
            status=exc.http_status,
        )

    response = drf_exception_handler(exc, context)
    if response is not None:
        details = response.data if isinstance(response.data, dict | list) else {}
        response.data = {
            "error": {
                "code": _code_for_drf_exception(exc),
                "message": _flatten_message(response.data),
                "details": details,
            }
        }
        return response

    return Response(
        {
            "error": {
                "code": "internal_error",
                "message": "An unexpected error occurred.",
                "details": {},
            }
        },
        status=500,
    )
