from odoo import http
from odoo.http import request

from ...services import content_service as content
from ...services import markup as markup_lib
from ...services import qa
from ...services.errors import bad_request
from .common import PREFIX, endpoint, if_match, json_body, json_response, query

READ = {"type": "http", "auth": "bearer", "csrf": False, "readonly": True}
WRITE = {"type": "http", "auth": "bearer", "csrf": False}


class LearningJapaneseApiV1(http.Controller):
    """REST API v1 of learning_japanese; the contract is static/api/openapi.yaml."""

    # ── meta, books, lessons ───────────────────────────────────────────────────

    @http.route(f"{PREFIX}/meta", methods=["GET"], **READ)
    @endpoint()
    def meta(self):
        return json_response(content.meta(request.env))

    @http.route(f"{PREFIX}/books", methods=["GET"], **READ)
    @endpoint()
    def list_books(self):
        return json_response(content.list_books(request.env, query()))

    @http.route(f"{PREFIX}/books/<int:book_id>", methods=["GET"], **READ)
    @endpoint()
    def get_book(self, book_id):
        book = content.get_book(request.env, book_id)
        return json_response(book, version=book["version"])

    @http.route(f"{PREFIX}/lessons", methods=["GET"], **READ)
    @endpoint()
    def list_lessons(self):
        return json_response(content.list_lessons(request.env, query()))

    # ── comprehensives ─────────────────────────────────────────────────────────

    @http.route(f"{PREFIX}/comprehensives", methods=["GET"], **READ)
    @endpoint()
    def list_comprehensives(self):
        return json_response(content.list_comprehensives(request.env, query()))

    @http.route(f"{PREFIX}/comprehensives", methods=["POST"], **WRITE)
    @endpoint(write=True)
    def create_comprehensive(self):
        item = content.create_comprehensive(request.env, json_body())
        location = f"{PREFIX}/comprehensives/{item['id']}"
        return json_response(item, status=201, version=item["version"], headers=[("Location", location)])

    @http.route(f"{PREFIX}/comprehensives/<int:item_id>", methods=["GET"], **READ)
    @endpoint()
    def get_comprehensive(self, item_id):
        item = content.get_comprehensive(request.env, item_id)
        return json_response(item, version=item["version"])

    @http.route(f"{PREFIX}/comprehensives/<int:item_id>", methods=["PATCH"], **WRITE)
    @endpoint(write=True)
    def update_comprehensive(self, item_id):
        item = content.update_comprehensive(request.env, item_id, json_body(), if_match())
        return json_response(item, version=item["version"])

    @http.route(f"{PREFIX}/comprehensives/<int:item_id>", methods=["DELETE"], **WRITE)
    @endpoint(write=True)
    def delete_comprehensive(self, item_id):
        content.delete_comprehensive(request.env, item_id, if_match())
        return request.make_response(b"", status=204)

    @http.route(f"{PREFIX}/comprehensives/<int:item_id>/audio", methods=["GET"], **READ)
    @endpoint()
    def get_audio(self, item_id):
        return content.audio_stream(request.env, item_id).get_response()

    @http.route(f"{PREFIX}/comprehensives/<int:item_id>/audio", methods=["PUT"], **WRITE)
    @endpoint(write=True)
    def put_audio(self, item_id):
        httprequest = request.httprequest
        if (httprequest.content_length or 0) > content.AUDIO_MAX_BYTES:
            raise content.ApiError(413, "too-large", f"Audio files are limited to {content.AUDIO_MAX_BYTES} bytes.")
        item = content.put_audio(
            request.env, item_id, httprequest.get_data(), httprequest.mimetype,
            httprequest.headers.get("X-Filename"), if_match(),
        )
        return json_response(item, version=item["version"])

    @http.route(f"{PREFIX}/comprehensives/<int:item_id>/grammar-overrides", methods=["GET"], **READ)
    @endpoint()
    def get_grammar_overrides(self, item_id):
        return json_response(content.get_overrides(request.env, item_id))

    @http.route(f"{PREFIX}/comprehensives/<int:item_id>/grammar-overrides", methods=["PUT"], **WRITE)
    @endpoint(write=True)
    def put_grammar_overrides(self, item_id):
        result = content.put_overrides(request.env, item_id, json_body(), if_match())
        return json_response(result, version=result["version"])

    # ── vocabularies ───────────────────────────────────────────────────────────

    @http.route(f"{PREFIX}/vocabularies", methods=["GET"], **READ)
    @endpoint()
    def list_vocabularies(self):
        return json_response(content.list_vocabularies(request.env, query()))

    @http.route(f"{PREFIX}/vocabularies", methods=["POST"], **WRITE)
    @endpoint(write=True)
    def create_vocabulary(self):
        record = content.create_vocabulary(request.env, json_body())
        location = f"{PREFIX}/vocabularies/{record['id']}"
        return json_response(record, status=201, version=record["version"], headers=[("Location", location)])

    @http.route(f"{PREFIX}/vocabularies/bulk", methods=["POST"], **WRITE)
    @endpoint(write=True)
    def bulk_vocabularies(self):
        return json_response(content.bulk_vocabularies(request.env, json_body()))

    @http.route(f"{PREFIX}/vocabularies/<int:vocabulary_id>", methods=["GET"], **READ)
    @endpoint()
    def get_vocabulary(self, vocabulary_id):
        record = content.get_vocabulary(request.env, vocabulary_id)
        return json_response(record, version=record["version"])

    @http.route(f"{PREFIX}/vocabularies/<int:vocabulary_id>", methods=["PATCH"], **WRITE)
    @endpoint(write=True)
    def update_vocabulary(self, vocabulary_id):
        record = content.update_vocabulary(request.env, vocabulary_id, json_body(), if_match())
        return json_response(record, version=record["version"])

    @http.route(f"{PREFIX}/vocabularies/<int:vocabulary_id>", methods=["DELETE"], **WRITE)
    @endpoint(write=True)
    def delete_vocabulary(self, vocabulary_id):
        content.delete_vocabulary(request.env, vocabulary_id, if_match())
        return request.make_response(b"", status=204)

    # ── catalogs, markup, QA ───────────────────────────────────────────────────

    @http.route([f"{PREFIX}/tags", f"{PREFIX}/context-tags", f"{PREFIX}/parts-of-speech", f"{PREFIX}/hanviet"],
                methods=["GET"], **READ)
    @endpoint()
    def list_catalog(self):
        name = request.httprequest.path.rstrip("/").rsplit("/", 1)[-1]
        return json_response(content.list_catalog(request.env, name, query()))

    @http.route(f"{PREFIX}/markup/preview", methods=["POST"], **READ)
    @endpoint()
    def preview_markup(self):
        body = json_body()
        source = body.get("markup") if isinstance(body, dict) else None
        if not isinstance(source, str):
            raise bad_request('The body must be {"markup": "..."}.')
        if len(source) > content.MARKUP_MAX:
            raise content.invalid([{"field": "markup", "message": f"At most {content.MARKUP_MAX} characters."}])
        hover, ruby = markup_lib.render(source)
        return json_response({"html_hover": hover, "html_ruby": ruby, **markup_lib.analyze(source)})

    @http.route(f"{PREFIX}/qa/issues", methods=["GET"], **READ)
    @endpoint()
    def list_issues(self):
        return json_response(qa.list_issues(request.env, query()))
