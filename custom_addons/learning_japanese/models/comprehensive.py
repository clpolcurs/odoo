import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class Comprehensive(models.Model):
    _name = "learning_japanese.comprehensive"
    _description = "Comprehensive skills"
    _rec_name = "title"
    _order = "id asc"
    _inherit = ["learning_japanese.furigana.mixin"]

    lesson_id = fields.Many2one(
        comodel_name="learning_japanese.lesson",
        string="Lesson",
        auto_join=True,
    )
    book_name = fields.Char(
        string="Book", related="lesson_id.book_id.name", store=True
    )
    level = fields.Selection(
        selection=[
            ("N5", "N5"),
            ("N4", "N4"),
            ("N3", "N3"),
            ("N2", "N2"),
            ("N1", "N1"),
        ],
        string="Level",
    )
    title = fields.Text(string="Tiêu đề", copy=False)
    audio_file = fields.Binary(string="Audio", copy=False)
    description = fields.Text(string="Diễn giải", copy=False)
    deadline = fields.Date(string="Hạn nộp", copy=False)
    category = fields.Selection(
        selection=[
            ("example", "Example"),
            ("listening", "Listening"),
            ("reading", "Reading"),
            ("writing", "Writing"),
            ("speaking", "Speaking"),
            ("grammar", "Grammar"),
        ],
        string="Comprehensive skills",
    )
