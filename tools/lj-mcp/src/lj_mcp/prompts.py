"""Prompts offered to the user, written in Vietnamese."""

from typing import Annotated

from pydantic import Field

ANNOTATE_RULES = """\
Hãy chuyển văn bản tiếng Nhật dưới đây sang markup của addon learning_japanese (Odoo).

Quy tắc:
1. Mọi từ viết bằng kanji phải nằm trong <<漢字 - よみ>>, cách đọc viết bằng hiragana; okurigana để ngoài marker:
   理解する → <<理解 - りかい>>する
   特に → <<特 - とく>>に
   女の人 → <<女 - おんな>>の<<人 - ひと>>
   悪い → <<悪 - わる>>い
2. Cách đọc đặc biệt thì đặt cả cụm vào một marker:
   1人 → <<1人 - ひとり>>, 一人 → <<一人 - ひとり>>, 2人 → <<2人 - ふたり>>, 二人 → <<二人 - ふたり>>, \
何ですか → <<何 - なん>>ですか
3. Chọn cách đọc theo ngữ cảnh (ví dụ 人 trong 係りの人 đọc là ひと, không phải にん) và luôn ghi cách đọc: \
<<漢字>> không có cách đọc sẽ bị server đoán bằng pykakasi và thường sai.
4. Không để chữ kanji nào nằm ngoài marker. Không thêm, bớt hay sửa chữ tiếng Nhật nào.
5. Giữ nguyên các đoạn HTML <p>...</p> (nếu văn bản chưa có thì mỗi đoạn văn là một <p>...</p>). \
Ngay sau phần tiếng Nhật của mỗi đoạn, đặt bản dịch tiếng Việt của cả đoạn trong {{...}}, trong cùng thẻ <p>:
   <p><<女 - おんな>>の<<人 - ひと>>が<<来 - き>>ました。<br/>{{Người phụ nữ đã đến.}}</p>

Sau đó:
- Gọi lj_preview_markup với markup vừa viết, sửa mọi issue (kanji_without_reading, auto_reading, unbalanced_marker, \
missing_translation...) rồi preview lại cho đến khi không còn issue nào.
- Trình bày markup cuối cùng cho tôi. Chỉ lưu (lj_create_comprehensive hoặc lj_update_comprehensive) khi tôi đồng ý.
"""


def annotate_japanese_text(
    text: Annotated[str, Field(description="Văn bản tiếng Nhật cần chú thích (văn bản thường hoặc HTML <p>...</p>).")],
    level: Annotated[str | None, Field(description="Trình độ JLPT của văn bản: N5, N4, N3, N2 hoặc N1.")] = None,
) -> str:
    """Chuyển văn bản tiếng Nhật sang markup <<漢字 - よみ>> + {{bản dịch}}, kiểm tra bằng lj_preview_markup."""
    level_line = f"\nTrình độ JLPT: {level} (dùng làm level khi lưu).\n" if level else ""
    return f"{ANNOTATE_RULES}{level_line}\nVăn bản:\n{text}"


def review_readings(
    comprehensive_id: Annotated[int, Field(description="Id của mục comprehensive cần rà soát.")],
) -> str:
    """Rà soát cách đọc <<漢字 - よみ>> của một mục, đề xuất các sửa để bạn duyệt rồi mới lưu."""
    return f"""\
Hãy rà soát cách đọc kanji của mục comprehensive #{comprehensive_id} trong Odoo.

1. Gọi lj_get_comprehensive(comprehensive_id={comprehensive_id}) và ghi nhớ version.
2. Kiểm tra từng marker <<漢字 - よみ>> trong markup theo ngữ cảnh của câu:
   - cách đọc phải đúng nghĩa trong câu. Lỗi kinh điển: 人 trong 係りの人 phải đọc là ひと, không phải にん;
   - cách đọc phải là hiragana và chỉ ứng với phần chữ trong marker (okurigana để ngoài: <<悪 - わる>>い);
   - cách đọc đặc biệt viết cả cụm: <<一人 - ひとり>>, <<二人 - ふたり>>, <<何 - なん>>ですか;
   - marker không có cách đọc (<<漢字>>) là do pykakasi đoán nên rất đáng ngờ: đề xuất cách đọc rõ ràng cho tất cả. \
lj_preview_markup cho biết cách đọc server đã đoán (issue auto_reading) và các kanji nằm ngoài marker \
(issue kanji_without_reading).
3. Liệt kê các đề xuất sửa thành bảng: câu chứa marker | marker hiện tại | marker đề xuất | lý do. \
Chưa sửa gì cả, chờ tôi xác nhận (tôi có thể bỏ bớt đề xuất).
4. Khi tôi đã xác nhận: chỉ áp dụng các sửa được duyệt vào markup, không đổi gì khác; kiểm tra lại bằng \
lj_preview_markup; rồi lưu bằng lj_update_comprehensive(comprehensive_id={comprehensive_id}, \
version=<version đã đọc>, markup=<markup mới>).
5. Nếu bị lỗi HTTP 412 (mục đã bị sửa trong lúc đó): đọc lại mục, áp dụng lại các sửa đã duyệt lên nội dung mới \
và lưu với version mới.
"""
