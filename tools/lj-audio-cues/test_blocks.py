from blocks import Block, blocks_of, key, speaker_of


def test_lines_of_dialogue_show_the_base_of_readings_and_no_translation():
    markup = ("<p>F: <<店 - みせ>>はどこですか。<br>{{F: Cửa hàng ở đâu?}}</p>"
              "<p>M：あそこです。{{M: Ở đằng kia.}}{{en: Over there.}}</p>")
    assert blocks_of(markup) == [
        Block("F: 店はどこですか。", "F", "店はどこですか。"),
        Block("M: あそこです。", "M", "あそこです。"),
    ]


def test_choices_questions_and_notes_are_paragraphs():
    markup = "<p>1. 機械の説明を受ける</p><p>男の人は何をしますか。</p><p>問題：正しいのはどれですか。</p>"
    assert [(b.text, b.speaker) for b in blocks_of(markup)] == [
        ("1. 機械の説明を受ける", None), ("男の人は何をしますか。", None), ("問題：正しいのはどれですか。", None),
    ]


def test_a_line_break_stays_inside_its_block():
    assert blocks_of("<p>F: はい。<br>そうです。</p><div>M: ええ</div>") == [
        Block("F: はい。\nそうです。", "F", "はい。\nそうです。"), Block("M: ええ", "M", "ええ"),
    ]


def test_escaped_markers_markers_without_reading_and_ruby_tags_show_their_base():
    markup = ("<p>木山：&lt;&lt;店 - みせ&gt;&gt;と<<駅>>と<ruby>漢字<rt>かんじ</rt></ruby>です。</p>"
              "<ul><li>A: <b>はい</b>、行きます。</li></ul>")
    assert [b.text for b in blocks_of(markup)] == ["木山: 店と駅と漢字です。", "A: はい、行きます。"]


def test_a_table_of_speaker_colon_text_rows_is_dialogue_and_any_other_table_is_left_out():
    dialogue = ("<table><tr><td>F</td><td>：</td><td>はい。</td></tr>"
                "<tr><td>男</td><td>:</td><td>いいえ。</td></tr></table>")
    assert [b.text for b in blocks_of(dialogue)] == ["F: はい。", "男: いいえ。"]
    assert blocks_of("<table><tr><td>月</td><td>火</td></tr></table><p>次へ</p>") == [Block("次へ", None, "次へ")]


def test_a_label_without_text_after_it_is_no_speaker():
    assert speaker_of("F:") == (None, "F:")
    assert speaker_of("例：はい") == (None, "例：はい")
    assert speaker_of("先生：はい") == ("先生", "はい")


def test_key_compares_as_nihongo_does():
    assert key("F：店は　どこ\nですか。") == key("F: 店はどこですか。") == "F:店はどこですか。"
    assert key("Ａ：​はい") == key("A: はい")
