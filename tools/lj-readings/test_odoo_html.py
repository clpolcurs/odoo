from odoo_html import FIELD, html_sanitize, read_back, to_send, to_source


def test_a_marker_starting_with_a_latin_letter_survives_only_when_escaped():
    markup = "<p>Khi đến <<kỳ nghỉ hè>>, <<休 - やす>>みます。</p>"
    assert to_source(str(html_sanitize(markup, **FIELD))) == "<p>Khi đến &lt;&gt;, <<休 - やす>>みます。</p>"
    assert to_send(markup) == "<p>Khi đến &lt;&lt;kỳ nghỉ hè>>, &lt;&lt;休 - やす>>みます。</p>"
    assert read_back(markup) == markup


def test_brackets_and_tags_next_to_markers_read_back_unchanged():
    for markup in (
        "<p>&lt;Aの<<意見 - いけん>>&gt;<br>{{&lt;Ý kiến của A&gt;}}</p>",
        "<p><b><<人 - ひと>></b>>></p>",
        "<p><<<b>人</b></p>",
        "<pre>cout<<endl;</pre>",
        "<p>&lt;<<質問 - しつもん>>&gt;<br>{{&lt;Câu hỏi&gt;}}</p>",
    ):
        assert read_back(markup) == markup
