# Learning Japanese — API v1

Addon có thêm REST API `/api/lj/v1` cho hai bên dùng:

- **lj-mcp** (`tools/lj-mcp`): Claude đọc và sửa nội dung qua MCP.
- **NihonGo**: đồng bộ một chiều nội dung đã xuất bản (change feed + snapshot), chỉ đọc.

Hợp đồng đầy đủ nằm ở [`static/api/openapi.yaml`](static/api/openapi.yaml).

## Có gì mới trong module

| Phần | Ghi chú |
| --- | --- |
| Cờ **Xuất bản NihonGo** trên Giáo trình | Mặc định tắt. Chỉ bài và từ vựng thuộc giáo trình đã bật cờ mới lên NihonGo. |
| **Mẫu khớp ngữ pháp** trên bài Grammar | Mỗi dòng một mẫu ở dạng từ điển (`ようとする`, `とする`). |
| Tab **Ghi đè ngữ pháp** trên bài đọc/nghe | Ghim hoặc ẩn một điểm ngữ pháp cho riêng bài đó. |
| Bảng `lj_change_log` | Outbox của change feed, ghi cùng transaction với thay đổi; cron xóa sự kiện quá 90 ngày. |
| **Nhật ký ghi qua API** | Trước/sau của mọi thao tác ghi qua API (Settings → Nhật ký ghi qua API). |
| Quyền | Hai nhóm sẵn có được ghi vào CSV: *Learning Japanese Read Only* (đọc), *Learning Japanese Admin* (đọc + ghi). |

## Cài lên server

1. Sao lưu database, rồi nâng cấp module:
   ```bash
   ./odoo-bin -c /etc/odoo/odoo.conf -d <database> -u learning_japanese --stop-after-init
   ```
   Cần PostgreSQL 13 trở lên (Odoo 19 cũng yêu cầu như vậy).
2. Tạo 2 user kỹ thuật (Settings → Users):
   - `claude-mcp`: nhóm **Learning Japanese Admin** (dùng cho MCP, được ghi).
   - `nihongo-sync`: nhóm **Learning Japanese Read Only** (dùng cho NihonGo, chỉ đọc).
3. Tạo API key cho từng user. Odoo 19 chỉ cho mỗi user tự tạo key của mình, tối đa 90 ngày
   (đăng nhập bằng user đó → Preferences → Account Security → New API Key).
   Muốn key dài hạn hơn, tạo bằng Odoo shell (key không hết hạn, chỉ hiện một lần):
   ```bash
   ./odoo-bin shell -c /etc/odoo/odoo.conf -d <database>
   ```
   ```python
   user = env["res.users"].search([("login", "=", "nihongo-sync")])
   print(env["res.users.apikeys"].with_user(user).sudo()._generate(None, "nihongo-sync", None))
   env.cr.commit()
   ```
4. Thử nhanh:
   ```bash
   curl -H "Authorization: Bearer $LJ_API_KEY" https://oht-t4-hcet.com/api/lj/v1/meta
   ```
5. Nên đặt giới hạn tốc độ cho `/api/lj/` ở nginx.

## Quy ước chính

- JSON `snake_case`, thời gian ISO-8601 UTC, lỗi dạng `application/problem+json` có trường `code`.
- Mỗi bản ghi có `version` (hash nội dung). `PATCH`/`DELETE` phải gửi `If-Match: "<version>"`;
  sai version trả `412` kèm `current_version`, thiếu header trả `428`.
- Markup giữ đúng quy ước cũ: `<<漢字 - よみ>>` cho cách đọc, `{{...}}` cho bản dịch.
  API trả và nhận marker ở dạng chưa escape; sửa markup qua API được chuyển đổi lại y như khi gõ trong Odoo.
- Server không bao giờ tự tải file từ URL; muốn gắn audio từ URL thì client (lj-mcp) tải về rồi `PUT` file.
- Change feed: `GET /changes?after=<cursor>`; con trỏ có dạng `<txid>-<seq>` và chỉ trả sự kiện của
  transaction đã kết thúc, nên không bỏ sót khi nhiều transaction commit lệch thứ tự.

## Chạy test

```bash
./odoo-bin -c <config> -d <database thử> -u learning_japanese --test-tags /learning_japanese --stop-after-init
```
