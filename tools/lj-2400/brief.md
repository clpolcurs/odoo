Transcribe parts {FIRST}–{LAST} (Topic {TOPIC}) of the vocabulary book "JLPT N2 ミニストーリーで覚える日本語能力試験ベスト単語合格2400" from phone screenshots in the user's Google Drive into one JSON file. This is read-only work: do not write to Odoo, Google Drive or any git repo. The data will be imported into a dictionary, so exactness matters more than speed.

## Paths
S = {DATA} (the data folder of tools/lj-2400, LJ_2400_DATA)
- Helper scripts (already there): S/bin/decode.py, S/bin/crop.py, S/bin/ocrsave.py
- Images go in S/img (skip any image already there), crops in S/crop (name them t{TOPIC}_<image>_<n>.png), OCR text in S/ocr, output in S/raw/topic{TT}.json.
- Run Python with `python3 -I` and pass paths as arguments.

## Getting the images
Load the Drive tools first: ToolSearch with query "select:mcp__Google_Drive__search_files,mcp__Google_Drive__download_file_content,mcp__Google_Drive__read_file_content".
The images are in the Drive folder "2400" (id 1pkOjMHUcWxA6kFd1Lt1pbcTzYr1dbo4r), named IMG_9338.PNG … IMG_9659.PNG in book order (a few numbers may be missing; skip a missing one). IMG_9338 = book page 14 = part 1; IMG_9460 = page 135, holding the end of part 164 and part 165. Part {FIRST} should start around {START} (an estimate): look at that image and its neighbours to find the image where "🔊{FIRST}" begins. Then go on in order until the image where part {NEXT} starts: include the end of part {LAST} if it is on that image, do not transcribe part {NEXT}. The image before part {FIRST} may hold the end of part {PREV}: that belongs to the previous topic, leave it out.
1. File id: mcp__Google_Drive__search_files with query `parentId = '1pkOjMHUcWxA6kFd1Lt1pbcTzYr1dbo4r' and title = 'IMG_9400.PNG'` and excludeContentSnippets true.
2. mcp__Google_Drive__download_file_content(fileId): the result is too big and is saved to a file; then `python3 -I S/bin/decode.py <that saved file> S/img`.
3. View the PNG with the Read tool. Images are about 1000–1040 px wide and 1000–1750 px tall. For small text (furigana, Chinese, Vietnamese diacritics, tags), crop and enlarge: `python3 -I S/bin/crop.py <png> x0 y0 x1 y1 2 S/crop/<name>.png`, then Read the crop. Do this for every story (furigana) and every translation paragraph; do not guess small characters from the full image.
4. Google's OCR of the same image: mcp__Google_Drive__read_file_content(fileId). Write its fileContent to S/ocr/<image name>.txt (if the result is saved to a file, use `python3 -I S/bin/ocrsave.py <file> S/ocr`). Use it only as a cross-check for Japanese, English and Vietnamese; it is poor for Chinese (it mixes in Japanese and traditional glyphs). The image is always the source of truth.

## Page layout
Each part starts with "🔊N" at the top right. Then the story: dialogue turns "A：…", "B：…" (or names) or a narrative paragraph, with furigana under the kanji; the target words are red and underlined. Then numbered word entries: the number, the term (sometimes followed by a small "[する]", "[な]" etc.), the furigana of the term under it in red, sometimes a mark before the term ("+" = related word; an icon of two linked circles = pair, as in 9 冷める / 10 冷ます; describe any other icon), the tags in grey boxes (名, 動3他, 動2自, 接尾, い形, な形, 副 …), and the meanings "English/Chinese/Vietnamese" separated by "/". After the entries: the translation of the whole story, "English/Chinese/Vietnamese", separated by "/". A part can run over onto the next image. Topic title pages or other non-part pages may appear: record them in the report, skip them in the data.

## Output: S/raw/topic{TT}.json
Write the file after each part you finish (the whole file each time, with every part done so far), so that nothing is lost.
{"topic": {TOPIC}, "parts": [
  {"part": 1, "images": ["IMG_9338.PNG"], "pages": [14], "kind": "dialogue",
   "lines": [{"speaker": "A", "text": "{先週|せんしゅう}{行|い}った{駅前|えきまえ}の[[{創作|そうさく}]]{料理|りょうり}の{店|みせ}、{閉店|へいてん}するんだって。"}],
   "words": [{"no": 1, "term": "創作", "after": "[する]", "reading": "そうさく", "ruby": "{創作|そうさく}", "mark": null, "tags": ["名", "動3他"], "en": "creative, create", "zh": "创作[创作]", "vi": "sự sáng tạo, sáng tạo"}],
   "translation": {"en": "A: I heard that … B: … A: …", "zh": "A: 上周去的…", "vi": "A: Cái quán …"},
   "notes": []}
]}
Rules:
- "text": the Japanese exactly as printed, with the punctuation as printed and half-width digits/letters as printed ("300 g", "1人前"). A word with furigana is `{base|reading}`: base is exactly the characters the furigana sits over (usually only the kanji: `{行|い}った`, `{大|おお}きさ`), the reading in hiragana as printed. Kanji without furigana stay plain.
- The red, underlined span is wrapped in `[[…]]` exactly as far as the red goes: `{甘|あま}[[み]]`, `[[{冷|さ}めたら]]`, `1[[{人前|にんまえ}]]`.
- Dialogue: one line per speaker turn, the speaker label without the colon. Narrative: "kind": "narrative", one line per paragraph, "speaker": null.
- Word entries: "term" as printed without the small suffix, keeping ～; "after" the small suffix as printed or null; "reading" the furigana as printed (null when there is none, e.g. katakana words); "ruby" the term in the story notation, each furigana on its own kanji run (冷める → "{冷|さ}める", 見た目 → "{見|み}た{目|め}", ～人前 → "～{人前|にんまえ}", katakana → the term as it is); "mark" "+" / "pair" / a description / null; "tags" as printed, in order.
- Meanings and translations: copy exactly, with ~, brackets and punctuation; split only at the "/" between the three languages. If the split is ambiguous (a "/" inside a language), put the whole text in "raw" and add a note.
- Do not correct the book. If you think the book is wrong (for example a Vietnamese meaning that does not fit the Japanese word, as 824 見方 "đồng minh, bạn", which is 味方), keep the book's text and add a note such as {"no": 824, "field": "vi", "note": "…"}. Note every character you are unsure of, with the part or word number.

## Checks before you finish
- Word numbers run on with no gap or repeat; parts {FIRST}–{LAST} are all there.
- Every red span in a story belongs to one of the entries of that part (note it if not), and the reading of each entry matches the furigana of the same word in the story.
- The plain Japanese of each line (drop `{`, `|reading}`, `[[`, `]]`) agrees with the Google OCR text, and so do English and Vietnamese, apart from OCR noise. Re-check the image wherever they disagree.

## Report back (short; the data stays in the file)
The images and book pages you used (first and last), counts of parts and words, the first and last word numbers, every note or doubt, anything unusual in the layout (title pages, icons, tags not listed above, notes in the margin).
