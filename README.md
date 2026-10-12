# 🤖 AI Discord Bot — Multi-Provider Edition

Bot Discord AI hỗ trợ nhiều nhà cung cấp (**DeepSeek**, **OpenRouter**, **Groq**, **OpenAI**, **Gemini**), tích hợp **bảng điều khiển CLI trực tiếp trên Terminal/VPS/Termux**, hỗ trợ **phím tắt prompt tự chạy**, **tự động cập nhật code từ GitHub**, và **đổi API Key / Model ngay tại máy chủ**.

---

## 🚀 1. Hướng Dẫn Cài Đặt Trên VPS / Termux

### Bước 1: Cài thư viện Python cần thiết
```bash
pip install discord.py python-dotenv
```
*(Ghi chú: Không cần cài thư viện `openai` hay trình biên dịch Rust, tương thích hoàn toàn 100% với Termux).*

### Bước 2: Khởi chạy Bot
```bash
python bot.py
```
> 🌟 **Lần đầu chạy:** Bot sẽ hỏi bạn nhập `Discord Bot Token` và `AI API Key` trực tiếp trên màn hình terminal.

---

## 💻 2. BẢNG LỆNH ĐIỀU KHIỂN TRÊN MÁY CHỦ (TERMINAL / VPS / TERMUX)

Khi bot chạy, terminal hiển thị:
```text
[VPS] > 
```

### 🧠 Model & Nhà Cung Cấp AI:
- `model` : Mở menu chọn nhanh 13 model bằng số:
  - `[ 1]` DeepSeek V3 Free (OpenRouter)
  - `[ 2]` DeepSeek R1 Free (OpenRouter)
  - `[ 3]` Gemini 2.0 Flash Free (OpenRouter)
  - `[ 4]` Gemini 2.5 Pro Free (OpenRouter)
  - `[ 5]` Llama 3.3 70B Free (OpenRouter)
  - `[ 6]` Qwen 2.5 72B Free (OpenRouter)
  - `[ 7]` Mistral 7B Free (OpenRouter)
  - `[ 8]` DeepSeek V3 (Chính chủ)
  - `[ 9]` DeepSeek R1 Reasoner (Chính chủ)
  - `[10]` Llama 3.3 70B (Groq - Siêu nhanh)
  - `[11]` Mixtral 8x7B (Groq)
  - `[12]` GPT-4o Mini (OpenAI)
  - `[13]` GPT-4o (OpenAI)
- `model <tên_model>` : Đổi trực tiếp sang tên model bất kỳ.
- `provider <tên> [key]` : Chuyển nhanh nhà cung cấp:
  - `provider openrouter [key]` — Chuyển sang OpenRouter (Dùng model Free)
  - `provider deepseek [key]` — Chuyển sang DeepSeek chính chủ
  - `provider groq [key]` — Chuyển sang Groq Cloud
  - `provider openai [key]` — Chuyển sang OpenAI
- `seturl <url>` : Đổi URL API tùy chỉnh.

### 🔑 Đổi API Key & Token:
- `api` : Menu tương tác đổi API Key / Discord Token.
- `setkey ai <key>` : Đổi riêng AI API Key *(áp dụng tức thì)*.
- `setkey discord <token>` : Đổi riêng Discord Bot Token.

### ⚡ Phím Tắt Tự Chạy Prompt (Shortcuts):
- `shortcuts` : Xem danh sách phím tắt hiện có.
- `shortcut add <tên> <prompt>` : Thêm phím tắt mới (vd: `shortcut add dich Hãy dịch sang tiếng Anh:`).
- `shortcut del <tên>` : Xóa phím tắt.

### 👑 Quản Lý Chủ Nhân & Admin:
- `owners` : Xem danh sách ID tất cả Chủ nhân tối cao.
- `addowner <id>` : Thêm Chủ nhân mới.
- `delowner <id>` : Xóa bớt Chủ nhân.
- `admins` / `addadmin <id>` / `deladmin <id>` : Quản lý Admin phụ.

### 👥 Phân Quyền Sử Dụng:
- `users` : Xem danh sách người trong Whitelist.
- `add <id>` / `del <id>` : Thêm hoặc xóa người dùng được phép chat.
- `mode restricted` : Chỉ người trong Whitelist mới được dùng bot.
- `mode public` : Mở quyền cho toàn bộ thành viên server.

### 🔄 Cập Nhật Code & Hệ Thống:
- `update` : Kéo code mới từ GitHub (`git pull`) và tự khởi động lại bot.
- `autoupdate on|off` : Bật/tắt tự động kiểm tra code mới mỗi 30 phút.
- `prompt` / `setprompt <nội dung>` / `resetprompt` : Quản lý System Prompt.
- `status` : Xem trạng thái hoạt động tổng quan.
- `restart` : Khởi động lại tiến trình bot.
- `stop` : Tắt bot an toàn.

---

## 💬 3. LỆNH TRÊN DISCORD

| Lệnh | Quyền hạn | Mô tả |
| :--- | :--- | :--- |
| `!ask <câu hỏi>` (hoặc `!ai <câu hỏi>`) | Thành viên hợp lệ | Chat, hỏi đáp với AI |
| `!<shortcut> <nội dung>` | Thành viên hợp lệ | Áp dụng ngay prompt dài (vd: `!dich text`, `!fixcode code`) |
| `!shortcuts` | Mọi người | Xem danh sách các phím tắt hiện có |
| `!models` | Mọi người | Xem danh sách model AI được gợi ý |
| `!model` | Mọi người | Xem model AI hiện tại đang dùng |
| `!model <tên>` | Admin & Chủ nhân | Đổi model AI đang chạy |
| `!shortcut add <tên> <prompt>` | Admin & Chủ nhân | Tạo phím tắt prompt mới |
| `!shortcut del <tên>` | Admin & Chủ nhân | Xóa phím tắt |
| `!grant @user` / `!revoke @user` | Admin & Chủ nhân | Cấp hoặc thu hồi quyền dùng bot |
| `!setting` | Admin & Chủ nhân | Bảng tổng hợp cài đặt bot |
| `!owners` / `!addowner @user` / `!delowner @user` | Chủ nhân | Quản lý Chủ nhân tối cao |
| `!update` | Chủ nhân | Kéo code mới từ GitHub và tự reload |
| `!clear` | Mọi người | Xóa ngữ cảnh đoạn chat của kênh hiện tại |
