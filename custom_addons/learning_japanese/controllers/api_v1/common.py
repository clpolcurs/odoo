import functools
import json
import logging

import psycopg2

from odoo.exceptions import AccessError, MissingError, UserError, ValidationError
from odoo.http import request

from ...services.content_service import READ_GROUP, WRITE_GROUP
from ...services.errors import ApiError, bad_request

_logger = logging.getLogger(__name__)

PREFIX = "/api/lj/v1"
JSON_BODY_MAX = 2 * 1024 * 1024


def json_response(data, status=200, version=None, headers=None):
    body = json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=str).encode()
    all_headers = [("Content-Type", "application/json; charset=utf-8"), ("Cache-Control", "no-store")]
    if version:
        all_headers.append(("ETag", f'"{version}"'))
    return request.make_response(body, all_headers + list(headers or []), status=status)


def problem_response(error):
    body = json.dumps(error.to_problem(), ensure_ascii=False, default=str).encode()
    return request.make_response(
        body, [("Content-Type", "application/problem+json"), ("Cache-Control", "no-store")], status=error.status,
    )


def json_body():
    httprequest = request.httprequest
    content_type = (httprequest.mimetype or "").lower()
    if content_type != "application/json":
        raise ApiError(415, "unsupported-media-type", "Send the body as application/json.")
    if (httprequest.content_length or 0) > JSON_BODY_MAX:
        raise ApiError(413, "too-large", f"JSON bodies are limited to {JSON_BODY_MAX} bytes.")
    try:
        return json.loads(httprequest.get_data(as_text=True) or "null")
    except ValueError:
        raise bad_request("The body is not valid JSON.") from None


def query():
    return request.httprequest.args


def if_match():
    return request.httprequest.headers.get("If-Match")


def endpoint(write=False):
    """Check the API groups, run the handler in a savepoint and map every error to problem+json.

    The savepoint makes a failed write leave nothing behind even though the
    response is a normal one (Odoo commits the request transaction).
    """

    def decorator(handler):
        @functools.wraps(handler)
        def wrapper(self, *args, **kwargs):
            try:
                user = request.env.user
                if not user.has_group(READ_GROUP):
                    raise ApiError(403, "forbidden", "The API key's user is not in Learning Japanese Read Only.")
                if write and not user.has_group(WRITE_GROUP):
                    raise ApiError(403, "forbidden", "Writing needs the group Learning Japanese Admin.")
                with request.env.cr.savepoint(flush=write):
                    return handler(self, *args, **kwargs)
            except ApiError as error:
                return problem_response(error)
            except AccessError as error:
                return problem_response(ApiError(403, "forbidden", str(error)))
            except MissingError as error:
                return problem_response(ApiError(404, "not-found", str(error)))
            except (ValidationError, UserError) as error:
                return problem_response(ApiError(422, "validation-error", str(error)))
            except psycopg2.IntegrityError as error:
                _logger.info("API v1 integrity error: %s", error)
                return problem_response(ApiError(409, "conflict", "The change breaks a uniqueness or integrity rule."))
            except Exception:
                _logger.exception("API v1 error on %s %s", request.httprequest.method, request.httprequest.path)
                return problem_response(ApiError(500, "internal-error", "Unexpected server error; see the Odoo log."))

        return wrapper

    return decorator
