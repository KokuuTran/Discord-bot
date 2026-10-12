"""
╔══════════════════════════════════════════════════════════════════╗
║           AI Discord Bot - Multi-Provider Edition               ║
║  Hỗ trợ: DeepSeek | OpenRouter | Groq | OpenAI | Gemini        ║
║  Giao diện: Discord (prefix !) + VPS Console (CLI)             ║
╚══════════════════════════════════════════════════════════════════╝
"""

# ================================================================
# PHẦN 1 — THƯ VIỆN & IMPORTS
# ================================================================
import os
import sys
import json
import logging
import threading
import asyncio
import subprocess
from datetime import datetime
from typing import Dict, List, Optional

import discord
from discord.ext import commands
from dotenv import load_dotenv
import aiohttp

# ================================================================
# PHẦN 2 — NẠP CẤU HÌNH & BIẾN MÔI TRƯỜNG
# ================================================================
load_dotenv()

DEFAULT_OWNER_ID = int(os.getenv("OWNER_ID", "1124340099111473232"))

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "").strip()
AI_API_KEY        = os.getenv("AI_API_KEY", os.getenv("DEEPSEEK_API_KEY", "")).strip()
AI_BASE_URL       = os.getenv("AI_BASE_URL", os.getenv("DEEPSEEK_BASE_URL", "https://openrouter.ai/api/v1")).strip()
AI_MODEL          = os.getenv("AI_MODEL", os.getenv("DEEPSEEK_MODEL", "deepseek/deepseek-chat:free")).strip()

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot_config.json")
ENV_FILE    = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

DEFAULT_SYSTEM_PROMPT = (
    "Bạn là một trợ lý AI thông minh, thân thiện và hữu ích. "
    "Hãy trả lời rõ ràng, sử dụng Markdown khi cần, ưu tiên ngôn ngữ của người dùng."
)

# ================================================================
# PHẦN 3 — LOGGING
# ================================================================
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("AIBot")
logger.setLevel(logging.INFO)

# ================================================================
# PHẦN 4 — DANH SÁCH MODEL GỢI Ý (để dùng trong menu)
# ================================================================
MODEL_LIST = [
    # (tên hiển thị, tên model, base_url)
    ("DeepSeek V3 Free (OpenRouter)",      "deepseek/deepseek-chat:free",              "https://openrouter.ai/api/v1"),
    ("DeepSeek R1 Free (OpenRouter)",      "deepseek/deepseek-r1:free",                "https://openrouter.ai/api/v1"),
    ("Gemini 2.0 Flash Free (OpenRouter)", "google/gemini-2.0-flash-exp:free",         "https://openrouter.ai/api/v1"),
    ("Gemini 2.5 Pro Free (OpenRouter)",   "google/gemini-2.5-pro-exp-03-25:free",     "https://openrouter.ai/api/v1"),
    ("Llama 3.3 70B Free (OpenRouter)",    "meta-llama/llama-3.3-70b-instruct:free",   "https://openrouter.ai/api/v1"),
    ("Qwen 2.5 72B Free (OpenRouter)",     "qwen/qwen2.5-72b-instruct:free",           "https://openrouter.ai/api/v1"),
    ("Mistral 7B Free (OpenRouter)",       "mistralai/mistral-7b-instruct:free",       "https://openrouter.ai/api/v1"),
    ("DeepSeek V3 (Chính chủ)",           "deepseek-chat",                             "https://api.deepseek.com"),
    ("DeepSeek R1 Reasoner (Chính chủ)",  "deepseek-reasoner",                         "https://api.deepseek.com"),
    ("Llama 3.3 70B (Groq - Siêu nhanh)", "llama-3.3-70b-versatile",                  "https://api.groq.com/openai/v1"),
    ("Mixtral 8x7B (Groq)",               "mixtral-8x7b-32768",                        "https://api.groq.com/openai/v1"),
    ("GPT-4o Mini (OpenAI)",              "gpt-4o-mini",                               "https://api.openai.com/v1"),
    ("GPT-4o (OpenAI)",                   "gpt-4o",                                    "https://api.openai.com/v1"),
]

PROVIDER_PRESETS = {
    "openrouter": {
        "url":   "https://openrouter.ai/api/v1",
        "model": "deepseek/deepseek-chat:free",
        "note":  "OpenRouter (DeepSeek Free mặc định — đổi model tùy thích)"
    },
    "deepseek": {
        "url":   "https://api.deepseek.com",
        "model": "deepseek-chat",
        "note":  "DeepSeek chính chủ"
    },
    "groq": {
        "url":   "https://api.groq.com/openai/v1",
        "model": "llama-3.3-70b-versatile",
        "note":  "Groq Cloud (tốc độ cực cao)"
    },
    "openai": {
        "url":   "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "note":  "OpenAI chính chủ"
    },
}

# ================================================================
# PHẦN 5 — QUẢN LÝ FILE .ENV & BOT_CONFIG.JSON
# ================================================================
def update_env_variable(key: str, value: str):
    """Cập nhật hoặc thêm một biến vào file .env và nạp vào os.environ ngay."""
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
    "is_setup":         True,
    "owners":           [DEFAULT_OWNER_ID],
    "admins":           [DEFAULT_OWNER_ID],
    "whitelist_users":  [DEFAULT_OWNER_ID],
    "allowed_channels": [],
    "access_mode":      "restricted",
    "model":            AI_MODEL,
    "base_url":         AI_BASE_URL,
    "system_prompt":    DEFAULT_SYSTEM_PROMPT,
    "max_history":      12,
    "auto_update":      False,
    "shortcuts": {
        "dich":    "Hãy dịch văn bản sau sang tiếng Anh chuẩn và giải thích từ vựng quan trọng:",
        "fixcode": "Hãy tìm lỗi, sửa và giải thích chi tiết đoạn code sau:",
        "tomtat":  "Hãy tóm tắt các ý chính bằng gạch đầu dòng ngắn gọn:"
    }
}


def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Bổ sung key mới nếu thiếu
            for key, val in DEFAULT_CONFIG.items():
                if key not in data:
                    data[key] = val
            # Tương thích ngược
            if "owner_id" in data and "owners" not in data:
                data["owners"] = [data["owner_id"]]
            if DEFAULT_OWNER_ID not in data.get("owners", []):
                data.setdefault("owners", []).append(DEFAULT_OWNER_ID)
            for oid in data.get("owners", []):
                if oid not in data.setdefault("admins", []):
                    data["admins"].append(oid)
                if oid not in data.setdefault("whitelist_users", []):
                    data["whitelist_users"].append(oid)
            return data
        except Exception as e:
            logger.error(f"Lỗi đọc config: {e}")
    return DEFAULT_CONFIG.copy()


def save_config(cfg: dict):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Lỗi lưu config: {e}")


bot_config = load_config()

# ================================================================
# PHẦN 6 — PHÂN QUYỀN
# ================================================================
def get_owners() -> List[int]:
    return bot_config.get("owners", [DEFAULT_OWNER_ID])


def is_owner(uid: int) -> bool:
    return uid in get_owners() or uid == DEFAULT_OWNER_ID


def is_admin(uid: int) -> bool:
    return is_owner(uid) or uid in bot_config.get("admins", [])


def has_chat_permission(uid: int, channel_id: int) -> tuple:
    if is_admin(uid):
        return True, ""
    allowed_channels = bot_config.get("allowed_channels", [])
    if allowed_channels and channel_id not in allowed_channels:
        ch_mentions = ", ".join([f"<#{c}>" for c in allowed_channels])
        return False, f"🚫 Bot chỉ hoạt động trong: {ch_mentions}"
    if bot_config.get("access_mode") == "public":
        return True, ""
    if uid in bot_config.get("whitelist_users", []):
        return True, ""
    return False, "⛔ Bạn chưa được cấp quyền dùng bot! Hãy liên hệ Admin."

# ================================================================
# PHẦN 7 — LỊCH SỬ HỘI THOẠI
# ================================================================
chat_histories: Dict[int, List[dict]] = {}


def append_history(session_id: int, role: str, content: str):
    hist = chat_histories.setdefault(session_id, [])
    hist.append({"role": role, "content": content})
    max_h = bot_config.get("max_history", 12)
    if len(hist) > max_h * 2:
        chat_histories[session_id] = hist[-max_h * 2:]


def clear_history(session_id: int):
    chat_histories[session_id] = []

# ================================================================
# PHẦN 8 — GỌI AI API (qua aiohttp, tương thích OpenAI format)
# ================================================================
async def generate_ai_response(session_id: int, user_text: str) -> str:
    global AI_API_KEY
    current_key = AI_API_KEY or os.getenv("AI_API_KEY", os.getenv("DEEPSEEK_API_KEY", "")).strip()
    if not current_key:
        return (
            "❌ **Chưa cấu hình API Key!**\n"
            "Trên terminal VPS gõ: `api` để nhập key mới."
        )

    append_history(session_id, "user", user_text)

    model    = bot_config.get("model", AI_MODEL)
    base_url = bot_config.get("base_url", AI_BASE_URL).rstrip("/")
    sys_prompt = bot_config.get("system_prompt", DEFAULT_SYSTEM_PROMPT)

    messages = [{"role": "system", "content": sys_prompt}]
    messages.extend(chat_histories.get(session_id, []))

    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization":  f"Bearer {current_key}",
        "Content-Type":   "application/json",
        "HTTP-Referer":   "https://discord.com",
        "X-Title":        "AI Discord Bot"
    }
    payload = {
        "model":       model,
        "messages":    messages,
        "temperature": 0.7,
        "max_tokens":  2048
    }

    try:
        timeout = aiohttp.ClientTimeout(total=90)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status == 200:
                    data    = await resp.json()
                    choices = data.get("choices", [])
                    if choices and "message" in choices[0]:
                        reply = choices[0]["message"].get("content", "").strip()
                        if not reply:
                            reply = "*(AI không trả về nội dung)*"
                    else:
                        reply = "*(Không tìm thấy nội dung phản hồi)*"
                    append_history(session_id, "assistant", reply)
                    return reply
                else:
                    err = await resp.text()
                    logger.error(f"AI API lỗi {resp.status}: {err}")
                    # Thông báo lỗi thân thiện hơn
                    if resp.status == 401:
                        return f"❌ **Lỗi 401 — API Key không hợp lệ!**\nGõ `api` trên VPS để đổi key mới."
                    if resp.status == 402:
                        return f"❌ **Lỗi 402 — Hết credit!**\nNạp thêm tiền hoặc đổi sang model miễn phí (gõ `model` trên VPS)."
                    if resp.status == 429:
                        return f"❌ **Lỗi 429 — Quá nhiều request!**\nHãy thử lại sau vài giây."
                    return f"❌ **Lỗi API (HTTP {resp.status}):**\n```{err[:300]}```"
    except asyncio.TimeoutError:
        return "❌ **Hết thời gian chờ (timeout 90s).** Thử lại nhé!"
    except Exception as e:
        logger.error(f"Lỗi AI API: {e}", exc_info=True)
        return f"❌ **Lỗi kết nối AI:**\n```{str(e)[:300]}```"

# ================================================================
# PHẦN 9 — TIỆN ÍCH: CHIA TIN NHẮN DÀI & MASK SECRET
# ================================================================
async def send_split_message(dest, text: str, reference: Optional[discord.Message] = None):
    if not text:
        return
    MAX_LEN = 1950
    if len(text) <= MAX_LEN:
        if reference:
            await dest.send(text, reference=reference, mention_author=False)
        else:
            await dest.send(text)
        return

    lines   = text.split("\n")
    chunks  = []
    current = ""
    for line in lines:
        if len(current) + len(line) + 1 > MAX_LEN:
            chunks.append(current)
            current = line + "\n"
        else:
            current += line + "\n"
    if current:
        chunks.append(current)

    for i, chunk in enumerate(chunks):
        if i == 0 and reference:
            await dest.send(chunk, reference=reference, mention_author=False)
        else:
            await dest.send(chunk)


def mask(s: str) -> str:
    if not s or len(s) < 8:
        return "(chưa cấu hình)"
    return s[:4] + "..." + s[-4:]

# ================================================================
# PHẦN 10 — KHỞI TẠO DISCORD BOT
# ================================================================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None
)

# ================================================================
# PHẦN 11 — SỰ KIỆN ON_READY
# ================================================================
@bot.event
async def on_ready():
    owners    = get_owners()
    owner_str = ", ".join(str(o) for o in owners)
    model     = bot_config.get("model", AI_MODEL)
    url       = bot_config.get("base_url", AI_BASE_URL)
    mode      = bot_config.get("access_mode", "restricted").upper()
    sc_count  = len(bot_config.get("shortcuts", {}))
    au        = bot_config.get("auto_update", False)

    print("\n" + "=" * 68)
    print("👑  XIN CHÀO CHỦ NHÂN! BOT ĐÃ KẾT NỐI THÀNH CÔNG!")
    print(f"🤖  Bot: {bot.user}  (ID: {bot.user.id})")
    print(f"👑  Chủ nhân: {owner_str}")
    print(f"🧠  Model AI : {model}")
    print(f"🌐  Base URL : {url}")
    print(f"🔒  Chế độ   : {mode}")
    print(f"⚡  Phím tắt : {sc_count} shortcuts sẵn sàng")
    print(f"🔄  Auto-update GitHub: {'BẬT' if au else 'TẮT'}")
    print("=" * 68)
    print("💻  BẠN CÓ TOÀN QUYỀN ĐIỀU KHIỂN BOT TẠI ĐÂY!")
    print("    Gõ  help  để xem toàn bộ lệnh VPS.")
    print("=" * 68)
    print("\n[VPS] > ", end="", flush=True)

    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Activity(
            type=discord.ActivityType.listening,
            name="!ask | !ai | !help"
        )
    )

    # Gửi DM chào chủ nhân
    for oid in owners:
        try:
            user = bot.get_user(oid) or await bot.fetch_user(oid)
            if user:
                embed = discord.Embed(
                    title="👑 XIN CHÀO CHỦ NHÂN!",
                    description=(
                        f"Chào **{user.display_name}**! Bot AI đã online.\n\n"
                        "**Lệnh cơ bản:**\n"
                        "• `!ask <câu hỏi>` hoặc `!ai <câu hỏi>` — Chat với AI\n"
                        "• `!models` — Danh sách model AI\n"
                        "• `!shortcuts` — Danh sách phím tắt prompt\n"
                        "• `!setting` — Cài đặt bot\n"
                        "• `!help` — Toàn bộ lệnh"
                    ),
                    color=discord.Color.gold(),
                    timestamp=datetime.now()
                )
                embed.set_footer(text=f"Model: {model}")
                await user.send(embed=embed)
        except Exception:
            pass


# ================================================================
# PHẦN 12 — XỬ LÝ TIN NHẮN (ON_MESSAGE): Shortcuts + Mention/DM
# ================================================================
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    content = message.content.strip()

    # --- Xử lý phím tắt shortcut (ví dụ: !dich, !fixcode) ---
    if content.startswith("!"):
        raw     = content[1:]
        parts   = raw.split(maxsplit=1)
        trigger = parts[0].lower() if parts else ""
        sc      = bot_config.get("shortcuts", {})

        if trigger in sc:
            allowed, reason = has_chat_permission(message.author.id, message.channel.id)
            if not allowed:
                await message.reply(reason, mention_author=False)
                return

            prefix      = sc[trigger]
            user_input  = parts[1].strip() if len(parts) > 1 else ""
            final_query = f"{prefix}\n\n{user_input}" if user_input else prefix

            async with message.channel.typing():
                resp = await generate_ai_response(message.channel.id, final_query)
                await send_split_message(message.channel, resp, reference=message)
            return  # Dừng — không xử lý tiếp là lệnh prefix

    # --- Xử lý lệnh prefix chuẩn (!ask, !setting, v.v.) ---
    ctx = await bot.get_context(message)
    if ctx.valid:
        await bot.process_commands(message)
        return

    # --- Xử lý mention @Bot hoặc DM ---
    is_dm       = isinstance(message.channel, discord.DMChannel)
    is_mentioned = bot.user and bot.user in message.mentions

    if is_mentioned or is_dm:
        allowed, reason = has_chat_permission(message.author.id, message.channel.id)
        if not allowed:
            await message.reply(reason, mention_author=False)
            return

        text = message.content
        if is_mentioned and bot.user:
            text = text.replace(f"<@{bot.user.id}>", "").replace(f"<@!{bot.user.id}>", "").strip()

        if not text:
            await message.reply(f"Xin chào {message.author.mention}! Hỏi tôi điều gì đó nha 😊", mention_author=False)
            return

        async with message.channel.typing():
            resp = await generate_ai_response(message.channel.id, text)
            await send_split_message(message.channel, resp, reference=message)


# ================================================================
# PHẦN 13 — CÁC LỆNH DISCORD
# ================================================================

# ---------- !ask / !ai — Chat với AI ----------
@bot.command(name="ask", aliases=["ai", "chat"])
async def cmd_ask(ctx: commands.Context, *, question: str = ""):
    if not question.strip():
        await ctx.reply("⚠️ Chưa nhập câu hỏi!\nVí dụ: `!ask Giải thích recursion là gì?`", mention_author=False)
        return
    allowed, reason = has_chat_permission(ctx.author.id, ctx.channel.id)
    if not allowed:
        await ctx.reply(reason, mention_author=False)
        return
    async with ctx.channel.typing():
        resp = await generate_ai_response(ctx.channel.id, question)
        await send_split_message(ctx.channel, resp, reference=ctx.message)


# ---------- !model — Xem / đổi model AI ----------
@bot.command(name="model")
async def cmd_model(ctx: commands.Context, *, new_model: str = ""):
    current = bot_config.get("model", AI_MODEL)
    if not new_model.strip():
        await ctx.reply(
            f"🧠 **Model AI hiện tại:** `{current}`\n"
            f"🌐 **Base URL:** `{bot_config.get('base_url', AI_BASE_URL)}`\n"
            "💡 Gõ `!models` để xem danh sách gợi ý.",
            mention_author=False
        )
        return

    if not is_admin(ctx.author.id):
        await ctx.reply("⛔ Chỉ Admin/Chủ nhân mới được đổi model!", mention_author=False)
        return

    m     = new_model.strip()
    note  = ""

    # Tự động chuyển URL nếu model là OpenRouter format (có dấu /)
    if "/" in m and "openrouter.ai" not in bot_config.get("base_url", ""):
        bot_config["base_url"] = "https://openrouter.ai/api/v1"
        update_env_variable("AI_BASE_URL", "https://openrouter.ai/api/v1")
        note = "\n🌐 *Tự động chuyển sang OpenRouter URL.*"
    elif m in ("deepseek-chat", "deepseek-reasoner") and "openrouter.ai" in bot_config.get("base_url", ""):
        bot_config["base_url"] = "https://api.deepseek.com"
        update_env_variable("AI_BASE_URL", "https://api.deepseek.com")
        note = "\n🌐 *Tự động chuyển về DeepSeek URL.*"
    elif m in ("llama-3.3-70b-versatile", "mixtral-8x7b-32768") and "groq.com" not in bot_config.get("base_url", ""):
        bot_config["base_url"] = "https://api.groq.com/openai/v1"
        update_env_variable("AI_BASE_URL", "https://api.groq.com/openai/v1")
        note = "\n🌐 *Tự động chuyển sang Groq URL.*"

    bot_config["model"] = m
    save_config(bot_config)
    update_env_variable("AI_MODEL", m)
    await ctx.reply(f"✅ **Đã đổi sang model:** `{m}`{note}", mention_author=False)


# ---------- !models — Danh sách model gợi ý ----------
@bot.command(name="models")
async def cmd_models(ctx: commands.Context):
    current = bot_config.get("model", AI_MODEL)
    embed   = discord.Embed(
        title="🧠 DANH SÁCH MODEL AI GỢI Ý",
        description=f"Đang dùng: `{current}`\n\nCopy tên model rồi gõ `!model <tên>`:",
        color=discord.Color.blue()
    )
    free_models    = []
    paid_models    = []
    groq_models    = []

    for display, name, url in MODEL_LIST:
        line = f"`{name}`"
        if "openrouter" in url:
            free_models.append(f"• {line} — {display}")
        elif "groq" in url:
            groq_models.append(f"• {line} — {display}")
        else:
            paid_models.append(f"• {line} — {display}")

    if free_models:
        embed.add_field(name="🎁 Miễn phí (OpenRouter)", value="\n".join(free_models), inline=False)
    if groq_models:
        embed.add_field(name="⚡ Siêu nhanh (Groq)", value="\n".join(groq_models), inline=False)
    if paid_models:
        embed.add_field(name="💳 Chính chủ (trả phí)", value="\n".join(paid_models), inline=False)

    embed.set_footer(text="Đổi model: !model <tên model>  |  Đổi URL: !setting url <url>")
    await ctx.reply(embed=embed, mention_author=False)


# ---------- !shortcuts / !shortcuts --- Xem phím tắt ----------
@bot.command(name="shortcuts", aliases=["aliases", "sc"])
async def cmd_shortcuts(ctx: commands.Context):
    sc = bot_config.get("shortcuts", {})
    if not sc:
        await ctx.reply("ℹ️ Chưa có phím tắt nào. Admin dùng `!shortcut add <tên> <prompt>` để tạo.", mention_author=False)
        return
    embed = discord.Embed(
        title="⚡ DANH SÁCH PHÍM TẮT PROMPT",
        description="Gõ `!<tên> <nội dung>` để bot tự áp prompt dài:",
        color=discord.Color.green()
    )
    for name, prompt_text in sc.items():
        short = prompt_text[:100] + "…" if len(prompt_text) > 100 else prompt_text
        embed.add_field(name=f"!{name}", value=f"_{short}_", inline=False)
    embed.set_footer(text="Thêm: !shortcut add <tên> <prompt>  |  Xóa: !shortcut del <tên>")
    await ctx.reply(embed=embed, mention_author=False)


# ---------- !shortcut — Quản lý phím tắt ----------
@bot.command(name="shortcut", aliases=["alias"])
async def cmd_shortcut(ctx: commands.Context, action: str = "", name: str = "", *, prompt: str = ""):
    if not is_admin(ctx.author.id):
        await ctx.reply("⛔ Chỉ Admin/Chủ nhân mới quản lý phím tắt!", mention_author=False)
        return

    action = action.lower().strip()
    name   = name.lower().strip().lstrip("!")

    if action == "add":
        if not name or not prompt:
            await ctx.reply("⚠️ Cú pháp: `!shortcut add <tên> <prompt dài>`", mention_author=False)
            return
        bot_config.setdefault("shortcuts", {})[name] = prompt
        save_config(bot_config)
        await ctx.reply(f"✅ Đã tạo phím tắt `!{name}`!\nGiờ mọi người chỉ cần gõ `!{name} <nội dung>`.", mention_author=False)

    elif action in ("del", "remove", "xoa"):
        if not name:
            await ctx.reply("⚠️ Cú pháp: `!shortcut del <tên>`", mention_author=False)
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
            "📖 **Hướng dẫn:**\n"
            "• `!shortcut add <tên> <prompt>` — Tạo phím tắt\n"
            "• `!shortcut del <tên>` — Xóa phím tắt\n"
            "• `!shortcuts` — Xem danh sách",
            mention_author=False
        )


# ---------- !clear — Xóa lịch sử hội thoại ----------
@bot.command(name="clear", aliases=["reset"])
async def cmd_clear(ctx: commands.Context):
    clear_history(ctx.channel.id)
    await ctx.reply("🧹 Đã xóa lịch sử hội thoại của kênh này!", mention_author=False)


# ---------- !update — Kéo code GitHub ----------
@bot.command(name="update")
async def cmd_update(ctx: commands.Context):
    if not is_owner(ctx.author.id):
        await ctx.reply("⛔ Chỉ Chủ nhân mới được kéo cập nhật!", mention_author=False)
        return
    msg = await ctx.reply("🔄 Đang kéo code từ GitHub...", mention_author=False)
    has_update, res = _pull_git_update()
    if has_update:
        await msg.edit(content=f"✅ {res}\n🚀 **Đang khởi động lại...**")
        _restart_program()
    else:
        await msg.edit(content=f"ℹ️ {res}")


# ---------- !setting — Cài đặt bot ----------
@bot.command(name="setting", aliases=["settings", "config"])
async def cmd_setting(ctx: commands.Context, sub: str = "", *, value: str = ""):
    if not is_admin(ctx.author.id):
        await ctx.reply("⛔ Lệnh này chỉ dành cho Admin/Chủ nhân!", mention_author=False)
        return

    sub   = sub.lower().strip()
    value = value.strip()

    if not sub:
        # Hiện bảng cài đặt tổng hợp
        owners     = get_owners()
        admins     = bot_config.get("admins", [])
        whitelist  = bot_config.get("whitelist_users", [])
        model      = bot_config.get("model", AI_MODEL)
        base_url   = bot_config.get("base_url", AI_BASE_URL)
        mode       = bot_config.get("access_mode", "restricted").upper()
        max_hist   = bot_config.get("max_history", 12)
        sc_count   = len(bot_config.get("shortcuts", {}))
        au         = bot_config.get("auto_update", False)
        channels   = bot_config.get("allowed_channels", [])

        embed = discord.Embed(title="⚙️ CÀI ĐẶT BOT", color=discord.Color.gold(), timestamp=datetime.now())
        embed.add_field(name="👑 Chủ nhân",      value=", ".join(f"<@{o}>" for o in owners),   inline=False)
        embed.add_field(name="🛡️ Admin",          value=f"{len(admins)} người",                  inline=True)
        embed.add_field(name="👥 Whitelist",      value=f"{len(whitelist)} người",               inline=True)
        embed.add_field(name="🔒 Chế độ",         value=f"`{mode}`",                             inline=True)
        embed.add_field(name="🧠 Model AI",       value=f"`{model}`",                            inline=False)
        embed.add_field(name="🌐 Base URL",       value=f"`{base_url}`",                         inline=False)
        embed.add_field(name="💬 Nhớ (max)",      value=f"`{max_hist} tin`",                     inline=True)
        embed.add_field(name="⚡ Shortcuts",      value=f"`{sc_count}` phím tắt",               inline=True)
        embed.add_field(name="🔄 Auto-update",    value="Bật" if au else "Tắt",                  inline=True)
        if channels:
            embed.add_field(name="📢 Kênh cho phép", value=", ".join(f"<#{c}>" for c in channels), inline=False)
        embed.add_field(
            name="🛠️ Lệnh con",
            value=(
                "`!setting mode restricted|public`\n"
                "`!setting prompt <nội dung>` / `!setting resetprompt`\n"
                "`!setting maxhistory <số>`\n"
                "`!setting url <base_url>`"
            ),
            inline=False
        )
        await ctx.reply(embed=embed, mention_author=False)
        return

    if sub == "mode":
        if value not in ("restricted", "public"):
            await ctx.reply("⚠️ `!setting mode restricted` hoặc `!setting mode public`", mention_author=False)
            return
        bot_config["access_mode"] = value
        save_config(bot_config)
        await ctx.reply(f"✅ Chế độ truy cập: **{value.upper()}**", mention_author=False)

    elif sub == "prompt":
        if not value:
            p = bot_config.get("system_prompt", DEFAULT_SYSTEM_PROMPT)
            await ctx.reply(f"🧠 **System Prompt hiện tại:**\n```\n{p}\n```", mention_author=False)
            return
        bot_config["system_prompt"] = value
        save_config(bot_config)
        await ctx.reply("✅ Đã cập nhật System Prompt mới!", mention_author=False)

    elif sub in ("resetprompt", "reset"):
        bot_config["system_prompt"] = DEFAULT_SYSTEM_PROMPT
        save_config(bot_config)
        await ctx.reply("🔄 Đã khôi phục System Prompt về mặc định!", mention_author=False)

    elif sub == "url":
        if not value:
            await ctx.reply(f"🌐 Base URL hiện tại: `{bot_config.get('base_url', AI_BASE_URL)}`", mention_author=False)
            return
        bot_config["base_url"] = value
        save_config(bot_config)
        update_env_variable("AI_BASE_URL", value)
        await ctx.reply(f"✅ Đã đổi Base URL: `{value}`", mention_author=False)

    elif sub == "maxhistory":
        try:
            n = int(value)
            bot_config["max_history"] = n
            save_config(bot_config)
            await ctx.reply(f"✅ Số tin nhớ tối đa: **{n}**", mention_author=False)
        except ValueError:
            await ctx.reply("⚠️ Nhập số hợp lệ.", mention_author=False)
    else:
        await ctx.reply(f"⚠️ Không nhận ra lệnh con `{sub}`. Gõ `!setting` để xem.", mention_author=False)


# ---------- !owners / !addowner / !delowner ----------
@bot.command(name="owners")
async def cmd_owners(ctx: commands.Context):
    owners = get_owners()
    lines  = [f"<@{o}> (`{o}`)" for o in owners]
    embed  = discord.Embed(title="👑 DANH SÁCH CHỦ NHÂN", description="\n".join(lines), color=discord.Color.gold())
    await ctx.reply(embed=embed, mention_author=False)


@bot.command(name="addowner")
async def cmd_addowner(ctx: commands.Context, member: Optional[discord.Member] = None):
    if not is_owner(ctx.author.id):
        await ctx.reply("⛔ Chỉ Chủ nhân mới được thêm Chủ nhân!", mention_author=False)
        return
    if not member:
        await ctx.reply("⚠️ Tag người: `!addowner @user`", mention_author=False)
        return
    owners = bot_config.setdefault("owners", [DEFAULT_OWNER_ID])
    if member.id in owners:
        await ctx.reply(f"ℹ️ {member.mention} đã là Chủ nhân.", mention_author=False)
        return
    owners.append(member.id)
    bot_config.setdefault("admins", []).append(member.id) if member.id not in bot_config.get("admins", []) else None
    bot_config.setdefault("whitelist_users", []).append(member.id) if member.id not in bot_config.get("whitelist_users", []) else None
    save_config(bot_config)
    await ctx.reply(f"👑 {member.mention} đã trở thành Chủ nhân!", mention_author=False)


@bot.command(name="delowner")
async def cmd_delowner(ctx: commands.Context, member: Optional[discord.Member] = None):
    if not is_owner(ctx.author.id):
        await ctx.reply("⛔ Chỉ Chủ nhân mới được xóa Chủ nhân!", mention_author=False)
        return
    if not member:
        await ctx.reply("⚠️ Tag người: `!delowner @user`", mention_author=False)
        return
    owners = bot_config.setdefault("owners", [DEFAULT_OWNER_ID])
    if member.id not in owners:
        await ctx.reply(f"ℹ️ {member.mention} không phải Chủ nhân.", mention_author=False)
        return
    if len(owners) <= 1:
        await ctx.reply("❌ Bot phải có ít nhất 1 Chủ nhân!", mention_author=False)
        return
    owners.remove(member.id)
    save_config(bot_config)
    await ctx.reply(f"✅ Đã gỡ quyền Chủ nhân của {member.mention}.", mention_author=False)


# ---------- !grant / !revoke — Thêm/Xóa whitelist ----------
@bot.command(name="grant", aliases=["adduser"])
async def cmd_grant(ctx: commands.Context, member: Optional[discord.Member] = None):
    if not is_admin(ctx.author.id):
        await ctx.reply("⛔ Chỉ Admin/Chủ nhân!", mention_author=False)
        return
    if not member:
        await ctx.reply("⚠️ Tag người: `!grant @user`", mention_author=False)
        return
    wl = bot_config.setdefault("whitelist_users", [])
    if member.id in wl:
        await ctx.reply(f"ℹ️ {member.mention} đã có quyền.", mention_author=False)
        return
    wl.append(member.id)
    save_config(bot_config)
    await ctx.reply(f"✅ Đã cấp quyền cho {member.mention}!", mention_author=False)


@bot.command(name="revoke", aliases=["deluser"])
async def cmd_revoke(ctx: commands.Context, member: Optional[discord.Member] = None):
    if not is_admin(ctx.author.id):
        await ctx.reply("⛔ Chỉ Admin/Chủ nhân!", mention_author=False)
        return
    if not member:
        await ctx.reply("⚠️ Tag người: `!revoke @user`", mention_author=False)
        return
    if is_owner(member.id):
        await ctx.reply("❌ Không thể thu hồi quyền Chủ nhân!", mention_author=False)
        return
    wl = bot_config.setdefault("whitelist_users", [])
    if member.id not in wl:
        await ctx.reply(f"ℹ️ {member.mention} không trong whitelist.", mention_author=False)
        return
    wl.remove(member.id)
    save_config(bot_config)
    await ctx.reply(f"🚫 Đã thu hồi quyền của {member.mention}.", mention_author=False)


# ---------- !help ----------
@bot.command(name="help")
async def cmd_help(ctx: commands.Context):
    embed = discord.Embed(
        title="🤖 HƯỚNG DẪN SỬ DỤNG BOT AI",
        description="Bot AI hỗ trợ nhiều nhà cung cấp: DeepSeek, OpenRouter, Groq, OpenAI...",
        color=discord.Color.blurple()
    )
    embed.add_field(
        name="💬 Dành cho tất cả",
        value=(
            "`!ask <câu hỏi>` hoặc `!ai <câu hỏi>` — Chat với AI\n"
            "`@Bot <câu hỏi>` — Mention để hỏi trực tiếp\n"
            "`!<shortcut> <nội dung>` — Phím tắt prompt (vd: `!dich`, `!fixcode`)\n"
            "`!shortcuts` — Xem danh sách phím tắt\n"
            "`!models` — Xem danh sách model AI\n"
            "`!model` — Xem model đang dùng\n"
            "`!clear` — Xóa lịch sử hội thoại kênh"
        ),
        inline=False
    )
    if is_admin(ctx.author.id):
        embed.add_field(
            name="🛠️ Dành cho Admin / Chủ nhân",
            value=(
                "`!model <tên>` — Đổi model AI\n"
                "`!shortcut add <tên> <prompt>` — Tạo phím tắt\n"
                "`!shortcut del <tên>` — Xóa phím tắt\n"
                "`!grant @user` / `!revoke @user` — Thêm/Xóa quyền\n"
                "`!setting` — Xem & chỉnh cài đặt bot\n"
                "`!owners` / `!addowner` / `!delowner` — Quản lý Chủ nhân\n"
                "`!update` — Kéo code mới từ GitHub"
            ),
            inline=False
        )
    embed.set_footer(text="Mọi lệnh VPS console: gõ  help  trên terminal")
    await ctx.reply(embed=embed, mention_author=False)


# ================================================================
# PHẦN 14 — GIT UPDATE & RESTART
# ================================================================
def _pull_git_update() -> tuple:
    try:
        res    = subprocess.run(["git", "pull"], capture_output=True, text=True, timeout=30)
        output = (res.stdout + "\n" + res.stderr).strip()
        if res.returncode == 0:
            if "Already up to date" in output:
                return False, "Code đã là phiên bản mới nhất!"
            return True, f"Đã kéo code mới:\n{output}"
        return False, f"Lỗi git pull:\n{output}"
    except Exception as e:
        return False, f"Lỗi: {e}"


def _restart_program():
    print("🔄 Đang khởi động lại...")
    os.execl(sys.executable, sys.executable, *sys.argv)


async def _auto_update_task():
    await bot.wait_until_ready()
    while not bot.is_closed():
        await asyncio.sleep(1800)  # 30 phút
        if bot_config.get("auto_update", False):
            has_update, _ = _pull_git_update()
            if has_update:
                logger.info("Tìm thấy code mới, tự động restart...")
                _restart_program()


# ================================================================
# PHẦN 15 — VPS CONSOLE (CLI TERMINAL)
# ================================================================
def _print_vps_help():
    print("""
╔══════════════════════════════════════════════════════════════════╗
║                 LỆNH VPS CONSOLE — TOÀN QUYỀN                  ║
╠══════════════════════════════════════════════════════════════════╣
║  help                    Xem bảng lệnh này                      ║
║  status                  Trạng thái bot, model, key hiện tại    ║
║  restart                 Khởi động lại bot                      ║
╠══════════════════════════════════════════════════════════════════╣
║  🔑  API KEY & TOKEN                                            ║
║  api                     Menu đổi AI Key / Discord Token        ║
║  setkey ai <key>         Đổi AI API Key (áp dụng ngay)          ║
║  setkey discord <token>  Đổi Discord Token (cần restart)        ║
╠══════════════════════════════════════════════════════════════════╣
║  🧠  MODEL & PROVIDER                                           ║
║  model                   Menu chọn model AI (số 1-13)           ║
║  model <tên>             Đổi model ngay                         ║
║  provider <tên> [key]    Chuyển nhà cung cấp nhanh              ║
║    → openrouter / deepseek / groq / openai                      ║
║  seturl <url>            Đổi Base URL API tùy chỉnh             ║
╠══════════════════════════════════════════════════════════════════╣
║  🎭  SYSTEM PROMPT                                              ║
║  prompt                  Xem System Prompt hiện tại             ║
║  setprompt <nội dung>    Đổi System Prompt AI                   ║
║  resetprompt             Khôi phục Prompt về mặc định           ║
╠══════════════════════════════════════════════════════════════════╣
║  ⚡  PHÍM TẮT SHORTCUTS                                         ║
║  shortcuts               Xem danh sách phím tắt                 ║
║  shortcut add <tên> <prompt dài>  Tạo phím tắt mới              ║
║  shortcut del <tên>      Xóa phím tắt                           ║
╠══════════════════════════════════════════════════════════════════╣
║  👑  QUẢN LÝ CHỦ NHÂN                                          ║
║  owners                  Danh sách Chủ nhân                     ║
║  addowner <id>           Thêm Chủ nhân                          ║
║  delowner <id>           Xóa Chủ nhân                           ║
╠══════════════════════════════════════════════════════════════════╣
║  👥  QUẢN LÝ NGƯỜI DÙNG                                        ║
║  users                   Danh sách whitelist                    ║
║  add <id>                Thêm user vào whitelist                ║
║  del <id>                Xóa user khỏi whitelist                ║
║  admins                  Danh sách Admin                        ║
║  addadmin <id>           Thêm Admin                             ║
║  deladmin <id>           Xóa Admin                              ║
║  mode restricted|public  Đổi chế độ truy cập                   ║
╠══════════════════════════════════════════════════════════════════╣
║  🔄  GITHUB AUTO-UPDATE                                         ║
║  update                  Kéo code mới từ GitHub ngay            ║
║  autoupdate on|off       Bật/tắt tự động cập nhật mỗi 30 phút  ║
╠══════════════════════════════════════════════════════════════════╣
║  stop / exit             Dừng bot an toàn                       ║
╚══════════════════════════════════════════════════════════════════╝
""")


def vps_console_listener(loop: asyncio.AbstractEventLoop):
    global AI_API_KEY, DISCORD_BOT_TOKEN

    while True:
        try:
            line = input().strip()
            if not line:
                print("[VPS] > ", end="", flush=True)
                continue

            parts = line.split(maxsplit=2)
            cmd   = parts[0].lower()

            # ---- help ----
            if cmd == "help":
                _print_vps_help()

            # ---- status ----
            elif cmd == "status":
                owners   = get_owners()
                model    = bot_config.get("model", AI_MODEL)
                base_url = bot_config.get("base_url", AI_BASE_URL)
                mode     = bot_config.get("access_mode", "restricted")
                wl       = bot_config.get("whitelist_users", [])
                admins   = bot_config.get("admins", [])
                sc       = bot_config.get("shortcuts", {})
                au       = bot_config.get("auto_update", False)
                print(f"""
📊 TRẠNG THÁI BOT:
  Chủ nhân ({len(owners)}): {owners}
  Chế độ truy cập : {mode.upper()}
  Model AI        : {model}
  Base URL        : {base_url}
  Whitelist       : {len(wl)} người
  Admin           : {len(admins)} người
  Phím tắt        : {len(sc)} shortcuts
  Auto-update     : {'BẬT (30p/lần)' if au else 'TẮT'}
  AI API Key      : {mask(AI_API_KEY)}
  Discord Token   : {mask(DISCORD_BOT_TOKEN)}
""")

            # ---- restart ----
            elif cmd == "restart":
                _restart_program()

            # ---- update ----
            elif cmd == "update":
                print("🔄 Đang kéo code từ GitHub...")
                has_update, msg = _pull_git_update()
                print(msg)
                if has_update:
                    ans = input("❓ Khởi động lại ngay? (y/n): ").strip().lower()
                    if ans == "y":
                        _restart_program()

            # ---- autoupdate ----
            elif cmd == "autoupdate":
                if len(parts) < 2 or parts[1] not in ("on", "off"):
                    print("⚠️ Cú pháp: autoupdate on | autoupdate off")
                else:
                    state = parts[1] == "on"
                    bot_config["auto_update"] = state
                    save_config(bot_config)
                    print(f"⚙️ Auto-update: {'BẬT' if state else 'TẮT'}")

            # ---- api (menu tương tác) ----
            elif cmd == "api":
                print("""
=============================================================
🔧 ĐỔI API KEY / TOKEN (Chọn tùy chọn):
  [1] Chỉ đổi AI API Key
  [2] Chỉ đổi Discord Bot Token
  [3] Đổi cả hai
  [0] Hủy
=============================================================""")
                choice = input("👉 Nhập (0-3): ").strip()
                if choice == "1":
                    new_key = input("👉 Nhập AI API Key mới: ").strip()
                    if new_key:
                        AI_API_KEY = new_key
                        update_env_variable("AI_API_KEY", new_key)
                        print(f"✅ Đã cập nhật AI API Key: {mask(new_key)} (áp dụng ngay)")
                elif choice == "2":
                    new_tok = input("👉 Nhập Discord Bot Token mới: ").strip()
                    if new_tok:
                        DISCORD_BOT_TOKEN = new_tok
                        update_env_variable("DISCORD_BOT_TOKEN", new_tok)
                        print(f"✅ Đã lưu Discord Token: {mask(new_tok)}")
                        ans = input("❓ Khởi động lại để áp dụng token mới? (y/n): ").strip().lower()
                        if ans == "y":
                            _restart_program()
                elif choice == "3":
                    new_key = input("👉 [1/2] AI API Key mới: ").strip()
                    new_tok = input("👉 [2/2] Discord Token mới: ").strip()
                    if new_key:
                        AI_API_KEY = new_key
                        update_env_variable("AI_API_KEY", new_key)
                    if new_tok:
                        DISCORD_BOT_TOKEN = new_tok
                        update_env_variable("DISCORD_BOT_TOKEN", new_tok)
                    print("✅ Đã cập nhật!")
                    ans = input("❓ Khởi động lại ngay? (y/n): ").strip().lower()
                    if ans == "y":
                        _restart_program()
                else:
                    print("Đã hủy.")

            # ---- setkey ai/discord ----
            elif cmd == "setkey":
                if len(parts) < 3:
                    print("⚠️ Cú pháp: setkey ai <key>  |  setkey discord <token>")
                else:
                    service = parts[1].lower()
                    val     = parts[2].strip()
                    if service in ("ai", "deepseek", "key"):
                        AI_API_KEY = val
                        update_env_variable("AI_API_KEY", val)
                        print(f"✅ AI API Key mới: {mask(val)} (áp dụng ngay)")
                    elif service in ("discord", "bot", "token"):
                        DISCORD_BOT_TOKEN = val
                        update_env_variable("DISCORD_BOT_TOKEN", val)
                        print(f"✅ Discord Token mới: {mask(val)} (gõ restart để nạp)")
                    else:
                        print("⚠️ Chọn: setkey ai <key>  hoặc  setkey discord <token>")

            # ---- model (menu hoặc đặt thẳng) ----
            elif cmd in ("model", "setmodel"):
                current = bot_config.get("model", AI_MODEL)
                if len(parts) >= 2:
                    # Đặt thẳng
                    new_m = parts[1].strip()
                    bot_config["model"] = new_m
                    save_config(bot_config)
                    update_env_variable("AI_MODEL", new_m)
                    print(f"✅ Đã đổi model: {new_m}")
                else:
                    print(f"\n🧠 MODEL AI HIỆN TẠI: {current}\n")
                    for i, (display, name, url) in enumerate(MODEL_LIST, 1):
                        cur_mark = " ◀ ĐANG DÙNG" if name == current else ""
                        print(f"  [{i:2d}] {name:<50} — {display}{cur_mark}")
                    print(f"  [ 0] Giữ nguyên\n")
                    try:
                        opt = input("👉 Nhập số (0 để bỏ qua) hoặc gõ tên model: ").strip()
                        if opt == "0" or not opt:
                            print("Giữ nguyên.")
                        elif opt.isdigit():
                            idx = int(opt) - 1
                            if 0 <= idx < len(MODEL_LIST):
                                display, chosen_m, chosen_url = MODEL_LIST[idx]
                                bot_config["model"]    = chosen_m
                                bot_config["base_url"] = chosen_url
                                save_config(bot_config)
                                update_env_variable("AI_MODEL",   chosen_m)
                                update_env_variable("AI_BASE_URL", chosen_url)
                                print(f"✅ Đã chọn: {chosen_m}\n   URL: {chosen_url}")
                            else:
                                print("❌ Số không hợp lệ.")
                        else:
                            bot_config["model"] = opt
                            save_config(bot_config)
                            update_env_variable("AI_MODEL", opt)
                            print(f"✅ Đã đổi model: {opt}")
                    except (KeyboardInterrupt, EOFError):
                        pass

            # ---- provider ----
            elif cmd == "provider":
                if len(parts) < 2:
                    print("⚠️ Cú pháp: provider <tên> [api_key]")
                    print("   Tên: openrouter | deepseek | groq | openai")
                else:
                    p_name  = parts[1].lower()
                    new_key = parts[2].strip() if len(parts) > 2 else ""
                    if p_name in PROVIDER_PRESETS:
                        preset = PROVIDER_PRESETS[p_name]
                        bot_config["base_url"] = preset["url"]
                        bot_config["model"]    = preset["model"]
                        save_config(bot_config)
                        update_env_variable("AI_BASE_URL", preset["url"])
                        update_env_variable("AI_MODEL",    preset["model"])
                        if new_key:
                            AI_API_KEY = new_key
                            update_env_variable("AI_API_KEY", new_key)
                            print(f"✅ {preset['note']} — Key: {mask(new_key)}")
                        else:
                            print(f"✅ {preset['note']}")
                            print(f"   Model: {preset['model']}")
                            print(f"   URL:   {preset['url']}")
                    else:
                        print(f"❌ Provider không hợp lệ. Chọn: {', '.join(PROVIDER_PRESETS)}")

            # ---- seturl ----
            elif cmd == "seturl":
                if len(parts) < 2:
                    print(f"⚠️ Cú pháp: seturl <url>")
                    print(f"   Hiện tại: {bot_config.get('base_url', AI_BASE_URL)}")
                else:
                    new_url = parts[1].strip()
                    bot_config["base_url"] = new_url
                    save_config(bot_config)
                    update_env_variable("AI_BASE_URL", new_url)
                    print(f"✅ Đã đổi Base URL: {new_url}")

            # ---- prompt / setprompt / resetprompt ----
            elif cmd == "prompt":
                p = bot_config.get("system_prompt", DEFAULT_SYSTEM_PROMPT)
                print(f"\n🧠 SYSTEM PROMPT HIỆN TẠI:\n{p}\n")

            elif cmd == "setprompt":
                full = line[len("setprompt"):].strip()
                if not full:
                    print("⚠️ Cú pháp: setprompt <nội dung prompt mới>")
                else:
                    bot_config["system_prompt"] = full
                    save_config(bot_config)
                    print(f"✅ Đã cập nhật System Prompt:\n> {full[:150]}...")

            elif cmd == "resetprompt":
                bot_config["system_prompt"] = DEFAULT_SYSTEM_PROMPT
                save_config(bot_config)
                print("🔄 Đã khôi phục System Prompt về mặc định!")

            # ---- shortcuts ----
            elif cmd in ("shortcuts", "aliases"):
                sc = bot_config.get("shortcuts", {})
                print(f"\n⚡ DANH SÁCH PHÍM TẮT ({len(sc)}):")
                if not sc:
                    print("  (Chưa có)")
                else:
                    for n, p in sc.items():
                        print(f"  !{n}  →  \"{p}\"")
                print()

            elif cmd in ("shortcut", "alias"):
                if len(parts) < 2:
                    print("⚠️ shortcut add <tên> <prompt>  |  shortcut del <tên>")
                else:
                    sub = parts[1].lower()
                    if sub == "add":
                        rest = line[len(f"{cmd} add"):].strip()
                        sub2 = rest.split(maxsplit=1)
                        if len(sub2) < 2:
                            print("⚠️ Cú pháp: shortcut add <tên> <prompt dài>")
                        else:
                            sc_name   = sub2[0].lstrip("!")
                            sc_prompt = sub2[1]
                            bot_config.setdefault("shortcuts", {})[sc_name] = sc_prompt
                            save_config(bot_config)
                            print(f"✅ Đã tạo phím tắt '!{sc_name}'")
                    elif sub in ("del", "remove", "xoa"):
                        sc_name = parts[2].strip().lstrip("!") if len(parts) > 2 else ""
                        if not sc_name:
                            print("⚠️ Cú pháp: shortcut del <tên>")
                        else:
                            sc = bot_config.setdefault("shortcuts", {})
                            if sc_name in sc:
                                del sc[sc_name]
                                save_config(bot_config)
                                print(f"✅ Đã xóa phím tắt '!{sc_name}'")
                            else:
                                print(f"ℹ️ Không tìm thấy '!{sc_name}'")

            # ---- owners ----
            elif cmd == "owners":
                owners = get_owners()
                print(f"\n👑 DANH SÁCH CHỦ NHÂN ({len(owners)}):")
                for o in owners:
                    print(f"  • {o}")
                print()

            elif cmd == "addowner":
                if len(parts) < 2:
                    print("⚠️ Cú pháp: addowner <user_id>")
                else:
                    try:
                        new_oid = int(parts[1])
                        owners = bot_config.setdefault("owners", [DEFAULT_OWNER_ID])
                        if new_oid in owners:
                            print(f"ℹ️ {new_oid} đã là Chủ nhân.")
                        else:
                            owners.append(new_oid)
                            bot_config.setdefault("admins", []).append(new_oid)
                            bot_config.setdefault("whitelist_users", []).append(new_oid)
                            save_config(bot_config)
                            print(f"👑 Đã thêm Chủ nhân: {new_oid}")
                    except ValueError:
                        print("❌ ID phải là số!")

            elif cmd == "delowner":
                if len(parts) < 2:
                    print("⚠️ Cú pháp: delowner <user_id>")
                else:
                    try:
                        rem_oid = int(parts[1])
                        owners  = bot_config.setdefault("owners", [DEFAULT_OWNER_ID])
                        if rem_oid not in owners:
                            print(f"ℹ️ {rem_oid} không là Chủ nhân.")
                        elif len(owners) <= 1:
                            print("❌ Không thể xóa — phải có ít nhất 1 Chủ nhân!")
                        else:
                            owners.remove(rem_oid)
                            save_config(bot_config)
                            print(f"✅ Đã xóa Chủ nhân: {rem_oid}")
                    except ValueError:
                        print("❌ ID phải là số!")

            # ---- users / whitelist ----
            elif cmd in ("users", "list", "whitelist"):
                wl = bot_config.get("whitelist_users", [])
                print(f"\n👥 WHITELIST ({len(wl)}):")
                for uid in wl:
                    tag = " 👑" if is_owner(uid) else ""
                    print(f"  • {uid}{tag}")
                print()

            elif cmd in ("add", "grant"):
                if len(parts) < 2:
                    print("⚠️ Cú pháp: add <user_id>")
                else:
                    try:
                        uid = int(parts[1])
                        wl  = bot_config.setdefault("whitelist_users", [])
                        if uid in wl:
                            print(f"ℹ️ {uid} đã có quyền.")
                        else:
                            wl.append(uid)
                            save_config(bot_config)
                            print(f"✅ Đã thêm {uid} vào whitelist.")
                    except ValueError:
                        print("❌ ID phải là số!")

            elif cmd in ("del", "revoke", "remove"):
                if len(parts) < 2:
                    print("⚠️ Cú pháp: del <user_id>")
                else:
                    try:
                        uid = int(parts[1])
                        if is_owner(uid):
                            print("❌ Không thể xóa Chủ nhân!")
                        else:
                            wl = bot_config.setdefault("whitelist_users", [])
                            if uid in wl:
                                wl.remove(uid)
                                save_config(bot_config)
                                print(f"🚫 Đã xóa {uid} khỏi whitelist.")
                            else:
                                print(f"ℹ️ {uid} không trong whitelist.")
                    except ValueError:
                        print("❌ ID phải là số!")

            # ---- admins ----
            elif cmd == "admins":
                admins = bot_config.get("admins", [])
                print(f"\n🛡️ ADMIN ({len(admins)}):")
                for a in admins:
                    tag = " 👑" if is_owner(a) else ""
                    print(f"  • {a}{tag}")
                print()

            elif cmd == "addadmin":
                if len(parts) < 2:
                    print("⚠️ Cú pháp: addadmin <user_id>")
                else:
                    try:
                        uid    = int(parts[1])
                        admins = bot_config.setdefault("admins", [])
                        wl     = bot_config.setdefault("whitelist_users", [])
                        if uid in admins:
                            print(f"ℹ️ {uid} đã là Admin.")
                        else:
                            admins.append(uid)
                            if uid not in wl:
                                wl.append(uid)
                            save_config(bot_config)
                            print(f"✅ Đã thêm Admin: {uid}")
                    except ValueError:
                        print("❌ ID phải là số!")

            elif cmd in ("deladmin", "removeadmin"):
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
                                print(f"✅ Đã xóa Admin: {uid}")
                            else:
                                print(f"ℹ️ {uid} không là Admin.")
                    except ValueError:
                        print("❌ ID phải là số!")

            # ---- mode ----
            elif cmd == "mode":
                if len(parts) < 2 or parts[1] not in ("restricted", "public"):
                    print("⚠️ Cú pháp: mode restricted  |  mode public")
                else:
                    bot_config["access_mode"] = parts[1]
                    save_config(bot_config)
                    print(f"⚙️ Chế độ truy cập: {parts[1].upper()}")

            # ---- stop / exit ----
            elif cmd in ("stop", "exit", "quit"):
                print("🛑 Đang dừng bot...")
                asyncio.run_coroutine_threadsafe(bot.close(), loop)
                sys.exit(0)

            else:
                print(f"⚠️ Không nhận ra lệnh '{cmd}'. Gõ 'help' để xem danh sách.")

            print("[VPS] > ", end="", flush=True)

        except (KeyboardInterrupt, EOFError):
            print("\n🛑 Thoát...")
            sys.exit(0)
        except Exception as e:
            print(f"❌ Lỗi: {e}")
            print("[VPS] > ", end="", flush=True)


# ================================================================
# PHẦN 16 — SETUP LẦN ĐẦU & KHỞI CHẠY BOT
# ================================================================
def setup_first_time():
    global DISCORD_BOT_TOKEN, AI_API_KEY

    need_token = not DISCORD_BOT_TOKEN or DISCORD_BOT_TOKEN.startswith("your_")
    need_api   = not AI_API_KEY or AI_API_KEY.startswith("your_") or AI_API_KEY.startswith("sk-xxxx")

    if not need_token and not need_api:
        return

    print("\n" + "=" * 60)
    print("🌟 CÀI ĐẶT LẦN ĐẦU — AI Discord Bot 🌟")
    print("=" * 60)

    if need_token:
        while True:
            try:
                tok = input("\n👉 Nhập Discord Bot Token: ").strip()
                if tok:
                    DISCORD_BOT_TOKEN = tok
                    break
                print("⚠️ Token không được trống!")
            except (KeyboardInterrupt, EOFError):
                sys.exit(0)

    if need_api:
        print("\n💡 Gợi ý: Dùng OpenRouter miễn phí tại https://openrouter.ai")
        while True:
            try:
                key = input("👉 Nhập AI API Key (sk-...): ").strip()
                if key:
                    AI_API_KEY = key
                    break
                print("⚠️ API Key không được trống!")
            except (KeyboardInterrupt, EOFError):
                sys.exit(0)

    update_env_variable("DISCORD_BOT_TOKEN", DISCORD_BOT_TOKEN)
    update_env_variable("AI_API_KEY",        AI_API_KEY)
    update_env_variable("AI_BASE_URL",       AI_BASE_URL)
    update_env_variable("AI_MODEL",          AI_MODEL)
    update_env_variable("OWNER_ID",          str(DEFAULT_OWNER_ID))
    print("\n✅ Đã lưu vào .env!\n")


async def _run_bot():
    asyncio.create_task(_auto_update_task())
    await bot.start(DISCORD_BOT_TOKEN)


def main():
    setup_first_time()

    if not DISCORD_BOT_TOKEN:
        print("❌ Thiếu DISCORD_BOT_TOKEN! Thêm vào file .env rồi chạy lại.")
        sys.exit(1)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    t = threading.Thread(target=vps_console_listener, args=(loop,), daemon=True)
    t.start()

    try:
        loop.run_until_complete(_run_bot())
    except discord.LoginFailure:
        print("\n❌ DISCORD TOKEN KHÔNG HỢP LỆ! Kiểm tra lại .env")
    except KeyboardInterrupt:
        print("\n🛑 Bot đã dừng.")
    finally:
        loop.close()


if __name__ == "__main__":
    main()
