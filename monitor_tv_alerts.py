import os
import logging
import requests
from datetime import datetime
from flask import Flask, request, jsonify
from zoneinfo import ZoneInfo

# ==========================
# Read environment variables
# ==========================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
SHARED_SECRET = os.getenv("SHARED_SECRET", "Admin@1716")
ACCOUNT_BALANCE = float(os.getenv("ACCOUNT_BALANCE", "200"))
DAILY_LOSS_LIMIT_PCT = float(os.getenv("DAILY_LOSS_LIMIT_PCT", "3.0"))
TZ = ZoneInfo(os.getenv("TZ", "Asia/Riyadh"))

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

# ==========================
# Telegram send function ✅
# ==========================
def send_telegram_message(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logging.error("Telegram credentials are missing!")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}

    try:
        requests.post(url, data=data)
    except Exception as e:
        logging.error(f"Error sending Telegram message: {e}")

# ==========================
# Test route ✅
# ==========================
@app.route("/test", methods=["GET"])
def test():
    if request.args.get("secret") != SHARED_SECRET:
        return "Unauthorized", 403
    send_telegram_message("✅ Bot is working and connected successfully!")
    return "Test message sent to Telegram!"

# ==========================
# Home route ✅
# ==========================
@app.route("/", methods=["GET"])
def home():
    return "TV2TG Alerts Bot is Running ✅"

# ==========================
# Run Flask App
# ==========================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
