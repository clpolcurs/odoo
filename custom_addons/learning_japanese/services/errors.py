"""Errors raised by the services and turned into application/problem+json by the controllers."""

TITLES = {
    "bad-request": "Bad request",
    "forbidden": "Forbidden",
    "not-found": "Not found",
    "conflict": "Conflict",
    "cursor-expired": "Cursor expired",
    "version-mismatch": "Version mismatch",
    "version-required": "If-Match required",
    "too-large": "Payload too large",
    "unsupported-media-type": "Unsupported media type",
    "validation-error": "Validation error",
    "internal-error": "Internal error",
}


class ApiError(Exception):
    def __init__(self, status, code, detail=None, errors=None, **extra):
        super().__init__(detail or TITLES.get(code, code))
        self.status = status
        self.code = code
        self.detail = detail
        self.errors = errors
        self.extra = extra

    def to_problem(self):
        problem = {
            "type": f"urn:lj:problem:{self.code}",
            "title": TITLES.get(self.code, self.code),
            "status": self.status,
            "code": self.code,
        }
        if self.detail:
            problem["detail"] = self.detail
        if self.errors:
            problem["errors"] = self.errors
        problem.update(self.extra)
        return problem


def bad_request(detail):
    return ApiError(400, "bad-request", detail)


def not_found(entity, record_id):
    return ApiError(404, "not-found", f"{entity} {record_id} does not exist.")


def invalid(errors, detail="Some fields are invalid."):
    """errors: [{"field": ..., "message": ...}] (with "index" in bulk requests)."""
    return ApiError(422, "validation-error", detail, errors=errors)
