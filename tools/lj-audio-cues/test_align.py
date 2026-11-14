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
    assert align.milliseconds(cues)[2] == {
        "text": "M: はい、十時からです。", "start_ms": 8450, "end_ms": round(cues[2].end * 1000),
    }


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
