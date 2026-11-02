from rest_framework.exceptions import ParseError, ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


class IntegrationError(Exception):
    def __init__(self, code, message, status=503, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.details = details


def exception_handler(exc, context):
    if isinstance(exc, IntegrationError):
        body = {"code": exc.code, "message": exc.message}
        if exc.details is not None:
            body["details"] = exc.details
        return Response(body, status=exc.status)
    response = drf_exception_handler(exc, context)
    if response is None:
        return None
    if isinstance(exc, (ParseError, ValidationError)):
        response.data = {
            "code": "INVALID_REQUEST",
            "message": "Проверьте формат и значения запроса.",
            "details": response.data,
        }
    else:
        response.data = {
            "code": str(getattr(exc, "default_code", "API_ERROR")).upper(),
            "message": str(getattr(exc, "detail", "Ошибка запроса.")),
        }
    return response
