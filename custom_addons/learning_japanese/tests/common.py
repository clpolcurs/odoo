from odoo.fields import Command
from odoo.tests import TransactionCase


class LearningJapaneseDataCase(TransactionCase):
    """Two books (one published), a lesson in each, tagged items, vocabulary."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.tag_reading = cls._tag("Reading")
        cls.tag_listening = cls._tag("Listening")
        cls.tag_grammar = cls._tag("Grammar")

        cls.book = env["learning_japanese.book"].create({"name": "ドリル&ドリル N2", "nihongo_published": True})
        cls.book_draft = env["learning_japanese.book"].create({"name": "CV tiếng Nhật"})
        cls.lesson = env["learning_japanese.lesson"].create({"lesson": "聴解・課題理解", "book_id": cls.book.id})
        cls.lesson_draft = env["learning_japanese.lesson"].create({"lesson": "Bài 1", "book_id": cls.book_draft.id})

        Item = env["learning_japanese.comprehensive"]
        cls.reading = Item.create({
            "title": "「話」と「メッセージ」",
            "level": "N2",
            "category_ids": [Command.set(cls.tag_reading.ids)],
            "lesson_ids": [Command.set(cls.lesson.ids)],
            "content_only_kanji": "<p><<係 - かかり>>りの<<人>>に<<渡 - わた>>す。{{Đưa cho người phụ trách.}}</p>",
        })
        cls.listening = Item.create({
            "title": "1番",
            "category_ids": [Command.set(cls.tag_listening.ids)],
            "lesson_ids": [Command.set(cls.lesson.ids)],
        })
        cls.grammar = Item.create({
            "title": "[Cơ bản] N1をN2とする",
            "level": "N2",
            "description": "coi N1 là N2",
            "category_ids": [Command.set(cls.tag_grammar.ids)],
            "lesson_ids": [Command.set(cls.lesson.ids)],
            "grammar_patterns": "とする",
        })
        cls.draft_item = Item.create({
            "title": "Giới thiệu bản thân",
            "level": "N3",
            "category_ids": [Command.set(cls.tag_reading.ids)],
            "lesson_ids": [Command.set(cls.lesson_draft.ids)],
        })
        cls.vocabulary = env["learning_japanese.vocabulary"].create({
            "vocabulary": "理解します",
            "higarana": "りかいします",
            "vietnamese": "hiểu",
            "level": "N3",
            "lesson_ids": [Command.set(cls.lesson.ids)],
        })

    @classmethod
    def _tag(cls, name):
        """Reuse the tag when the database already has it (tag names are unique)."""
        Tag = cls.env["learning_japanese.comprehensive_tag"]
        return Tag.search([("name", "=ilike", name)], limit=1) or Tag.create({"name": name})

    def feed(self, after="0", limit=1000):
        """(events, next_after, has_more) of the change feed after the cursor."""
        events, next_after, has_more = self.env["learning_japanese.change_log"]._read_after(after, limit)
        return events, next_after, has_more
