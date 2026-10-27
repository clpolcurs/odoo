import pytest

from gmatch import Analysed, Pattern, examples, resolve, unmarked_examples


@pytest.mark.parametrize(
    ("pattern", "text", "found"),
    [
        ("ことにする", "休みを取ることにした。", True),  # the last word conjugates
        ("ようとする", "話し手が伝えようとした話", True),  # 伝えよう is one Sudachi word
        ("ことか", "なんと美しいことか。", True),
        ("ことか", "詳しいことから、", False),  # must end at a word boundary
        ("まい", "もう二度と飲むまいと思う。", True),
        ("まい", "まいったなあ。", False),
        ("まい", "宿題をしまいました。", False),  # must start at a word boundary
        ("Vます得る", "十分に予測し得る事故だった。", True),
        ("Vます得る", "周りの協力が得られるとは限らない。", False),
        ("Vるあまり", "体型を気にするあまり過激なダイエットをする。", True),
        ("Vるあまり", "あまり好きではない。", False),
        ("N上[じょう]", "子どもの教育上よくない。", True),
        ("N上[じょう]", "机の上に置いた。", False),
        ("Aなことに、", "残念なことに、雨が降った。", True),
        ("さえ…ば", "お金さえあれば何でもできる。", True),
        ("も…なら…も", "授業に遅れようものなら教室にも入れない。", False),  # pieces must be whole words
        ("を…Nとする", "自然保護を目的とするグループ", True),
        ("を…Nとする", "時代を迎えようとしていた。", False),
        ("かのようだ", "まるで見てきたかのように話した。", True),  # な/に forms after よう
        ("ものなら", "ものです。", False),  # なら is that exact form
        ("わけではない", "病気が治ったわけではありません。", True),  # ない also matches ありません
        ("Aい上に", "スピードが出やすい上に、", True),  # やすい is an adjective suffix
        ("Vたものだ", "昔はよく川で泳いだものだ。", True),  # past だ after a voiced stem
        ("Vることだ", "やせたければ、たばこをやめることです。", True),
        ("Vることだ", "三日で退院できるということだ。", False),  # hearsay
        ("ぶる", "あいつは先生の前だといい子ぶっている。", True),
        ("ぶる", "10年ぶりに優勝した。", False),
    ],
)
def test_patterns(pattern, text, found):
    assert bool(Analysed(text).matches(Pattern(pattern))) is found


def test_longer_match_of_another_point_wins():
    sentence = Analysed("お金がないときに限って、友達から誘われる。")
    found = [
        (point, p, s, e)
        for point, p in (("2491", "に限る"), ("2506", "に限って"))
        for s, e in sentence.matches(Pattern(p))
    ]
    assert {f[0] for f in found} == {"2491", "2506"}
    assert {f[0] for f in resolve(found)} == {"2506"}


def test_unmarked_examples_are_numbered_lines_and_dialogues_outside_exercises():
    markup = (
        "<p>「<<際 - さい>>」は<<説明書 - せつめいしょ>>で<<使 - つか>>う。</p>"
        "<p>1. <<雨天 - うてん>>の<<際 - さい>>は<<中止 - ちゅうし>>です。<br>1. Khi trời mưa thì hủy.</p>"
        "<p>A: <<明日 - あした>>は？<br>B: <<休 - やす>>みの<<際 - さい>>に<<話 - はな>>そう。</p>"
        "<p><strong>やってみよう！</strong></p><p>1. <<際 - さい>>のない<<文 - ぶん>>。</p>"
        "<p>～に<<際 - さい>>して</p><p>1. <<出発 - しゅっぱつ>>に<<際 - さい>>して<<挨拶 - あいさつ>>した。</p>"
    )
    assert [text for text, _ in unmarked_examples(markup)] == [
        "1. 雨天の際は中止です。",
        "A: 明日は？\nB: 休みの際に話そう。",
        "1. 出発に際して挨拶した。",
    ]


def test_examples_keep_bold_spans_and_drop_readings_and_translations():
    markup = (
        "<p>1. もう<<甘 - あま>>いものは<<食 - た>>べ<strong>まい</strong>と思う。<br>{{Tôi sẽ không ăn đồ ngọt.}}</p>"
    )
    ((text, spans),) = examples(markup)
    assert text == "1. もう甘いものは食べまいと思う。"
    assert [text[s:e] for s, e in spans] == ["まい"]
