import logging

from odoo import fields, models, api

_logger = logging.getLogger(__name__)


class Comprehensive(models.Model):
    _name = "learning_japanese.comprehensive"
    _description = "Comprehensive skills"
    _rec_name = "title"
    _order = "id asc"
    _inherit = ["learning_japanese.furigana.mixin"]

    lesson_ids = fields.Many2many(
        comodel_name="learning_japanese.lesson",
        relation="comprehensive_lesson_rel",
        column1="comprehensive_id",
        column2="lesson_id",
        string="Lessons",
    )
    book_ids = fields.Many2many(
        comodel_name="learning_japanese.book",
        string="Books",
        compute="_compute_book_ids",
        store=True,
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
    title = fields.Text(string="Title", copy=False)
    audio_file = fields.Binary(string="Audio", copy=False)
    description = fields.Text(string="Description", copy=False)
    deadline = fields.Date(string="Deadline", copy=False)
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

    @api.depends("lesson_ids.book_id")
    def _compute_book_ids(self):
        for record in self:
            record.book_ids = record.lesson_ids.mapped("book_id")