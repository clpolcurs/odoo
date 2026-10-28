import importlib.util
import json
from pathlib import Path

import pytest

from apply_translations import problem_of
from translations import Unwrap, apply, explanations, find

ADDON = Path(__file__).resolve().parents[2] / "custom_addons" / "learning_japanese" / "services" / "translations.py"
_spec = importlib.util.spec_from_file_location("addon_translations", ADDON)
addon = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(addon)

CASES = [
    # (markup, the markup with the braces the proposal adds)
    (
        "<p>1. 6時半になって、東の空が明るくなり始めた。Lúc 6h30, bầu trời phía đông bắt đầu sáng.</p>",
        "<p>1. 6時半になって、東の空が明るくなり始めた。{{Lúc 6h30, bầu trời phía đông bắt đầu sáng.}}</p>",
    ),
    ("<p>十日間ですか。10 ngày cơ à?</p>", "<p>十日間ですか。{{10 ngày cơ à?}}</p>"),
    (
        "<p>男の人はこの後、何をしますか。<br>Sau đó, người đàn ông sẽ làm gì?</p>",
        "<p>男の人はこの後、何をしますか。<br>{{Sau đó, người đàn ông sẽ làm gì?}}</p>",
    ),
    (
        "<p>今日は<<雨 - あめ>>です。</p><p><br></p><p>Hôm nay trời mưa.</p>",
        "<p>今日は<<雨 - あめ>>です。</p><p><br></p><p>{{Hôm nay trời mưa.}}</p>",
    ),
    ("<p>まだ間に合うよ。<br>M: Vẫn kịp mà, đi thôi.</p>", "<p>まだ間に合うよ。<br>{{M: Vẫn kịp mà, đi thôi.}}</p>"),
    (
        "<p>「~という」は内容を言う時に使う。<br>~という dùng khi nói về nội dung như “台風”.</p>",
        "<p>「~という」は内容を言う時に使う。<br>{{~という dùng khi nói về nội dung như “台風”.}}</p>",
    ),
    (
        "<p><<雨 - あめ>>だ。Trời&nbsp;đang mưa.&nbsp;</p>",
        "<p><<雨 - あめ>>だ。{{Trời&nbsp;đang mưa.}}&nbsp;</p>",
    ),
    (
        '<p><span style="color: red">日本語です。Đây là <b>tiếng</b> Nhật.</span></p>',
        '<p><span style="color: red">日本語です。{{Đây là <b>tiếng</b> Nhật.}}</span></p>',
    ),
    (
        "<p>雪がたくさん降りました。Tuyết đã rơi nhiều.<br>Trường hợp động từ</p>",
        "<p>雪がたくさん降りました。{{Tuyết đã rơi nhiều.}}<br>Trường hợp động từ</p>",
    ),
    # the editor leaves zero-width spaces between sentences
    ("<p>そうですか。\u200b\u200bVậy à, thế thì tốt.</p>", "<p>そうですか。\u200b\u200b{{Vậy à, thế thì tốt.}}</p>"),
    ("<p>雪が降った。<br>\u200bTuyết đã rơi rồi.</p>", "<p>雪が降った。<br>\u200b{{Tuyết đã rơi rồi.}}</p>"),
    (
        "<p>・明日雨が降ったら、お祭りがありません。<br>・Nếu ngày mai trời mưa, sẽ không có lễ hội.</p>",
        "<p>・明日雨が降ったら、お祭りがありません。<br>{{・Nếu ngày mai trời mưa, sẽ không có lễ hội.}}</p>",
    ),
    (
        "<p>* 変化を表す動詞が使われる。<br>* Động từ mô tả sự thay đổi cũng được sử dụng.</p>",
        "<p>* 変化を表す動詞が使われる。<br>{{* Động từ mô tả sự thay đổi cũng được sử dụng.}}</p>",
    ),
    (
        "<p>【相談】朝起きられません。<br>[Tư vấn] Tôi không thể thức dậy vào buổi sáng.</p>",
        "<p>【相談】朝起きられません。<br>{{[Tư vấn] Tôi không thể thức dậy vào buổi sáng.}}</p>",
    ),
    # what a term means is its translation
    (
        "<p>〜はずがない<br>Tuyệt đối không ~ / Làm gì có chuyện ~</p>",
        "<p>〜はずがない<br>{{Tuyệt đối không ~ / Làm gì có chuyện ~}}</p>",
    ),
    # a translation may quote whole Japanese examples (Try N2 #827)
    (
        "<p>「留学生として」のように使う。<br>Sử dụng khi nói lên tư cách như là “留学生として”.</p>",
        "<p>「留学生として」のように使う。<br>{{Sử dụng khi nói lên tư cách như là “留学生として”.}}</p>",
    ),
    # the term it opens with may run into the Vietnamese (Try N2 #867)
    (
        "<p>「~のみ」は、「~だけ」と言いたいときに使う。<br>~のみdùng khi muốn nói là “chỉ ~”.</p>",
        "<p>「~のみ」は、「~だけ」と言いたいときに使う。<br>{{~のみdùng khi muốn nói là “chỉ ~”.}}</p>",
    ),
    # or be any term of the sentence above: slashes, dots, quotes (Try N3 #708, Try N2 #886, Try N3 #692)
    (
        "<p>「～による・～によって」は、手段を表す。<br>～による/～によって thể hiện phương pháp, cách thức.</p>",
        "<p>「～による・～によって」は、手段を表す。<br>{{～による/～によって thể hiện phương pháp, cách thức.}}</p>",
    ),
    (
        "<p>「お/ご~願います」は、丁寧に頼む時に使う。<br>“お/ご~願います” được sử dụng khi nhờ lịch sự.</p>",
        "<p>「お/ご~願います」は、丁寧に頼む時に使う。<br>{{“お/ご~願います” được sử dụng khi nhờ lịch sự.}}</p>",
    ),
    (
        "<p>「〜と、...」は、気づいた時に使う。<br>〜と、... sử dụng khi nhận ra điều gì đó.</p>",
        "<p>「〜と、...」は、気づいた時に使う。<br>{{〜と、... sử dụng khi nhận ra điều gì đó.}}</p>",
    ),
    # a question and its answer on one line, with the dots of a dialogue (Minna 1 #1196, #1198)
    (
        "<p>1. お手洗いはどこですか。Nhà vệ sinh ở đâu?&nbsp; &nbsp; .....あそこです。....Ở đằng kia.</p>",
        "<p>1. お手洗いはどこですか。{{Nhà vệ sinh ở đâu?}}&nbsp; &nbsp; .....あそこです。{{....Ở đằng kia.}}</p>",
    ),
    (
        "<p>1. 今何時ですか。Bây giờ là mấy giờ?　........7時10分です。....... 7 giờ 10 phút.</p>",
        "<p>1. 今何時ですか。{{Bây giờ là mấy giờ?}}　........7時10分です。{{....... 7 giờ 10 phút.}}</p>",
    ),
    # a short answer, one that opens with a number, a sentence with a Vietnamese note (Minna 1 #1294, #1313)
    ("<p>.......うん、持って「い」る。Có</p>", "<p>.......うん、持って「い」る。{{Có}}</p>"),
    (
        "<p>1. 売り上げが全体の80%を占めている。80% doanh thu là nhờ vào truyền thông.</p>",
        "<p>1. 売り上げが全体の80%を占めている。{{80% doanh thu là nhờ vào truyền thông.}}</p>",
    ),
    (
        "<p>3. 交差点を右に（hoặc へ）曲がります。Tôi rẽ phải ở ngã tư.</p>",
        "<p>3. 交差点を右に（hoặc へ）曲がります。{{Tôi rẽ phải ở ngã tư.}}</p>",
    ),
    # a Japanese note in brackets after the translation stays outside (Minna 1 #1316)
    (
        "<p>ええ、佐藤さんがくれました。Vâng, chị Sato tặng tôi đấy ạ. (佐藤さんがこのワインをくれました。)</p>",
        "<p>ええ、佐藤さんがくれました。{{Vâng, chị Sato tặng tôi đấy ạ.}} (佐藤さんがこのワインをくれました。)</p>",
    ),
    # Japanese that no 。 closes belongs to the translation
    (
        "<p>これはいくつですか。Cái này bao nhiêu cái? Dùng いくつ khi hỏi số lượng.</p>",
        "<p>これはいくつですか。{{Cái này bao nhiêu cái? Dùng いくつ khi hỏi số lượng.}}</p>",
    ),
    # a speaker and a Vietnamese stage direction open the translation of the line above
    (
        "<p>理容師：（鏡を見せて）よろしいですか？<br>理容師：(Cho xem gương) Như này được không ạ?</p>",
        "<p>理容師：（鏡を見せて）よろしいですか？<br>{{理容師：(Cho xem gương) Như này được không ạ?}}</p>",
    ),
]

LEFT_ALONE = [
    "<p>できます biểu thị năng lực hoặc khả năng thực hiện.</p>",
    "<p>Danh từ みたい</p><p>Dùng để nói với bạn bè</p>",
    "<p>雪が降った。{{Tuyết đã rơi.}}</p><p>Chú ý: dùng trong văn viết</p>",
    "<p>日本語。Kangaroo は動物だ。</p>",
    "<table><tr><td>日本語です。</td><td>Đây là tiếng Nhật.</td></tr></table>",
    "<ul><li>学校へ行きます。</li><li>Tôi đi đến trường.</li></ul>",
    "<pre>コードです。Đây là mã nguồn.</pre>",
    # how a term is used is an explanation
    "<p>「しか」 được dùng sau danh từ, lượng từ.</p>",
    "<p>～ため（に）<br>sử dụng khi nói rằng “~” là nguyên nhân.</p>",
    "<p>( 4 ) お／ご～ ください<br>Đây là hình thức tôn kính của câu nhờ vả.</p>",
    "<p>Vます がたい<br>Chủ yếu dùng với động từ chỉ ý chí.</p>",
    # a term under a heading, not under a sentence
    "<p>3. ～んですが、～</p><p>「～んですが」có chức năng mở đầu câu chuyện.</p>",
    # a term with a colon is a gloss, and a term the sentence above does not hold is not its translation
    "<p>毎日日本語を勉強している。<br>～ている: diễn tả trạng thái đang tiếp diễn</p>",
    "<p>毎日日本語を勉強している。<br>～による/～によって thể hiện phương pháp, cách thức.</p>",
]


@pytest.mark.parametrize(("markup", "expected"), CASES)
def test_braces_go_around_the_translation_only(markup, expected):
    found = find(markup)
    assert found.doubts == []
    assert apply(markup, found.wraps) == expected


@pytest.mark.parametrize("markup", LEFT_ALONE)
def test_explanations_and_translated_lines_are_left_alone(markup):
    found = find(markup)
    assert found.wraps == [] and found.doubts == []


def test_braces_come_off_the_explanations_they_hold():
    markup = "<p>「しか」 {{được dùng sau danh từ, lượng từ.}}</p><p>雨だ。{{Trời mưa rồi đấy.}}</p>"
    unwraps = explanations(markup)
    assert unwraps == [Unwrap(8, 44, "được dùng sau danh từ, lượng từ.", "「しか」")]
    assert (
        apply(markup, [], unwraps)
        == "<p>「しか」 được dùng sau danh từ, lượng từ.</p><p>雨だ。{{Trời mưa rồi đấy.}}</p>"
    )
    assert explanations("<p>〜はずがない<br>{{Tuyệt đối không ~ / Làm gì có chuyện ~}}</p>") == []


def test_the_translation_of_a_japanese_explanation_keeps_its_braces():
    # Try N3 #700: the Vietnamese line repeats the term and translates the Japanese sentence above
    markup = "<p>「～させられる」は、言われてする時に使う。<br>「～させられる」{{sử dụng khi bị người khác bảo.}}</p>"
    assert explanations(markup) == []
    # Minna 2 #1663: the sentence above has its own translation, so the line explains the term
    markup = (
        "<li>パソコンが故障してしまいました。{{Máy vi tính bị hỏng mất rồi.}}</li>"
        "<li>「～て しまいます」{{diễn tả hành động sẽ kết thúc.}}</li>"
    )
    assert [u.text for u in explanations(markup)] == ["diễn tả hành động sẽ kết thúc."]
    # Minna 2 #1648: a heading above, no sentence
    markup = "<p>3. ～んですが、～</p><p>「～んですが」{{có chức năng mở đầu câu chuyện.}}</p>"
    assert [u.text for u in explanations(markup)] == ["có chức năng mở đầu câu chuyện."]


def test_formatting_that_cuts_a_translation_is_left_to_a_person():
    found = find("<p><b>日本語です。Đây</b> là tiếng Nhật.</p>")
    assert found.wraps == []
    assert found.doubts == [("Đây là tiếng Nhật.", "định dạng (đậm, màu…) cắt ngang bản dịch")]


@pytest.mark.parametrize("markup", [case[0] for case in CASES] + LEFT_ALONE)
def test_the_addon_reports_what_the_tool_proposes(markup):
    found = find(markup)
    assert addon.untagged(markup) == [w.text for w in found.wraps] + [text for text, _why in found.doubts]


def test_the_addon_agrees_on_the_fetched_items():
    data = Path(__file__).parent / "data" / "items.json"
    if not data.exists():
        pytest.skip("run fetch.py first")
    for item in json.loads(data.read_text()):
        found = find(item["markup"] or "")
        expected = sorted([w.text for w in found.wraps] + [text for text, _why in found.doubts])
        assert sorted(addon.untagged(item["markup"] or "")) == expected, item["id"]


def preview(translations, untagged=None, issues=()):
    stats = {"translations": translations}
    if untagged is not None:
        stats["untagged_translations"] = untagged
    return {"stats": stats, "issues": [{"code": code} for code in issues]}


def test_only_the_expected_change_is_written():
    old = "<p>雨だ。Trời đang mưa.</p>"
    new = apply(old, find(old).wraps)
    assert problem_of(old, new, preview(0, 1), preview(1, 0), 1) is None
    assert problem_of(old, new, preview(0), preview(1), 1) is None  # an Odoo that does not report the issue yet
    assert problem_of(old, new, preview(0, 1), preview(1, 1), 1) == "0 untagged translations less instead of 1"
    assert problem_of(old, new, preview(0), preview(0), 1) == "0 translations more instead of 1"
    assert problem_of(old, new, preview(0), preview(1, issues=["unbalanced_translation"]), 1) == (
        "new unbalanced_translation issue"
    )
    assert problem_of(old, new.replace("mưa", "nắng"), preview(0), preview(1), 1) == "more than braces would change"


def test_only_the_braces_of_the_explanations_come_off():
    old = "<p>「しか」 {{được dùng sau danh từ, lượng từ.}}</p>"
    new = apply(old, [], explanations(old))
    assert problem_of(old, new, preview(1, 0), preview(0, 0), 0, 1) is None
    # an Odoo whose QA still reads the explanation as a translation
    assert problem_of(old, new, preview(1, 0), preview(0, 1), 0, 1) == "-1 untagged translations less instead of 0"
