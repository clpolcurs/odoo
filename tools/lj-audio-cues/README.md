# lj-audio-cues

Công cụ đề xuất và ghi **mốc thời gian của audio** (`audio_cues`) cho các bài nghe của addon Odoo `learning_japanese`:
câu nào trong bài được audio đọc từ mili giây nào tới mili giây nào. NihonGo dùng các mốc này để tô câu đang đọc và
cho người học nghe lại từ một câu (ADR-055 của NihonGo).

## Cách tính

1. `faster-whisper` (mô hình `small`, chạy CPU) nghe file audio của bài, cho chữ và thời điểm của từng từ. Kết quả lưu ở
   `data/asr/<sha1>.<model>.json`, chạy lại không tốn thời gian. Mô hình `small` chạy nhanh khoảng 4 lần thời lượng audio
   trên 4 CPU (bài 1 phút rưỡi mất khoảng 20 giây).
2. Markup của bài được cắt thành block giống hệt cách NihonGo cắt (`blocks.py`, theo `MarkupConverter` của NihonGo):
   mỗi đoạn, mục danh sách hay câu thoại là một block; `<br>` không cắt; `<<漢字 - よみ>>` hiện 漢字; `{{...}}` bị bỏ.
3. Sudachi đọc cả hai phía ra hiragana, rồi so từng chữ kana bằng dãy con chung dài nhất (LCS). Nhờ vậy những gì audio
   không đọc (các lựa chọn in trong sách) và những gì văn bản không có (第1回, 1番) tự rơi ra.
4. Một block được gắn mốc khi audio đọc đủ phần kana của nó, và các kana đó nằm gần nhau. Block ngắn phải khớp nhiều
   hơn (80% với block từ 4 kana trở xuống, 50% với block từ 10 kana), để lựa chọn như `1. ア ウ` không bị ghép nhầm
   vào chữ ア, ウ của câu khác. Trước khi xét, vài kana lẻ ở đầu hay cuối block, cách phần còn lại hơn 3 giây, bị bỏ:
   giáo trình 153 đọc một danh sách từ sau mỗi truyện, và LCS hay ghép kana cuối của đoạn văn vào một từ đọc sau đó,
   hay kana đầu vào một từ đọc trước khi Whisper bỏ sót chữ đầu đoạn.
5. Câu bắt đầu ở kana đầu tiên nghe được, kéo về điểm hết khoảng lặng ngay trước đó (`ffmpeg silencedetect`, -35 dB,
   0,25 giây) nếu có trong khoảng 0,7 giây trước tới 0,4 giây sau. Câu mở đầu bằng tiếng ngập ngừng mà Whisper bỏ qua
   (うーん, ええ, あ) được tìm khoảng lặng xa hơn, nhưng không trước âm cuối của câu trước. Câu kết thúc khi câu sau bắt
   đầu, hoặc 0,6 giây sau kana cuối nghe được, cộng 0,11 giây cho mỗi kana cuối câu mà Whisper không chép.
6. Từ mà Whisper cho thời lượng 0 bị bỏ: Whisper hay tự thêm `ご視聴ありがとうございました` ở cuối file.

Chữ của mỗi mốc là chữ của block như NihonGo hiện, có cả người nói (`F: すみません。`). NihonGo so mốc với block bỏ khoảng
trắng và gộp dạng chữ toàn/nửa độ rộng (NFKC), theo thứ tự trong bài. Sửa chữ một câu trên Odoo thì chỉ mốc của câu đó
không còn khớp và bị bỏ qua; các câu khác vẫn giữ mốc.

## Quy trình

```bash
cd tools/lj-audio-cues
uv sync                                                     # Python ≥ 3.11, faster-whisper, Sudachi; cần ffmpeg
uv run python propose.py 168                                # proposals/168-n2.json và 168-n2_report.json
uv run python propose.py 168 --items 58,59                  # chỉ vài bài
uv run python apply.py proposals/168-n2.json                # kiểm tra với Odoo, không ghi
uv run python apply.py proposals/168-n2.json --apply        # chỉ chạy sau khi đã duyệt
uv run pytest -q
```

- Key API giống `tools/lj-readings`: biến `LJ_API_KEY`, hoặc network secret của môi trường cloud Claude Code (khi đó
  để trống `LJ_API_KEY`). Lần đầu chạy cần tải mô hình từ Hugging Face (`huggingface.co` và CDN của nó).
- `propose.py` chỉ lấy các bài **Listening** đã xuất bản, có audio và markup. Audio tải về `data/audio/<sha1>.bin`,
  kiểm tra sha1 trước khi dùng.
- Bài mà audio đọc chưa tới một nửa số câu thoại thì không có đề xuất, và báo cáo ghi lý do: thường là gắn nhầm file
  audio của bài khác. Báo cáo cũng ghi khi audio đọc số bài (`8番`) khác tiêu đề (`10番`).
- `apply.py` chỉ ghi một bài khi bài chưa bị sửa từ lúc đề xuất (`version`), audio vẫn là file đã nghe (`audio_sha1`)
  và mỗi mốc vẫn khớp một block của markup hiện tại. Sau khi ghi, mốc được đọc lại để so.
- Sửa tay một bài thì dùng `lj_set_audio_cues` của lj-mcp.
- `data/` và các file `*_report.json` không được commit.

## Kết quả với giáo trình 168 (ドリル&ドリル日本語能力試験N2聴解読解, 14/11/2026)

- 29 trên 30 bài có audio được đề xuất, 408 mốc. Mọi câu thoại của 29 bài đều có mốc, cùng câu dẫn và câu hỏi.
- Bài 67 (`10番`) không có đề xuất: file audio của nó là file của bài 65 (`8番`), cùng sha1. Tùng tải audio đúng lên
  ngày 15/11/2026; đề xuất riêng của bài là `proposals/168-n2-67.json` (15 mốc, mọi câu thoại, nghe lại đủ 15 mốc
  mở đầu đúng câu).
- Kiểm tra độc lập: nghe lại 1,5 giây đầu của mỗi mốc bằng Whisper, 389 trên 408 mốc mở đầu đúng câu của nó. Phần lớn
  số còn lại là câu mở đầu bằng tiếng ngập ngừng, mà Whisper không chép khi nghe một đoạn ngắn, hay chữ đầu câu bị nghe
  nhầm. Trước khi có luật cho tiếng ngập ngừng (mục Cách tính, bước 5) con số này là 382.
- Cả 408 mốc khớp block khi chạy qua `MarkupConverter` và `AudioCues` của NihonGo với markup thật.
- Tùng duyệt, và ngày 15/11/2026 cả 423 mốc của 30 bài được ghi lên Odoo và đọc lại khớp. Trên nihon-go.co, cả 30 bài
  có đúng số câu mang mốc như đã ghi.
- Chạy lại với luật bỏ kana lẻ và bù cuối câu (16/11/2026): vẫn 423 mốc, cùng điểm đầu; 27 điểm cuối muộn hơn tối đa
  0,55 giây, một điểm cuối của bài 85 sớm hơn 3,75 giây. Mốc trên Odoo giữ nguyên. Audio của bài 85 đọc câu
  `モノレールで行くより安いし、結構早く行けそうだね。` (57,0 tới 60,3 giây) mà markup không có.

## Kết quả với giáo trình 153 (JLPT N2 ミニストーリーで覚える…2400, 16/11/2026)

- Audio mới của 23 bài, Tùng tải lên ngày 16/11/2026: 4,8 giờ, Whisper nghe trong khoảng một giờ.
- Mỗi bài là các truyện ngắn, đoạn văn hay hội thoại, có dòng số `🔊155` trước mỗi truyện; sau mỗi truyện audio đọc
  danh sách từ của truyện, không có trong markup. Dòng số và danh sách từ không có mốc.
- 23 trên 23 bài có đề xuất, 812 mốc, trên 812 của 816 đoạn văn và câu thoại (526 trên 529 câu thoại). Bốn block
  không có mốc: ba câu thoại ngắn (`ねえ、「ルッキズム」ってどういう意味？`, `はい、分かりました。`, `えー…。`) và đoạn
  `2050年には…` của bài 2557, mà Whisper bỏ sót phần đầu.
- Luật bỏ kana lẻ (mục Cách tính, bước 4) thêm 18 mốc, sửa 6 mốc mở đầu sớm 6 tới 22 giây, và cho 88 đoạn văn kết thúc
  khi đọc xong thay vì kéo qua danh sách từ.
- Kiểm tra độc lập: nghe lại 1,5 giây đầu của mỗi mốc, 787 trên 812 mốc mở đầu đúng câu. Xem tay 25 mốc còn lại: 23
  mốc đúng (Whisper nghe khác chữ: こないだ và この間, WEB và ウェブ, 今日 đọc こんにち; hay không chép được đoạn quá
  ngắn), 2 mốc chưa chắc, ở bài 2552, nơi Whisper không chép được audio; hai mốc đó nằm ở khoảng lặng ngay trước đoạn.
- Cả 812 mốc khớp block khi chạy qua `MarkupConverter` (bản có `en`, `zh`) và `AudioCues` của NihonGo với markup thật.
- Tùng duyệt, và ngày 16/11/2026 lúc 11:24 cả 812 mốc của 23 bài được ghi lên Odoo và đọc lại khớp. Trên nihon-go.co,
  cả 23 bài có đúng số câu mang mốc; phát thử bài `155–161`, câu đang đọc được tô đúng, và không câu nào được tô khi
  audio đọc danh sách từ.
