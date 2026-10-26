import logging

from odoo import fields, models, api

_logger = logging.getLogger(__name__)


class ComprehensiveTag(models.Model):
    _name = "learning_japanese.comprehensive_tag"
    _description = "Comprehensive Tag"
    _order = "name"
    _inherit = ["learning_japanese.change.tracked.mixin"]
    _lj_entity = "tag"

    name = fields.Char(string="Comprehensive Topic", required=True)
    color = fields.Integer(string="Color Index")

    _sql_constraints = models.Constraint(
        "UNIQUE(name)",
        "Comprehensive Topic phải là duy nhất!"
    )

    def write(self, vals):
        result = super().write(vals)
        if "name" in vals:
            # Items expose their tags by name.
            self._lj_log_items()
        return result

    def unlink(self):
        self._lj_log_items()
        return super().unlink()

    def _lj_log_items(self):
        items = self.env["learning_japanese.comprehensive"].search([("category_ids", "in", self.ids)])
        items._lj_log("update")


class Comprehensive(models.Model):
    _name = "learning_japanese.comprehensive"
    _description = "Comprehensive skills"
    _rec_name = "title"
    _order = "id asc"
    _inherit = ["learning_japanese.furigana.mixin", "learning_japanese.change.tracked.mixin"]
    _lj_entity = "comprehensive"

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
    category_ids = fields.Many2many(
        comodel_name="learning_japanese.comprehensive_tag",
        relation="comprehensive_tag_rel",
        column1="comprehensive_id",
        column2="tag_id",
        string="Comprehensive Topics",
    )
    is_grammar = fields.Boolean(
        string="Is Grammar",
        compute="_compute_category_flags",
        store=True,
    )
    is_writing_or_speaking = fields.Boolean(
        string="Is Writing/Speaking",
        compute="_compute_category_flags",
        store=True,
    )
    grammar_patterns = fields.Text(
        string="Mẫu khớp ngữ pháp",
        copy=False,
        help="Mỗi dòng một mẫu ở dạng từ điển, ví dụ ようとする hoặc とする. "
             "NihonGo dùng các mẫu này để tìm điểm ngữ pháp trong bài đọc.",
    )
    grammar_override_ids = fields.One2many(
        comodel_name="learning_japanese.grammar_override",
        inverse_name="comprehensive_id",
        string="Ghi đè ngữ pháp",
    )
    nihongo_published = fields.Boolean(
        string="Có trên NihonGo",
        compute="_compute_nihongo_published",
        search="_search_nihongo_published",
        help="Bài thuộc ít nhất một giáo trình đã bật cờ Xuất bản NihonGo.",
    )

    @api.depends("category_ids", "category_ids.name")
    def _compute_category_flags(self):
        for record in self:
            names = [tag.name.lower() for tag in record.category_ids if tag.name]
            # Tự động phát hiện nếu có gắn thẻ ngữ pháp
            record.is_grammar = any("grammar" in n or "ngữ pháp" in n for n in names)
            # Tự động phát hiện nếu có gắn thẻ viết hoặc nói
            record.is_writing_or_speaking = any(
                "writing" in n or "speaking" in n or "viết" in n or "nói" in n for n in names
            )

    @api.depends("lesson_ids.book_id")
    def _compute_book_ids(self):
        for record in self:
            record.book_ids = record.lesson_ids.mapped("book_id")

    @api.depends("book_ids.nihongo_published")
    def _compute_nihongo_published(self):
        for record in self:
            record.nihongo_published = any(record.book_ids.mapped("nihongo_published"))

    def _search_nihongo_published(self, operator, value):
        if operator not in ("=", "!=") or not isinstance(value, bool):
            return NotImplemented
        published = (operator == "=") == value
        domain = [("book_ids.nihongo_published", "=", True)]
        return domain if published else ["!", *domain]

    def unlink(self):
        # Overrides pointing at a deleted grammar point vanish with it (ON DELETE CASCADE),
        # which changes the output of the items that held them.
        overrides = self.env["learning_japanese.grammar_override"].search([("grammar_id", "in", self.ids)])
        (overrides.comprehensive_id - self)._lj_log("update")
        return super().unlink()

    @api.model
    def default_get(self, fields_list):
        """
        Tự động tìm hoặc tạo thẻ mặc định khi bấm 'Add a line' từ các tab của Lesson.
        """
        res = super().default_get(fields_list)
        default_tag_name = self.env.context.get("default_tag_name")
        if default_tag_name and "category_ids" in fields_list:
            tag = self.env["learning_japanese.comprehensive_tag"].search(
                [("name", "ilike", default_tag_name)], limit=1
            )
            if not tag:
                tag = self.env["learning_japanese.comprehensive_tag"].create(
                    {"name": default_tag_name}
                )
            res["category_ids"] = [(6, 0, [tag.id])]
        return res
