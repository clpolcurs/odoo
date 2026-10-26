from odoo import http
from odoo.http import request

from ...services import sync
from .common import PREFIX, endpoint, json_response, query

# Always the primary database: the feed cursor relies on transaction ids,
# which a read replica configured for readonly routes would not share.
SYNC_ROUTE = {"type": "http", "auth": "bearer", "csrf": False, "readonly": False}


class LearningJapaneseSyncV1(http.Controller):
    """Change feed and snapshots for NihonGo (read-only key `nihongo-sync`)."""

    @http.route(f"{PREFIX}/changes", methods=["GET"], **SYNC_ROUTE)
    @endpoint()
    def changes(self):
        return json_response(sync.changes(request.env, query()))

    @http.route(f"{PREFIX}/changes/head", methods=["GET"], **SYNC_ROUTE)
    @endpoint()
    def changes_head(self):
        return json_response(sync.head(request.env))

    @http.route(f"{PREFIX}/snapshot/<string:entity>", methods=["GET"], **SYNC_ROUTE)
    @endpoint()
    def snapshot(self, entity):
        return json_response(sync.snapshot(request.env, entity, query()))
