from odoo import api, models


class ChangeTrackedMixin(models.AbstractModel):
    """Write create/update/delete events of the inheriting model to the change feed.

    Each model sets `_lj_entity`, the entity name consumers see in the feed.
    Models whose changes alter other records' API output (lesson membership,
    publish flag, tag names) log those records too, in their own overrides.
    """

    _name = "learning_japanese.change.tracked.mixin"
    _description = "Change Feed Tracking"

    _lj_entity = None

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._lj_log("create")
        return records

    def write(self, vals):
        result = super().write(vals)
        self._lj_log("update")
        return result

    def unlink(self):
        self._lj_log("delete")
        return super().unlink()

    def _lj_log(self, op, entity=None, ids=None):
        self.env["learning_japanese.change_log"]._record(
            entity or self._lj_entity, self.ids if ids is None else ids, op,
        )

    def _lj_lesson_members(self, lesson_ids):
        """(comprehensive ids, vocabulary ids) linked to the given lessons, from the database."""
        if not lesson_ids:
            return set(), set()
        self.env.flush_all()
        cr = self.env.cr
        cr.execute(
            "SELECT comprehensive_id FROM comprehensive_lesson_rel WHERE lesson_id = ANY(%s)",
            [list(lesson_ids)],
        )
        items = {row[0] for row in cr.fetchall()}
        cr.execute(
            "SELECT vocabulary_id FROM lesson_vocabulary_rel WHERE lesson_id = ANY(%s)",
            [list(lesson_ids)],
        )
        vocabularies = {row[0] for row in cr.fetchall()}
        return items, vocabularies
