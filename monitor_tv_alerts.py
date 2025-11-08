import os, logging, requests
from datetime import datetime, timedelta, timezone
from flask import Flask, request, jsonify

# ==== إعدادات من Environment ====
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
SHARED_SECRET    = os.getenv("SHARED_SECRET", "Admin@1716")
ACCOUNT_BALANCE  = float(os.getenv("ACCOUNT_BALANCE", "200"))
DAILY_LOSS_LIMIT_PCT = float(os.getenv("DAILY_LOSS_LIMIT_PCT", "3"))
# توقيت الرياض (+3) بدون الاعتماد على zoneinfo
KSA_TZ = timezone(timedelta(hours=3))

# ==== إعداد اللوج ====
logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

# ==== دالة إرسال رسالة لتليجرام ====
def tg_send(text: str) -> bool:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        app.logger.warning("❌ بيانات التليجرام ناقصة (TOKEN أو CHAT_ID)")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    try:
        r = requests.post(url, data=data, timeout=10)
        app.logger.info("📨 Telegram Response: %s - %s", r.status_code, r.text)
        return r.ok
    except Exception as e:
        app.logger.exception("خطأ في إرسال رسالة التليجرام: %s", e)
        return False

def ok(msg):     return (msg, 200)
def bad(msg):    return (msg, 400)
def unauth(msg): return (msg, 403)

# ==== المسارات الرئيسية ====
@app.get("/")
def root():
    return ok("✅ Bot is running successfully")

@app.get("/ping")
def ping():
    now = datetime.now(KSA_TZ).strftime("%Y-%m-%d %H:%M:%S")
    return jsonify({"status": "ok", "time_riyadh": now})

@app.get("/test")
def test():
    secret = request.args.get("secret", "")
    msg    = request.args.get("msg", "Test message")
    if secret != SHARED_SECRET:
        return unauth("Unauthorized")
    sent = tg_send(f"✅ Test: {msg} @ {datetime.now(KSA_TZ):%Y-%m-%d %H:%M:%S}")
    return ok("✅ Message sent" if sent else "❌ Message failed")

@app.post("/hook")
def hook():
    secret = request.args.get("secret") or request.headers.get("X-Secret", "")
    if secret != SHARED_SECRET:
        return unauth("Unauthorized")
    payload = request.get_json(silent=True) or {}
    text = payload.get("message") or payload.get("alert") or str(payload)
    if not text:
        return bad("No message")
    sent = tg_send(f"📢 TradingView Alert: {text}")
    return ok("✅ Alert sent" if sent else "❌ Alert failed")

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=False)
