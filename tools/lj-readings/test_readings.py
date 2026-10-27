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
        ("<p>何時ごろ行きますか。</p>", "<<何時 - なんじ>>ごろ", True),
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
        ("<p>何時から何時までですか。</p>", "<<何時 - なんじ>>から"),
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


def test_markers_without_reading_are_marked_again_in_the_house_style():
    for markup, expected in (
        (
            "<p><<強く>><<握手した>>。<<3日>>に<<kỳ nghỉ hè>>、<<人 - ひと>></p>",
            "<p><<強 - つよ>>く<<握手 - あくしゅ>>した。<<3日 - みっか>>に<<kỳ nghỉ hè>>、<<人 - ひと>></p>",
        ),
        ("<p>22<<歳>>になりました。</p>", "<p><<22歳 - にじゅうにさい>>になりました。</p>"),  # the number joins
        ("<p><<学>><<校>>へ<<行 - い>>く</p>", "<p><<学校 - がっこう>>へ<<行 - い>>く</p>"),  # one word, two markers
    ):
        proposal = Proposer().propose_auto(markup)
        assert apply(markup, proposal.markers, proposal.fixes) == expected
        assert not proposal.missing


def test_a_marker_without_reading_in_a_translation_is_kept():
    proposal = Proposer().propose_auto("<p>{{<<日本>>}}</p>")
    assert not proposal.markers and not proposal.fixes
    assert [m.why for m in proposal.missing] == ["nằm trong bản dịch hoặc khối code"]


@pytest.mark.parametrize(
    "markup, expected",
    [
        ("<p>林檎を四つ、卵を八つ買った。</p>", "<<四 - よっ>>つ、<<卵 - たまご>>を<<八 - やっ>>つ"),  # not よん, よう
        ("<p>中国のお茶です。</p>", "<<中国 - ちゅうごく>>の"),  # a place name keeps its reading
        ("<p>今何時ですか。</p>", "<<何時 - なんじ>>ですか"),
        ("<p>松本良子さん</p>", "<<良子 - よしこ>>さん"),
    ],
)
def test_counted_things_place_names_and_times(markup, expected):
    assert expected in marked(markup)


@pytest.mark.parametrize(
    "markup, expected",
    [
        ("<p>重そうですね。</p>", "<<重 - おも>>そう"),  # not 重曹 じゅうそう
        ("<p>休みは何曜日ですか。</p>", "<<日 - び>>ですか"),
        ("<p>ピアノが弾けません。</p>", "<<弾 - ひ>>けません"),
        ("<p>子供を来させます。</p>", "<<来 - こ>>させます"),
    ],
)
def test_readings_sudachi_takes_for_another_word(markup, expected):
    assert expected in marked(markup)


@pytest.mark.parametrize(
    "markup, expected",
    [
        ("<p>部屋中が散らかって、今日中に片付ける。</p>", "<<部屋 - へや>><<中 - じゅう>>が"),
        ("<p>興味深い話を聞いた。</p>", "<<興味深 - きょうみぶか>>い"),  # one word of WORDS, not 興味 + 深い
        ("<p>一晩泊まった。</p>", "<<一晩 - ひとばん>>"),
        ("<p>現在形を使う。</p>", "<<形 - けい>>を"),
        ("<p>数を数える。</p>", "<<数 - かず>>を"),
        ("<p>「…」の数（1000円）と言う</p>", "<<数 - かず>>（"),
        ("<p>猫を抱いたら、毛だらけになった。</p>", "<<抱 - だ>>いたら"),
        ("<p>3時頃に着いた。</p>", "<<頃 - ごろ>>"),
        ("<p>十分気をつけてください。</p>", "<<十分 - じゅうぶん>>"),
        ("<p>9時十分に着いた。</p>", "<<十分 - じゅっぷん>>"),
        ("<p>上田さんって人</p>", "<<上田 - うえだ>>"),  # a name keeps its reading
        ("<p>何着ていく？</p>", "<<何 - なに>>"),
        ("<p>体の調子がいい。</p>", "<<体 - からだ>>"),
        ("<p>部屋中フィギュアでいっぱいだ。</p>", "<<部屋 - へや>><<中 - じゅう>>フィギュア"),  # Sudachi: a prefix
        ("<p>午前中に来る。</p>", "<<午前中 - ごぜんちゅう>>"),
        ("<p>といった小動物の数も減った。</p>", "<<小動物 - しょうどうぶつ>>の<<数 - かず>>も"),  # 小動 + 物の数
        ("<p>この前、行ったんだけど</p>", "この<<前 - まえ>>、"),
        ("<p>宝くじ1億円当たったなんて</p>", "<<当 - あ>>たった"),  # not 当 (あたり) + たった
        ("<p>だって腹減ってるんだもん。</p>", "<<腹 - はら>><<減 - へ>>って"),
        ("<p>休館日以外も閉まっている。</p>", "<<休館 - きゅうかん>><<日 - び>>"),
        ("<p>引っ越し日を決めた。</p>", "<<日 - び>>を"),
        ("<p>住み難い町だ。</p>", "<<難 - にく>>い"),
        ("<p>りんご等を買った。1等になった。</p>", "<<等 - など>>を"),
        ("<p>毎日用品を買う。日用品を買う。</p>", "<<日用品 - にちようひん>>を"),
    ],
)
def test_words_sudachi_splits_or_misreads(markup, expected):
    assert expected in marked(markup)


@pytest.mark.parametrize(
    "markup, expected",
    [
        ("<p>パスポート は 他 の 所 に</p>", "<<他 - ほか>> の"),  # Minna no Nihongo: spaces between words
        ("<p>これは 何 と 読みますか。</p>", "<<何 - なん>> と"),
        ("<p>こちらの 方 が いいです。</p>", "<<方 - ほう>> が"),
        ("<p>答え：........7時です。</p>", "<<7時 - しちじ>>"),  # dots, not a decimal point
        ("<p>玉ねぎ（1/4個）</p>", "1/4<<個 - こ>>"),  # a fraction stays out of the counter
        ("<p>住み 難いですか。</p>", "<<難 - にく>>いですか"),
        ("<p>覚え 難いし、</p>", "<<難 - にく>>いし"),
    ],
)
def test_spaces_dots_and_fractions_around_words(markup, expected):
    assert expected in marked(markup)


@pytest.mark.parametrize(
    "markup, expected",
    [
        ("<p>右の方です。</p>", "<<方 - ほう>>です"),  # a direction, not a person
        ("<p>綺麗な方ですね。</p>", "<<方 - かた>>ですね"),
        ("<p>N2レベル以上の方に限り</p>", "<<方 - かた>>に"),
        ("<p>一番上の方にある。</p>", "<<方 - ほう>>に"),
        ("<p>このカレー、辛すぎて食べられない。</p>", "<<辛 - から>>すぎて"),
        ("<p>毎日残業で、仕事辛くないですか。</p>", "<<辛 - つら>>くない"),
    ],
)
def test_readings_chosen_by_the_words_around(markup, expected):
    assert expected in marked(markup)


@pytest.mark.parametrize(
    "markup, expected",
    [
        ("<p>と改まった形で話す。</p>", "<<形 - かたち>>で"),  # the た of a verb, not the た形
        ("<p>少ない形</p>", "<<形 - かたち>>"),
        ("<p>「ます」形を使う。</p>", "<<形 - けい>>を"),
        ("<p>、ます形を使う。</p>", "<<形 - けい>>を"),
        ("<p>和、洋、中なんでもある。</p>", "<<中 - ちゅう>>なんでも"),
        ("<p>小さいトマトなら鉢でもできる。</p>", "<<鉢 - はち>>でも"),  # Sudachi: ばち
        ("<p>お降りの際は足元にご注意ください。</p>", "お<<降 - お>>りの"),
        ("<p>机の下でメールを打っている。</p>", "<<下 - した>>で"),
        ("<p>実ができはじめたら</p>", "<<実 - み>>が"),
        ("<p>新聞を火の傍に置いたら</p>", "<<傍 - そば>>に"),
        ("<p>五分咲き、満開</p>", "<<五分 - ごぶ>>"),
        ("<p>ジョギングなら金もかからないし。</p>", "<<金 - かね>>も"),
        ("<p>おなかが空いてしょうがない。</p>", "<<空 - す>>いて"),
        ("<p>テニスコートは空いてますか。</p>", "<<空 - あ>>いて"),
        ("<p>開かないわけだ、かぎがかかっているよ。</p>", "<<開 - あ>>かない"),
        ("<p>銀行が開いているうちに</p>", "<<開 - あ>>いている"),
        ("<p>画像ファイルを開いたとたん</p>", "<<開 - ひら>>いた"),
        ("<p>会議が開かれた。</p>", "<<開 - ひら>>かれた"),
    ],
)
def test_forms_and_foods(markup, expected):
    assert expected in marked(markup)


def test_a_reading_sudachi_gives_for_a_symbol_is_not_written():
    proposal = Proposer().propose("<p>禄々なペット</p>")
    assert not [m for m in proposal.markers if m.text == "々"]
    assert [m.text for m in proposal.missing] == ["々"]


def test_a_name_sudachi_makes_across_a_marker_is_read_in_pieces():
    assert "<<親 - おや>>に" in marked("<p>あの<<時 - とき>>親に反対されても</p>")  # not the name 時親 (ときちか)


def test_a_marker_with_a_typo_waits_for_its_fix():
    markup = "<p><<山由>>さんと<<話す>></p>"
    proposal = Proposer().propose_auto(markup, keep=("山由",))
    assert apply(markup, proposal.markers, proposal.fixes) == "<p><<山由>>さんと<<話 - はな>>す</p>"
    assert [(m.text, m.why) for m in proposal.missing] == [("山由", "lỗi gõ, chờ sửa")]


def test_a_word_cut_short_by_a_typo_is_read_and_questioned():
    (marker,) = [m for m in Proposer().propose("<p>とっておいたお好、全部食べた。</p>").markers if m.text == "好"]
    assert marker.reading == "この" and "お好み" in marker.doubt
