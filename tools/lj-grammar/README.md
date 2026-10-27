# lj-grammar

Công cụ soạn và kiểm tra **mẫu khớp** (`grammar_patterns`) của các điểm ngữ pháp trong addon Odoo
`learning_japanese`. NihonGo dùng các mẫu này để tìm điểm ngữ pháp trong bài đọc, bài nghe.
`gmatch.py` là bộ khớp tham chiếu cho NihonGo (giai đoạn 3): bản Java phải cho cùng kết quả.

## Cách viết mẫu

Mỗi điểm ngữ pháp có một hoặc vài mẫu; mỗi mẫu là phần tiếng Nhật cố định của điểm đó.

| Ký hiệu | Nghĩa | Ví dụ |
| --- | --- | --- |
| `ことにする` | Dạng từ điển; từ cuối khớp mọi dạng chia | khớp ことにした, ことにします |
| `…` | Khoảng trống tối đa 12 ký tự trong cùng câu; mỗi đoạn hai bên phải là từ trọn vẹn | `さえ…ば` khớp お金さえあれば |
| `N` ở đầu mẫu (hoặc sau `…`) | Từ đứng ngay trước là danh từ | `N次第で` khớp 天候次第で |
| `Vる` `Vた` `Vて` `Vます` `Vない` | Động từ thể từ điển, thể ta, thể te, gốc masu, thể nai | `Vるあまり` khớp 気にするあまり, không khớp あまり～ない |
| `Aい` `Aな` | Tính từ -i, tính từ -na | `Aなことに、` khớp 残念なことに、 |
| `上[じょう]` | Chữ Hán phải có đúng cách đọc này | `N上[じょう]` khớp 教育上, không khớp 机の上 |

Quy tắc khớp (Sudachi, chế độ tách C):

- Chỗ khớp phải bắt đầu ở ranh giới từ (`まい` không khớp しまいました), trừ khi đứng ngay sau động từ thể ý chí
  (伝えよう + `とする`). Mẫu không kết thúc bằng từ chia đuôi thì cũng phải kết thúc ở ranh giới từ
  (`ことか` không khớp ことから).
- Chỉ từ cuối ở dạng từ điển mới được chia: `ものなら`, `かのように` khớp đúng dạng đó.
- Chỗ khớp của điểm này nằm trong chỗ khớp dài hơn của điểm khác thì điểm dài hơn thắng (に限って thắng
  に限る, のみならず thắng のみ); dài bằng nhau thì giữ cả hai. Mẫu có `…` không lấn mẫu khác.

## Quy trình

```bash
cd tools/lj-grammar
uv sync                                   # Python ≥ 3.11, sudachipy, từ điển SudachiDict core
uv run python fetch.py                    # tải điểm ngữ pháp + câu của bài đọc/nghe đã xuất bản vào data/
uv run python evaluate.py proposals/175-mimi-bunpo-n2.json --show-noise 3
uv run python apply.py proposals/175-mimi-bunpo-n2.json            # xem trước thay đổi
uv run python apply.py proposals/175-mimi-bunpo-n2.json --apply    # chỉ sau khi đã duyệt
uv run pytest -q
```

- Key API: biến `LJ_API_KEY` (key của user `claude-mcp`), hoặc network secret của môi trường cloud Claude Code
  (khi đó để trống `LJ_API_KEY`). `LJ_BASE_URL` mặc định là `https://oht-t4-hcet.com`.
- `evaluate.py` chấm mỗi điểm theo hai chiều: mẫu có khớp đúng phần in đậm trong câu ví dụ của chính điểm đó
  không (`4/4`), và khớp bao nhiêu câu trong các bài đọc, bài nghe đã xuất bản (càng cao càng dễ khớp nhầm).
  `MISSED` là câu ví dụ bị trượt, `SHADOWED` là câu ví dụ bị điểm khác có mẫu dài hơn thắng.
- Mỗi file trong `proposals/` là một giáo trình, dạng `{"<id điểm ngữ pháp>": ["mẫu", ...]}`. Bảng duyệt nằm trong
  tài liệu "NihonGo — Mẫu khớp ngữ pháp"; sửa mẫu ở đó, rồi cập nhật file và chạy lại `evaluate.py`.
- `data/` (nội dung tải về) và `*_report.json` không được commit.
