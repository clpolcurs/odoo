from apply_edits import edited, problem_of
from test_translations import preview


def test_braces_go_where_the_edit_says():
    markup = "<p>へえ。Hả.</p><p>「～させられる」は、使う。<br>「～させられる」{{sử dụng khi bị bảo.}}</p>"
    new, pairs, why = edited(
        markup, [["へえ。Hả.", "へえ。{{Hả.}}"], ["「～させられる」{{sử dụng", "{{「～させられる」sử dụng"]]
    )
    assert why is None
    assert pairs == 1
    assert new == "<p>へえ。{{Hả.}}</p><p>「～させられる」は、使う。<br>{{「～させられる」sử dụng khi bị bảo.}}</p>"


def test_an_edit_changes_only_braces_and_finds_its_place_once():
    markup = "<p>うん。Ừ.</p><p>うん。Ừ.</p>"
    assert edited(markup, [["うん。Ừ.", "うん。{{Ừ.}}"]])[2] == "found 2 times instead of once: 'うん。Ừ.'"
    assert edited(markup, [["うん。Ừ.</p><p>", "うん。{{Vâng.}}</p><p>"]])[2].startswith("more than braces")


def test_only_the_expected_change_is_written():
    old = "<p>へえ。Hả.</p>"
    new = "<p>へえ。{{Hả.}}</p>"
    assert problem_of(old, new, preview(0, 0), preview(1, 0), 1) is None
    assert problem_of(old, new, preview(0), preview(1), 1) is None
    assert problem_of(old, new, preview(0, 0), preview(1, 1), 1) == "1 untagged translations more"
    assert problem_of(old, new, preview(0), preview(0), 1) == "0 translations more instead of 1"
    # braces moved to hold the whole line: as many translations as before
    moved_old = "<p>「～させられる」{{sử dụng khi bị bảo.}}</p>"
    moved_new = "<p>{{「～させられる」sử dụng khi bị bảo.}}</p>"
    assert problem_of(moved_old, moved_new, preview(1, 0), preview(1, 0), 0) is None
