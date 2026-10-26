# lj-mcp

MCP server cho phép Claude (qua Claude Code) đọc và sửa nội dung của addon Odoo `learning_japanese`:
bài đọc, bài nghe, điểm ngữ pháp, từ vựng, giáo trình. Server gọi REST API `/api/lj/v1` của addon
(hợp đồng: [`custom_addons/learning_japanese/static/api/openapi.yaml`](../../custom_addons/learning_japanese/static/api/openapi.yaml))
bằng API key của một user kỹ thuật.

- Chạy trên máy của bạn (hoặc trong môi trường cloud của Claude Code), nói chuyện với Claude Code qua stdio.
- Mọi thao tác ghi dùng khóa lạc quan: `version` đọc được gửi lại trong `If-Match`. Lỗi API được trả cho Claude
  kèm mã HTTP, `code`, `detail`, lỗi từng trường và `current_version`, nên Claude có thể đọc lại rồi thử lại.
- Audio từ URL do lj-mcp tự tải về rồi upload lên Odoo: server Odoo không bao giờ tự tải URL (chống SSRF).

## Yêu cầu

- [uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`). uv tự lo Python ≥ 3.11 và
  các thư viện (`mcp`, `httpx`) đúng theo `uv.lock`.
- Odoo đã nâng cấp module `learning_japanese` có API v1 (xem README của addon).
- Claude Code.

## 1. Tạo user kỹ thuật `claude-mcp` trong Odoo

1. Settings → Users & Companies → Users → **New**: Name `Claude MCP`, Login `claude-mcp`, loại Internal User.
2. Cho user vào nhóm **Learning Japanese Admin** (nhóm này đã bao gồm *Learning Japanese Read Only*).
   Nếu form user không hiện nhóm này: bật Developer mode → Settings → Users & Companies → Groups →
   mở **Learning Japanese Admin** → tab Users → thêm `claude-mcp`.
3. Đặt mật khẩu cho user (⚙ Action → Change Password); cần mật khẩu này để tạo API key.

## 2. Tạo API key

1. Đăng nhập bằng `claude-mcp` (nên dùng cửa sổ ẩn danh).
2. Avatar góc phải → **Preferences** → tab **Account Security** → **New API Key**, nhập lại mật khẩu,
   đặt tên (ví dụ `lj-mcp`) và chọn thời hạn. Odoo 19 chỉ cho tạo key tối đa 90 ngày qua giao diện; key dài hạn
   hơn thì tạo bằng Odoo shell như trong README của addon (thay login bằng `claude-mcp`).
3. Copy key ngay: Odoo chỉ hiện key một lần.
4. Kiểm tra (`can_write` phải là `true`):
   ```bash
   curl -H "Authorization: Bearer $LJ_API_KEY" https://oht-t4-hcet.com/api/lj/v1/meta
   ```

## 3. Dùng với Claude Code trên máy

```bash
export LJ_API_KEY='<key của claude-mcp>'   # có thể đặt trong ~/.bashrc, ~/.zshrc hoặc trình quản lý secret
cd /đường/dẫn/tới/odoo                      # gốc repo, nơi có .mcp.json
claude
```

- File `.mcp.json` ở gốc repo khai báo server `learning-japanese` (phạm vi project). Lần đầu mở repo,
  Claude Code hỏi có dùng server này không: chọn đồng ý. Gõ `/mcp` để xem trạng thái và danh sách tool.
- Claude Code thay `${LJ_API_KEY}` bằng biến môi trường lúc khởi động, nên đừng ghi key vào file.
  Đổi key thì export lại rồi khởi động lại Claude Code.
- Server chạy bằng `uv run --directory tools/lj-mcp lj-mcp`; lần đầu uv tải thư viện nên mất vài giây.
- Thiếu `LJ_API_KEY` thì server vẫn chạy và vẫn liệt kê tool, nhưng mọi lời gọi tool báo lỗi hướng dẫn tạo key.

## 4. Dùng trong môi trường cloud của Claude Code

Mở menu môi trường (cloud environment) trên thanh tiêu đề của session → **Edit**:

- **Secret**: thêm `LJ_API_KEY` ở mục **Network secrets** (app cũ gọi là **API credentials**) nếu có mục này,
  nếu không thì thêm biến môi trường `LJ_API_KEY`. Chỉ session mới nhận giá trị mới.
- **Network access**: chọn mức **Limited** và thêm `oht-t4-hcet.com` vào **Allowed domains**, giữ ô
  **Allow package managers** để uv tải được thư viện từ PyPI (app cũ: mức **Custom**, có ô dùng danh sách
  package manager mặc định). Chi tiết: <https://code.claude.com/docs/en/cloud-environments#network-access>.
  Muốn dùng `lj_set_audio_from_url` thì host chứa file audio cũng phải nằm trong Allowed domains.
- Môi trường cần có `uv` (image mặc định đã có; nếu không, cài trong setup script).

## Cấu hình

| Biến | Mặc định | Ý nghĩa |
| --- | --- | --- |
| `LJ_BASE_URL` | `https://oht-t4-hcet.com` | URL gốc của Odoo (bỏ `/` ở cuối); API là `${LJ_BASE_URL}/api/lj/v1`. |
| `LJ_API_KEY` | bắt buộc | API key của `claude-mcp`, gửi trong `Authorization: Bearer`. lj-mcp không bao giờ ghi log hay in key. |
| `LJ_ALLOW_DELETE` | tắt | `1` hoặc `true` để có thêm hai tool xóa. |
| `LJ_TIMEOUT` | `30` | Timeout (giây) cho mỗi request tới Odoo và mỗi lần tải audio. |

## Tool

Tool chỉ đọc:

| Tool | Việc làm | API |
| --- | --- | --- |
| `lj_search_comprehensives` | Tìm bài (đọc, nghe, ngữ pháp, ví dụ...) theo `q`, `level`, `tag`, `book_id`, `lesson_id`, `published`; trả dạng tóm tắt, có phân trang | `GET /comprehensives` |
| `lj_get_comprehensive` | Một bài đầy đủ: markup, mẫu ngữ pháp, ghi đè, audio và `version`; HTML sinh ra (`html_hover`, `html_ruby`) chỉ khi `include_html=true` | `GET /comprehensives/{id}` |
| `lj_list_books` | Danh sách giáo trình kèm bài học | `GET /books` |
| `lj_get_book` | Một giáo trình kèm bài học và tóm tắt các bài của nó (tối đa 100, đọc tiếp bằng `lj_search_comprehensives`) | `GET /books/{id}`, `GET /comprehensives?book_id=` |
| `lj_search_grammar` | Tìm điểm ngữ pháp (bài có tag chứa "grammar" hoặc "ngữ pháp") | `GET /comprehensives?grammar=true` |
| `lj_list_catalog` | Tra tên và id mà các tool khác cần: tag, bài học (lesson), chủ đề từ vựng, từ loại, Hán Việt | `GET /tags`, `/lessons`, `/context-tags`, `/parts-of-speech`, `/hanviet` |
| `lj_search_vocabulary` | Tìm từ vựng | `GET /vocabularies` |
| `lj_get_vocabulary` | Một từ vựng và `version` | `GET /vocabularies/{id}` |
| `lj_preview_markup` | Chuyển đổi thử markup như khi lưu trong Odoo và báo lỗi; không lưu gì (HTML chỉ khi `include_html=true`) | `POST /markup/preview` |
| `lj_list_issues` | Báo cáo QA: những bài cần sửa trước khi lên NihonGo | `GET /qa/issues` |

Tool ghi:

| Tool | Việc làm | API |
| --- | --- | --- |
| `lj_create_comprehensive` | Tạo bài | `POST /comprehensives` |
| `lj_update_comprehensive` | Sửa các trường được truyền; cần `version` | `PATCH /comprehensives/{id}` |
| `lj_set_audio_from_url` | lj-mcp tải audio (http/https, theo redirect, ≤ 30 MiB, phải là audio) rồi upload | `PUT /comprehensives/{id}/audio` |
| `lj_set_audio_from_file` | Upload file audio trên máy (đường dẫn tuyệt đối) | `PUT /comprehensives/{id}/audio` |
| `lj_create_vocabulary` | Tạo từ vựng | `POST /vocabularies` |
| `lj_update_vocabulary` | Sửa từ vựng; cần `version` | `PATCH /vocabularies/{id}` |
| `lj_bulk_update_vocabulary` | Tạo/sửa tối đa 100 từ trong một transaction; lỗi ghi rõ `index` của từng mục | `POST /vocabularies/bulk` |
| `lj_link_lesson` | Gắn hoặc gỡ một bài học (lesson) khỏi một bài | `GET` rồi `PATCH /comprehensives/{id}` |
| `lj_set_grammar_patterns` | Thay các mẫu khớp của một điểm ngữ pháp; cần `version` | `PATCH /comprehensives/{id}` |
| `lj_set_grammar_overrides` | Thay danh sách điểm ngữ pháp được ghim/ẩn trên một bài đọc/nghe | `PUT /comprehensives/{id}/grammar-overrides` |

Tool xóa, chỉ có khi `LJ_ALLOW_DELETE` bật: `lj_delete_comprehensive` (`DELETE /comprehensives/{id}`) và
`lj_delete_vocabulary` (`DELETE /vocabularies/{id}`), đều cần `version`.

Kết quả là JSON của API, viết gọn (không thụt dòng), chỉ bỏ `html_hover` và `html_ruby`: hai trường này sinh ra từ
markup và lớn gấp vài lần markup, nên chỉ trả khi gọi với `include_html=true`. Claude Code mặc định giới hạn kết
quả của một tool MCP ở 25.000 token; vì vậy `lj_get_book` chỉ trả tối đa 100 bài. Nếu một kết quả vẫn vượt mức này
(trang `limit=200` của từ vựng có nhiều ví dụ, một bài rất dài với `include_html=true`), giảm `limit` hoặc tăng giới
hạn trước khi chạy Claude Code, ví dụ `export MAX_MCP_OUTPUT_TOKENS=80000`.

Tên file audio gửi trong header `X-Filename` được mã hóa phần trăm theo UTF-8 (`聴解.mp3` thành
`%E8%81%B4%E8%A7%A3.mp3`); Odoo giải mã lại nên file đính kèm giữ đúng tên tiếng Nhật.

## Prompt

Claude Code đưa prompt của MCP thành lệnh `/`:

- `/mcp__learning-japanese__annotate_japanese_text <text> [level]`: chuyển văn bản tiếng Nhật sang markup
  `<<漢字 - よみ>>` + `{{bản dịch}}` (ví dụ `<<理解 - りかい>>する`, `<<女 - おんな>>の<<人 - ひと>>`), kiểm tra bằng
  `lj_preview_markup`, chỉ lưu khi bạn đồng ý.
- `/mcp__learning-japanese__review_readings <comprehensive_id>`: rà soát cách đọc của một bài (ví dụ 人 trong 係りの人
  phải đọc ひと chứ không phải にん; marker không ghi cách đọc là do pykakasi đoán), liệt kê đề xuất để bạn duyệt rồi
  mới lưu bằng `lj_update_comprehensive`.

## Bật tool xóa

Mặc định không có tool xóa. Muốn bật trên máy mình, thêm `"LJ_ALLOW_DELETE": "1"` vào `env` của server
`learning-japanese` trong `.mcp.json` (đừng commit thay đổi này) rồi khởi động lại Claude Code. Claude chỉ nên
xóa khi bạn yêu cầu rõ ràng; bản ghi đã xóa không khôi phục được.

## Chạy test

Từ gốc repo:

```bash
uv run --directory tools/lj-mcp pytest -q
```

Test chạy hoàn toàn với mock (`httpx.MockTransport`) và một MCP client in-memory, không cần Odoo hay mạng.

## Ghi chú phát triển

- Mã nguồn: `src/lj_mcp/` (`config.py` biến môi trường, `client.py` HTTP client và lỗi problem+json,
  `audio.py` tải/đọc audio, `server.py` tool, `prompts.py` prompt); test trong `tests/`.
- Dùng SDK `mcp` 1.x (`from mcp.server.fastmcp import FastMCP`), khóa `<2` vì `mcp` 2 đã đổi FastMCP thành
  `MCPServer` và đổi cả API.
- `.gitignore` riêng của thư mục này cũng là file hatchling đọc khi build; không có nó, quy tắc `/src/` trong
  `.gitignore` gốc của repo làm package bị build rỗng.
