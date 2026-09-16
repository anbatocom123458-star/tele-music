# Wioos Witness 🎙🎨

Telegram bot sản phẩm thật chạy trên Railway với **2 workflow độc lập**:

- **`/voice`** — văn bản → giọng nói tiếng Việt bằng **TTS model chạy local trong container** (Piper VITS, CPU-friendly, model tải/cache lúc khởi động).
- **`/svg`** — mô tả → hình SVG: AI API trả **structured JSON**, server tự render SVG, sanitize, và cho xem **Preview (PNG)** hoặc **Source Code**.

Kèm theo: redeem code → account + credit ($100 ban đầu), conversation/history, state machine lưu DB, job queue chống block, admin command, health check.

---

## Kiến trúc

```
Telegram (long polling) ⇄ python-telegram-bot 21
        │
        ├─ app/bot/handlers/*   → workflow: start/redeem/acc/new/voice/svg/history/admin
        ├─ app/workers/queue.py → job queue (global cap + per-user cap + timeout)
        ├─ app/tts/engine.py    → Piper (onnxruntime) + FFmpeg (WAV→OGG/Opus)
        ├─ app/ai/client.py     → OpenAI-compatible POST {AI_BASE_URL}/chat/completions
        ├─ app/svg/*            → structured JSON → validated scene → renderer → sanitizer → PNG
        ├─ app/billing/credits  → calculate_voice_cost / calculate_svg_cost (single source of truth)
        ├─ app/database/*       → ChromaDB (HTTP client; users/redeem/conversations/messages/usage/gens)
        └─ app/web/health.py    → GET /health  {status, tts, database}
```

## Đếm giọng TTS — trung thực (không giả lập)

Model Piper tiếng Việt thực tế trên `rhasspy/piper-voices` (đã xác minh `num_speakers` trong ONNX config):

| Model | Speakers | Ghi chú |
|---|---|---|
| `vi_VN-vais1000-medium` | 1 | 👩 nữ, 22.05 kHz |
| `vi_VN-25hours_single-low` | 1 | 👨 nam, 16 kHz |
| `vi_VN-vivos-x_low` | 65 | speaker thật (VIVOSSPK/VIVOSDEV) nhưng **dataset không công bố giới tính** → menu ghi nhãn trung thực |

**Limitation rõ ràng:** các giọng "Nam 2 / Nữ 2 / Trẻ / Trầm lớn tuổi" **không tồn tại** trong checkpoint nên không hiển thị trong menu. Điều chỉnh tốc độ/pitch/volume không được bật vì Piper chỉ hỗ trợ ổn định `length_scale` (tốc độ) — hiện tắt để UX ổn định.

## Deploy lên Railway

1. Push repo, tạo service từ Dockerfile (`railway.toml` đã cấu hình `healthcheckPath=/health`, timeout 300s vì lần đầu phải tải ~155MB model).
2. Thêm **Volume** mount tại `/data` (cache model + không tải lại khi redeploy).
3. Khai báo Variables theo `.env.example` (bắt buộc: `TELEGRAM_BOT_TOKEN`, `AI_*`, `CHROMA_URL`/`CHROMA_DATABASE`/`CHROMA_APIKEY`/`CHROMA_SECRET`, `REDEEM_CODE_1..8`, khuyến nghị `ADMIN_TELEGRAM_ID`).
4. ChromaDB cần chạy ở chế độ HTTP server (tự host hoặc Chroma cloud) — biến `CHROMA_URL` trỏ tới nó.

## Bảo mật

- Secret **chỉ** nằm trong ENV; logging có filter tự redact token/key.
- Redeem code chỉ lưu **SHA-256 hash** trong DB; trạng thái đã dùng lưu DB (restart không hồi sinh code).
- AI API chỉ tạo JSON scene; **không** quyết credit/auth/redeem. SVG luôn đi qua validator + sanitizer (cắt `script`, event handler `on*`, external href, `url()` trong style, entity injection).
- TTS/SVG/FFmpeg/AI đều có timeout; giới hạn ký tự, số elements, dung lượng; queue giới hạn 1 job/user và 2 job toàn cục.
- File tạm `/tmp/voice`, `/tmp/svg` xoá sau khi gửi.

## Kiểm thử

```bash
pip install -r requirements.txt
pytest -q          # unit tests: text normalization, credit, redeem, SVG validate/render/sanitize
```

Tests dùng fake Chroma collection (không cần server). Bot end-to-end cần ENV thật (token Telegram, Chroma server, AI API) — chạy `python -m app.main` sau khi khai báo variables.
