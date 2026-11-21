import align
from blocks import blocks_of


def spoken(text, start, step=0.12):
    """Words as the recogniser gives them: one a character, `step` seconds each, from `start`."""
    return [{"start": round(start + k * step, 3), "end": round(start + (k + 1) * step, 3), "word": c}
            for k, c in enumerate(text)]


MARKUP = ("<p>1. ア ウ</p><p>男の人と女の人が話しています。</p>"
          "<p>F: 明日、会議がありますか。</p><p>M: はい、十時からです。</p><p>2. イ エ</p>")


def test_lcs_pairs_follow_both_sequences():
    assert align.lcs("あいうえお", "かあうおき") == [(0, 1), (2, 2), (4, 3)]
    assert align.lcs("", "あ") == []


def test_short_blocks_need_more_of_their_kana_heard():
    assert align.needed_ratio(3) == 0.8
    assert align.needed_ratio(12) == 0.5
    assert 0.5 < align.needed_ratio(7) < 0.8


def test_words_without_length_are_left_out():
    words = [*spoken("はい", 1.0), {"start": 9.0, "end": 9.0, "word": "ご視聴ありがとうございました"}]
    assert [c for c, _ in align.heard(words)] == ["は", "い"]


def test_the_blocks_the_audio_reads_get_cues_in_order():
    blocks = blocks_of(MARKUP)
    words = (spoken("16番", 0.5) + spoken("男の人と女の人が話しています", 2.0)
             + spoken("明日会議がありますか", 6.0) + spoken("はい十時からです", 8.5))
    cues = align.cues_of(blocks, words, onsets=[1.9, 5.9, 8.45], duration=11.0)

    assert [c.block for c in cues] == [1, 2, 3]
    assert [c.text for c in cues] == [
        "男の人と女の人が話しています。", "F: 明日、会議がありますか。", "M: はい、十時からです。",
    ]
    assert [c.start for c in cues] == [1.9, 5.9, 8.45]
    assert all(c.snapped for c in cues)
    assert cues[0].end <= cues[1].start and cues[1].end <= cues[2].start
    assert cues[2].end <= 11.0
    third = align.milliseconds(cues)[2]
    assert {key: value for key, value in third.items() if key != "marks"} == {
        "text": "M: はい、十時からです。", "start_ms": 8450, "end_ms": round(cues[2].end * 1000),
    }
    # the words after はい、: 十 時 から です
    assert [third["text"][at] for at, _ in third["marks"]] == ["十", "時", "か", "で"]


def test_a_start_with_no_silence_before_it_is_estimated_from_the_words():
    blocks = blocks_of("<p>F: 明日、会議がありますか。</p><p>M: はい、十時からです。</p>")
    words = spoken("明日会議がありますか", 1.0) + spoken("はい十時からです", 3.0)
    cues = align.cues_of(blocks, words, onsets=[], duration=6.0)
    assert [c.snapped for c in cues] == [False, False]
    assert 0.8 <= cues[0].start <= 1.3 and 2.8 <= cues[1].start <= 3.3


def test_an_audio_that_reads_another_text_gives_no_cue():
    blocks = blocks_of(MARKUP)
    cues = align.cues_of(blocks, spoken("今日はとても寒いですね", 1.0), onsets=[1.0], duration=5.0)
    assert cues == []


def test_a_filler_the_recogniser_left_out_starts_at_the_silence_before_it():
    blocks = blocks_of("<p>F: 明日、会議がありますか。</p><p>M: うーん、十時からです。</p>")
    # the recogniser heard no うーん: the line seems to start at 4.0, but the silence before it ended at 3.3
    words = spoken("明日会議がありますか", 1.0) + spoken("十時からです", 4.0)
    cues = align.cues_of(blocks, words, onsets=[0.9, 3.3], duration=6.0)
    assert [c.start for c in cues] == [0.9, 3.3]
    assert cues[1].snapped


def test_a_start_is_never_well_before_the_last_kana_of_the_line_before():
    blocks = blocks_of("<p>F: 明日、会議がありますか。</p><p>M: うーん、十時からです。</p>")
    # 1.85 ends a pause inside the line before, whose last kana is heard at 2.08: not where the next line starts
    words = spoken("明日会議がありますか", 1.0) + spoken("十時からです", 2.6)
    cues = align.cues_of(blocks, words, onsets=[0.9, 1.85], duration=6.0)
    assert cues[1].start > 2.08 - align.SMEAR
    assert not cues[1].snapped


def test_a_word_read_after_a_story_does_not_take_the_end_of_its_paragraph():
    # a word read seconds later ends with the last kana of the paragraph (渡す: た); the longest common subsequence
    # pairs the two, so the paragraph seems to last until the word, too long to be read there
    blocks = blocks_of("<p>寒くて凍えそうだった。夜明けに家に帰った。</p>")
    words = spoken("寒くて凍えそうだった夜明けに家に帰った", 1.0) + spoken("渡す", 12.0)
    cues = align.cues_of(blocks, words, onsets=[0.95, 11.9], duration=14.0)
    assert [c.block for c in cues] == [0]
    assert cues[0].start == 0.95
    assert cues[0].end < 4.0


def test_a_word_read_before_a_story_does_not_take_the_start_of_its_paragraph():
    # the recogniser missed the first word of the paragraph (寒くて); the word read before the story (寒い) would
    # take its first kana, and the paragraph would seem to start five seconds early
    blocks = blocks_of("<p>寒くて凍えそうだった。夜明けに家に帰った。</p>")
    words = spoken("寒い", 1.0) + spoken("凍えそうだった夜明けに家に帰った", 6.0)
    cues = align.cues_of(blocks, words, onsets=[0.95, 5.6], duration=9.0)
    assert [c.block for c in cues] == [0]
    assert cues[0].start == 5.6


def test_an_end_the_recogniser_missed_is_still_part_of_the_cue():
    # the recogniser missed the last words (家へ帰った); the cue lasts for about the time they take
    blocks = blocks_of("<p>寒くて凍えそうだった。夜明けに家へ帰った。</p>")
    words = spoken("寒くて凍えそうだった夜明けに", 1.0)
    cues = align.cues_of(blocks, words, onsets=[0.95], duration=9.0)
    heard_end = 1.0 + len("寒くて凍えそうだった夜明けに") * 0.12
    assert cues[0].end > heard_end + align.TAIL_SECONDS + 0.5


def test_a_word_of_one_time_step_is_heard():
    # the recogniser's times come in steps of 0.02 s; a quick ありがとうございます may get one step and no more
    words = [*spoken("はい", 31.8), {"start": 33.14, "end": 33.16, "word": "ありがとう"}]
    assert "".join(c for c, _ in align.heard(words)) == "はいありがとう"


def test_a_stage_direction_in_square_brackets_is_not_looked_for():
    blocks = blocks_of("<p>F: これです。</p><p>M: はい。［書類を確認して］では、どうぞ。</p>")
    words = spoken("これです", 1.0) + spoken("はいではどうぞ", 3.0)
    cues = align.cues_of(blocks, words, onsets=[0.9, 2.9], duration=6.0)
    assert [c.text for c in cues] == ["F: これです。", "M: はい。［書類を確認して］では、どうぞ。"]
    assert cues[1].start == 2.9


def test_a_short_line_whose_small_tsu_the_recogniser_does_not_write_is_timed():
    blocks = blocks_of("<p>F: 実は、転勤することになったんだ。</p><p>M: えっ…。</p><p>F: うん。</p>")
    words = (spoken("実は転勤することになったんだ", 1.0) + [{"start": 4.5, "end": 4.7, "word": "え?"}]
             + spoken("うん", 6.0))
    cues = align.cues_of(blocks, words, onsets=[0.9, 4.5, 5.9], duration=8.0)
    assert [c.block for c in cues] == [0, 1, 2]
    assert (cues[1].start, cues[1].ratio) == (4.5, 1.0)


def test_a_line_whose_speaker_has_a_role_is_timed_on_what_is_said():
    blocks = blocks_of("<p>中川（主任）：お疲れさま。</p><p>佐藤：あ、主任、お疲れさまです。</p>")
    words = spoken("お疲れさま", 0.0) + spoken("あ主任お疲れさまです", 1.5)
    cues = align.cues_of(blocks, words, onsets=[1.5], duration=4.0)
    assert [c.text for c in cues] == ["中川（主任）: お疲れさま。", "佐藤: あ、主任、お疲れさまです。"]


def test_the_words_inside_a_block_get_marks():
    blocks = blocks_of("<p>F: 明日、会議があります。今日は休みです。</p>")
    words = spoken("明日会議があります", 1.0) + spoken("今日は休みです", 3.0)
    [cue] = align.cues_of(blocks, words, onsets=[0.9, 2.95], duration=6.0)

    # the first word has the start of the cue; 会議 comes after 明日、, as the cue's text writes it
    assert cue.text == "F: 明日、会議があります。今日は休みです。"
    assert cue.text[cue.marks[0][0]] == "会"
    starts = {cue.text[at]: seconds for at, seconds in cue.marks}
    # a sentence start moves to the end of the silence before it, as a block start does
    assert starts["今"] == 2.95
    times = [seconds for _, seconds in cue.marks]
    assert times == sorted(times) and all(cue.start < t < cue.end for t in times)
    assert align.milliseconds([cue])[0]["marks"][0] == [cue.marks[0][0], round(cue.marks[0][1] * 1000)]


def test_marks_count_the_characters_of_the_text_a_stage_direction_and_all():
    spoken_text, where = align.spoken_map("［書類を確認して］ありがとうございます。")
    assert spoken_text == "ありがとうございます。"
    assert where[0] == 9
    blocks = blocks_of("<p>事務員：［書類を確認して］ありがとうございます。それでは、こちらへ。</p>")
    words = spoken("ありがとうございますそれではこちらへ", 1.0)
    [cue] = align.cues_of(blocks, words, onsets=[0.95], duration=5.0)
    assert {cue.text[at] for at, _ in cue.marks} >= {"そ", "こ"}


def test_a_mark_rounded_onto_the_end_of_its_cue_is_left_out():
    cue = align.Cue(0, "F: はい、そうです。", 1.0, 2.0, 1.0, True, ((6, 1.5), (8, 1.9996)))
    assert align.milliseconds([cue])[0]["marks"] == [[6, 1500]]
