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
