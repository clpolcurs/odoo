"""convert.py RAW.json OUT.json: one topic of the 2400 book (raw transcription) -> API v1 payloads for Odoo.

RAW is the transcription (DATA/raw/topicNN.json). OUT gets:
  item      the comprehensive of the topic: title, level, tags, lesson_ids, markup
  words     one vocabulary payload per book entry, with "no" (book number) and "match" (id of an existing word to
            update, or null to create)
  report    problems for a person to look at (empty when all is well)

Data files in DATA (LJ_2400_DATA, default tools/lj-2400/data): hanviet.json and vocab_all.json (every word in Odoo,
from fetch_all.py). fixes.json next to this script holds the corrections of the book: {"<no>": {"vi": "…"}} for a
word, {"<no>": {"match": <id>}} to update an existing word, {"p<part>": {"vi": [["old", "new"]]}} for a translation.
Run with a Python that has pykakasi: uv run --with pykakasi python convert.py RAW OUT.
"""

import ast
import html
import json
import os
import re
import sys
from pathlib import Path

from pykakasi import kakasi

DATA = Path(os.environ.get("LJ_2400_DATA") or Path(__file__).resolve().parent / "data")
REPO = Path(__file__).resolve().parents[2]
ODOO_VOCABULARY = REPO / "custom_addons" / "learning_japanese" / "models" / "vocabulary.py"

BOOK = 153
TOPIC_LESSON = {topic: 1645 + topic for topic in range(1, 24)}
TOPIC_PARTS = {
    1: (1, 17),
    2: (18, 35),
    3: (36, 46),
    4: (47, 67),
    5: (68, 91),
    6: (92, 118),
    7: (119, 135),
    8: (136, 154),
    9: (155, 161),
    10: (162, 184),
    11: (185, 201),
    12: (202, 216),
    13: (217, 231),
    14: (232, 253),
    15: (254, 278),
    16: (279, 308),
    17: (309, 335),
    18: (336, 355),
    19: (356, 371),
    20: (372, 389),
    21: (390, 412),
    22: (413, 427),
    23: (428, 452),
}
# Items that already exist: Topic 1 reuses 1919 (it held part 1).
TOPIC_ITEM = {1: 1919}
RED = '<font style="color: rgb(255, 0, 0);">'

POS = {
    "名": 1,
    "動": 2,
    "い形": 3,
    "イ形": 3,
    "イ": 3,
    "な形": 4,
    "ナ形": 4,
    "ナ": 4,
    "助": 5,
    "副": 6,
    "接続": 7,
    "接": 7,
    "数": 8,
    "助数": 9,
    "疑": 10,
    "代": 11,
    "感": 12,
    "接尾": 14,
}
# tags with no part of speech in Odoo yet: the word is written without one, and the topic's notices list it
NO_POS = {"接頭", "連"}
VERB_TAG = re.compile(r"^動([123])([自他]*)$")

TOKEN = re.compile(r"\{([^{}|]+)\|([^{}|]+)\}|\[\[|\]\]")
KANJI = re.compile(r"[㐀-䶿一-鿿豈-﫿々〆ヶ]")
# a part that can be left out, printed in brackets (アマ(チュア), ほっぺ(た)): Odoo writes it 「…」, as in 四角「形」
OPTIONAL = re.compile(r"[(（]([^()（）]+)[)）]")
U_TO_I = dict(zip("うくぐすつぬぶむる", "いきぎしちにびみり", strict=True))


# ── Verb forms, computed by the very functions of the Odoo form ────────────────────────────────────────────────


def _odoo_helpers():
    tree = ast.parse(ODOO_VOCABULARY.read_text())
    namespace = {}
    body = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and all(isinstance(t, ast.Name) and t.id.isupper() for t in node.targets):
            body.append(node)
        if isinstance(node, ast.ClassDef) and node.name == "Vocabulary":
            for item in node.body:
                if (
                    isinstance(item, ast.FunctionDef)
                    and item.name.startswith("get_")
                    and any(isinstance(d, ast.Name) and d.id == "staticmethod" for d in item.decorator_list)
                ):
                    item.decorator_list = []
                    body.append(item)
    module = ast.Module(body=body, type_ignores=[])
    exec(compile(module, str(ODOO_VOCABULARY), "exec"), namespace)
    return namespace


H = _odoo_helpers()


def verb_forms(term, group):
    """The 12 forms of a verb in ます form, as the Odoo form fills them in."""
    nhom = {"group1": "nhom_1", "group2": "nhom_2", "group3": "nhom_3"}[group]
    dictionary = H["get_the_nguyen_dang"](term, nhom)
    causative_passive = H["get_the_sai_khien_thu_dong"](term, nhom)
    short = H["get_the_sai_khien_thu_dong_rut_gon"](term, nhom)
    forms = {
        "dictionary": dictionary,
        "te": H["get_the_te"](term, nhom),
        "past": H["get_the_ta"](term, nhom),
        "negative": H["get_the_phu_dinh"](term, nhom),
        "potential": H["get_the_kha_nang"](term, nhom),
        "volitional": H["get_the_y_dinh"](term, nhom),
        "imperative": H["get_the_menh_lenh"](term, nhom),
        "prohibitive": (dictionary + "な") if dictionary else None,
        "passive": H["get_the_thu_dong"](term, nhom),
        "causative": H["get_the_sai_khien"](term, nhom),
        "causative_passive": (f"{causative_passive}, {short}" if short else causative_passive),
        "conditional": H["get_the_dieu_kien"](term, nhom),
    }
    return {name: (value or None) for name, value in forms.items()}


# ── Text helpers ─────────────────────────────────────────────────────────────────────────────────────────────

KKS = kakasi()


def kata_to_hira(text):
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in text)


def hira_to_kata(text):
    return "".join(chr(ord(c) + 0x60) if "ぁ" <= c <= "ゖ" else c for c in text)


def romaji(ruby, group):
    """Hepburn, a word per kanji run with the kana after it, the ending of a verb apart: 'Samashi masu' (group 1 and 2),
    'Shoubu shimasu' (group 3), 'Tabe houdai'."""
    tokens, pos = [], 0
    for m in TOKEN.finditer(ruby):
        if m.group(1):
            if ruby[pos : m.start()]:
                if tokens:
                    tokens[-1] += ruby[pos : m.start()]
                else:
                    tokens.append(ruby[pos : m.start()])
            tokens.append(m.group(2))
            pos = m.end()
    rest = ruby[pos:]
    if tokens:
        tokens[-1] += rest
    else:
        tokens.append(rest)
    if group:
        ending = "します" if group == "group3" else "ます"
        if tokens[-1].endswith(ending) and len(tokens[-1]) > len(ending):
            tokens[-1:] = [tokens[-1][: -len(ending)], ending]
    words = [" ".join(t["hepburn"] for t in KKS.convert(kata_to_hira(token)) if t["hepburn"]) for token in tokens]
    return " ".join(w for w in words if w).strip().capitalize()


def ruby_reading(ruby):
    """'{冷|さ}める' -> 'さめる'; kana stay as they are, katakana become hiragana."""
    return kata_to_hira(TOKEN.sub(lambda m: m.group(2) if m.group(1) else "", ruby))


def plain(text):
    return TOKEN.sub(lambda m: m.group(1) if m.group(1) else "", text)


def esc(text):
    return html.escape(text, quote=False)


def ja_markup(text, problems, where):
    if text.count("[[") != text.count("]]"):
        problems.append(f"{where}: [[ ]] do not pair up")
    out, pos = [], 0
    for m in TOKEN.finditer(text):
        out.append(esc(text[pos : m.start()]))
        token = m.group(0)
        if token == "[[":
            out.append(RED)
        elif token == "]]":
            out.append("</font>")
        else:
            out.append(f"<<{m.group(1).strip()} - {m.group(2).strip()}>>")
        pos = m.end()
    out.append(esc(text[pos:]))
    rest = TOKEN.sub("", text)
    if re.search(r"[{}|]", rest):
        problems.append(f"{where}: stray {{, }} or | in {text!r}")
    if KANJI.search(TOKEN.sub(lambda m: "" if m.group(1) else m.group(0), text)):
        bare = KANJI.findall(TOKEN.sub(lambda m: "" if m.group(1) else m.group(0), text))
        problems.append(f"{where}: kanji without furigana: {''.join(bare)}")
    return "".join(out)


def split_turns(text, speakers):
    """The translation of a dialogue cut at each speaker label, in order; None if the labels are not all there."""
    starts, pos = [], 0
    for speaker in speakers:
        # a label follows a space or the end of the turn before it: "…B:", "”B:", "。B:"
        label = re.compile(r"(?:^|(?<=[\s…”\"」』。.!?！？)）~～]))" + re.escape(speaker) + r"\s*[:：]")
        m = label.search(text, pos)
        if not m or (not starts and text[: m.start()].strip()):
            return None
        starts.append(m.start())
        pos = m.end()
    return [text[a:b].strip() for a, b in zip(starts, [*starts[1:], len(text)], strict=True)]


def translations(vi, en, zh):
    parts = []
    if vi:
        parts.append("{{" + esc(vi) + "}}")
    if en:
        parts.append("{{en: " + esc(en) + "}}")
    if zh:
        parts.append("{{zh: " + esc(zh) + "}}")
    return "<br>".join(parts)


def fixed_translation(part, fixes, problems):
    """The translations of a part with the fixes of fixes.json ("p165": {"vi": [["old", "new"], ...]}) applied."""
    tr = dict(part.get("translation") or {})
    for lang, pairs in fixes.get(f"p{part['part']}", {}).items():
        for old, new in pairs:
            if old not in (tr.get(lang) or ""):
                problems.append(f"part {part['part']}: fix {old!r} not found in the {lang} translation")
            tr[lang] = (tr.get(lang) or "").replace(old, new)
    return tr


def part_markup(part, problems, fixes):
    n = part["part"]
    lines = part["lines"]
    tr = fixed_translation(part, fixes, problems)
    blocks = [f"<p>🔊{n}</p>"]
    turns = None
    if part.get("kind") == "dialogue" and all(line.get("speaker") for line in lines):
        speakers = [line["speaker"] for line in lines]
        turns = {lang: split_turns(tr.get(lang) or "", speakers) for lang in ("vi", "en", "zh")}
        missing = [lang for lang, cut in turns.items() if cut is None]
        if missing:
            problems.append(f"part {n}: speaker labels not found in the {', '.join(missing)} translation")
            turns = None
    for i, line in enumerate(lines):
        ja = ja_markup(line["text"], problems, f"part {n} line {i + 1}")
        speaker = line.get("speaker")
        head = f"{esc(speaker)}: " if speaker else ""
        if turns:
            tail = translations(turns["vi"][i], turns["en"][i], turns["zh"][i])
        elif i == len(lines) - 1:
            tail = translations(tr.get("vi"), tr.get("en"), tr.get("zh"))
        else:
            tail = ""
        blocks.append(f"<p>{head}{ja}" + (f"<br>{tail}" if tail else "") + "</p>")
    return "".join(blocks)


# ── Words ────────────────────────────────────────────────────────────────────────────────────────────────────


def to_masu(term, hira, group, problems, where):
    if group == "group2":
        if term.endswith("る") and hira.endswith("る"):
            return term[:-1] + "ます", hira[:-1] + "ます"
    elif group == "group1":
        if term[-1] in U_TO_I and hira[-1] in U_TO_I:
            return term[:-1] + U_TO_I[term[-1]] + "ます", hira[:-1] + U_TO_I[hira[-1]] + "ます"
    elif group == "group3":
        if term.endswith("する"):
            return term[:-2] + "します", hira[:-2] + "します"
        if term.endswith(("来る", "くる")):
            return term[:-2] + "来ます" if term.endswith("来る") else term[:-2] + "きます", hira[:-2] + "きます"
    problems.append(f"{where}: cannot put {term} ({group}) in ます form")
    return term, hira


def word_payload(word, part_markups, topic, hanviet, fixes, problems, notices):
    no = word["no"]
    where = f"word {no} {word['term']}"
    tags = fixes.get(str(no), {}).get("tags") or word.get("tags") or []
    after = (word.get("after") or "").strip()
    if after == "な":
        after = "[な]"
    fix = fixes.get(str(no), {})
    term = fix.get("term", word["term"])
    ruby = fix.get("ruby", word.get("ruby") or term)
    if plain(ruby) != term:
        problems.append(f"{where}: ruby {ruby!r} does not spell the term")
    # ～(と) and ～な printed full size as part of the term: the same as a small (と) or [な]
    for tail, suffix in (("(と)", "（と）"), ("（と）", "（と）")):
        if term.endswith(tail) and not after:
            term, ruby, after = term[: -len(tail)], ruby[: -len(tail)], suffix
    term, ruby = OPTIONAL.sub(r"「\1」", term), OPTIONAL.sub(r"「\1」", ruby)
    if term.endswith("な") and not after and any(t in ("ナ", "ナ形", "な形") for t in tags):
        term, ruby, after = term[:-1], ruby[:-1], "[な]"
    hira = ruby_reading(ruby)

    pos, group, intransitive = [], None, None
    for tag in tags:
        verb = VERB_TAG.match(tag)
        if verb:
            pos.append(POS["動"])
            group = f"group{verb.group(1)}"
            if "自" in verb.group(2) and "他" not in verb.group(2):
                intransitive = True
            elif "他" in verb.group(2) and "自" not in verb.group(2):
                intransitive = False
        elif tag in POS:
            pos.append(POS[tag])
        elif tag in NO_POS:
            notices.append(f"{where}: tag {tag} has no part of speech in Odoo; written without one")
        else:
            problems.append(f"{where}: no part of speech for tag {tag!r}")
    pos = list(dict.fromkeys(pos))

    suru = after in ("[する]", "［する］")
    if suru:
        term, hira, ruby = term + "します", hira + "します", ruby + "します"
        if group != "group3":
            problems.append(f"{where}: [する] without 動3")
            group = "group3"
    elif group:
        dictionary = term
        term, hira = to_masu(term, hira, group, problems, where)
        # the ruby ends with the same kana as the dictionary form: swap that ending for the ます one
        pairs = enumerate(zip(dictionary, term, strict=False))
        k = next((i for i, (a, b) in pairs if a != b), min(len(dictionary), len(term)))
        if ruby.endswith(dictionary[k:]):
            ruby = ruby[: len(ruby) - len(dictionary) + k] + term[k:]
        else:
            problems.append(f"{where}: ruby {ruby!r} does not end like {dictionary}")
    if after in ("[な]", "［な］") or (not after and POS["な形"] in pos and not term.endswith("「な」")):
        term, hira = term + "「な」", hira + "「な」"
    elif after in ("（と）", "(と)", "[と]", "［と］"):
        term, hira = term + "（と）", hira + "（と）"
    elif after and not suru and after not in ("[な]", "［な］"):
        problems.append(f"{where}: unknown suffix {after!r}")

    payload = {
        "term": term,
        "hiragana": hira,
        "katakana": hira_to_kata(hira),
        "romaji": romaji(ruby, group),
        "meaning_vi": fix.get("vi", word.get("vi")),
        "meaning_en": fix.get("en", word.get("en")),
        "meaning_zh": fix.get("zh", word.get("zh")),
        "han_viet": " ".join(hanviet[c] for c in term if c in hanviet) or None,
        "level": "N2",
        "part_of_speech_ids": pos,
        "lesson_ids": [TOPIC_LESSON[topic]],
        "examples_markup": part_markups[word["part"]],
        "verb_group": group,
        "is_intransitive": bool(intransitive),
        "forms": verb_forms(term, group) if group else {name: None for name in verb_forms("します", "group3")},
    }
    for lang in ("vi", "en", "zh"):
        if not payload[f"meaning_{lang}"]:
            problems.append(f"{where}: no {lang} meaning")
    return payload


def base_of(term):
    for suffix in ("します", "「な」", "（と）"):
        if term.endswith(suffix):
            return term[: -len(suffix)]
    return term


def match_existing(payloads, existing, problems):
    """Pair each existing word of the topic with the book entry it is: same term, else same base."""
    by_term = {p["term"]: p for p in payloads}
    by_base = {}
    for p in payloads:
        by_base.setdefault(base_of(p["term"]), []).append(p)
    taken = {p["match"] for p in payloads if p.get("match")}
    for record in existing:
        if record["id"] in taken:
            continue
        target = by_term.get(record["term"])
        if target is None:
            candidates = by_base.get(base_of(record["term"]), [])
            target = candidates[0] if len(candidates) == 1 else None
        if target is None or target.get("match"):
            problems.append(f"existing word {record['id']} {record['term']}: no book entry to update")
            continue
        target["match"] = record["id"]


def convert(raw, hanviet, every_word, fixes):
    topic = raw["topic"]
    first, last = TOPIC_PARTS[topic]
    problems, notices = [], []
    parts = sorted(raw["parts"], key=lambda p: p["part"])
    numbers = [p["part"] for p in parts]
    if numbers != list(range(first, last + 1)):
        problems.append(f"parts {numbers[:1]}…{numbers[-1:]} are not {first}–{last} without a gap")
    markups = {p["part"]: part_markup(p, problems, fixes) for p in parts}

    words = []
    for p in parts:
        for word in p["words"]:
            words.append({**word, "part": p["part"]})
    nos = [w["no"] for w in words]
    if nos != list(range(nos[0], nos[0] + len(nos))) if nos else True:
        problems.append(f"word numbers are not consecutive: {nos[:1]}…{nos[-1:]}")

    payloads = []
    for word in words:
        payload = word_payload(word, markups, topic, hanviet, fixes, problems, notices)
        payloads.append({"no": word["no"], "match": fixes.get(str(word["no"]), {}).get("match"), **payload})

    lesson = TOPIC_LESSON[topic]
    existing = [w for w in every_word if lesson in (w.get("lesson_ids") or [])]
    match_existing(payloads, existing, problems)

    # term + meaning_vi is unique in Odoo, across every book
    taken = {(w["term"], w.get("meaning_vi")): w["id"] for w in every_word}
    seen = {}
    for p in payloads:
        key = (p["term"], p["meaning_vi"])
        owner = taken.get(key)
        if owner and owner != p["match"]:
            problems.append(f"word {p['no']} {p['term']}: same term and meaning_vi as word {owner} already in Odoo")
        if key in seen:
            problems.append(f"word {p['no']} {p['term']}: same term and meaning_vi as book word {seen[key]}")
        seen[key] = p["no"]

    item = {
        "id": TOPIC_ITEM.get(topic),
        "title": f"🔊{first}–{last}",
        "level": "N2",
        "tags": ["Listening"],
        "lesson_ids": [lesson],
        "markup": "".join(markups[n] for n in sorted(markups)),
    }
    return {"topic": topic, "item": item, "words": payloads, "report": problems, "notices": notices}


def main():
    raw = json.loads(Path(sys.argv[1]).read_text())
    hanviet = {}
    for entry in json.loads(Path(DATA / "hanviet.json").read_text()):
        if entry.get("kanji") and entry.get("han_viet") and entry["kanji"] not in hanviet:
            hanviet[entry["kanji"]] = entry["han_viet"].strip()
    every_word = json.loads(Path(DATA / "vocab_all.json").read_text())
    fixes_path = Path(__file__).resolve().parent / "fixes.json"
    fixes = json.loads(Path(fixes_path).read_text()) if fixes_path.exists() else {}
    result = convert(raw, hanviet, every_word, fixes)
    Path(sys.argv[2]).write_text(json.dumps(result, ensure_ascii=False, indent=1))
    print(
        f"topic {result['topic']}: {len(result['words'])} words "
        f"({sum(1 for w in result['words'] if w['match'])} existing), markup {len(result['item']['markup'])} chars, "
        f"{len(result['report'])} problems"
    )
    for problem in result["report"]:
        print("  -", problem)
    for notice in result["notices"]:
        print("  note:", notice)


if __name__ == "__main__":
    main()
