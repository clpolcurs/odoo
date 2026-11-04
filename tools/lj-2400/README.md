# lj-2400

Công cụ nhập sách **JLPT N2 ミニストーリーで覚える日本語能力試験ベスト単語合格2400** (giáo trình 153 trên Odoo, 23 topic,
452 phần, 2400 từ) từ ảnh chụp trang sách (folder "2400" trên Google Drive) vào Odoo qua API v1. Nghĩa và bản dịch có đủ
tiếng Việt, tiếng Anh, tiếng Trung (ADR-052 của NihonGo).

## Dữ liệu

Thư mục `data/` (hoặc biến `LJ_2400_DATA`) không đưa vào git, vì là nội dung của sách:

| Đường dẫn | Nội dung |
| --- | --- |
| `img/`, `ocr/`, `crop/` | ảnh tải từ Drive, chữ OCR của Drive cho từng ảnh, ảnh cắt phóng to |
| `raw/topicNN.json` | bản chép của một topic (định dạng ở `brief.md`) |
| `out/topicNN.json` | bài và từ vựng của topic, sẵn để ghi |
| `applied/topicNN.json` | id của bài và từng từ đã ghi |
| `hanviet.json`, `vocab_all.json` | bảng Hán Việt và mọi từ đang có trên Odoo (`fetch_all.py /hanviet …`, `fetch_all.py /vocabularies …`) |

`fixes.json` (trong git) ghi các chỗ sửa: lỗi của sách, nghĩa tiếng Việt đổi cho khỏi trùng, từ cũ ghép bằng tay.

## Các bước

1. **Chép.** Mỗi topic một agent làm theo `brief.md` (thay `{FIRST}`, `{LAST}`…): đọc ảnh, phóng to furigana và tiếng
   Trung, đối chiếu với OCR của Drive, ghi `raw/topicNN.json`. `decode.py`, `crop.py`, `ocrsave.py` là công cụ phụ.
2. **Kiểm tra.**
   - `check_readings.py`: furigana mà Sudachi đọc khác (phần lớn sách đúng: 日本 にほん, 米 こめ).
   - `check_ocr.py`: chữ Nhật, Anh, Việt mà OCR không có (phần lớn là OCR sai dấu).
   - `convert.py` báo lỗi cấu trúc: số thứ tự, nhãn loại từ lạ, lượt lời không tách được, từ trùng trên Odoo.
3. **Chuyển:** `uv run --with pykakasi python convert.py data/raw/topicNN.json data/out/topicNN.json`.
4. **Ghi:** `env -u LJ_API_KEY uv run --project ../lj-readings python apply_topic.py data/out/topicNN.json` để chạy khô
   (`/markup/preview`, bộ lọc HTML của Odoo, so từ cũ), thêm `--apply` để ghi, rồi đọc lại từng trường.
5. **Sau khi addon có `meaning_en`, `meaning_zh`** (commit 166bcc1a được deploy):
   `env -u LJ_API_KEY uv run --project ../lj-readings python move_meanings.py`, rồi thêm `--apply`.
6. **Duyệt:** `python3 -I report_fixes.py OUT.md` liệt kê mọi chỗ sửa của `fixes.json` cạnh chữ của sách (lỗi của sách,
   bản dịch, nghĩa tiếng Việt đổi cho khỏi trùng) để tác giả duyệt lại.

## Quy ước

- **Bài:**
  - mỗi topic một bài, tên `🔊<phần đầu>–<phần cuối>`, nhãn Listening, N2; topic 1 dùng lại bài 1919;
  - mỗi phần bắt đầu bằng `<p>🔊N</p>`;
  - hội thoại: mỗi lượt lời một đoạn, có `{{…}}` (Việt), `{{en: …}}`, `{{zh: …}}` ngay dưới; truyện kể: cả đoạn rồi
    ba bản dịch;
  - cách đọc `<<漢字 - よみ>>` theo furigana của sách, từ cần học tô đỏ như sách.
- **Từ vựng:**
  - động từ ở thể ます; `[する]` thành `～します`, loại từ Danh từ + Động từ nhóm 3; tính từ な thành `～「な」`;
    giữ `（と）` và `～`;
  - loại từ theo nhãn của sách (名, 動1/2/3 + 自/他, イ, ナ, 副, 接, 接尾); `接頭` chưa có loại từ trên Odoo nên để
    trống;
  - các thể chia tính bằng chính các hàm của form Odoo (`models/vocabulary.py`); Hán Việt theo bảng Hán Việt của Odoo;
  - ví dụ là đoạn truyện của phần có từ đó.
- **Từ trùng:** Odoo không cho hai từ trùng cả chữ lẫn nghĩa tiếng Việt (`UNIQUE(vocabulary, vietnamese)`). Từ của
  sách trùng với giáo trình khác (thường là N3) có bản ghi N2 riêng, với nghĩa đầy đủ hơn trong `fixes.json`.
- **Nghĩa tiếng Anh, tiếng Trung của từ:** khi addon chưa có hai trường mới, chúng nằm tạm ở đầu tab Ví dụ:
  `<p>{{en: …}}<br>{{zh: …}}</p>`. NihonGo bỏ cả hai (ADR-052); `move_meanings.py` chuyển chúng vào trường.
