import pytest

from gmatch import Analysed, Pattern, blocks, examples, resolve, unmarked_examples


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
        ("Vると[接続助詞]", "駅に着くと、友達はもう来ていた。", True),
        ("Vると[接続助詞]", "明日は雨が降ると思う。", False),
        ("ていく", "渡り鳥は南へ飛んでいった。", False),  # で, not て
        ("でいく", "渡り鳥は南へ飛んでいった。", True),
        ("Vますそうもない", "こんなに食べられそうもない。", True),
        ("Aくなんかない", "友達もいるから寂しくなんかないよ。", True),
        ("Aくなんかない", "テレビなんかなくても困らない。", False),
        ("でる", "お酒が原因でまわりに迷惑をかけた。", False),  # the last word must be でる itself
        ("でる", "今、本を読んでるところ。", True),
        ("Vますです", "朝コーヒーを飲んだきりで、", False),  # だ of 飲んだ is not です
        ("させられる", "父にトイレ掃除をさせられた。", True),
        ("Nらしい", "やっと社会人らしくなってきた。", True),
        ("Aそう[形状詞]だ", "この料理は辛そうです。", True),  # the stem of 辛い
        ("Aすぎる", "この部屋は狭すぎる。", True),
        ("Aなそう[形状詞]だ", "彼は親切そうです。", True),  # 親切 is a noun that can be a na-adjective
        ("そう[名詞]だ", "明日は寒くなるそうです。", True),  # hearsay
        ("そう[名詞]だ", "今にも雨が降りそうです。", False),  # looks like: そう is a 形状詞 there
        ("う。", "ちょっと休もう。", True),
        ("う。", "明日は雨でしょう。", False),  # only a volitional verb
        ("お～する", "また今度お願いします。", True),  # ～ is one word
        ("お～する", "私の友達はお年寄りの世話をするボランティアをしています。", False),
        ("お〜する", "お待ちしております。", True),  # the wave dash as well
        ("ご～いたす", "後ほどご連絡いたします。", True),
        ("お～ところ", "お忙しいところを申し訳ありません。", True),
        ("お～ところ", "鍋にお湯を沸かし、沸騰したところへ鶏肉を入れます。", False),
        ("お～のところ", "お疲れのところ、すみません。", True),
        ("お～になる", "先生はもうお帰りになりました。", True),
        ("お～ください", "少々お待ちください。", True),
    ],
)
def test_patterns(pattern, text, found):
    assert bool(Analysed(text).matches(Pattern(pattern))) is found


def test_a_slot_match_spans_the_pieces_and_the_word():
    text = "番組へのご意見をお待ちしております。"
    assert [text[s:e] for s, e in Analysed(text).matches(Pattern("お～する"))] == ["お待ちし"]


@pytest.mark.parametrize("pattern", ["お～…する", "お～する～", "お～"])
def test_a_pattern_holds_one_slot_with_words_after_it(pattern):
    with pytest.raises(ValueError):
        Pattern(pattern)


def test_blocks_drop_word_spacing_and_zero_width_spaces():
    ((text, _),) = blocks("<p>コンピューターが あります。お手洗い\u200bは<<二階 - にかい>>です。</p>")
    assert text == "コンピューターがあります。お手洗いは二階です。"
    assert Analysed(text).matches(Pattern("がある"))


def test_blocks_drop_color_spans_inside_words():
    ((text, _),) = blocks('<p>日本へ<<来る>><<前<span class="text-o-color-1">​</span>に>>、勉強しました。</p>')
    assert text == "日本へ来る前に、勉強しました。"


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


def test_unmarked_examples_keep_answers_and_fall_back_to_translated_lines():
    markup = (
        "<p>1. これは<<誰 - だれ>>の<<本 - ほん>>ですか。</p>"
        "<p>........<<佐藤 - さとう>>さんのです。</p>"
        "<p>2. A: あれは<<何 - なん>>ですか。<br>B: <<辞書 - じしょ>>です。</p>"
    )
    assert [text for text, _ in unmarked_examples(markup)] == [
        "1. これは誰の本ですか。\n........佐藤さんのです。",
        "2. A: あれは何ですか。\nB: 辞書です。",
    ]
    markup = (  # no numbered lines: a Japanese line followed by its translation is an example
        "<p>Trước は là chủ ngữ.</p>"
        "<p><<寝 - ね>>る<<前 - まえ>>に、<<本 - ほん>>を<<読 - よ>>みます。Trước khi đi ngủ, tôi đọc sách.</p>"
    )
    assert [text for text, _ in unmarked_examples(markup)] == ["寝る前に、本を読みます。"]


def test_examples_keep_bold_spans_and_drop_readings_and_translations():
    markup = (
        "<p>1. もう<<甘 - あま>>いものは<<食 - た>>べ<strong>まい</strong>と思う。<br>{{Tôi sẽ không ăn đồ ngọt.}}</p>"
    )
    ((text, spans),) = examples(markup)
    assert text == "1. もう甘いものは食べまいと思う。"
    assert [text[s:e] for s, e in spans] == ["まい"]
