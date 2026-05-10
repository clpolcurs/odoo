import re
import html
import logging
import openai

from typing import Any
from pykakasi import kakasi
from google import genai

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

NHOM_1 = [
    "い",
    "き",
    "ぎ",
    "ち",
    "ぢ",
    "じ",
    "に",
    "ひ",
    "び",
    "ぴ",
    "み",
    "り",
]

NHOM_2 = [
    "え",
    "け",
    "げ",
    "せ",
    "ぜ",
    "て",
    "で",
    "ね",
    "へ",
    "べ",
    "ぺ",
    "め",
    "れ",
]
NHOM_3 = ["します", "きます"]

THE_TU_DIEN_MAPPING = {
    "い": "う",
    "き": "く",
    "ぎ": "ぐ",
    "ち": "つ",
    "ぢ": "づ",
    "し": "す",
    "じ": "ず",
    "に": "ぬ",
    "ひ": "ふ",
    "び": "ぶ",
    "ぴ": "ぷ",
    "み": "む",
    "り": "る",
}

THE_PHU_DINH_MAPPING = {
    "い": "わない",
    "き": "かない",
    "ぎ": "がない",
    "ち": "たない",
    "ぢ": "だない",
    "し": "さない",
    "じ": "ざない",
    "に": "なない",
    "ひ": "はない",
    "び": "ばない",
    "ぴ": "ぱない",
    "み": "まない",
    "り": "らない",
}

THE_KHA_KHANG_MAPPING = {
    "い": "える",
    "き": "ける",
    "ぎ": "げる",
    "ち": "てる",
    "ぢ": "でる",
    "し": "せる",
    "じ": "ぜる",
    "に": "ねる",
    "ひ": "へる",
    "び": "べる",
    "ぴ": "ぺる",
    "み": "める",
    "り": "れる",
}

THE_Y_DINH_MAPPING = {
    "い": "おう",
    "き": "こう",
    "ぎ": "ごう",
    "ち": "とう",
    "ぢ": "どう",
    "し": "そう",
    "じ": "ぞう",
    "に": "のう",
    "ひ": "ほう",
    "び": "ぼう",
    "ぴ": "ぽう",
    "み": "もう",
    "り": "ろう",
}

THE_MENH_LENH_MAPPING = {
    "い": "え",
    "き": "け",
    "ぎ": "げ",
    "ち": "て",
    "ぢ": "で",
    "し": "せ",
    "じ": "ぜ",
    "に": "ね",
    "ひ": "へ",
    "び": "べ",
    "ぴ": "ぺ",
    "み": "め",
    "り": "れ",
}

THE_THU_DONG_MAPPING = {
    "い": "われる",
    "き": "かれる",
    "ぎ": "がれる",
    "ち": "たれる",
    "ぢ": "だれる",
    "し": "される",
    "じ": "ざれる",
    "に": "なれる",
    "ひ": "はれる",
    "び": "ばれる",
    "ぴ": "ぱれる",
    "み": "まれる",
    "り": "られる",
}

THE_SAI_KHIEN_MAPPING = {
    "い": "わせる",
    "き": "かせる",
    "ぎ": "がせる",
    "ち": "たせる",
    "ぢ": "だせる",
    "し": "させる",
    "じ": "ざせる",
    "に": "なせる",
    "ひ": "はせる",
    "び": "ばせる",
    "ぴ": "ぱせる",
    "み": "ませる",
    "り": "らせる",
}

THE_SAI_KHIEN_THU_DONG_MAPPING = {
    "い": "わせられる",
    "き": "かせられる",
    "ぎ": "がせられる",
    "ち": "たせられる",
    "ぢ": "だせられる",
    "し": "させられる",
    "じ": "ざせられる",
    "に": "なせられる",
    "ひ": "はせられる",
    "び": "ばせられる",
    "ぴ": "ぱせられる",
    "み": "ませられる",
    "り": "らせられる",
}

THE_SAI_KHIEN_THU_DONG_RUT_GON_MAPPING = {
    "い": "わされる",
    "き": "かされる",
    "ぎ": "がされる",
    "ち": "たされる",
    "ぢ": "だされる",
    # "し": "さされる",
    "じ": "ざされる",
    "に": "なされる",
    "ひ": "はされる",
    "び": "ばされる",
    "ぴ": "ぱされる",
    "み": "まされる",
    "り": "らされる",
}

THE_DIEU_KIEN_MAPPING = {
    "い": "えば",
    "き": "けば",
    "ぎ": "げば",
    "ち": "てば",
    "ぢ": "でば",
    "し": "せば",
    "じ": "ぜば",
    "に": "ねば",
    "ひ": "へば",
    "び": "べば",
    "ぴ": "ぺば",
    "み": "めば",
    "り": "れば",
}

NGOAI_LE_NHOM_2 = [
    "起きます",
    "見ます",
    "降ります",
    "過ぎます",
    "足ります",
    "似ます",
    "生きます",
    "閉じます",
    "案じます",
    "演じます",
    "感じます",
    "禁じます",
    "煎じます",
    "投じます",
    "応じます",
    "信じます",
    "出来ます",
    "浴びます",
    "借ります",
    "います",
    "軽んじます",
    "そらんじます",
    "あまんじます",
    "ひからびます",
    "尽きます",
    "着ます",
    "落ちます",
    "飽きます",
    "存じます",
    "煮ます",
]

class Book(models.Model):
    _name = "learning_japanese.book"
    _description = "Book"
    _rec_name = "name"
    _order = "name asc"
    name = fields.Char(string="Book name", copy=False)
    lesson_ids = fields.One2many(
        comodel_name="learning_japanese.lesson", inverse_name="book_id", string="Lessons"
    )


class Lesson(models.Model):
    _name = "learning_japanese.lesson"
    _description = "Lesson"
    _rec_name = "combination"
    _order = "id asc"

    lesson = fields.Char(string="Bài")
    book_id = fields.Many2one(
        comodel_name="learning_japanese.book", string="Book",
    )
    combination = fields.Char(
        string="Combination Name", compute="_compute_fields_combination", store=True
    )
    vocabulary_ids = fields.Many2many(
        comodel_name="learning_japanese.vocabulary",
        relation="lesson_vocabulary_rel",
        column1="lesson_id",
        column2="vocabulary_id",
        string="Vocabulary",
    )
    grammar_ids = fields.One2many(
        comodel_name="learning_japanese.comprehensive",
        inverse_name="lesson_id",
        string="Grammar",
        domain=[("category", "=", "grammar")],
    )
    example_ids = fields.One2many(
        comodel_name="learning_japanese.comprehensive",
        inverse_name="lesson_id",
        string="Example",
        domain=[("category", "=", "example")],
    )

    reading_ids = fields.One2many(
        comodel_name="learning_japanese.comprehensive",
        inverse_name="lesson_id",
        string="Reading",
        domain=[("category", "=", "reading")],
    )

    listening_ids = fields.One2many(
        comodel_name="learning_japanese.comprehensive",
        inverse_name="lesson_id",
        string="Listening",
        domain=[("category", "=", "listening")],
    )

    writing_ids = fields.One2many(
        comodel_name="learning_japanese.comprehensive",
        inverse_name="lesson_id",
        string="Writing",
        domain=[("category", "=", "writing")],
    )

    @api.depends("lesson", "book_id")
    def _compute_fields_combination(self):
        for record in self:
            if record.lesson and record.book_id:
                record.combination = record.book_id.name + " - " + record.lesson


class PartOfSpeech(models.Model):
    _name = "learning_japanese.part_of_speech"
    _description = "Part of Speech"
    _rec_name = "combination"
    _order = "id asc"

    kanji = fields.Char(string="Kanji")
    higarana = fields.Char(string="Higarana")
    vietnamese = fields.Char(string="Vietnamese")
    combination = fields.Char(
        string="Combination Name", compute="_compute_fields_combination", store=True
    )
    vocabulary_ids = fields.Many2many(
        comodel_name="learning_japanese.vocabulary",
        relation="vocabulary_part_of_speech_rel",
        column1="part_of_speech_id",
        column2="vocabulary_id",
        string="Vocabularies",
    )

    @api.onchange("kanji")
    def _onchange_kanji(self):
        if self.kanji:
            kks = kakasi()
            result = kks.convert(self.kanji)
            # join all higarana
            self.higarana = "".join([item["hira"] for item in result])

    @api.depends("higarana", "kanji", "vietnamese")
    def _compute_fields_combination(self):
        for record in self:
            if record.kanji and record.higarana and record.vietnamese:
                record.combination = (
                    record.kanji + " - " + record.higarana + " - " + record.vietnamese
                )


class ContextTag(models.Model):
    _name = "learning_japanese.context_tag"
    _description = "Context Tag"
    _order = "name"
    _rec_name = "name"
    _parent_store = True

    name = fields.Char()
    complete_name = fields.Char(
        "Complete Name", compute="_compute_complete_name", recursive=True, store=True
    )
    parent_id = fields.Many2one(
        "learning_japanese.context_tag",
        string="Parent Context Tag",
        index=True,
    )
    child_ids = fields.One2many(
        "learning_japanese.context_tag", "parent_id", string="Child Vocabularies"
    )
    vocabulary_ids = fields.Many2many(
        comodel_name="learning_japanese.vocabulary",
        relation="vocabulary_context_tag_rel",
        column1="context_tag_id",
        column2="vocabulary_id",
        string="Từ vựng",
    )
    parent_path = fields.Char(index=True)
    master_context_tag_id = fields.Many2one(
        "learning_japanese.context_tag",
        "Master Context Tag",
        compute="_compute_master_context_tag_id",
        store=True,
    )

    # Check if name is unique
    # _sql_constraints = [
    #     ("check_context_tag_name", "UNIQUE(id)", "Name must be unique"),
    # ]

    @api.depends("name", "parent_id.complete_name")
    def _compute_complete_name(self):
        for context_tag in self:
            if context_tag.parent_id:
                context_tag.complete_name = "%s / %s" % (
                    context_tag.parent_id.complete_name,
                    context_tag.name,
                )
            else:
                context_tag.complete_name = context_tag.name
    #
    @api.depends("parent_path")
    def _compute_master_context_tag_id(self):
        for context_tag in self:
            context_tag.master_context_tag_id = int(
                context_tag.parent_path.split("/")[0]
            )

    @api.depends("name", "complete_name")
    def _compute_display_name(self):
        """
        Dynamically switch display name based on context.
        Defaults to short name, switches to complete_name if requested.
        """
        for record in self:
            if self.env.context.get("show_complete_name") and record.complete_name:
                record.display_name = record.complete_name
            else:
                record.display_name = record.name

class HanViet(models.Model):
    _name = "learning_japanese.hanviet"
    _description = "Han Viet"
    _rec_name = "kanji"
    _order = "id asc"

    kanji = fields.Char(string="Kanji")
    han_viet = fields.Char(string="Hán Việt")


class Vocabulary(models.Model):
    _name = "learning_japanese.vocabulary"
    _description = "Learning Japanese"
    _rec_name = "vocabulary"
    _order = "id desc"
    _inherit = ["learning_japanese.furigana.mixin"]

    part_of_speech_ids = fields.Many2many(
        comodel_name="learning_japanese.part_of_speech",
        relation="vocabulary_part_of_speech_rel",
        column1="vocabulary_id",
        column2="part_of_speech_id",
        string="Từ loại",
    )

    lesson_ids = fields.Many2many(
        comodel_name="learning_japanese.lesson",
        relation="lesson_vocabulary_rel",
        column1="vocabulary_id",
        column2="lesson_id",
        string="Lesson",
    )
    book_ids = fields.Many2many(
        comodel_name="learning_japanese.book",
        string="Giáo trình",
        compute="_compute_book_ids",
        store=True,
    )
    context_tag_ids = fields.Many2many(
        comodel_name="learning_japanese.context_tag",
        relation="vocabulary_context_tag_rel",
        column1="vocabulary_id",
        column2="context_tag_id",
        string="Topic",
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
    vocabulary = fields.Char(string="Vocabulary", copy=False, index=True)
    higarana = fields.Char(string="Higarana", index=True)
    katakana = fields.Char(string="Katakana")
    romanji = fields.Char(string="Romanji")
    vietnamese = fields.Char(string="Nghĩa", copy=False, index=True)
    han_viet = fields.Char(string="Âm Hán Việt", copy=False)
    is_intransitive = fields.Boolean(string="Tự động từ", copy=False)
    nhom_ngu = fields.Selection(
        selection=[
            ("kinh_ngu", "Kính ngữ"),
            ("khiem_nhuong_ngu", "Khiêm nhường ngữ"),
        ],
        string="Loại ngữ",
    )
    nhom_dong_tu = fields.Selection(
        selection=[
            ("nhom_1", "Nhóm 1"),
            ("nhom_2", "Nhóm 2"),
            ("nhom_3", "Nhóm 3"),
        ],
        string="Nhóm động từ",
    )

    the_tu_dien = fields.Char(string="Thể nguyên dạng", copy=False)
    the_qua_khu = fields.Char(string="Thể quá khứ", copy=False)
    the_phu_dinh = fields.Char(string="Thể phủ định", copy=False)
    the_te = fields.Char(string="Thể て", copy=False)
    the_kha_nang = fields.Char(string="Thể khả năng", copy=False)
    the_thu_dong = fields.Char(string="Thể thụ động", copy=False)
    the_sai_khien = fields.Char(string="Thể sai khiến", copy=False)
    the_sai_khien_thu_dong = fields.Char(string="Thể sai khiến thụ động", copy=False)
    the_dieu_kien = fields.Char(string="Thể điều kiện", copy=False)
    the_menh_lenh = fields.Char(string="Thể mệnh lệnh", copy=False)
    the_y_chi = fields.Char(string="Thể ý chí", copy=False)
    the_cam_chi = fields.Char(string="Thể cấm chỉ", copy=False)
    is_verb = fields.Boolean(
        string="Is verb?",
        compute="_compute_is_verb",
        store=True,
    )

    _check_unique_vocabulary = models.Constraint(
            "UNIQUE(vocabulary, vietnamese)",
            "Từ mới và nghĩa không được trùng nhau",
    )


    def get_openai_key(self) -> str:
        return self.env["ir.config_parameter"].sudo().get_param("openai.api_key")

    @staticmethod
    def create_prompt(vocabulary: str) -> str:
        return f"""
        Act like a Japanese teacher, please give me the Vietnamese meaning of {vocabulary}, just the meaning, no explanation.
        After that, give 3 examples of this word. Please follow the below format:
        1. Put only all Japanese vocabularies which are in Kanji form into <<>> of all Japanese sentences following below examples.
        For example:
            理解する　→　<<理解 - りかい>>する
            特に　→　<<特 - とく>>に
            女の人　→　<<女 - おんな>>の<<人 - ひと>>
            悪い　→　<<悪 - わる>>い
        For special cases such as 1人, 一人, 2人, 二人, 何ですか, ... ➝ <<1人 - ひとり>>, <<一人 - ひとり>>, <<2人 - ふたり>>, <<二人 - ふたり>>, <<何 - なん>>ですか, ...
        2. You put the Vietnamese paragraph in the {{{{}}}}.
        
        Final response:
        Nghĩa: You put the meaning here
        Ví dụ 1: Japanese sentence with vocabulary and grammar of N4 level。{{{{Vietnamese meaning}}}}
        Ví dụ 2: Japanese sentence with vocabulary and grammar of N3 level。{{{{Vietnamese meaning}}}}
        Ví dụ 3: Japanese sentence with vocabulary and grammar of N2 level。{{{{Vietnamese meaning}}}}
    
        
        Examples for you to refer:
        If the vocabulary is "元々”, the response should be:
        Nghĩa: You put the meaning here
        Ví dụ 1: <<彼 - かれ>>は<<元々 - もともと>>の<<友達> - ともだち>>だった。{{{{Từ trước, anh ấy đã là bạn của tôi.}}}}
        Ví dụ 2: <<元々 - もともと>>はこの<<町 - まち>>に<<住 - す>>んでいた。{{{{Từ trước, tôi đã sống ở thị trấn này.}}}}
        Ví dụ 3: <<元々 - もともと>>はこの<<仕事 - しごと>>をしていた。{{{{Từ trước, tôi đã làm công việc này.}}}}
        """

    def generate_response_from_transcript(
            self, vocabulary: str
    ) -> str | tuple[Any, ...] | tuple[str, str, str]:
        # 1. Search for an active LLM configuration in the database
        llm_config = self.env["learning_japanese.llm_config"].search(
            [("is_active", "=", True)],
            order="sequence asc, id desc",
            limit=1
        )
        if not llm_config:
            raise UserError("No active LLM configuration found. Please enable at least one provider.")

        prompt_text = self.create_prompt(vocabulary)
        full_response = ""

        # 2. Route request dynamically based on the active provider
        if llm_config.provider == "openAI":
            api_key = self.env["ir.config_parameter"].sudo().get_param("openai.api_key")
            if not api_key:
                raise AccessError("OpenAI API Key is missing in System Parameters.")

            # Using the modern OpenAI client instantiation
            client = openai.OpenAI(api_key=api_key)
            try:
                response = client.chat.completions.create(
                    model=llm_config.model_code,  # Uses dynamic model code (e.g., gpt-4o)
                    messages=[{"role": "system", "content": prompt_text}],
                    temperature=1,
                )
                full_response = response.choices[0].message.content or ""
            except Exception as e:
                raise AccessError(f"OpenAI Error: {e}")

        elif llm_config.provider == "gemini":
            api_key = self.env["ir.config_parameter"].sudo().get_param("gemini.api_key")
            if not api_key:
                raise AccessError("Gemini API Key is missing in System Parameters.")

            # Using the Gemini client instantiation
            client = genai.Client(api_key=api_key)
            try:
                response = client.models.generate_content(
                    model=llm_config.model_code,  # Uses dynamic model code (e.g., gemini-1.5-flash)
                    contents=prompt_text,
                )
                full_response = response.text or ""
            except Exception as e:
                raise AccessError(f"Gemini Error: {e}")
        else:
            raise UserError("Unsupported LLM provider.")

        # 3. Parse and return the response lines following the standard format
        try:
            lines = full_response.split("\n")
            return tuple(
                line.split(":", 1)[1].strip() for line in lines if ":" in line
            )[:4]
        except Exception:
            return "", "", "", ""

    def get_part_of_speech(self, env: str, condition: tuple) -> int:
        return self.env[env].search([condition]).id

    @staticmethod
    def get_nhom_dong_tu(vocabulary: str):
        if vocabulary[-3:-2] in NHOM_2 or vocabulary in NGOAI_LE_NHOM_2:
            return "nhom_2"
        elif vocabulary[-3:-2] in NHOM_1:
            return "nhom_1"
        elif vocabulary[-3:] == "します":
            return "nhom_3"
        return False

    @staticmethod
    def get_the_nguyen_dang(vocabulary: str, nhom_dong_tu: str = None) -> str | bool:
        if nhom_dong_tu == "nhom_1":
            appr_char = THE_TU_DIEN_MAPPING.get(vocabulary[-3:-2])
            if appr_char:
                return vocabulary[:-3] + appr_char
        elif nhom_dong_tu == "nhom_2":
            return vocabulary[:-2] + "る"
        elif nhom_dong_tu == "nhom_3":
            return vocabulary[:-3] + "する"
        return False

    @staticmethod
    def get_the_te(vocabulary: str, nhom_dong_tu: str = None) -> str | bool:
        if nhom_dong_tu == "nhom_1":
            if vocabulary[-3:-2] in ["い", "ち", "り"]:
                return vocabulary[:-3] + "って"
            elif vocabulary[-3:-2] in ["み", "び", "に"]:
                return vocabulary[:-3] + "んで"
            elif vocabulary[-3:-2] == "き":
                return vocabulary[:-3] + "いて"
            elif vocabulary[-3:-2] == "ぎ":
                return vocabulary[:-3] + "いで"
            elif vocabulary[-3:-2] == "し":
                return vocabulary[:-2] + "て"
        elif nhom_dong_tu == "nhom_2":
            return vocabulary[:-2] + "て"
        elif nhom_dong_tu == "nhom_3":
            return vocabulary[:-3] + "して"
        return False

    @staticmethod
    def get_the_ta(vocabulary: str, nhom_dong_tu: str = None) -> str | bool:
        if nhom_dong_tu == "nhom_1":
            if vocabulary[-3:-2] in ["い", "ち", "り"]:
                return vocabulary[:-3] + "った"
            elif vocabulary[-3:-2] in ["み", "び", "に"]:
                return vocabulary[:-3] + "んだ"
            elif vocabulary[-3:-2] == "き":
                return vocabulary[:-3] + "いた"
            elif vocabulary[-3:-2] == "ぎ":
                return vocabulary[:-3] + "いだ"
            elif vocabulary[-3:-2] == "し":
                return vocabulary[:-2] + "た"
        elif nhom_dong_tu == "nhom_2":
            return vocabulary[:-2] + "た"
        elif nhom_dong_tu == "nhom_3":
            return vocabulary[:-3] + "した"
        return False

    @staticmethod
    def get_the_phu_dinh(vocabulary: str, nhom_dong_tu: str = None) -> str | bool:
        if nhom_dong_tu == "nhom_1":
            appr_char = THE_PHU_DINH_MAPPING.get(vocabulary[-3:-2])
            if appr_char:
                return vocabulary[:-3] + appr_char
        elif nhom_dong_tu == "nhom_2":
            return vocabulary[:-2] + "ない"
        elif nhom_dong_tu == "nhom_3":
            return vocabulary[:-3] + "しない"
        return False

    @staticmethod
    def get_the_kha_nang(vocabulary: str, nhom_dong_tu: str = None) -> str | bool:
        if nhom_dong_tu == "nhom_1":
            appr_char = THE_KHA_KHANG_MAPPING.get(vocabulary[-3:-2])
            if appr_char:
                return vocabulary[:-3] + appr_char
        elif nhom_dong_tu == "nhom_2":
            return vocabulary[:-2] + "られる"
        elif nhom_dong_tu == "nhom_3":
            return vocabulary[:-3] + "できる"
        return False

    @staticmethod
    def get_the_y_dinh(vocabulary: str, nhom_dong_tu: str = None) -> str | bool:
        if nhom_dong_tu == "nhom_1":
            appr_char = THE_Y_DINH_MAPPING.get(vocabulary[-3:-2])
            if appr_char:
                return vocabulary[:-3] + appr_char
        elif nhom_dong_tu == "nhom_2":
            return vocabulary[:-2] + "よう"
        elif nhom_dong_tu == "nhom_3":
            return vocabulary[:-3] + "しよう"
        return False

    @staticmethod
    def get_the_menh_lenh(vocabulary: str, nhom_dong_tu: str = None) -> str | bool:
        if nhom_dong_tu == "nhom_1":
            appr_char = THE_MENH_LENH_MAPPING.get(vocabulary[-3:-2])
            if appr_char:
                return vocabulary[:-3] + appr_char
        elif nhom_dong_tu == "nhom_2":
            return vocabulary[:-2] + "ろ"
        elif nhom_dong_tu == "nhom_3":
            return vocabulary[:-3] + "しろ"
        return False

    def get_the_cam_chi(self, vocabulary: str, nhom_dong_tu: str = None) -> str | bool:
        the_nguyen_dang = self.get_the_nguyen_dang(vocabulary, nhom_dong_tu)
        if the_nguyen_dang:
            return the_nguyen_dang + "な"
        return False

    @staticmethod
    def get_the_thu_dong(vocabulary: str, nhom_dong_tu: str = None) -> str | bool:
        if nhom_dong_tu == "nhom_1":
            appr_char = THE_THU_DONG_MAPPING.get(vocabulary[-3:-2])
            if appr_char:
                return vocabulary[:-3] + appr_char
        elif nhom_dong_tu == "nhom_2":
            return vocabulary[:-2] + "られる"
        elif nhom_dong_tu == "nhom_3":
            return vocabulary[:-3] + "される"
        return False

    @staticmethod
    def get_the_sai_khien(vocabulary: str, nhom_dong_tu: str = None) -> str | bool:
        if nhom_dong_tu == "nhom_1":
            appr_char = THE_SAI_KHIEN_MAPPING.get(vocabulary[-3:-2])
            if appr_char:
                return vocabulary[:-3] + appr_char
        elif nhom_dong_tu == "nhom_2":
            return vocabulary[:-2] + "させる"
        elif nhom_dong_tu == "nhom_3":
            return vocabulary[:-3] + "させる"
        return False

    @staticmethod
    def get_the_sai_khien_thu_dong(
        vocabulary: str, nhom_dong_tu: str = None
    ) -> str | bool:
        if nhom_dong_tu == "nhom_1":
            appr_char = THE_SAI_KHIEN_THU_DONG_MAPPING.get(vocabulary[-3:-2])
            if appr_char:
                return vocabulary[:-3] + appr_char
        elif nhom_dong_tu == "nhom_2":
            return vocabulary[:-2] + "させられる"
        elif nhom_dong_tu == "nhom_3":
            return vocabulary[:-3] + "させられる"
        return False

    @staticmethod
    def get_the_sai_khien_thu_dong_rut_gon(
        vocabulary: str, nhom_dong_tu: str = None
    ) -> str | bool:
        if nhom_dong_tu == "nhom_1":
            appr_char = THE_SAI_KHIEN_THU_DONG_RUT_GON_MAPPING.get(vocabulary[-3:-2])
            if appr_char:
                return vocabulary[:-3] + appr_char
        return False

    @staticmethod
    def get_the_dieu_kien(vocabulary: str, nhom_dong_tu: str = None) -> str | bool:
        if nhom_dong_tu == "nhom_1":
            appr_char = THE_DIEU_KIEN_MAPPING.get(vocabulary[-3:-2])
            if appr_char:
                return vocabulary[:-3] + appr_char
        elif nhom_dong_tu == "nhom_2":
            return vocabulary[:-2] + "れば"
        elif nhom_dong_tu == "nhom_3":
            return vocabulary[:-3] + "すれば"
        return False

    def get_cac_the_dong_tu(self, nhom_dong_tu: str = None):
        self.nhom_dong_tu = nhom_dong_tu
        self.the_tu_dien = self.get_the_nguyen_dang(self.vocabulary, nhom_dong_tu)
        self.the_te = self.get_the_te(self.vocabulary, nhom_dong_tu)
        self.the_qua_khu = self.get_the_ta(self.vocabulary, nhom_dong_tu)
        self.the_phu_dinh = self.get_the_phu_dinh(self.vocabulary, nhom_dong_tu)
        self.the_kha_nang = self.get_the_kha_nang(self.vocabulary, nhom_dong_tu)
        self.the_y_chi = self.get_the_y_dinh(self.vocabulary, nhom_dong_tu)
        self.the_menh_lenh = self.get_the_menh_lenh(self.vocabulary, nhom_dong_tu)
        self.the_cam_chi = self.get_the_cam_chi(self.vocabulary, nhom_dong_tu)
        self.the_thu_dong = self.get_the_thu_dong(self.vocabulary, nhom_dong_tu)
        self.the_sai_khien = self.get_the_sai_khien(self.vocabulary, nhom_dong_tu)
        the_sai_khien_thu_dong = self.get_the_sai_khien_thu_dong(
            self.vocabulary, nhom_dong_tu
        )
        the_sai_khien_thu_dong_rut_gon = self.get_the_sai_khien_thu_dong_rut_gon(
            self.vocabulary, nhom_dong_tu
        )
        self.the_sai_khien_thu_dong = (
            (the_sai_khien_thu_dong + ", " + the_sai_khien_thu_dong_rut_gon)
            if the_sai_khien_thu_dong_rut_gon
            else the_sai_khien_thu_dong
        )
        self.the_dieu_kien = self.get_the_dieu_kien(self.vocabulary, nhom_dong_tu)

    @api.onchange("vocabulary")
    def _onchange_vocabulary(self):
        if self.vocabulary:
            if self.vocabulary[-2:] == "ます":
                pos_id = self.get_part_of_speech(
                    "learning_japanese.part_of_speech",
                    ("combination", "=", "動詞 - どうし - Động từ"),
                )
                # Assign using Many2many command: replace existing with [pos_id]
                self.part_of_speech_ids = [(6, 0, [pos_id])]
                nhom_dong_tu = self.get_nhom_dong_tu(self.vocabulary)
                self.get_cac_the_dong_tu(nhom_dong_tu)

            elif self.vocabulary[-1] == "い":
                pos_id = self.get_part_of_speech(
                    "learning_japanese.part_of_speech",
                    ("combination", "=", "い形容詞 - いけいようし - Tính từ い"),
                )
                self.part_of_speech_ids = [(6, 0, [pos_id])]
                self.get_cac_the_dong_tu()

            elif self.vocabulary[-3:] == "「な」":
                pos_id = self.get_part_of_speech(
                    "learning_japanese.part_of_speech",
                    ("combination", "=", "な形容詞 - なけいようし - Tính từ な"),
                )
                self.part_of_speech_ids = [(6, 0, [pos_id])]
                self.get_cac_the_dong_tu()
            else:
                pos_id = self.get_part_of_speech(
                    "learning_japanese.part_of_speech",
                    ("combination", "=", "名詞 - めいし - Danh từ"),
                )
                self.part_of_speech_ids = [(6, 0, [pos_id])]
                self.get_cac_the_dong_tu()

            kks = kakasi()
            result = kks.convert(self.vocabulary)
            orig = "".join([item["orig"] for item in result])
            han_viet = []
            for char in orig:
                han_viet.append(
                    self.env["learning_japanese.hanviet"]
                    .search([("kanji", "=", char)])
                    .han_viet
                )
            han_viet_list = list(filter(None, han_viet))
            self.han_viet = " ".join(han_viet_list) if han_viet_list else False
            self.higarana = "".join([item["hira"] for item in result])
            self.katakana = "".join([item["kana"] for item in result])
            self.romanji = " ".join([item["hepburn"] for item in result]).capitalize()

            (
                vietnamese_meaning,
                example_1,
                example_2,
                example_3,
            ) = self.generate_response_from_transcript(self.vocabulary)

            self.vietnamese = vietnamese_meaning.lower()

            # 1. Escape the characters to handle the << >> markers safely[cite: 1, 3]
            safe_ex1 = html.escape(example_1)
            safe_ex2 = html.escape(example_2)
            safe_ex3 = html.escape(example_3)

            # 2. Use regex to find the Japanese period and add a line break
            # This looks for "。" and replaces it with "。<br/>"
            formatted_ex1 = re.sub(r'\{\{', r'<br/>{{', safe_ex1)
            formatted_ex2 = re.sub(r'\{\{', r'<br/>{{', safe_ex2)
            formatted_ex3 = re.sub(r'\{\{', r'<br/>{{', safe_ex3)

            # 3. Assign to the field to trigger the FuriganaMixin
            self.content_only_kanji = (
                f"<p>{formatted_ex1}</p></br>"
                f"<p>{formatted_ex2}</p></br>"
                f"<p>{formatted_ex3}</p>"
            )

    @api.onchange("nhom_dong_tu")
    def _onchange_nhom_dong_tu(self):
        if self.nhom_dong_tu:
            self.the_tu_dien = self.get_the_nguyen_dang(
                self.vocabulary, self.nhom_dong_tu
            )
            self.the_te = self.get_the_te(self.vocabulary, self.nhom_dong_tu)
            self.the_qua_khu = self.get_the_ta(self.vocabulary, self.nhom_dong_tu)
            self.the_phu_dinh = self.get_the_phu_dinh(
                self.vocabulary, self.nhom_dong_tu
            )
            self.the_kha_nang = self.get_the_kha_nang(
                self.vocabulary, self.nhom_dong_tu
            )
            self.the_y_chi = self.get_the_y_dinh(self.vocabulary, self.nhom_dong_tu)
            self.the_menh_lenh = self.get_the_menh_lenh(
                self.vocabulary, self.nhom_dong_tu
            )
            self.the_cam_chi = self.get_the_cam_chi(self.vocabulary, self.nhom_dong_tu)
            self.the_thu_dong = self.get_the_thu_dong(
                self.vocabulary, self.nhom_dong_tu
            )
            self.the_sai_khien = self.get_the_sai_khien(
                self.vocabulary, self.nhom_dong_tu
            )
            the_sai_khien_thu_dong = self.get_the_sai_khien_thu_dong(
                self.vocabulary, self.nhom_dong_tu
            )
            the_sai_khien_thu_dong_rut_gon = self.get_the_sai_khien_thu_dong_rut_gon(
                self.vocabulary, self.nhom_dong_tu
            )
            self.the_sai_khien_thu_dong = (
                (the_sai_khien_thu_dong + ", " + the_sai_khien_thu_dong_rut_gon)
                if the_sai_khien_thu_dong_rut_gon
                else the_sai_khien_thu_dong
            )
            self.the_dieu_kien = self.get_the_dieu_kien(
                self.vocabulary, self.nhom_dong_tu
            )

    @api.depends("lesson_ids.book_id")
    def _compute_book_ids(self):
        for record in self:
            # mapped() automatically collects unique records and returns a recordset
            record.book_ids = record.lesson_ids.mapped("book_id")

    @api.depends("part_of_speech_ids", "part_of_speech_ids.kanji", "part_of_speech_ids.combination")
    def _compute_is_verb(self):
        for record in self:
            # Dynamically check if any selected part of speech represents a verb
            record.is_verb = any(
                pos.kanji == "動詞" or (pos.combination and "動詞" in pos.combination)
                for pos in record.part_of_speech_ids
            )