"""UI strings (Vietnamese) — centralized so handlers stay clean."""
from __future__ import annotations


def display_name(user: dict) -> str:
    if user.get("username"):
        return f"@{user['username']}"
    return user.get("first_name") or "Bạn"


START_TEXT = (
    "Xin chào bạn 🥰\n\n"
    "Để bắt đầu sử dụng bot, hãy nhập mã redeem bằng:\n"
    "/redeem YOUR_CODE\n\n"
    "Sau đó bạn có thể dùng:\n"
    "/acc - xem tài khoản\n"
    "/new - tạo cuộc trò chuyện mới\n"
    "/voice - tạo giọng nói\n"
    "/svg - tạo SVG\n"
    "/history - xem lịch sử"
)

NOT_ACTIVATED = (
    "🔒 Bạn chưa kích hoạt tài khoản.\n"
    "Hãy nhập mã redeem bằng: /redeem YOUR_CODE"
)

REDEEM_OK = "🎉 Kích hoạt thành công!\n💰 Credit: {credit}\n👤 Tài khoản đã được tạo.\nBạn có thể dùng /acc để xem thông tin."
REDEEM_ALREADY = "Bạn đã kích hoạt tài khoản trước đó."
REDEEM_INVALID = "Mã redeem không hợp lệ."
REDEEM_USED = "Mã redeem đã được sử dụng trước đó."
REDEEM_USAGE = "Cách dùng: /redeem YOUR_CODE"

ACC_TEXT = (
    "👤 Account\n\n"
    "Tên: {name}\n"
    "UID: {uid}\n"
    "💰 Credit: {credit}\n"
    "🔢 Số lần sử dụng: {usage}\n"
    "🆔 Account ID: {account_id}\n"
    "📅 Ngày tạo: {created}"
)

NEW_CHAT_TEXT = "🆕 Cuộc trò chuyện mới đã được tạo.\nConversation: {cid}"

VOICE_PROMPT = "🎙️ Voice Generator\n\nHãy gửi đoạn văn bản bạn muốn chuyển thành giọng nói."
VOICE_SELECT = "🎙️ Chọn giọng:"
VOICE_VOICE_NOTE = (
    "\n\n⚠️ Lưu ý: hiện có {n} giọng thực tế từ model Piper (vi_VN). "
    "Các giọng \"Nam 2 / Nữ 2 / Trẻ / Trầm\" chưa có trong checkpoint nên không "
    "được giả lập. Giọng VIVOS: giới tính chưa được dataset ghi nhận."
)
VOICE_PROCESSING = "⏳ Đang tạo giọng nói…"
VOICE_DONE = (
    "🎧 Đã tạo giọng nói.\n\n"
    "Voice: {voice}\n"
    "Thời lượng: {duration} giây\n"
    "Credit đã sử dụng: {cost}"
)
VOICE_EMPTY = "Vui lòng gửi văn bản cần chuyển giọng nói (tin nhắn chữ)."
VOICE_TOO_SHORT = "Văn bản quá ngắn, hãy gửi đoạn văn dài hơn."
VOICE_TOO_LONG = "Văn bản quá dài ({chars} ký tự). Tối đa {max} ký tự."
VOICE_CANCELLED = "✅ Đã huỷ yêu cầu tạo giọng nói."

SVG_PROMPT = (
    "🎨 SVG Generator\n\n"
    "Hãy mô tả hình ảnh bạn muốn tạo.\n"
    "Ví dụ: \"một ngôi nhà nhỏ giữa đầm lầy, phong cách hoạt hình\""
)
SVG_PROCESSING = "⏳ Đang tạo SVG…"
SVG_DONE = (
    "🎨 SVG đã được tạo.\n\n"
    "Kích thước: {width}x{height}\n"
    "Số elements: {elements}\n"
    "Credit đã sử dụng: {cost}"
)
SVG_RESULT_NOTE = "Chọn cách xem bên dưới 👇"
SVG_NO_PREVIEW = "⚠️ Không tạo được ảnh preview từ SVG này, nhưng bạn vẫn có thể xem code."
SVG_BAD_PROMPT = "Mô tả quá dài ({chars} ký tự). Tối đa {max} ký tự."

BUSY = "⏳ Bạn đang có một tác vụ đang xử lý. Vui lòng chờ hoàn tất."
NO_CREDIT = (
    "❌ Không đủ credit.\n\n"
    "Credit hiện tại: {balance}\n"
    "Cần: {cost}\n"
    "Vui lòng liên hệ admin để nạp thêm."
)
STRAY_TEXT = (
    "🤔 Mình chưa hiểu yêu cầu này.\n"
    "Bạn có thể chọn chức năng bên dưới, hoặc dùng lệnh:\n"
    "/voice - tạo giọng nói\n"
    "/svg - tạo SVG"
)
PROCESSING_NOTE = "⏳ Đang xử lý tác vụ trước đó, vui lòng chờ…"

HISTORY_TITLE = "📚 Lịch sử"
HISTORY_EMPTY = "📚 Lịch sử\n\nChưa có cuộc trò chuyện nào. Hãy dùng /new để tạo."
CONV_DETAIL = (
    "📂 Conversation: {cid}\n"
    "👤 UID: {uid}\n"
    "📅 Tạo: {created}\n"
    "🕒 Cập nhật: {updated}\n"
    "🔁 Loại: {workflow}\n"
    "💬 Messages: {messages}\n"
    "💸 Tổng credit: {cost}\n\n"
    "{extra}"
)
BACK_TEXT = "« Quay lại"

ADMIN_DENIED = "⛔ Lệnh này chỉ dành cho admin."
ADMIN_NO_CONFIG = "⛔ Admin chưa được cấu hình (ADMIN_TELEGRAM_ID)."
ADMIN_STATS = (
    "🛠 Admin\n\n"
    "👥 Users: {users} (đã kích hoạt: {activated})\n"
    "💰 Tổng credit: {credit}\n"
    "🎟 Redeem còn lại: {remaining}\n"
    "🎙 Voice generations: {voice_gens}\n"
    "🎨 SVG generations: {svg_gens}\n"
    "⚙️ Jobs đang chạy: {jobs}"
)
ADMIN_ADDCREDIT_USAGE = "Cách dùng: /addcredit USER_UID SÓ_TIỀN (vd: /addcredit 123456 50)"
ADMIN_ADDCREDIT_OK = "✅ Đã cộng ${amount} cho UID {uid}. Số dư mới: {balance}"
ADMIN_USER_NOT_FOUND = "❌ Không tìm thấy user với UID này."

DB_DOWN = "⚠️ Hệ thống dữ liệu tạm thời không khả dụng. Vui lòng thử lại sau."
AI_DOWN = "⚠️ AI đang gặp sự cố. Vui lòng thử lại sau."
TTS_DOWN = "⚠️ Không thể tạo giọng nói lúc này."
SVG_DOWN = "⚠️ Không thể tạo SVG từ mô tả này."
GENERIC_DOWN = "⚠️ Có lỗi xảy ra. Vui lòng thử lại sau."
