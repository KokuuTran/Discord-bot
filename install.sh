#!/bin/bash
# ==============================================================================
# SCRIPT TỰ ĐỘNG CÀI ĐẶT VÀ KHỞI CHẠY DISCORD BOT DEEPSEEK TRÊN TERMUX
# ==============================================================================

echo "=========================================================="
echo "🚀 ĐANG TIẾN HÀNH CÀI ĐẶT MÔI TRƯỜNG CHO TERMUX..."
echo "=========================================================="

# 1. Cập nhật gói và cài các công cụ cần thiết
pkg update -y && pkg upgrade -y
pkg install python git clang libffi openssl -y

# 2. Cài đặt các thư viện Python
echo "📦 Đang cài đặt thư viện Python (discord.py, python-dotenv)..."
pip install -r requirements.txt 2>/dev/null || pip install discord.py python-dotenv

# 3. Giữ Termux chạy nền (tránh bị hệ thống Android tắt khi khóa màn hình)
termux-wake-lock 2>/dev/null

echo "=========================================================="
echo "✅ CÀI ĐẶT HOÀN TẤT! ĐANG KHỞI CHẠY BOT..."
echo "=========================================================="

# 4. Chạy bot
python bot.py
