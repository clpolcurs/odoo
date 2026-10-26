from datetime import timedelta

from odoo import fields
from odoo.fields import Command
from odoo.tests import tagged

from ..models.change_log import PURGED_CURSOR_PARAM
from .common import LearningJapaneseDataCase


@tagged("post_install", "-at_install")
class TestChangeFeed(LearningJapaneseDataCase):

    def setUp(self):
        super().setUp()
        self.start = self.env["learning_japanese.change_log"]._head_cursor()

    def events(self):
        events, _next_after, _has_more = self.feed(self.start)
        return {(e["entity"], e["id"], e["op"]) for e in events}

    def test_create_update_delete(self):
        item = self.env["learning_japanese.comprehensive"].create({"title": "新しい"})
        item.write({"level": "N4"})
        item_id = item.id
        item.unlink()
        self.assertLessEqual(
            {("comprehensive", item_id, "create"), ("comprehensive", item_id, "update"),
             ("comprehensive", item_id, "delete")},
            self.events(),
        )

    def test_publishing_a_book_touches_its_members(self):
        self.book_draft.nihongo_published = True
        self.assertLessEqual(
            {("book", self.book_draft.id, "update"), ("lesson", self.lesson_draft.id, "update"),
             ("comprehensive", self.draft_item.id, "update")},
            self.events(),
        )

    def test_lesson_membership_logs_only_the_difference(self):
        self.lesson.write({"reading_ids": [Command.link(self.draft_item.id)]})
        events = self.events()
        self.assertIn(("comprehensive", self.draft_item.id, "update"), events)
        self.assertNotIn(("comprehensive", self.reading.id, "update"), events)

    def test_moving_a_lesson_touches_both_books(self):
        self.lesson_draft.book_id = self.book
        self.assertLessEqual(
            {("book", self.book.id, "update"), ("book", self.book_draft.id, "update"),
             ("comprehensive", self.draft_item.id, "update")},
            self.events(),
        )

    def test_grammar_override_logs_the_item(self):
        self.env["learning_japanese.grammar_override"].create({
            "comprehensive_id": self.reading.id, "grammar_id": self.grammar.id, "action": "pin",
        })
        self.assertIn(("comprehensive", self.reading.id, "update"), self.events())

    def test_deleting_a_grammar_point_logs_items_that_pinned_it(self):
        self.env["learning_japanese.grammar_override"].create({
            "comprehensive_id": self.reading.id, "grammar_id": self.grammar.id, "action": "pin",
        })
        self.start = self.env["learning_japanese.change_log"]._head_cursor()
        self.grammar.unlink()
        self.assertIn(("comprehensive", self.reading.id, "update"), self.events())

    def test_renaming_a_tag_logs_its_items(self):
        self.tag_listening.name = "Nghe"
        self.assertIn(("comprehensive", self.listening.id, "update"), self.events())

    def test_cursor_paging(self):
        for level in ("N5", "N4", "N3"):
            self.reading.level = level
        events, next_after, has_more = self.feed(self.start, limit=2)
        self.assertEqual(len(events), 2)
        self.assertTrue(has_more)
        rest, last, has_more = self.feed(next_after, limit=10)
        self.assertEqual(len(rest), 1)
        self.assertFalse(has_more)
        self.assertEqual(self.feed(last)[0], [])
        self.assertEqual(last, self.env["learning_japanese.change_log"]._head_cursor())

    def test_purge_expires_old_cursors(self):
        log = self.env["learning_japanese.change_log"]
        self.reading.level = "N1"
        self.env.cr.execute("UPDATE lj_change_log SET at = %s", [fields.Datetime.now() - timedelta(days=91)])
        log._cron_purge()
        mark = self.env["ir.config_parameter"].get_param(PURGED_CURSOR_PARAM)
        self.assertTrue(mark)
        with self.assertRaises(LookupError):
            log._read_after("0", 10)
        self.assertEqual(log._head_cursor(), mark)
        self.assertEqual(log._read_after(mark, 10)[0], [])

    def test_malformed_cursor(self):
        with self.assertRaises(ValueError):
            self.feed("abc")
