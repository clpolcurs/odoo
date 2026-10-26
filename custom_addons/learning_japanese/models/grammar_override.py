from odoo import api, fields, models


class GrammarOverride(models.Model):
    """A grammar point pinned to, or hidden from, one reading/listening item.

    Set while reviewing an item with Claude through MCP; NihonGo applies it
    on top of the automatic grammar matching.
    """

    _name = "learning_japanese.grammar_override"
    _description = "Grammar Override"
    _order = "comprehensive_id, grammar_id"

    comprehensive_id = fields.Many2one(
        "learning_japanese.comprehensive", string="Item", required=True, ondelete="cascade", index=True,
    )
    grammar_id = fields.Many2one(
        "learning_japanese.comprehensive",
        string="Grammar point",
        required=True,
        ondelete="cascade",
        index=True,
        domain=[("is_grammar", "=", True)],
    )
    action = fields.Selection(selection=[("pin", "Pin"), ("hide", "Hide")], required=True, default="pin")
    note = fields.Char()

    _unique_grammar_per_item = models.Constraint(
        "UNIQUE(comprehensive_id, grammar_id)",
        "Mỗi điểm ngữ pháp chỉ ghi đè một lần cho một bài.",
    )

    # The overrides are part of the item's API output, so changes are logged on the item.
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._log_items()
        return records

    def write(self, vals):
        before = self.comprehensive_id
        result = super().write(vals)
        (before | self.comprehensive_id)._lj_log("update")
        return result

    def unlink(self):
        self._log_items()
        return super().unlink()

    def _log_items(self):
        self.comprehensive_id._lj_log("update")
