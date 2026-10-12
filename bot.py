import os
import sys
import json
import logging
import threading
import asyncio
import subprocess
from datetime import datetime
from typing import Dict, List, Optional, Set

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
import aiohttp

# ---------------------------------------------------------
# 1. Cấu hình & Nạp biến môi trường
# ---------------------------------------------------------
load_dotenv()

# ID Chủ bot mặc định ban đầu theo yêu cầu
DEFAULT_OWNER_ID = int(os.getenv("OWNER_ID", "1124340099111473232"))

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "").strip()
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", os.getenv("AI_API_KEY", "")).strip()
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip()
DEFAULT_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip()

ORIGINAL_SYSTEM_PROMPT = (
    "Bạn là một trợ lý AI thông minh, nhiệt tình và chính xác, được cung cấp bởi DeepSeek trên Discord. "
    "Hãy trả lời mạch lạc, sử dụng định dạng Markdown đẹp mắt và ngôn ngữ tự nhiên bằng tiếng Việt."
)

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "bot_config.json")
ENV_FILE = os.path.join(os.path.dirname(__file__), ".env")

# Cấu hình Logging
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("DeepSeekDiscordBot")
logger.setLevel(logging.INFO)


# ---------------------------------------------------------
# 2. Quản lý File .env & File Cấu hình (bot_config.json)
# ---------------------------------------------------------
def update_env_variable(key: str, value: str):
    """Cập nhật hoặc thêm một biến vào file .env và nạp vào os.environ."""
    lines = []
    found = False
    if os.path.exists(ENV_FILE):
        try:
            with open(ENV_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith(f"{key}=") or stripped.startswith(f"{key} ="):
                    lines[i] = f"{key}={value}\n"
                    found = True
                    break
        except Exception as e:
            logger.error(f"Lỗi đọc .env: {e}")

    if not found:
        lines.append(f"{key}={value}\n")

    try:
        with open(ENV_FILE, "w", encoding="utf-8") as f:
            f.writelines(lines)
    except Exception as e:
        logger.error(f"Lỗi ghi .env: {e}")

    os.environ[key] = value


DEFAULT_CONFIG = {
    "is_setup": True,
    "owners": [DEFAULT_OWNER_ID],
    "admins": [DEFAULT_OWNER_ID],
    "whitelist_users": [DEFAULT_OWNER_ID],
    "allowed_channels": [],
    "access_mode": "restricted",
    "model": DEFAULT_MODEL,
    "base_url": DEEPSEEK_BASE_URL,
    "system_prompt": ORIGINAL_SYSTEM_PROMPT,
    "max_history": 12,
    "auto_update": True,  # Tự động cập nhật code từ GitHub
    "shortcuts": {
        "dich": "Hãy dịch văn bản sau sang tiếng Anh chuẩn bản ngữ và phân tích ngắn gọn các từ vựng cần lưu ý:",
        "fixcode": "Hãy kiểm tra lỗi, sửa lại đoạn code sau cho tối ưu và giải thích chi tiết:",
        "tomtat": "Hãy tóm tắt ngắn gọn các ý chính nhất của văn bản sau dưới dạng các gạch đầu dòng rõ ràng:"
    }
}


def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for key, val in DEFAULT_CONFIG.items():
                    if key not in data:
                        data[key] = val

                # Tương thích ngược nếu trước đây lưu owner_id đơn lẻ
                if "owner_id" in data and "owners" not in data:
                    data["owners"] = [data["owner_id"]]

                if DEFAULT_OWNER_ID not in data.get("owners", []):
                    data.setdefault("owners", []).append(DEFAULT_OWNER_ID)

                for oid in data.get("owners", []):
                    if oid not in data.setdefault("admins", []):
                        data["admins"].append(oid)
                    if oid not in data.setdefault("whitelist_users", []):
                        data["whitelist_users"].append(oid)

                if "shortcuts" not in data:
                    data["shortcuts"] = DEFAULT_CONFIG["shortcuts"].copy()

                return data
        except Exception as e:
            logger.error(f"Lỗi đọc {CONFIG_FILE}: {e}")
    return DEFAULT_CONFIG.copy()


def save_config(config_data: dict):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Lỗi lưu {CONFIG_FILE}: {e}")


bot_config = load_config()


def get_owners() -> List[int]:
    return bot_config.get("owners", [DEFAULT_OWNER_ID])


def is_owner(user_id: int) -> bool:
    return user_id in get_owners() or user_id == DEFAULT_OWNER_ID


def is_admin(user_id: int) -> bool:
    if is_owner(user_id):
        return True
    return user_id in bot_config.get("admins", [])


def has_chat_permission(user_id: int, channel_id: int) -> tuple[bool, str]:
    if is_admin(user_id):
        return True, ""

    allowed_channels = bot_config.get("allowed_channels", [])
    if allowed_channels and channel_id not in allowed_channels:
        channel_mentions = ", ".join([f"<#{cid}>" for cid in allowed_channels])
        return False, f"🚫 Bot chỉ được phép hoạt động trong các kênh được chỉ định: {channel_mentions}"

    mode = bot_config.get("access_mode", "restricted")
    if mode == "public":
        return True, ""

    whitelist = bot_config.get("whitelist_users", [])
    if user_id in whitelist:
        return True, ""

    return False, "⛔ Bạn chưa được cấp quyền sử dụng bot! Hãy liên hệ Chủ nhân/Quản trị viên để được duyệt (Whitelist)."


# ---------------------------------------------------------
# 3. Quản lý Bộ nhớ Hội thoại Ngắn hạn
# ---------------------------------------------------------
chat_histories: Dict[int, List[dict]] = {}


def append_history(session_id: int, role: str, content: str):
    if session_id not in chat_histories:
        chat_histories[session_id] = []
    chat_histories[session_id].append({"role": role, "content": content})
    max_history = bot_config.get("max_history", 12)
    if len(chat_histories[session_id]) > max_history * 2:
        chat_histories[session_id] = chat_histories[session_id][-max_history * 2:]


def clear_history(session_id: int):
    if session_id in chat_histories:
        chat_histories[session_id] = []


# ---------------------------------------------------------
# 4. Khởi tạo Discord Bot & Quyền Intents
# ---------------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None
)


# ---------------------------------------------------------
# 5. Cập nhật Code từ GitHub & Tự động Khởi động lại
# ---------------------------------------------------------
def pull_git_update() -> tuple[bool, str]:
    """Kiểm tra và kéo code mới từ GitHub bằng git pull."""
    try:
        res = subprocess.run(["git", "pull"], capture_output=True, text=True, timeout=30)
        output = (res.stdout + "\n" + res.stderr).strip()
        if res.returncode == 0:
            if "Already up to date" in output or "Đã cập nhật" in output:
                return False, "Code hiện tại đã là phiên bản mới nhất từ GitHub!"
            else:
                return True, f"✅ Đã kéo code mới thành công:\n{output}"
        else:
            return False, f"❌ Lỗi khi chạy git pull:\n{output}"
    except Exception as e:
        return False, f"❌ Lỗi thực thi git pull: {e}"


def restart_program():
    """Khởi động lại tiến trình Python bot."""
    print("🔄 Đang khởi động lại bot...")
    python = sys.executable
    os.execl(python, python, *sys.argv)


async def auto_update_background_task():
    """Tự động kiểm tra cập nhật git định kỳ mỗi 30 phút."""
    await bot.wait_until_ready()
    while not bot.is_closed():
        await asyncio.sleep(1800)  # 30 phút kiểm tra 1 lần
        if bot_config.get("auto_update", True):
            has_update, msg = pull_git_update()
            if has_update:
                logger.info("Phát hiện code mới trên GitHub, tự động cập nhật và khởi động lại...")
                restart_program()


# ---------------------------------------------------------
# 6. Hàm Gửi Tin Nhắn Dài (> 2000 ký tự)
# ---------------------------------------------------------
async def send_split_message(destination, text: str, reference: Optional[discord.Message] = None):
    if not text:
        return

    MAX_LEN = 1950
    if len(text) <= MAX_LEN:
        if reference:
            await destination.send(text, reference=reference, mention_author=False)
        else:
            await destination.send(text)
        return

    lines = text.split("\n")
    chunks = []
    current_chunk = ""

    for line in lines:
        if len(current_chunk) + len(line) + 1 > MAX_LEN:
            chunks.append(current_chunk)
            current_chunk = line + "\n"
        else:
            current_chunk += line + "\n"

    if current_chunk:
        chunks.append(current_chunk)

    for i, chunk in enumerate(chunks):
        if i == 0 and reference:
            await destination.send(chunk, reference=reference, mention_author=False)
        else:
            await destination.send(chunk)


# ---------------------------------------------------------
# 7. Gọi DeepSeek API qua aiohttp
# ---------------------------------------------------------
async def generate_deepseek_response(session_id: int, user_text: str) -> str:
    current_key = DEEPSEEK_API_KEY or os.getenv("DEEPSEEK_API_KEY", os.getenv("AI_API_KEY", "")).strip()
    if not current_key:
        return "❌ **Lỗi:** Chưa cấu hình `DEEPSEEK_API_KEY`. Nhập lệnh `api` trên VPS để bổ sung API Key!"

    append_history(session_id, "user", user_text)

    system_prompt = bot_config.get("system_prompt", ORIGINAL_SYSTEM_PROMPT)
    model = bot_config.get("model", "deepseek-chat")

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(chat_histories.get(session_id, []))

    base_url = bot_config.get("base_url", DEEPSEEK_BASE_URL).rstrip("/")
    url = f"{base_url}/chat/completions"

    headers = {
        "Authorization": f"Bearer {current_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://discord.com",
        "X-Title": "Discord AI Bot"
    }

    try:
        timeout = aiohttp.ClientTimeout(total=75)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    choices = data.get("choices", [])
                    if choices and "message" in choices[0]:
                        reply = choices[0]["message"].get("content", "")
                        if not reply:
                            reply = "DeepSeek không trả về nội dung."
                    else:
                        reply = "Không tìm thấy nội dung phản hồi từ DeepSeek."

                    append_history(session_id, "assistant", reply)
                    return reply
                else:
                    err_text = await resp.text()
                    logger.error(f"DeepSeek API lỗi {resp.status}: {err_text}")
                    return f"❌ **Lỗi DeepSeek API (Mã {resp.status}):**\n```{err_text[:300]}```"

    except Exception as e:
        logger.error(f"Lỗi DeepSeek API: {e}", exc_info=True)
        return f"❌ **Lỗi kết nối tới DeepSeek API:**\n```{str(e)[:350]}```"


# ---------------------------------------------------------
# 8. SỰ KIỆN KHI BOT KẾT NỐI (on_ready)
# ---------------------------------------------------------
@bot.event
async def on_ready():
    owners = get_owners()
    owner_str = ", ".join([str(o) for o in owners])

    print("\n" + "=" * 70)
    print("👑 XIN CHÀO CHỦ NHÂN!")
    print(f"🤖 Bot đã kết nối thành công: {bot.user} (ID: {bot.user.id})")
    print(f"👑 Danh sách Chủ nhân: [{owner_str}]")
    print(f"⚙️  Chế độ truy cập: {bot_config.get('access_mode').upper()}")
    print(f"🧠 DeepSeek Model: {bot_config.get('model')}")
    print(f"⚡ Phím tắt nhanh (Shortcuts): {len(bot_config.get('shortcuts', {}))} phím tắt sẵn sàng")
    print(f"🔄 Tự động cập nhật GitHub: {'BẬT (Mỗi 30p)' if bot_config.get('auto_update') else 'TẮT'}")
    print("💻 BẠN CÓ TOÀN QUYỀN ĐIỀU KHIỂN BOT TRỰC TIẾP TẠI ĐÂY (TRÊN VPS)!")
    print("👉 Gõ 'help' để xem toàn bộ danh sách lệnh.")
    print("=" * 70)
    print("\n[VPS-Admin] > ", end="", flush=True)

    activity = discord.Activity(type=discord.ActivityType.listening, name="!ask | !shortcuts | !setting")
    await bot.change_presence(status=discord.Status.online, activity=activity)

    # Gửi DM cho các Chủ nhân
    for oid in owners:
        try:
            owner_user = bot.get_user(oid) or await bot.fetch_user(oid)
            if owner_user:
                embed = discord.Embed(
                    title="👑 XIN CHÀO CHỦ NHÂN!",
                    description=(
                        f"Chào mừng Chủ nhân **{owner_user.name}**!\n"
                        f"Bot DeepSeek đã kết nối thành công từ VPS.\n\n"
                        "💡 **Tính năng nổi bật:**\n"
                        "• `!ask <câu hỏi>` : Chat thông thường\n"
                        "• `!shortcuts` : Danh sách phím tắt prompt nhanh (Ví dụ: `!dich`, `!fixcode`, `!tomtat`)\n"
                        "• `!shortcut add <tên> <prompt>` : Tạo phím tắt tùy chỉnh mới\n"
                        "• `!setting` : Cài đặt bot\n"
                        "• `!update` : Kéo code mới từ GitHub và tự reload"
                    ),
                    color=discord.Color.gold(),
                    timestamp=datetime.now()
                )
                await owner_user.send(embed=embed)
        except Exception:
            pass


# ---------------------------------------------------------
# 9. BẢNG ĐIỀU KHIỂN TRỰC TIẾP TRÊN TERMINAL VPS (CLI)
# ---------------------------------------------------------
def mask_secret(s: str) -> str:
    if not s or len(s) < 8:
        return "Chưa cấu hình"
    return s[:4] + "..." + s[-4:]


def print_vps_help():
    print("""
================================================================================
🛠️  DANH SÁCH LỆNH TOÀN QUYỀN TRÊN MÁY CHỦ VPS (KHÔNG CẦN VÀO DISCORD)
================================================================================
  help                     : Xem bảng hướng dẫn lệnh này
  status                   : Xem trạng thái cấu hình, model, danh sách chủ, key
  restart                  : Khởi động lại bot ngay trên VPS

  🔄 CẬP NHẬT GITHUB:
  update                   : Kéo code mới nhất từ GitHub (git pull) & tự reload
  autoupdate <on|off>      : Bật/tắt tự động kiểm tra cập nhật mỗi 30 phút

  🔑 THAY ĐỔI 1 HOẶC CẢ 2 API KEY:
  api                      : Menu hỏi đổi: [1] DeepSeek Key, [2] Discord Token, [3] Cả hai
  setkey deepseek <key>    : Đổi riêng DeepSeek API Key mới (Áp dụng ngay)
  setkey discord <token>   : Đổi riêng Discord Bot Token mới (Lưu vào .env)
  setkey both <key> <tok>  : Đổi cả 2 API cùng một lúc

  ⚡ PHÍM TẮT DÒNG LỆNH (SHORTCUTS / PROMPT TỰ CHẠY):
  shortcuts / aliases      : Xem danh sách phím tắt hiện có
  shortcut add <tên> <nội dung prompt dài> : Thêm phím tắt tự chạy prompt
  shortcut del <tên>       : Xóa phím tắt

  👑 QUẢN LÝ CHỦ NHÂN & ADMIN:
  owners                   : Xem danh sách ID tất cả các Chủ nhân
  addowner <id>            : Thêm một Chủ nhân mới (Cùng có toàn quyền)
  delowner <id>            : Xóa bớt một Chủ nhân
  admins                   : Xem danh sách ID Admin
  addadmin <id>            : Thêm Admin phụ
  deladmin <id>            : Xóa Admin phụ

  👥 QUẢN LÝ NGƯỜI XÀI BOT:
  users / list / whitelist : Xem danh sách ID người được phép chat
  add <id>                 : Cấp quyền cho một người dùng (Nhập Discord ID)
  del <id>                 : Thu hồi quyền của một người dùng

  🧠 TÍNH CÁCH & MODEL AI:
  model / setmodel         : Menu chọn nhanh model AI (bằng số 1-9) hoặc gõ tên model
  provider <tên> [key]     : Chuyển nhanh nhà cung cấp (openrouter, deepseek, groq, openai)
  seturl <url>             : Đổi Base URL API tùy chỉnh
  prompt                   : Xem System Prompt tính cách AI hiện tại
  setprompt <nội dung>     : Đổi System Prompt tính cách AI trực tiếp
  resetprompt              : Khôi phục Prompt về mặc định ban đầu
  mode <restricted|public> : Đổi chế độ: chỉ whitelist hoặc mở cho cả server

  stop / exit              : Dừng và tắt bot an toàn
================================================================================
""")


def vps_console_listener(loop: asyncio.AbstractEventLoop):
    """Luồng độc lập lắng nghe câu lệnh trực tiếp từ bàn phím VPS."""
    global DEEPSEEK_API_KEY, DISCORD_BOT_TOKEN

    while True:
        try:
            line = input().strip()
            if not line:
                print("[VPS-Admin] > ", end="", flush=True)
                continue

            parts = line.split(maxsplit=2)
            cmd = parts[0].lower()

            if cmd == "help":
                print_vps_help()

            elif cmd == "status":
                owners = get_owners()
                admins = bot_config.get("admins", [])
                whitelist = bot_config.get("whitelist_users", [])
                mode = bot_config.get("access_mode", "restricted")
                model = bot_config.get("model", "deepseek-chat")
                sc = bot_config.get("shortcuts", {})
                au = bot_config.get("auto_update", True)

                print(f"""
📊 TRẠNG THÁI BOT TRÊN MÁY CHỦ:
• Danh sách Chủ nhân ({len(owners)}): {owners}
• Chế độ truy cập: {mode.upper()}
• DeepSeek Model: {model}
• Số người được xài: {len(whitelist)} người
• Số Admin: {len(admins)} người
• Phím tắt tự chạy: {len(sc)} phím tắt
• Tự động cập nhật GitHub: {'BẬT (30 phút/lần)' if au else 'TẮT'}
• Discord Token: {mask_secret(DISCORD_BOT_TOKEN)}
• DeepSeek API Key: {mask_secret(DEEPSEEK_API_KEY)}
""")

            elif cmd == "restart":
                restart_program()

            # Kéo code từ GitHub
            elif cmd == "update":
                print("🔄 Đang kiểm tra và kéo code mới từ GitHub...")
                has_update, msg = pull_git_update()
                print(msg)
                if has_update:
                    ans = input("❓ Bạn có muốn khởi động lại bot ngay để nạp code mới? (y/n): ").strip().lower()
                    if ans == "y":
                        restart_program()

            elif cmd == "autoupdate":
                if len(parts) < 2 or parts[1].lower() not in ["on", "off"]:
                    print("⚠️ Cú pháp: autoupdate on HOẶC autoupdate off")
                else:
                    state = parts[1].lower() == "on"
                    bot_config["auto_update"] = state
                    save_config(bot_config)
                    print(f"⚙️ Tự động cập nhật code GitHub mỗi 30 phút: {'BẬT' if state else 'TẮT'}")

            # Đổi linh hoạt 1 API hoặc cả 2 API qua Menu tương tác
            elif cmd == "api":
                print("""
=============================================================
🔧 THIẾT LẬP API (CHỌN TÙY CHỌN BẠN MUỐN ĐỔI):
[1] Chỉ đổi DeepSeek API Key (AI)
[2] Chỉ đổi Discord Bot Token
[3] Đổi cả hai (DeepSeek Key + Discord Token)
[0] Hủy bỏ
=============================================================
""")
                choice = input("👉 Nhập lựa chọn của bạn (0-3): ").strip()
                if choice == "1":
                    new_ds = input(f"👉 Nhập DeepSeek API Key mới (sk-...): ").strip()
                    if new_ds:
                        DEEPSEEK_API_KEY = new_ds
                        update_env_variable("DEEPSEEK_API_KEY", new_ds)
                        print(f"✅ Đã cập nhật DeepSeek API Key mới: {mask_secret(new_ds)} (Áp dụng ngay)")
                elif choice == "2":
                    new_dis = input(f"👉 Nhập Discord Bot Token mới: ").strip()
                    if new_dis:
                        DISCORD_BOT_TOKEN = new_dis
                        update_env_variable("DISCORD_BOT_TOKEN", new_dis)
                        print(f"✅ Đã lưu Discord Bot Token mới: {mask_secret(new_dis)} vào .env")
                        ans = input("❓ Bạn có muốn khởi động lại bot ngay để nạp token mới? (y/n): ").strip().lower()
                        if ans == "y":
                            restart_program()
                elif choice == "3":
                    new_ds = input(f"👉 [1/2] Nhập DeepSeek API Key mới: ").strip()
                    if new_ds:
                        DEEPSEEK_API_KEY = new_ds
                        update_env_variable("DEEPSEEK_API_KEY", new_ds)
                    new_dis = input(f"👉 [2/2] Nhập Discord Bot Token mới: ").strip()
                    if new_dis:
                        DISCORD_BOT_TOKEN = new_dis
                        update_env_variable("DISCORD_BOT_TOKEN", new_dis)
                    print(f"✅ Đã cập nhật cả 2 API thành công!")
                    ans = input("❓ Bạn có muốn khởi động lại bot ngay để áp dụng đầy đủ? (y/n): ").strip().lower()
                    if ans == "y":
                        restart_program()
                else:
                    print("Đã hủy bỏ thao tác.")

            elif cmd == "setkey":
                if len(parts) < 3:
                    print("⚠️ Cú pháp:")
                    print("• setkey deepseek <api_key_mới>          (Chỉ đổi DeepSeek)")
                    print("• setkey discord <token_mới>             (Chỉ đổi Discord)")
                    print("• setkey both <deepseek_key> <token_dis> (Đổi cả hai)")
                else:
                    service = parts[1].lower()
                    if service in ["deepseek", "ai"]:
                        new_val = parts[2].strip()
                        DEEPSEEK_API_KEY = new_val
                        update_env_variable("DEEPSEEK_API_KEY", new_val)
                        print(f"✅ ĐÃ CẬP NHẬT DeepSeek API Key mới ({mask_secret(new_val)}) và áp dụng ngay!")
                    elif service in ["discord", "bot"]:
                        new_val = parts[2].strip()
                        DISCORD_BOT_TOKEN = new_val
                        update_env_variable("DISCORD_BOT_TOKEN", new_val)
                        print(f"✅ ĐÃ LƯU Discord Bot Token mới ({mask_secret(new_val)}) vào .env! (Gõ 'restart' để nạp)")
                    elif service == "both":
                        sub_tokens = parts[2].strip().split()
                        if len(sub_tokens) < 2:
                            print("⚠️ Cú pháp: setkey both <deepseek_key> <discord_token>")
                        else:
                            k_ds, k_dis = sub_tokens[0], sub_tokens[1]
                            DEEPSEEK_API_KEY = k_ds
                            DISCORD_BOT_TOKEN = k_dis
                            update_env_variable("DEEPSEEK_API_KEY", k_ds)
                            update_env_variable("DISCORD_BOT_TOKEN", k_dis)
                            print("✅ Đã cập nhật cả 2 key thành công! Gõ 'restart' để nạp bot mới.")

            # Quản lý phím tắt (Shortcuts)
            elif cmd in ["shortcuts", "aliases"]:
                sc = bot_config.get("shortcuts", {})
                print(f"\n⚡ DANH SÁCH PHÍM TẮT DÒNG LỆNH HIỆN CÓ ({len(sc)}):")
                if not sc:
                    print("  (Chưa có phím tắt nào)")
                else:
                    for name, prompt_text in sc.items():
                        print(f"  • !{name} => \"{prompt_text}\"")
                print("💡 Trên Discord chỉ cần gõ !<tên> <nội dung> là bot tự động ghép prompt dài!\n")

            elif cmd in ["shortcut", "alias"]:
                if len(parts) < 2:
                    print("⚠️ Cú pháp:")
                    print("• shortcut add <tên_phím_tắt> <prompt_dài>")
                    print("• shortcut del <tên_phím_tắt>")
                    print("• shortcuts (xem danh sách)")
                else:
                    sub = parts[1].lower()
                    if sub == "add":
                        rest = line[len("shortcut add"):].strip() if line.lower().startswith("shortcut add") else line[len("alias add"):].strip()
                        sub_parts = rest.split(maxsplit=1)
                        if len(sub_parts) < 2:
                            print("⚠️ Cú pháp: shortcut add <tên> <nội dung prompt dài>")
                        else:
                            sc_name = sub_parts[0].lower().replace("!", "")
                            sc_prompt = sub_parts[1].strip()
                            bot_config.setdefault("shortcuts", {})[sc_name] = sc_prompt
                            save_config(bot_config)
                            print(f"✅ ĐÃ TẠO PHÍM TẮT '!{sc_name}' THÀNH CÔNG!\nPrompt: \"{sc_prompt}\"")
                    elif sub in ["del", "remove"]:
                        sc_tokens = parts[2].split() if len(parts) > 2 else []
                        if not sc_tokens:
                            print("⚠️ Cú pháp: shortcut del <tên_phím_tắt>")
                        else:
                            sc_name = sc_tokens[0].lower().replace("!", "")
                            sc = bot_config.setdefault("shortcuts", {})
                            if sc_name in sc:
                                del sc[sc_name]
                                save_config(bot_config)
                                print(f"✅ Đã xóa phím tắt '!{sc_name}'.")
                            else:
                                print(f"ℹ️ Không tìm thấy phím tắt '!{sc_name}'.")

            # Quản lý chủ nhân
            elif cmd == "owners":
                owners = get_owners()
                print(f"\n👑 DANH SÁCH CHỦ NHÂN TỐI CAO ({len(owners)}):")
                for oid in owners:
                    print(f"  • ID: {oid}")
                print()

            elif cmd == "addowner":
                if len(parts) < 2:
                    print("⚠️ Cú pháp: addowner <user_id>")
                else:
                    try:
                        new_oid = int(parts[1])
                        owners = bot_config.setdefault("owners", [DEFAULT_OWNER_ID])
                        if new_oid in owners:
                            print(f"ℹ️ User ID {new_oid} đã là Chủ nhân rồi.")
                        else:
                            owners.append(new_oid)
                            if new_oid not in bot_config.setdefault("admins", []):
                                bot_config["admins"].append(new_oid)
                            if new_oid not in bot_config.setdefault("whitelist_users", []):
                                bot_config["whitelist_users"].append(new_oid)
                            save_config(bot_config)
                            print(f"👑 ĐÃ THÊM: User ID {new_oid} làm Chủ nhân tối cao!")
                    except ValueError:
                        print("❌ User ID phải là dãy số!")

            elif cmd == "delowner":
                if len(parts) < 2:
                    print("⚠️ Cú pháp: delowner <user_id>")
                else:
                    try:
                        rem_oid = int(parts[1])
                        owners = bot_config.setdefault("owners", [DEFAULT_OWNER_ID])
                        if rem_oid not in owners:
                            print(f"ℹ️ User ID {rem_oid} không có trong danh sách Chủ nhân.")
                        elif len(owners) <= 1:
                            print("❌ Không thể xóa vì bot phải có ít nhất 1 Chủ nhân!")
                        else:
                            owners.remove(rem_oid)
                            save_config(bot_config)
                            print(f"✅ Đã gỡ quyền Chủ nhân của ID {rem_oid}.")
                    except ValueError:
                        print("❌ User ID phải là dãy số!")

            # Quản lý người xài
            elif cmd in ["users", "list", "whitelist"]:
                whitelist = bot_config.get("whitelist_users", [])
                print(f"\n👥 DANH SÁCH ID NGƯỜI ĐƯỢC XÀI BOT ({len(whitelist)}):")
                if not whitelist:
                    print("  (Trống)")
                else:
                    for uid in whitelist:
                        tag = " (Chủ nhân)" if is_owner(uid) else ""
                        print(f"  • {uid}{tag}")
                print()

            elif cmd in ["add", "grant"]:
                if len(parts) < 2:
                    print("⚠️ Cú pháp: add <user_id>")
                else:
                    try:
                        uid = int(parts[1])
                        whitelist = bot_config.setdefault("whitelist_users", [])
                        if uid in whitelist:
                            print(f"ℹ️ User ID {uid} đã có trong danh sách từ trước.")
                        else:
                            whitelist.append(uid)
                            save_config(bot_config)
                            print(f"✅ ĐÃ THÊM: User ID {uid} được phép xài bot!")
                    except ValueError:
                        print("❌ User ID phải là dãy số!")

            elif cmd in ["del", "revoke", "remove"]:
                if len(parts) < 2:
                    print("⚠️ Cú pháp: del <user_id>")
                else:
                    try:
                        uid = int(parts[1])
                        if is_owner(uid):
                            print("❌ Không thể xóa Chủ nhân khỏi danh sách!")
                        else:
                            whitelist = bot_config.setdefault("whitelist_users", [])
                            if uid in whitelist:
                                whitelist.remove(uid)
                                save_config(bot_config)
                                print(f"🚫 ĐÃ XÓA: User ID {uid} khỏi danh sách sử dụng!")
                            else:
                                print(f"ℹ️ User ID {uid} không có trong danh sách.")
                    except ValueError:
                        print("❌ User ID phải là dãy số!")

            elif cmd == "admins":
                admins = bot_config.get("admins", [])
                print(f"\n🛡️ DANH SÁCH ID ADMIN ({len(admins)}):")
                for aid in admins:
                    tag = " (Chủ nhân)" if is_owner(aid) else ""
                    print(f"  • {aid}{tag}")
                print()

            elif cmd == "addadmin":
                if len(parts) < 2:
                    print("⚠️ Cú pháp: addadmin <user_id>")
                else:
                    try:
                        uid = int(parts[1])
                        admins = bot_config.setdefault("admins", [])
                        whitelist = bot_config.setdefault("whitelist_users", [])
                        if uid in admins:
                            print(f"ℹ️ User ID {uid} đã là Admin từ trước.")
                        else:
                            admins.append(uid)
                            if uid not in whitelist:
                                whitelist.append(uid)
                            save_config(bot_config)
                            print(f"👑 ĐÃ THÊM: User ID {uid} làm Admin bot!")
                    except ValueError:
                        print("❌ User ID phải là dãy số!")

            elif cmd in ["deladmin", "removeadmin"]:
                if len(parts) < 2:
                    print("⚠️ Cú pháp: deladmin <user_id>")
                else:
                    try:
                        uid = int(parts[1])
                        if is_owner(uid):
                            print("❌ Không thể xóa Admin của Chủ nhân!")
                        else:
                            admins = bot_config.setdefault("admins", [])
                            if uid in admins:
                                admins.remove(uid)
                                save_config(bot_config)
                                print(f"✅ Đã gỡ quyền Admin của User ID {uid}.")
                            else:
                                print(f"ℹ️ User ID {uid} không nằm trong danh sách Admin.")
                    except ValueError:
                        print("❌ User ID phải là dãy số!")

            elif cmd == "prompt":
                p = bot_config.get("system_prompt", ORIGINAL_SYSTEM_PROMPT)
                print(f"\n🧠 SYSTEM PROMPT HIỆN TẠI:\n{p}\n")

            elif cmd == "setprompt":
                if len(parts) < 2:
                    print("⚠️ Cú pháp: setprompt <nội dung prompt mới>")
                else:
                    full_p = line[len("setprompt"):].strip()
                    bot_config["system_prompt"] = full_p
                    save_config(bot_config)
                    print(f"✅ ĐÃ CẬP NHẬT SYSTEM PROMPT MỚI:\n> {full_p[:150]}...")

            elif cmd == "resetprompt":
                bot_config["system_prompt"] = ORIGINAL_SYSTEM_PROMPT
                save_config(bot_config)
                print(f"🔄 ĐÃ KHÔI PHỤC SYSTEM PROMPT VỀ MẶC ĐỊNH BAN ĐẦU!")

            elif cmd == "mode":
                if len(parts) < 2 or parts[1].lower() not in ["restricted", "public"]:
                    print("⚠️ Cú pháp: mode restricted (chỉ whitelist) HOẶC mode public (ai cũng xài)")
                else:
                    m = parts[1].lower()
                    bot_config["access_mode"] = m
                    save_config(bot_config)
                    print(f"⚙️ Đã chuyển chế độ truy cập sang: {m.upper()}")

            elif cmd == "seturl":
                if len(parts) < 2:
                    print("⚠️ Cú pháp: seturl <base_url>")
                    print("Ví dụ OpenRouter: seturl https://openrouter.ai/api/v1")
                    print("Ví dụ Groq: seturl https://api.groq.com/openai/v1")
                else:
                    new_url = parts[1].strip()
                    bot_config["base_url"] = new_url
                    save_config(bot_config)
                    update_env_variable("DEEPSEEK_BASE_URL", new_url)
                    print(f"🌐 Đã đổi Base URL thành công: {new_url}")

            elif cmd == "provider":
                if len(parts) < 2:
                    print("""
⚠️ Cú pháp: provider <tên> [api_key]
Các nhà cung cấp có sẵn:
• provider openrouter [key] : Dùng OpenRouter (Có DeepSeek Free, Llama 3.3...)
• provider deepseek [key]   : Dùng DeepSeek gốc
• provider groq [key]       : Dùng Groq Cloud siêu nhanh
• provider openai [key]     : Dùng OpenAI chính chủ
""")
                else:
                    p_name = parts[1].lower()
                    key_provided = parts[2].strip() if len(parts) > 2 else ""

                    if p_name == "openrouter":
                        bot_config["base_url"] = "https://openrouter.ai/api/v1"
                        bot_config["model"] = "deepseek/deepseek-chat:free"
                        update_env_variable("DEEPSEEK_BASE_URL", "https://openrouter.ai/api/v1")
                        update_env_variable("DEEPSEEK_MODEL", "deepseek/deepseek-chat:free")
                        if key_provided:
                            DEEPSEEK_API_KEY = key_provided
                            update_env_variable("DEEPSEEK_API_KEY", key_provided)
                        save_config(bot_config)
                        print("🎉 ĐÃ CHUYỂN SANG OPENROUTER THÀNH CÔNG!")
                        print("• URL: https://openrouter.ai/api/v1")
                        print("• Model: deepseek/deepseek-chat:free (MIỄN PHÍ)")
                        if not key_provided and not DEEPSEEK_API_KEY.startswith("sk-or"):
                            print("👉 Nhập API Key OpenRouter bằng lệnh: setkey deepseek sk-or-v1-...")

                    elif p_name == "deepseek":
                        bot_config["base_url"] = "https://api.deepseek.com"
                        bot_config["model"] = "deepseek-chat"
                        update_env_variable("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
                        update_env_variable("DEEPSEEK_MODEL", "deepseek-chat")
                        if key_provided:
                            DEEPSEEK_API_KEY = key_provided
                            update_env_variable("DEEPSEEK_API_KEY", key_provided)
                        save_config(bot_config)
                        print("🎉 Đã chuyển về DeepSeek gốc (URL: https://api.deepseek.com, Model: deepseek-chat)!")

                    elif p_name == "groq":
                        bot_config["base_url"] = "https://api.groq.com/openai/v1"
                        bot_config["model"] = "llama-3.3-70b-versatile"
                        update_env_variable("DEEPSEEK_BASE_URL", "https://api.groq.com/openai/v1")
                        update_env_variable("DEEPSEEK_MODEL", "llama-3.3-70b-versatile")
                        if key_provided:
                            DEEPSEEK_API_KEY = key_provided
                            update_env_variable("DEEPSEEK_API_KEY", key_provided)
                        save_config(bot_config)
                        print("🎉 Đã chuyển sang Groq Cloud (Model: llama-3.3-70b-versatile)!")

                    elif p_name == "openai":
                        bot_config["base_url"] = "https://api.openai.com/v1"
                        bot_config["model"] = "gpt-4o-mini"
                        update_env_variable("DEEPSEEK_BASE_URL", "https://api.openai.com/v1")
                        update_env_variable("DEEPSEEK_MODEL", "gpt-4o-mini")
                        if key_provided:
                            DEEPSEEK_API_KEY = key_provided
                            update_env_variable("DEEPSEEK_API_KEY", key_provided)
                        save_config(bot_config)
                        print("🎉 Đã chuyển sang OpenAI chính chủ (Model: gpt-4o-mini)!")
                    else:
                        print("❌ Chọn một trong các nhà cung cấp: openrouter, deepseek, groq, openai")

            elif cmd in ["model", "models", "setmodel"]:
                current_m = bot_config.get("model", "deepseek-chat")
                if len(parts) >= 2:
                    m = parts[1].strip()
                    bot_config["model"] = m
                    save_config(bot_config)
                    update_env_variable("DEEPSEEK_MODEL", m)
                    print(f"🧠 Đã đổi model AI sang: {m}")
                else:
                    print(f"""
=============================================================
🧠 CHỌN NHANH MODEL AI (HIỆN TẠI: {current_m})
=============================================================
[1] deepseek-chat                 (DeepSeek-V3 chính chủ)
[2] deepseek-reasoner             (DeepSeek-R1 suy luận chính chủ)
[3] deepseek/deepseek-chat:free   (DeepSeek V3 Miễn Phí trên OpenRouter)
[4] deepseek/deepseek-r1:free     (DeepSeek R1 Miễn Phí trên OpenRouter)
[5] meta-llama/llama-3.3-70b-instruct (Llama 3.3 70B trên OpenRouter)
[6] google/gemini-2.0-flash-exp:free  (Gemini 2.0 Flash Miễn Phí)
[7] llama-3.3-70b-versatile       (Groq Cloud tốc độ cực cao)
[8] gpt-4o-mini                   (OpenAI ChatGPT)
[9] Tự nhập tên model AI khác
[0] Giữ nguyên model hiện tại
=============================================================
""")
                    opt = input("👉 Nhập số lựa chọn (0-9): ").strip()
                    model_map = {
                        "1": "deepseek-chat",
                        "2": "deepseek-reasoner",
                        "3": "deepseek/deepseek-chat:free",
                        "4": "deepseek/deepseek-r1:free",
                        "5": "meta-llama/llama-3.3-70b-instruct",
                        "6": "google/gemini-2.0-flash-exp:free",
                        "7": "llama-3.3-70b-versatile",
                        "8": "gpt-4o-mini"
                    }
                    if opt in model_map:
                        chosen = model_map[opt]
                        bot_config["model"] = chosen
                        save_config(bot_config)
                        update_env_variable("DEEPSEEK_MODEL", chosen)
                        print(f"✅ ĐÃ ĐỔI MODEL SANG: {chosen}")
                    elif opt == "9":
                        custom_m = input("👉 Nhập chính xác tên model AI: ").strip()
                        if custom_m:
                            bot_config["model"] = custom_m
                            save_config(bot_config)
                            update_env_variable("DEEPSEEK_MODEL", custom_m)
                            print(f"✅ ĐÃ ĐỔI MODEL SANG: {custom_m}")
                    else:
                        print("Đã giữ nguyên model.")

            elif cmd in ["stop", "exit", "quit"]:
                print("🛑 Đang đóng bot và tắt tiến trình...")
                asyncio.run_coroutine_threadsafe(bot.close(), loop)
                sys.exit(0)

            else:
                print(f"⚠️ Không nhận diện được lệnh '{cmd}'. Gõ 'help' để xem danh sách lệnh.")

            print("[VPS-Admin] > ", end="", flush=True)

        except (KeyboardInterrupt, EOFError):
            print("\n🛑 Đang thoát...")
            sys.exit(0)
        except Exception as e:
            print(f"❌ Lỗi xử lý lệnh VPS: {e}")
            print("[VPS-Admin] > ", end="", flush=True)


# ---------------------------------------------------------
# 10. HỆ THỐNG CÂU LỆNH TRÊN DISCORD
# ---------------------------------------------------------

# --- LỆNH HỎI AI THƯỜNG (!ask) ---
@bot.command(name="ask")
async def cmd_ask(ctx: commands.Context, *, question: str = ""):
    """Hỏi đáp với DeepSeek AI qua lệnh !ask."""
    if not question.strip():
        await ctx.reply("⚠️ Bạn chưa nhập câu hỏi. Ví dụ: `!ask Giải thích Big O`", mention_author=False)
        return

    allowed, reason = has_chat_permission(ctx.author.id, ctx.channel.id)
    if not allowed:
        await ctx.reply(reason, mention_author=False)
        return

    async with ctx.channel.typing():
        response_text = await generate_deepseek_response(ctx.channel.id, question)
        await send_split_message(ctx.channel, response_text, reference=ctx.message)


# --- XEM HOẶC ĐỔI MODEL TRÊN DISCORD (!model / !models) ---
@bot.command(name="model")
async def cmd_model(ctx: commands.Context, *, new_model: str = ""):
    """Xem hoặc đổi model AI (Chỉ Admin/Chủ nhân mới đổi được)."""
    current_m = bot_config.get("model", "deepseek-chat")
    if not new_model.strip():
        await ctx.reply(f"🧠 **Model AI hiện tại:** `{current_m}`\n💡 Gõ `!models` để xem danh sách gợi ý hoặc `!model <tên_model>` để đổi.", mention_author=False)
        return

    if not is_admin(ctx.author.id):
        await ctx.reply("⛔ Chỉ Admin và Chủ nhân mới có quyền đổi model AI!", mention_author=False)
        return

    m = new_model.strip()
    bot_config["model"] = m
    save_config(bot_config)
    update_env_variable("DEEPSEEK_MODEL", m)
    await ctx.reply(f"✅ **Đã chuyển sang model AI:** `{m}`", mention_author=False)


@bot.command(name="models")
async def cmd_models(ctx: commands.Context):
    """Xem danh sách các model gợi ý phổ biến."""
    current_m = bot_config.get("model", "deepseek-chat")
    embed = discord.Embed(
        title="🧠 DANH SÁCH MODEL AI GỢI Ý",
        description=f"Model đang sử dụng: `{current_m}`\n\nBạn có thể copy tên model dưới đây và gõ `!model <tên>`:",
        color=discord.Color.green()
    )
    embed.add_field(
        name="🌟 DeepSeek Chính Chủ (Cần nạp tiền)",
        value="• `deepseek-chat` : Chat V3 siêu nhanh\n• `deepseek-reasoner` : Suy luận R1",
        inline=False
    )
    embed.add_field(
        name="🎁 Miễn Phí Trên OpenRouter",
        value="• `deepseek/deepseek-chat:free` : DeepSeek V3 Free\n• `deepseek/deepseek-r1:free` : DeepSeek R1 Free\n• `google/gemini-2.0-flash-exp:free` : Gemini 2.0 Flash Free",
        inline=False
    )
    embed.add_field(
        name="⚡ Tốc Độ Cao Khác",
        value="• `llama-3.3-70b-versatile` : Groq Cloud\n• `gpt-4o-mini` : OpenAI ChatGPT",
        inline=False
    )
    embed.set_footer(text="Đổi model: !model <tên_model>")
    await ctx.reply(embed=embed, mention_author=False)


# --- QUẢN LÝ PHÍM TẮT DÒNG LỆNH TRÊN DISCORD (!shortcut / !shortcuts) ---
@bot.command(name="shortcut", aliases=["alias"])
async def cmd_shortcut(ctx: commands.Context, action: str = "", name: str = "", *, prompt: str = ""):
    """Tạo hoặc xóa phím tắt prompt nhanh (Chỉ Chủ nhân / Admin)."""
    if not is_admin(ctx.author.id):
        await ctx.reply("⛔ Lệnh này chỉ dành cho Admin và Chủ nhân bot!", mention_author=False)
        return

    action = action.lower().strip()
    name = name.lower().strip().replace("!", "")

    if action == "add":
        if not name or not prompt:
            await ctx.reply("⚠️ Cú pháp: `!shortcut add <tên> <nội dung prompt dài>`\nVí dụ: `!shortcut add dich Hãy dịch sang tiếng Anh:`", mention_author=False)
            return

        bot_config.setdefault("shortcuts", {})[name] = prompt
        save_config(bot_config)
        await ctx.reply(
            f"✅ **Đã tạo phím tắt `!{name}` thành công!**\n"
            f"👉 Bây giờ mọi người chỉ cần gõ: `!{name} <nội dung>` là bot tự động áp dụng prompt này!",
            mention_author=False
        )

    elif action in ["del", "remove"]:
        if not name:
            await ctx.reply("⚠️ Cú pháp: `!shortcut del <tên_phím_tắt>`", mention_author=False)
            return

        sc = bot_config.setdefault("shortcuts", {})
        if name in sc:
            del sc[name]
            save_config(bot_config)
            await ctx.reply(f"✅ Đã xóa phím tắt `!{name}`.", mention_author=False)
        else:
            await ctx.reply(f"ℹ️ Không tìm thấy phím tắt `!{name}`.", mention_author=False)

    else:
        await ctx.reply(
            "⚠️ Hướng dẫn dùng lệnh Shortcut:\n"
            "• `!shortcut add <tên> <prompt>` : Tạo phím tắt mới\n"
            "• `!shortcut del <tên>` : Xóa phím tắt\n"
            "• `!shortcuts` : Xem danh sách phím tắt",
            mention_author=False
        )


@bot.command(name="shortcuts", aliases=["aliases"])
async def cmd_shortcuts_list(ctx: commands.Context):
    """Xem danh sách các phím tắt hiện có."""
    sc = bot_config.get("shortcuts", {})
    if not sc:
        await ctx.reply("ℹ️ Chưa có phím tắt nào được tạo.", mention_author=False)
        return

    embed = discord.Embed(
        title="⚡ DANH SÁCH PHÍM TẮT DÒNG LỆNH (SHORTCUTS)",
        description="Gõ trực tiếp `!<tên> <nội dung>` để bot tự chạy prompt dài:",
        color=discord.Color.blue()
    )
    for name, p in sc.items():
        embed.add_field(
            name=f"👉 !{name} <nội dung>",
            value=f"_{p[:120]}..._" if len(p) > 120 else f"_{p}_",
            inline=False
        )
    embed.set_footer(text="Thêm phím tắt mới: !shortcut add <tên> <prompt>")
    await ctx.reply(embed=embed, mention_author=False)


# --- CẬP NHẬT CODE GITHUB TỪ DISCORD (!update) ---
@bot.command(name="update")
async def cmd_update(ctx: commands.Context):
    """Kéo code mới nhất từ GitHub về (Chỉ Chủ nhân)."""
    if not is_owner(ctx.author.id):
        await ctx.reply("⛔ Chỉ Chủ nhân tối cao mới có quyền kéo cập nhật!", mention_author=False)
        return

    msg = await ctx.reply("🔄 Đang kiểm tra và kéo code mới từ GitHub...", mention_author=False)
    has_update, res_text = pull_git_update()

    if has_update:
        await msg.edit(content=f"✅ {res_text}\n\n🚀 **Đang khởi động lại bot để áp dụng code mới...**")
        restart_program()
    else:
        await msg.edit(content=f"ℹ️ {res_text}")


# --- CÀI ĐẶT / CẤU HÌNH BOT (!setting / !settings) ---
@bot.command(name="setting", aliases=["settings", "config"])
async def cmd_setting(ctx: commands.Context, sub_cmd: str = "", *, value: str = ""):
    if not is_admin(ctx.author.id):
        await ctx.reply("⛔ Lệnh này chỉ dành cho Admin và Chủ nhân bot!", mention_author=False)
        return

    sub_cmd = sub_cmd.lower().strip()
    value = value.strip()

    if not sub_cmd:
        owners = get_owners()
        owner_str = ", ".join([f"<@{o}>" for o in owners])
        admins = bot_config.get("admins", [])
        admin_str = ", ".join([f"<@{a}>" for a in admins])
        mode = bot_config.get("access_mode", "restricted").upper()
        model = bot_config.get("model", "deepseek-chat")
        history_len = bot_config.get("max_history", 12)
        whitelist = bot_config.get("whitelist_users", [])
        sc_count = len(bot_config.get("shortcuts", {}))

        embed = discord.Embed(
            title="⚙️ BẢNG CÀI ĐẶT & THIẾT LẬP BOT",
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )
        embed.add_field(name="👑 Chủ nhân tối cao", value=owner_str, inline=False)
        embed.add_field(name="🛡️ Danh sách Admin", value=admin_str, inline=False)
        embed.add_field(name="🔒 Chế độ truy cập", value=f"`{mode}`", inline=True)
        embed.add_field(name="🧠 Model DeepSeek", value=f"`{model}`", inline=True)
        embed.add_field(name="💬 Lịch sử nhớ", value=f"`{history_len} tin`", inline=True)
        embed.add_field(name="👥 Số người được xài", value=f"`{len(whitelist)} người`", inline=True)
        embed.add_field(name="⚡ Phím tắt nhanh", value=f"`{sc_count} phím tắt`", inline=True)

        embed.add_field(
            name="🛠️ Lệnh điều chỉnh nhanh:",
            value=(
                "• `!setting mode <restricted|public>` : Đổi chế độ\n"
                "• `!setting model <chat|reasoner>` : Đổi model\n"
                "• `!setting prompt <nội dung>` : Đổi Prompt tính cách\n"
                "• `!setting resetprompt` : Reset Prompt về mặc định\n"
                "• `!setting maxhistory <số>` : Đổi số tin nhớ"
            ),
            inline=False
        )
        await ctx.reply(embed=embed, mention_author=False)
        return

    if sub_cmd == "mode":
        if value.lower() not in ["restricted", "public"]:
            await ctx.reply("⚠️ Chọn: `!setting mode restricted` HOẶC `!setting mode public`", mention_author=False)
            return
        bot_config["access_mode"] = value.lower()
        save_config(bot_config)
        await ctx.reply(f"✅ Đã đổi chế độ sang: **{value.upper()}**", mention_author=False)

    elif sub_cmd == "model":
        if value not in ["deepseek-chat", "deepseek-reasoner", "chat", "reasoner"]:
            await ctx.reply("⚠️ Model hợp lệ: `deepseek-chat` hoặc `deepseek-reasoner`", mention_author=False)
            return
        m = "deepseek-chat" if "chat" in value else "deepseek-reasoner"
        bot_config["model"] = m
        save_config(bot_config)
        await ctx.reply(f"🧠 Đã đổi model AI sang: **{m}**", mention_author=False)

    elif sub_cmd == "prompt":
        if not value:
            current_prompt = bot_config.get("system_prompt", ORIGINAL_SYSTEM_PROMPT)
            await ctx.reply(f"🧠 **System Prompt hiện tại:**\n```text\n{current_prompt}\n```", mention_author=False)
            return
        bot_config["system_prompt"] = value
        save_config(bot_config)
        await ctx.reply(f"✅ **Đã cập nhật System Prompt mới!**", mention_author=False)

    elif sub_cmd == "resetprompt":
        bot_config["system_prompt"] = ORIGINAL_SYSTEM_PROMPT
        save_config(bot_config)
        await ctx.reply(f"🔄 **Đã khôi phục System Prompt về mặc định ban đầu!**", mention_author=False)

    elif sub_cmd == "url":
        if not value:
            current_url = bot_config.get("base_url", DEEPSEEK_BASE_URL)
            await ctx.reply(f"🌐 **Base URL hiện tại:** `{current_url}`", mention_author=False)
            return
        bot_config["base_url"] = value
        save_config(bot_config)
        update_env_variable("DEEPSEEK_BASE_URL", value)
        await ctx.reply(f"✅ Đã đổi Base URL sang: `{value}`", mention_author=False)

    elif sub_cmd == "maxhistory":
        try:
            num = int(value)
            bot_config["max_history"] = num
            save_config(bot_config)
            await ctx.reply(f"✅ Đã đặt số lượng nhớ tối đa: **{num} tin**", mention_author=False)
        except ValueError:
            await ctx.reply("⚠️ Vui lòng nhập số hợp lệ.", mention_author=False)


# --- QUẢN LÝ CHỦ NHÂN & PHÂN QUYỀN TRÊN DISCORD ---
@bot.command(name="owners")
async def cmd_owners(ctx: commands.Context):
    owners = get_owners()
    owner_str = ", ".join([f"<@{o}> (`{o}`)" for o in owners])
    embed = discord.Embed(title="👑 DANH SÁCH CHỦ NHÂN TỐI CAO", description=owner_str, color=discord.Color.gold())
    await ctx.reply(embed=embed, mention_author=False)


@bot.command(name="addowner")
async def cmd_addowner(ctx: commands.Context, member: Optional[discord.Member] = None):
    if not is_owner(ctx.author.id):
        await ctx.reply("⛔ Chỉ Chủ nhân hiện tại mới có quyền thêm Chủ nhân!", mention_author=False)
        return
    if member is None:
        await ctx.reply("⚠️ Tag người bạn muốn phong làm Chủ nhân: `!addowner @user`", mention_author=False)
        return

    owners = bot_config.setdefault("owners", [DEFAULT_OWNER_ID])
    if member.id in owners:
        await ctx.reply(f"ℹ️ {member.mention} đã là Chủ nhân từ trước.", mention_author=False)
        return

    owners.append(member.id)
    if member.id not in bot_config.setdefault("admins", []):
        bot_config["admins"].append(member.id)
    if member.id not in bot_config.setdefault("whitelist_users", []):
        bot_config["whitelist_users"].append(member.id)

    save_config(bot_config)
    await ctx.reply(f"👑 **ĐÃ THÊM CHỦ NHÂN:** Chúc mừng {member.mention} đã trở thành Chủ nhân tối cao!", mention_author=False)


@bot.command(name="delowner")
async def cmd_delowner(ctx: commands.Context, member: Optional[discord.Member] = None):
    if not is_owner(ctx.author.id):
        await ctx.reply("⛔ Chỉ Chủ nhân mới được xóa Chủ nhân!", mention_author=False)
        return
    if member is None:
        await ctx.reply("⚠️ Tag thành viên: `!delowner @user`", mention_author=False)
        return

    owners = bot_config.setdefault("owners", [DEFAULT_OWNER_ID])
    if member.id not in owners:
        await ctx.reply(f"ℹ️ {member.mention} không nằm trong danh sách Chủ nhân.", mention_author=False)
        return
    if len(owners) <= 1:
        await ctx.reply("❌ Không thể xóa vì bot phải giữ ít nhất 1 Chủ nhân!", mention_author=False)
        return

    owners.remove(member.id)
    save_config(bot_config)
    await ctx.reply(f"✅ Đã gỡ quyền Chủ nhân của {member.mention}.", mention_author=False)


@bot.command(name="grant", aliases=["add"])
async def cmd_grant(ctx: commands.Context, member: Optional[discord.Member] = None):
    if not is_admin(ctx.author.id):
        await ctx.reply("⛔ Bạn không có quyền Admin/Chủ nhân!", mention_author=False)
        return
    if member is None:
        await ctx.reply("⚠️ Tag thành viên: `!grant @user` hoặc `!add @user`", mention_author=False)
        return

    whitelist = bot_config.setdefault("whitelist_users", [])
    if member.id in whitelist:
        await ctx.reply(f"ℹ️ {member.mention} đã có trong danh sách từ trước.", mention_author=False)
        return

    whitelist.append(member.id)
    save_config(bot_config)
    await ctx.reply(f"✅ Đã thêm {member.mention} vào danh sách được phép sử dụng bot!", mention_author=False)


@bot.command(name="revoke", aliases=["del", "remove"])
async def cmd_revoke(ctx: commands.Context, member: Optional[discord.Member] = None):
    if not is_admin(ctx.author.id):
        await ctx.reply("⛔ Bạn không có quyền Admin/Chủ nhân!", mention_author=False)
        return
    if member is None:
        await ctx.reply("⚠️ Tag thành viên: `!revoke @user` hoặc `!del @user`", mention_author=False)
        return
    if is_owner(member.id):
        await ctx.reply("❌ Không thể xóa quyền của Chủ nhân!", mention_author=False)
        return

    whitelist = bot_config.setdefault("whitelist_users", [])
    if member.id not in whitelist:
        await ctx.reply(f"ℹ️ {member.mention} không có trong danh sách được cấp quyền.", mention_author=False)
        return

    whitelist.remove(member.id)
    save_config(bot_config)
    await ctx.reply(f"🚫 Đã xóa {member.mention} khỏi danh sách sử dụng bot.", mention_author=False)


@bot.command(name="clear")
async def cmd_clear(ctx: commands.Context):
    clear_history(ctx.channel.id)
    await ctx.reply("🧹 Đã làm sạch ngữ cảnh hội thoại kênh này!", mention_author=False)


@bot.command(name="help")
async def cmd_help(ctx: commands.Context):
    embed = discord.Embed(
        title="🤖 DEEPSEEK DISCORD BOT - HƯỚNG DẪN",
        description="Bot trợ lý AI DeepSeek hỗ trợ phím tắt tự chạy prompt và điều khiển toàn diện.",
        color=discord.Color.gold()
    )
    embed.add_field(
        name="💬 Dành Cho Người Dùng",
        value=(
            "• `!ask <câu hỏi>` : Chat thông thường với DeepSeek\n"
            "• `!<tên_phím_tắt> <nội dung>` : Chạy phím tắt nhanh (Ví dụ: `!dich <văn bản>`, `!fixcode <code lỗi>`)\n"
            "• `!shortcuts` : Xem danh sách phím tắt prompt nhanh\n"
            "• `!clear` : Làm sạch ngữ cảnh hội thoại cũ"
        ),
        inline=False
    )
    if is_admin(ctx.author.id):
        embed.add_field(
            name="🛠️ Dành Cho Admin & Chủ Nhân",
            value=(
                "• `!shortcut add <tên> <prompt>` : Tạo thêm phím tắt prompt mới\n"
                "• `!shortcut del <tên>` : Xóa phím tắt\n"
                "• `!setting` : Xem & chỉnh cài đặt bot\n"
                "• `!grant @user` / `!revoke @user` : Thêm / Xóa người xài\n"
                "• `!update` : Kéo code mới từ GitHub & tự reload"
            ),
            inline=False
        )
    await ctx.reply(embed=embed, mention_author=False)


# --- XỬ LÝ PHÍM TẮT DÒNG LỆNH TỰ CHẠY TRONG ON_MESSAGE ---
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    content = message.content.strip()

    # 1. Kiểm tra xem có khớp với Phím tắt (Shortcut) nào không
    if content.startswith("!"):
        parts = content[1:].split(maxsplit=1)
        trigger = parts[0].lower()
        shortcuts = bot_config.get("shortcuts", {})

        if trigger in shortcuts:
            allowed, reason = has_chat_permission(message.author.id, message.channel.id)
            if not allowed:
                await message.reply(reason, mention_author=False)
                return

            prefix_prompt = shortcuts[trigger]
            user_input = parts[1].strip() if len(parts) > 1 else ""

            # Gộp prompt dài đã cài sẵn với nội dung người dùng gõ
            if user_input:
                final_prompt = f"{prefix_prompt}\n\n{user_input}"
            else:
                final_prompt = prefix_prompt

            async with message.channel.typing():
                response_text = await generate_deepseek_response(message.channel.id, final_prompt)
                await send_split_message(message.channel, response_text, reference=message)
            return

    # 2. Xử lý các lệnh prefix chuẩn (!ask, !setting, v.v.)
    ctx = await bot.get_context(message)
    if ctx.valid:
        await bot.process_commands(message)
        return

    # 3. Mention @Bot hoặc DM
    is_dm = isinstance(message.channel, discord.DMChannel)
    is_mentioned = bot.user in message.mentions

    if is_mentioned or is_dm:
        allowed, reason = has_chat_permission(message.author.id, message.channel.id)
        if not allowed:
            await message.reply(reason, mention_author=False)
            return

        cleaned_text = message.content
        if is_mentioned and bot.user:
            cleaned_text = cleaned_text.replace(f"<@{bot.user.id}>", "").replace(f"<@!{bot.user.id}>", "").strip()

        if not cleaned_text:
            await message.reply(f"Xin chào {message.author.mention}! Hãy đặt câu hỏi sau khi tag tôi nhé 😊", mention_author=False)
            return

        async with message.channel.typing():
            response_text = await generate_deepseek_response(message.channel.id, cleaned_text)
            await send_split_message(message.channel, response_text, reference=message)


# ---------------------------------------------------------
# 11. TỰ ĐỘNG HỎI TOKEN LẦN ĐẦU & KHỞI CHẠY BOT
# ---------------------------------------------------------
def setup_first_time_interactive():
    global DISCORD_BOT_TOKEN, DEEPSEEK_API_KEY

    needs_token = not DISCORD_BOT_TOKEN or DISCORD_BOT_TOKEN.startswith("your_")
    needs_api = not DEEPSEEK_API_KEY or DEEPSEEK_API_KEY.startswith("your_") or DEEPSEEK_API_KEY.startswith("sk-xxxx")

    if not needs_token and not needs_api:
        return

    print("\n" + "=" * 65)
    print("🌟 CÀI ĐẶT LẦN ĐẦU TIÊN TRÊN MÁY CHỦ VPS / TERMUX 🌟")
    print("Vui lòng nhập Token và Key cần thiết:")
    print("=" * 65)

    if needs_token:
        while True:
            try:
                token_input = input("\n👉 [1/2] Nhập Discord Bot Token: ").strip()
                if token_input:
                    DISCORD_BOT_TOKEN = token_input
                    break
                print("⚠️ Token Discord không được để trống!")
            except (KeyboardInterrupt, EOFError):
                sys.exit(0)

    if needs_api:
        while True:
            try:
                api_input = input("👉 [2/2] Nhập DeepSeek API Key (sk-...): ").strip()
                if api_input:
                    DEEPSEEK_API_KEY = api_input
                    break
                print("⚠️ DeepSeek API Key không được để trống!")
            except (KeyboardInterrupt, EOFError):
                sys.exit(0)

    update_env_variable("DISCORD_BOT_TOKEN", DISCORD_BOT_TOKEN)
    update_env_variable("DEEPSEEK_API_KEY", DEEPSEEK_API_KEY)
    update_env_variable("DEEPSEEK_BASE_URL", DEEPSEEK_BASE_URL)
    update_env_variable("DEEPSEEK_MODEL", DEFAULT_MODEL)
    update_env_variable("OWNER_ID", str(DEFAULT_OWNER_ID))
    print("\n✅ Đã lưu cấu hình vào file .env!")


async def run_bot_async():
    # Chạy song song task tự động kiểm tra code mới từ GitHub
    asyncio.create_task(auto_update_background_task())
    await bot.start(DISCORD_BOT_TOKEN)


def main():
    setup_first_time_interactive()

    if not DISCORD_BOT_TOKEN:
        print("❌ LỖI: Chưa có DISCORD_BOT_TOKEN!")
        sys.exit(1)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Chạy song song luồng lắng nghe lệnh console trên VPS
    console_thread = threading.Thread(
        target=vps_console_listener,
        args=(loop,),
        daemon=True
    )
    console_thread.start()

    try:
        loop.run_until_complete(run_bot_async())
    except discord.LoginFailure:
        print("\n❌ LỖI ĐĂNG NHẬP: DISCORD_BOT_TOKEN không hợp lệ!")
    except KeyboardInterrupt:
        print("\n🛑 Bot đã dừng.")
    finally:
        loop.close()


if __name__ == "__main__":
    main()
