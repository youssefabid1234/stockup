"""Business errors. Raise them from services; main.py turns them into
{"error": {"code": ..., "message": ...}} with the right HTTP status."""


class HttpError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def not_found(what: str, id: str) -> HttpError:
    return HttpError(404, "not_found", f"{what} introuvable : {id}")


def bad_request(code: str, message: str) -> HttpError:
    return HttpError(400, code, message)


def conflict(code: str, message: str) -> HttpError:
    return HttpError(409, code, message)


def validation_error(message: str) -> HttpError:
    """Same code as an invalid request body (400 validation_error)."""
    return HttpError(400, "validation_error", message)
