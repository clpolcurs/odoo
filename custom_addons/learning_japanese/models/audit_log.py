import json

from odoo import api, fields, models


class AuditLog(models.Model):
    """Before/after record of every write made through API v1."""

    _name = "learning_japanese.audit_log"
    _description = "API Audit Log"
    _order = "id desc"
    _rec_name = "entity"

    user_id = fields.Many2one("res.users", string="User", readonly=True, index=True)
    entity = fields.Char(readonly=True, index=True)
    res_id = fields.Integer(string="Record ID", readonly=True, index=True)
    op = fields.Selection(
        selection=[
            ("create", "Create"),
            ("update", "Update"),
            ("delete", "Delete"),
            ("audio", "Audio"),
            ("grammar_overrides", "Grammar overrides"),
        ],
        readonly=True,
    )
    before = fields.Text(readonly=True)
    after = fields.Text(readonly=True)

    @api.model
    def _log(self, entity, res_id, op, before=None, after=None):
        """Store only the keys that changed; a create keeps `after`, a delete keeps `before`."""
        before, after = before or {}, after or {}
        if before and after:
            keys = sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k))
            before = {k: before.get(k) for k in keys}
            after = {k: after.get(k) for k in keys}
        self.sudo().create({
            "user_id": self.env.uid,
            "entity": entity,
            "res_id": res_id,
            "op": op,
            "before": json.dumps(before, ensure_ascii=False, default=str) if before else False,
            "after": json.dumps(after, ensure_ascii=False, default=str) if after else False,
        })
