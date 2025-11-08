import os, logging, requests
from datetime import datetime
from flask import Flask, request, jsonify
from zoneinfo import ZoneInfo

# === إعدادات من Environment ===
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
SHARED_SECRET    = os.getenv("SHARED_SECRET", "supersecret123")
ACCOUNT_BALANCE  = float(os.getenv("ACCOUNT_BALANCE", "200"))
DAILY_LOSS_LIMIT_PCT = float(os.getenv("DAILY_LOSS_LIMIT_PCT", "3.0"))
TZ = ZoneInfo(os.getenv("TZ", "Asia/Riyadh"))

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

# === وظائف مساعدة ===
def tg_send(text: str) -> bool:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        app.logger.warning("Telegram creds missing; not sending message")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    try:
        r = requests.post(url, data=data, timeout=10)
        app.logger.info("Telegram status %s: %s", r.status_code, r.text)
        return r.ok
    except Exception as e:
        app.logger.exception("Telegram send failed: %s", e)
        return False

def ok(msg):     return (msg, 200)
def bad(msg):    return (msg, 400)
def unauth(msg): return (msg, 403)

# === مسارات الخدمة ===

@app.get("/")
def root():
    return ok("OK")

@app.get("/ping")
def ping():
    # مسار صحي بدون أي صلاحيات — لأدوات المراقبة و Render Health Check
    now = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
    return jsonify({"status": "ok", "time": now})

@app.get("/test")
def test():
    # اختبار يدوي بإرسال رسالة لتليغرام
    secret = request.args.get("secret", "")
    msg    = request.args.get("msg", "Test message from /test")
    if secret != SHARED_SECRET:
        return unauth("Unauthorized")
    ok_send = tg_send(f"✅ Test: {msg} @ {datetime.now(TZ):%Y-%m-%d %H:%M:%S}")
    return ok("sent" if ok_send else "not sent")

@app.post("/hook")
def hook():
    # وبهوك TradingView أو أي مصدر
    secret = request.args.get("secret", "") or request.headers.get("X-Secret", "")
    if secret != SHARED_SECRET:
        return unauth("Unauthorized")
    try:
        payload = request.get_json(force=True, silent=True) or {}
        text = payload.get("message") or payload.get("alert") or str(payload)
        if not text:
            return bad("No message")
        sent = tg_send(f"📢 Alert: {text}")
        return ok("sent" if sent else "not sent")
    except Exception as e:
        app.logger.exception("hook error: %s", e)
        return bad("error")

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=False)
