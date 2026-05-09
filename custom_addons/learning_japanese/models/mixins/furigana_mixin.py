import logging
from odoo import api, fields, models
from ...utils.furigana_helper import process_furigana

_logger = logging.getLogger(__name__)


class FuriganaMixin(models.AbstractModel):
    _name = "learning_japanese.furigana.mixin"
    _description = "Furigana Processing Mixin"

    # ── Fields ────────────────────────────────────────────────────────────
    content_only_kanji = fields.Html(string="Nội dung",        copy=False)
    content            = fields.Html(string="Chú thích kanji", copy=False)
    backup_text        = fields.Html(string="Lưu trữ",         copy=False)
    is_finalized       = fields.Boolean(string="Đã hoàn thành", default=False, copy=False)

    # ── Internal helper ───────────────────────────────────────────────────
    def _apply_furigana(self, vals: dict, raw_html: str) -> dict:
        """
        Run furigana processing on raw_html and populate vals in-place.
        Always call this instead of process_furigana directly.
        """
        furigana_hover, furigana = process_furigana(raw_html)
        vals.update({
            "backup_text":        raw_html,
            "content_only_kanji": furigana_hover,
            "content":            furigana,
            "is_finalized":       True,
        })
        return vals

    def _should_process(self, raw_html: str) -> bool:
        """
        Return True only if the incoming HTML differs from the stored backup.
        Avoids reprocessing on unrelated writes.
        """
        if not raw_html:
            return False
        if self.is_finalized:
            return False
        current_backup = self.backup_text or ""
        return raw_html.strip() != current_backup.strip()

    # ── ORM overrides ─────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list: list[dict]) -> models.Model:
        for vals in vals_list:
            raw_html = vals.get("content_only_kanji")
            if raw_html:
                self._apply_furigana(vals, raw_html)
        return super().create(vals_list)

    def write(self, vals: dict) -> bool:
        raw_html = vals.get("content_only_kanji")
        # On a recordset write, check each record individually
        if raw_html:
            for record in self:
                if record._should_process(raw_html):
                    record._apply_furigana(vals, raw_html)
                    break  # vals is shared — process once, applies to all
        return super().write(vals)

    # ── Actions ───────────────────────────────────────────────────────────
    def action_reverse(self) -> bool:
        for record in self:
            if record.backup_text:
                models.Model.write(record, {
                    "content_only_kanji": record.backup_text,
                    "content":            False,
                    "is_finalized":       False,
                })
        return True