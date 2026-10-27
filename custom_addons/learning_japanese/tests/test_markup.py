from odoo.tests import BaseCase, tagged
from odoo.tools import html_sanitize

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

    def test_markers_are_stored_escaped(self):
        source = "<p>Khi đến <<kỳ nghỉ hè>>, <<休 - やす>>みます。</p>"
        self.assertEqual(markup.to_stored(source), "<p>Khi đến &lt;&lt;kỳ nghỉ hè>>, &lt;&lt;休 - やす>>みます。</p>")
        self.assertEqual(markup.to_source(html_sanitize(markup.to_stored(source))), source)
        self.assertNotIn("kỳ nghỉ hè", html_sanitize(source))  # read as a <kỳ> tag when not escaped

    def test_a_bracket_before_a_marker_stays_a_bracket(self):
        source = "<p>&lt;<<質問 - しつもん>>&gt;</p>"
        stored = html_sanitize(markup.to_stored(source))
        self.assertEqual(stored, "<p>&lt;&lt;&lt;質問 - しつもん&gt;&gt;&gt;</p>")
        self.assertEqual(markup.to_source(stored), source)
        self.assertEqual(markup.plain_text(source), "<質問>")
        self.assertEqual(markup.to_source("<p>&lt;&lt;&lt;&lt;</p>"), "<p><<<<</p>")

    def test_brackets_stay_text_in_the_rendered_html(self):
        stored = "<p>&lt;Aの&lt;&lt;意見 - いけん&gt;&gt;&gt;<br>{{&lt;Ý kiến của A&gt;}}</p>"
        hover, ruby = (html_sanitize(html) for html in markup.render(stored))
        self.assertIn("<p>&lt;Aの<span", hover)  # was an <aの> tag, dropped with its text
        self.assertIn('title="いけん">意見</span>&gt;</p>', hover)
        self.assertIn("&lt;Aの<ruby>", ruby)
        self.assertIn("&lt;Ý kiến của A&gt;", ruby)
        hover, _ruby = markup.render("<p>a &lt; b &amp;&amp; c&nbsp;{{x}}</p>")
        self.assertEqual(hover, "<p>a &lt; b &amp;&amp; c</p>")

    def test_markers_render_in_every_form_they_arrive_in(self):
        source = "<p><<人 - ひと>>だ。</p>"
        hover, ruby = markup.render(source)
        self.assertIn('title="ひと">人</span>', hover)
        for form in (markup.to_stored(source), str(html_sanitize(markup.to_stored(source)))):
            self.assertEqual(markup.render(form), (hover, ruby), form)

    def test_plain_text(self):
        self.assertEqual(markup.plain_text("<p><<人 - ひと>>です{{là người}}</p>"), "人です")
        self.assertFalse(markup.has_markup("<p><br></p>"))

    def test_display_title_keeps_usage_prefixes(self):
        self.assertEqual(display_title("[Cơ bản] そうですね"), "そうですね")
        self.assertEqual(display_title("[A][B]  PI わけだ"), "PI わけだ")
        self.assertEqual(display_title("thể ta + ことがある"), "thể ta + ことがある")

    def test_patterns_are_trimmed_and_unique(self):
        self.assertEqual(patterns_of(" とする\n\nようとする\nとする "), ["とする", "ようとする"])
