from odoo import http
from odoo.http import request

from ...services import sync
from .common import PREFIX, endpoint, json_response, query

READ = {"type": "http", "auth": "bearer", "csrf": False, "readonly": True}


class LearningJapaneseSyncV1(http.Controller):
    """Change feed and snapshots for NihonGo (read-only key `nihongo-sync`)."""

    @http.route(f"{PREFIX}/changes", methods=["GET"], **READ)
    @endpoint()
    def changes(self):
        return json_response(sync.changes(request.env, query()))

    @http.route(f"{PREFIX}/changes/head", methods=["GET"], **READ)
    @endpoint()
    def changes_head(self):
        return json_response(sync.head(request.env))

    @http.route(f"{PREFIX}/snapshot/<string:entity>", methods=["GET"], **READ)
    @endpoint()
    def snapshot(self, entity):
        return json_response(sync.snapshot(request.env, entity, query()))
