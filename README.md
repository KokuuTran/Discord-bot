# 🤖 DeepSeek Discord Bot (Toàn Quyền Điều Khiển Trực Tiếp Trên VPS)

Bot Discord AI tích hợp trực tiếp **DeepSeek API** (`deepseek-chat` / `deepseek-reasoner`), **chạy song song bảng điều khiển Terminal trực tiếp trên VPS/Termux**, hỗ trợ **tự động cập nhật code từ GitHub**, **phím tắt dòng lệnh tự chạy prompt**, và **đổi linh hoạt 1 hoặc cả 2 API**.

---

## 🚀 1. Hướng Dẫn Cài Đặt Trên VPS / Termux

### Bước 1: Cài thư viện Python
```bash
pip install discord.py python-dotenv
```

### Bước 2: Khởi chạy Bot
```bash
python bot.py
```
> 🌟 **Lần đầu chạy:** Bot sẽ hỏi trực tiếp trên màn hình VPS để bạn nhập Token Discord và DeepSeek API Key.

---

## 💻 2. BẢNG LỆNH TOÀN QUYỀN ĐIỀU KHIỂN TRỰC TIẾP TRÊN VPS

Khi bot kết nối thành công, màn hình VPS sẽ hiện giao diện dòng lệnh:
```text
[VPS-Admin] > 
```

### 🔄 Cập Nhật Code Mới Từ GitHub:
- `update` : Kéo code mới nhất từ GitHub (`git pull`) và tự khởi động lại bot.
- `autoupdate on` / `autoupdate off` : Bật hoặc tắt tính năng tự động kiểm tra code mới mỗi 30 phút.

### 🔑 Đổi 1 API Hoặc Cả 2 API:
- `api` : Mở menu lựa chọn:
  - `[1]` Chỉ đổi DeepSeek API Key (AI)
  - `[2]` Chỉ đổi Discord Bot Token
  - `[3]` Đổi cả hai API
- `setkey deepseek <key>` : Đổi riêng DeepSeek API Key *(Áp dụng ngay tức thì)*
- `setkey discord <token>` : Đổi riêng Discord Bot Token *(Lưu vào .env)*
- `setkey both <deepseek_key> <discord_token>` : Đổi cả 2 trong 1 dòng lệnh.
- `restart` : Khởi động lại bot trên VPS.

### ⚡ Phím Tắt Tự Chạy Prompt (Shortcuts / Không Cần Gõ Prompt Dài):
- `shortcuts` : Xem danh sách phím tắt hiện có.
- `shortcut add <tên> <nội dung prompt dài>` : Thêm một phím tắt mới.
  *(Ví dụ: `shortcut add dich Hãy dịch văn bản sau sang tiếng Anh chuẩn bản ngữ:`)*
- `shortcut del <tên>` : Xóa phím tắt.

### 👑 Quản Lý Chủ Nhân & Admin:
- `owners` : Xem danh sách tất cả các Chủ nhân tối cao.
- `addowner <user_id>` : Thêm một Chủ nhân mới (có toàn quyền như bạn).
- `delowner <user_id>` : Xóa bớt một Chủ nhân.
- `addadmin <user_id>` / `deladmin <user_id>` : Thêm / Xóa Admin phụ.

### 👥 Quản Lý Người Xài:
- `users` : Xem danh sách ID người được phép xài bot.
- `add <user_id>` : Cấp quyền cho một người dùng.
- `del <user_id>` : Thu hồi quyền của một người dùng.

### 🧠 Tính Cách & Cấu Hình AI:
- `prompt` : Xem System Prompt hiện tại.
- `setprompt <nội dung>` : Đổi System Prompt tính cách AI.
- `resetprompt` : Khôi phục Prompt về mặc định ban đầu.
- `mode <restricted|public>` : Đổi chế độ: chỉ whitelist hoặc mở cho cả server.
- `setmodel <chat|reasoner>` : Đổi model giữa `deepseek-chat` (V3) và `deepseek-reasoner` (R1).
- `stop` (hoặc `exit`) : Tắt bot an toàn từ VPS.

---

## 💬 3. DÀNH CHO NGƯỜI DÙNG & QUẢN TRỊ TRÊN DISCORD

| Lệnh trên Discord | Người được dùng | Mô tả chức năng |
| :--- | :--- | :--- |
| `!ask <câu hỏi>` | Mọi người (đã cấp quyền) | Trò chuyện, đặt câu hỏi thông thường cho AI |
| `!<tên_phím_tắt> <nội dung>` | Mọi người (đã cấp quyền) | **Tự động áp dụng prompt dài đã cài sẵn!**<br>Ví dụ: `!dich Hello world`<br>Ví dụ: `!fixcode print("hi")`<br>Ví dụ: `!tomtat <đoạn văn dài>` |
| `!shortcuts` | Mọi người | Xem danh sách tất cả phím tắt prompt hiện có |
| `!shortcut add <tên> <prompt>` | Admin & Chủ nhân | Tạo thêm phím tắt prompt tùy chỉnh mới |
| `!shortcut del <tên>` | Admin & Chủ nhân | Xóa bớt một phím tắt |
| `!update` | Chủ nhân | Kéo code mới nhất từ GitHub và tự động khởi động lại bot |
| `!setting` (hoặc `!settings`)| Admin & Chủ nhân | **Xem và điều chỉnh cài đặt:** mode, model, prompt, max history... |
| `!owners` | Admin & Chủ nhân | Xem danh sách tất cả các Chủ nhân tối cao |
| `!addowner @user` | Chủ nhân | Thêm một Chủ nhân mới |
| `!delowner @user` | Chủ nhân | Xóa bớt một Chủ nhân |
| `!grant @user` / `!add @user` | Admin & Chủ nhân | Thêm người dùng vào Whitelist |
| `!revoke @user` / `!del @user` | Admin & Chủ nhân | Xóa người dùng khỏi Whitelist |
| `!clear` | Mọi người | Xóa ngữ cảnh hội thoại cũ của kênh |
