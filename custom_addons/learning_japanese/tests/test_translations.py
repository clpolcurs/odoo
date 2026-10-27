from odoo.tests import BaseCase, tagged

from ..services import markup
from ..services.translations import split, untagged


@tagged("post_install", "-at_install")
class TestUntaggedTranslations(BaseCase):

    def test_a_translation_after_the_sentence_on_the_same_line(self):
        self.assertEqual(
            untagged("<p>1. 6時半になって、東の空が明るくなり始めた。Lúc 6h30, bầu trời phía đông bắt đầu sáng.</p>"),
            ["Lúc 6h30, bầu trời phía đông bắt đầu sáng."],
        )
        self.assertEqual(untagged("<p>十日間ですか。10 ngày cơ à?</p>"), ["10 ngày cơ à?"])
        self.assertEqual(split("日本語。「引用」と言った。Tôi đã nói “trích dẫn”."), len("日本語。「引用」と言った。"))

    def test_a_translation_on_the_next_line(self):
        self.assertEqual(untagged("<p>男の人はこの後、何をしますか。<br>Sau đó, người đàn ông sẽ làm gì?</p>"),
                         ["Sau đó, người đàn ông sẽ làm gì?"])
        self.assertEqual(untagged("<p>今日は<<雨 - あめ>>です。</p><p><br></p><p>Hôm nay trời mưa.</p>"),
                         ["Hôm nay trời mưa."])
        self.assertEqual(untagged("<p>まだ間に合うよ。<br>M: Vẫn kịp mà, đi thôi.</p>"), ["M: Vẫn kịp mà, đi thôi."])
        self.assertEqual(untagged("<p>「~という」は内容を言う時に使う。<br>~という dùng khi nói về nội dung như “台風”.</p>"),
                         ["~という dùng khi nói về nội dung như “台風”."])

    def test_explanations_and_translated_lines_are_left_alone(self):
        for source in (
            "<p>できます biểu thị năng lực hoặc khả năng thực hiện.</p>",
            "<p>Danh từ みたい</p><p>Dùng để nói với bạn bè</p>",
            "<p>雪が降った。{{Tuyết đã rơi.}}</p><p>Chú ý: dùng trong văn viết</p>",
            "<p>日本語。Kangaroo は動物だ。</p>",
            "<table><tr><td>日本語です。</td><td>Đây là tiếng Nhật.</td></tr></table>",
            "<ul><li>学校へ行きます。</li><li>Tôi đi đến trường.</li></ul>",
            "<pre>コードです。Đây là mã nguồn.</pre>",
        ):
            with self.subTest(source=source):
                self.assertEqual(untagged(source), [])

    def test_zero_width_spaces_bullets_and_brackets_hide_no_translation(self):
        self.assertEqual(untagged("<p>そうですか。\u200b\u200bVậy à, thế thì tốt.</p>"), ["Vậy à, thế thì tốt."])
        self.assertEqual(untagged("<p>雪が降った。<br>&#8203;Tuyết đã rơi rồi.</p>"), ["Tuyết đã rơi rồi."])
        self.assertEqual(untagged("<p>・明日雨が降ったら、お祭りがありません。<br>・Nếu ngày mai trời mưa, sẽ không có lễ hội.</p>"),
                         ["・Nếu ngày mai trời mưa, sẽ không có lễ hội."])
        self.assertEqual(untagged("<p>【相談】朝起きられません。<br>[Tư vấn] Tôi không thể thức dậy vào buổi sáng.</p>"),
                         ["[Tư vấn] Tôi không thể thức dậy vào buổi sáng."])

    def test_what_a_term_means_is_a_translation_how_it_is_used_is_not(self):
        self.assertEqual(untagged("<p>〜はずがない<br>Tuyệt đối không ~ / Làm gì có chuyện ~</p>"),
                         ["Tuyệt đối không ~ / Làm gì có chuyện ~"])
        for source in (
            "<p>「しか」 được dùng sau danh từ, lượng từ.</p>",
            "<p>～ため（に）<br>sử dụng khi nói rằng “~” là nguyên nhân.</p>",
            "<p>( 4 ) お／ご～ ください<br>Đây là hình thức tôn kính của câu nhờ vả.</p>",
            "<p>Vます がたい<br>Chủ yếu dùng với động từ chỉ ý chí.</p>",
        ):
            with self.subTest(source=source):
                self.assertEqual(untagged(source), [])

    def test_a_sentence_has_one_translation(self):
        self.assertEqual(untagged("<p>雪がたくさん降りました。Tuyết đã rơi nhiều.<br>Trường hợp động từ</p>"),
                         ["Tuyết đã rơi nhiều."])

    def test_preview_and_qa_report_them(self):
        result = markup.analyze("<p><<雨 - あめ>>だ。Trời đang mưa.</p>")
        self.assertEqual(result["stats"]["untagged_translations"], 1)
        self.assertEqual([i["text"] for i in result["issues"] if i["code"] == "untagged_translation"],
                         ["Trời đang mưa."])
