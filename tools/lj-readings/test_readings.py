from collections import Counter

import pytest

from readings import RE_MARKER, RE_READING, Proposer, apply, counter_reading, paragraphs, parse_number


def marked(markup, known=None):
    return apply(markup, Proposer(known).propose(markup).markers)


def visible(markup):
    return RE_MARKER.sub(lambda m: RE_READING.sub(r"\1", m.group(1)).strip(), markup)


def test_paragraphs_drop_tags_and_keep_marked_words():
    markup = "<p><b>今日</b>は<<雨 - あめ>>です。{{Hôm nay mưa.}}</p><p>a&amp;b\u200bc</p>"
    (first, second) = paragraphs(markup)
    assert first.text == "今日は雨です。"
    assert first.marked == [False, False, False, True, False, False, False]
    assert [markup[i] if i is not None else None for i in first.sources] == ["今", "日", "は", None, "で", "す", "。"]
    assert second.text == "a&bc" and second.sources[1] is None  # an entity is not plain text of the markup


@pytest.mark.parametrize(
    ("markup", "expected"),
    [
        ("<p>彼に言って、食べる。</p>", "<p><<彼 - かれ>>に<<言 - い>>って、<<食 - た>>べる。</p>"),
        ("<p>引っ越しの準備</p>", "<p><<引 - ひ>>っ<<越 - こ>>しの<<準備 - じゅんび>></p>"),
        ("<p>お土産を買った。</p>", "<p>お<<土産 - みやげ>>を<<買 - か>>った。</p>"),
        ("<p><<日本>>語が<<上手 - じょうず>>です。</p>", "<p><<日本>><<語 - ご>>が<<上手 - じょうず>>です。</p>"),
        ("<p>何が好き？何ですか。</p>", "<p><<何 - なに>>が<<好 - す>>き？<<何 - なん>>ですか。</p>"),
    ],
)
def test_markers_wrap_the_kanji_with_their_own_reading(markup, expected):
    assert marked(markup) == expected


@pytest.mark.parametrize(
    "markup",
    [
        '<p><span title="漢字">かな</span></p>',  # attribute
        "<p><<漢字 - かんじ>></p>",  # marker
        "<p>{{漢字 tiếng Việt}}</p>",  # translation
        "<p><code>漢字</code></p>",  # pasted code
    ],
)
def test_nothing_outside_the_plain_text_is_touched(markup):
    assert marked(markup) == markup


def test_a_kanji_word_cut_by_a_tag_is_left_for_a_person():
    proposal = Proposer().propose("<p>漢<b>字</b>を書く</p>")
    assert [m.text for m in proposal.markers] == ["書"]
    assert [m.text for m in proposal.missing] == ["漢字"]


@pytest.mark.parametrize(
    ("markup", "expected"),
    [
        ("<p>3日に行く</p>", "<<3日 - みっか>>"),
        ("<p>10分待つ</p>", "<<10分 - じゅっぷん>>"),
        ("<p>30分かかる</p>", "<<30分 - さんじゅっぷん>>"),
        ("<p>1人で来た</p>", "<<1人 - ひとり>>"),
        ("<p>4月に</p>", "<<4月 - しがつ>>"),
        ("<p>家賃は3万円</p>", "<<3万円 - さんまんえん>>"),
        ("<p>1,000円です</p>", "<<1,000円 - せんえん>>"),
        ("<p>三十分待った</p>", "<<三十分 - さんじゅっぷん>>"),
        ("<p>一回につき</p>", "<<一回 - いっかい>>"),
        ("<p>二十五歳</p>", "<<二十五歳 - にじゅうごさい>>"),
    ],
)
def test_a_number_goes_into_the_marker_of_its_counter(markup, expected):
    assert expected in marked(markup)


@pytest.mark.parametrize(
    ("n", "counter", "reading"),
        [         (1, "本", "いっぽん"), (3, "本", "さんぼん"), (6, "本", "ろっぽん"), (3, "階", "さんがい"), (8,
        "歳", "はっさい"), (100, "匹", "ひゃっぴき"), (300, "本", "さんびゃっぽん"), (4, "分", "よんぷん"), (15,
        "分", "じゅうごふん"), (9, "時", "くじ"), (7, "時", "しちじ"), (14, "時間", "じゅうよじかん"), (4, "人",
        "よにん"), (20, "日", "はつか"), (17, "日", "じゅうしちにち"), (24, "日", "にじゅうよっか"), (3, "日間",
        "みっかかん"), (1, "か月", "いっかげつ"), (2024, "年", "にせんにじゅうよねん"), (8000, "円",
        "はっせんえん"), (1, "点", "いってん"), (3, "泊", "さんぱく"),
    ],
)  # fmt: skip
def test_counter_readings(n, counter, reading):
    assert counter_reading(n, counter)[0] == reading


def test_counter_readings_that_need_a_person():
    assert counter_reading(1, "日")[1]  # ついたち or いちにち
    assert counter_reading(20, "歳") == ("はたち", "20歳: はたち hay にじゅっさい")
    assert counter_reading(3, "つ") is None


def test_parse_number():
    assert [parse_number(t) for t in ("１２", "1,000", "二十五", "百", "3万", "1億2000万", "三四", "1.5")] == [
        12,
        1000,
        25,
        100,
        30000,
        120000000,
        None,
        None,
    ]


def test_the_content_decides_between_readings_sudachi_gets_wrong():
    known = {"私": Counter({"わたし": 40}), "好": Counter({"す": 12})}
    markup = "<p>私はいたずら好きです。</p>"
    proposal = Proposer(known).propose(markup)
    by_text = {m.text: m for m in proposal.markers}
    assert by_text["私"].reading == "わたし" and by_text["私"].note  # Sudachi: わたくし
    assert by_text["好"].reading == "ず" and by_text["好"].doubt  # いたずら好き: ず, the content only has す


def test_doubts_on_words_read_by_meaning():
    proposal = Proposer().propose("<p>こちらの方がいい。何で行きますか。</p>")
    doubts = {m.text: m.doubt for m in proposal.markers}
    assert doubts["方"] and doubts["何"]


def test_marking_twice_changes_nothing_and_the_visible_text_stays():
    markup = "<p>昨日、3日間<b>雨</b>が降った。<<今日 - きょう>>は晴れ。</p>"
    once = marked(markup)
    assert marked(once) == once
    assert visible(once) == visible(markup)


@pytest.mark.parametrize(
    ("markup", "expected", "doubt"),
    [
        ("<p>16万人が来た。</p>", "<<16万人 - じゅうろくまんにん>>", False),  # Sudachi reads 16 digit by digit
        ("<p>二十の国</p>", "<<二十 - にじゅう>>", False),
        ("<p>もう一つ</p>", "<<一 - ひと>>つ", False),
        ("<p>今電車が止まっています。</p>", "<<今 - いま>>", True),  # not こん of 今世紀
        ("<p>~以上(は)</p>", "<<以上 - いじょう>>(は)", False),  # the dictionary has 以上(は): brackets not read
        ("<p>何時ごろ行きますか。</p>", "<<何時 - いつ>>ごろ", True),
    ],
)
def test_words_sudachi_reads_badly(markup, expected, doubt):
    proposal = Proposer().propose(markup)
    assert expected in apply(markup, proposal.markers)
    assert any(m.doubt for m in proposal.markers) is doubt


def test_partly_marked_words_get_the_rest_of_their_reading():
    markup = "<p>昼ご<<飯 - はん>>、2<<年 - ねん>>間、病<<気 - き>>、大<<人 - ひと>>、<<日本>>語</p>"
    proposal = Proposer().propose(markup)
    assert apply(markup, proposal.markers) == (
        "<p><<昼 - ひる>>ご<<飯 - はん>>、2<<年 - ねん>><<間 - かん>>、<<病 - びょう>><<気 - き>>、大<<人 - ひと>>、"
        "<<日本>><<語 - ご>></p>"
    )
    assert [m.text for m in proposal.missing] == ["大人"]  # 人 is not ひと in 大人 (おとな): a person fixes it


@pytest.mark.parametrize(
    ("markup", "expected"),
    [
        ("<p>1日に3回飲んで。</p>", "<<1日 - いちにち>>"),  # a day, not the first of the month
        ("<p>1月1日です。</p>", "<<1日 - ついたち>>"),
        ("<p>何時に着きますか。</p>", "<<何時 - なんじ>>"),
        ("<p>何時でもいい。</p>", "<<何時 - いつ>>"),
        ("<p>他にもあります。</p>", "<<他 - ほか>>"),
    ],
)
def test_readings_that_follow_the_next_words(markup, expected):
    assert expected in marked(markup)


def test_a_long_vowel_typed_as_the_kanji_one_is_fixed_not_read():
    for markup, fixed in (
        ("<p>助けて一」</p>", "<p><<助 - たす>>けてー」</p>"),
        ("<p>ノ一残業デー</p>", "<p>ノー<<残業 - ざんぎょう>>デー</p>"),
    ):
        proposal = Proposer().propose(markup)
        assert [f.replacement for f in proposal.fixes] == ["ー"]
        assert apply(markup, proposal.markers, proposal.fixes) == fixed
    assert not Proposer().propose("<p>もう一つ</p>").fixes
