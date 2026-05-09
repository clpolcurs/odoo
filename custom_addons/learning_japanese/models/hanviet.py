import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class HanViet(models.Model):
    _name = "learning_japanese.hanviet"
    _description = "Han Viet"
    _rec_name = "kanji"
    _order = "id asc"

    kanji = fields.Char(string="Kanji")
    han_viet = fields.Char(string="Hán Việt")
