# lj-readings

Công cụ đề xuất và ghi **cách đọc** cho các chữ Hán chưa nằm trong dấu `<<漢字 - よみ>>` trong markup của addon
Odoo `learning_japanese`. Đây là mục QA `kanji_without_reading`: chữ Hán ngoài dấu thì không có furigana.

## Cách đề xuất

- Sudachi (chế độ tách C) đọc cả đoạn, kể cả các từ đã có dấu, để có ngữ cảnh.
- Dấu chỉ bọc phần chữ Hán, cách đọc là của chính phần đó, giống các dấu đã ghi tay: `<<言 - い>>って`,
  `<<食 - た>>べる`, `<<引 - ひ>>っ<<越 - こ>>し`.
- Số đứng trước đơn vị đếm được gộp vào cùng một dấu, ví dụ `<<3日 - みっか>>`, `<<10分 - じゅっぷん>>`,
  `<<1人 - ひとり>>`, `<<3万円 - さんまんえん>>`. Cách đọc lấy từ bảng số đếm trong `readings.py` (âm biến っ, ぱ, ば),
  không lấy của Sudachi, vì Sudachi đọc 10 là いちれい.
- 何 đọc なん khi đứng trước で, だ, の, と, て, ど và đơn vị đếm; ở các chỗ khác đọc なに.
- Một danh từ đứng riêng mà Sudachi đọc khác mọi cách ghi tay trong nội dung đã xuất bản thì lấy theo nội dung:
  私 わたし, 日本 にほん, 明日 あした, 富士山 ふじさん. Chữ Hán nằm trong từ dài hơn (好 của いたずら好き, 店 của
  駅前店) thì không lấy theo nội dung mà gắn cờ cần xem.
- Từ đã có dấu một phần thì lấy phần còn lại của cách đọc: 2<<年 - ねん>>間 → 間 = かん. Nếu dấu cũ không ghi cách
  đọc thì tách theo từ ngắn của Sudachi.
- 一 đứng ngay sau katakana (ノ一残業) hoặc sau kana và trước dấu câu (助けて一」) là dấu kéo dài ー gõ nhầm: đề xuất
  sửa thành ー (`fixes` trong file đề xuất) chứ không ghi cách đọc.
- Không đụng vào thẻ HTML, dấu có sẵn, bản dịch `{{...}}`, khối `<pre>`/`<code>`. Chữ hiển thị giữ nguyên, trừ các
  chỗ gõ nhầm trong `fixes`.
- Những chỗ cần người xem (`doubt`) gồm:
  - từ đọc theo nghĩa, liệt kê trong `AMBIGUOUS` (方, 家, 後, 間, 皆, 今日…);
  - tên riêng chưa có cách đọc nào trong nội dung;
  - 何で, 1日, 20歳;
  - 今 đứng trước danh từ;
  - chữ mà nội dung đang ghi cách đọc khác.

## Dấu không ghi cách đọc (`--auto`)

Mục QA `auto_readings`: dấu như `<<状態>>`, `<<強く>>` không ghi cách đọc, nên Odoo để pykakasi đoán furigana.
`propose.py --auto` bỏ ngoặc của các dấu đó rồi đề xuất lại như với chữ Hán chưa có dấu, theo cùng các quy tắc:

- `<<強く>>` → `<<強 - つよ>>く`, `<<取り入れる>>` → `<<取 - と>>り<<入 - い>>れる`;
- số đứng ngoài dấu được gộp vào: `22<<歳>>` → `<<22歳 - にじゅうにさい>>`; một từ chia hai dấu được gộp lại:
  `<<学>><<校>>` → `<<学校 - がっこう>>`;
- dấu nào không phủ hết được chữ Hán của nó, hoặc nằm trong bản dịch `{{...}}`, thì giữ nguyên và ghi trong báo cáo;
  dấu không có chữ Hán (chữ Việt, kana) cũng được liệt kê riêng.

Đề xuất nằm ở `proposals/auto/`. Việc bỏ ngoặc là `fixes`; dấu mới được đặt vào markup sau khi đã làm các `fixes` đó,
nên `apply.py` dùng được như với đề xuất thường.

## Quy trình

```bash
cd tools/lj-readings
uv sync                                                    # Python ≥ 3.11, sudachipy, SudachiDict core
uv run python fetch.py                                     # tải bài đã xuất bản (Reading, Listening, Grammar) vào data/
uv run python propose.py                                   # proposals/<sách>.json và <sách>_report.json cho mọi sách
uv run python propose.py --auto 158                        # proposals/auto/: dấu không ghi cách đọc
uv run python apply.py proposals/158-minna-1.json          # kiểm tra với Odoo, không ghi
uv run python apply.py proposals/158-minna-1.json --apply  # chỉ chạy sau khi đã duyệt
uv run pytest -q
```

- Key API giống `tools/lj-grammar`: biến `LJ_API_KEY`, hoặc network secret của môi trường cloud Claude Code (khi đó để
  trống `LJ_API_KEY`).
- Mỗi file đề xuất gắn với phiên bản của từng bài. Bài nào bị sửa sau khi đề xuất thì `apply.py` bỏ qua; khi đó chạy
  lại `fetch.py` và `propose.py`.
- `apply.py` chỉ ghi một bài khi đủ bốn điều kiện:
  - chữ hiển thị không đổi, trừ các chỗ gõ nhầm trong `fixes`;
  - số cách đọc ghi rõ tăng đúng bằng số dấu đề xuất;
  - `/markup/preview` không báo lỗi markup mới;
  - markup đi qua bộ lọc HTML của Odoo (`html_sanitize` trong `odoo/tools/mail.py` của repo, xem `odoo_html.py`)
    mà đọc lại vẫn y nguyên.
- Markup được gửi với `<<` đã escape thành `&lt;&lt;`, giống cách trình soạn thảo Odoo lưu. Nếu gửi nguyên, bộ lọc
  đọc `<<kỳ nghỉ hè>>` thành thẻ `<kỳ>` và xoá mất chữ.
- `propose.py` bỏ qua các bài trong `BY_HAND`, là những bài phải sửa markup bằng tay trước.
- `data/` và các file `*_report.json` không được commit.
