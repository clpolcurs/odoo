from odoo.tests import BaseCase, tagged

from ..services import markup
from ..services.serializers import display_title, patterns_of


@tagged("post_install", "-at_install")
class TestMarkup(BaseCase):

    def codes(self, source):
        return [issue["code"] for issue in markup.analyze(source)["issues"]]

    def test_explicit_readings_have_no_issue(self):
        result = markup.analyze("<p><<係 - かかり>>りの<<人 - ひと>>に<<渡 - わた>>す。{{Đưa cho người phụ trách.}}</p>")
        self.assertEqual(result["issues"], [])
        self.assertEqual(result["stats"]["markers"], 3)
        self.assertEqual(result["stats"]["explicit_readings"], 3)
        self.assertEqual(result["stats"]["translations"], 1)

    def test_marker_without_reading_reports_the_guess(self):
        [issue] = markup.analyze("<p><<人>>です。</p>")["issues"]
        self.assertEqual(issue["code"], "auto_reading")
        self.assertEqual(issue["text"], "人")
        self.assertTrue(issue["reading"])

    def test_kanji_outside_markers(self):
        issues = markup.analyze("<p>機械の<<説明 - せつめい>>を受ける。</p>")["issues"]
        self.assertEqual([i["text"] for i in issues if i["code"] == "kanji_without_reading"], ["機械", "受"])

    def test_unbalanced_and_non_kana(self):
        self.assertIn("unbalanced_marker", self.codes("<p><<人 - ひと>>と<<話 - はな</p>"))
        self.assertIn("reading_not_kana", self.codes("<p><<人 - nguoi>></p>"))
        self.assertIn("empty_marker", self.codes("<p><<>>です</p>"))
        self.assertIn("unbalanced_translation", self.codes("<p><<人 - ひと>>{{người</p>"))

    def test_missing_translation_only_when_others_have_one(self):
        two_blocks = "<p><<雨 - あめ>>だ。{{Mưa.}}</p><p><<雪 - ゆき>>だ。</p>"
        self.assertEqual(self.codes(two_blocks), ["missing_translation"])
        self.assertEqual(self.codes("<p><<雨 - あめ>>だ。</p><p><<雪 - ゆき>>だ。</p>"), [])

    def test_translation_in_next_paragraph_counts(self):
        self.assertEqual(self.codes("<p><<雨 - あめ>>だ。</p><p>{{Mưa.}}</p>"), [])

    def test_escaped_markers_from_odoo(self):
        stored = "<p>&lt;&lt;人 - ひと&gt;&gt;です</p>"
        self.assertEqual(markup.to_source(stored), "<p><<人 - ひと>>です</p>")
        self.assertTrue(markup.same_markup(stored, "<p><<人 - ひと>>です</p>"))
        self.assertEqual(self.codes(stored), [])

    def test_plain_text(self):
        self.assertEqual(markup.plain_text("<p><<人 - ひと>>です{{là người}}</p>"), "人です")
        self.assertFalse(markup.has_markup("<p><br></p>"))

    def test_display_title_keeps_usage_prefixes(self):
        self.assertEqual(display_title("[Cơ bản] そうですね"), "そうですね")
        self.assertEqual(display_title("[A][B]  PI わけだ"), "PI わけだ")
        self.assertEqual(display_title("thể ta + ことがある"), "thể ta + ことがある")

    def test_patterns_are_trimmed_and_unique(self):
        self.assertEqual(patterns_of(" とする\n\nようとする\nとする "), ["とする", "ようとする"])
