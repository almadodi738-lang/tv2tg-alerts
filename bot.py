import os, logging, requests, pandas as pd, yfinance as yf
from datetime import datetime, timedelta, timezone
from flask import Flask, jsonify

# ==== إعدادات عامة ====
KSA_TZ = timezone(timedelta(hours=3))
ACCOUNT_BALANCE = float(os.getenv("ACCOUNT_BALANCE", "200"))
DAILY_LOSS_LIMIT_PCT = float(os.getenv("DAILY_LOSS_LIMIT_PCT", "3"))

# ==== إعداد التليجرام ====
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
SHARED_SECRET = os.getenv("SHARED_SECRET", "Admin@1716")

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# ==== دالة إرسال رسالة لتليجرام ====
def tg_send(text: str) -> bool:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        app.logger.warning("❌ بيانات التليجرام ناقصة (TOKEN أو CHAT_ID)")
        return False
    try:
        r = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                          data={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=10)
        return r.ok
    except Exception as e:
        app.logger.error(f"خطأ في إرسال رسالة تليجرام: {e}")
        return False

# ==== رموز Yahoo Finance الصحيحة ====
SYMBOLS = {
    "XAUUSD=X": "الذهب XAU/USD",
    "EURUSD=X": "اليورو/دولار EUR/USD",
    "CL=F": "النفط WTI"
}

# ==== دالة مراقبة الأداء ====
def monitor_market():
    result = []
    for symbol, name in SYMBOLS.items():
        try:
            data = yf.download(symbol, period="1d", interval="15m")
            if data.empty:
                result.append(f"⚠️ لا توجد بيانات لـ {name}")
                continue

            last_price = data["Close"].iloc[-1]
            open_price = data["Open"].iloc[0]
            change_pct = ((last_price - open_price) / open_price) * 100

            if change_pct <= -3:
                tg_send(f"🚨 {name}\nقف التداول الآن – وصلت حد الخسارة اليومية ({change_pct:.2f}%)")
            elif change_pct >= 0.8:
                risk = ACCOUNT_BALANCE * 0.01
                tp1 = last_price * 1.005
                tp2 = last_price * 1.01
                sl = last_price * 0.995
                tg_send(
                    f"✅ {name}\nادخل الآن – فرصة قوية للربح\n"
                    f"الدخول: {last_price:.2f}\nوقف الخسارة: {sl:.2f}\n"
                    f"TP1: {tp1:.2f}\nTP2: {tp2:.2f}\nحجم الصفقة: ${risk:.2f}"
                )
            else:
                result.append(f"{name}: مستقر ({change_pct:.2f}%)")
        except Exception as e:
            result.append(f"❌ خطأ في {name}: {e}")
    return result

# ==== المسارات ====
@app.get("/")
def root():
    return jsonify({"status": "ok", "time": datetime.now(KSA_TZ).strftime("%Y-%m-%d %H:%M:%S")})

@app.get("/monitor")
def monitor():
    updates = monitor_market()
    return jsonify({"result": updates})

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)
