import os
import logging
from datetime import datetime, timedelta, timezone

import requests
from flask import Flask, request, jsonify

# ===== إعدادات عامة =====
KSA_TZ = timezone(timedelta(hours=3))

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
SHARED_SECRET = os.getenv("SHARED_SECRET", "Admin@1716")

ACCOUNT_BALANCE = float(os.getenv("ACCOUNT_BALANCE", "200"))      # رصيد الحساب
RISK_PCT = float(os.getenv("RISK_PCT", "1"))                      # 1% للمعلومية فقط
DAILY_LOSS_LIMIT_PCT = float(os.getenv("DAILY_LOSS_LIMIT_PCT", "3"))  # حد الخسارة اليومي 3%

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# حالة اليوم (للمتابعة)
STATE = {
    "date": None,
    "pnl": 0.0,
    "wins": 0,
    "losses": 0,
    "trades": 0,
}


# ===== دوال مساعدة =====

def now_ksa() -> datetime:
    return datetime.now(KSA_TZ)


def reset_state_if_newday():
    """لو تغيّر اليوم نرجّع العدّاد للصفر"""
    today = now_ksa().date()
    if STATE["date"] != today:
        STATE["date"] = today
        STATE["pnl"] = 0.0
        STATE["wins"] = 0
        STATE["losses"] = 0
        STATE["trades"] = 0


def tg_send(text: str) -> bool:
    """إرسال رسالة إلى تيليجرام"""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        app.logger.warning("TELEGRAM_TOKEN أو TELEGRAM_CHAT_ID غير موجودين.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        r = requests.post(
            url,
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text},
            timeout=10,
        )
        app.logger.info("Telegram: %s %s", r.status_code, r.text)
        return r.ok
    except Exception as e:
        app.logger.exception("Telegram error: %s", e)
        return False


def check_secret() -> bool:
    """التحقق من السر القادم من ThinkTrader"""
    secret = (
        request.args.get("secret", "")
        or request.headers.get("X-Secret", "")
        or ""
    )
    return secret == SHARED_SECRET


# ===== المسارات الأساسية =====

@app.get("/")
def root():
    reset_state_if_newday()
    return jsonify({
        "ok": True,
        "message": "Trading helper running (ThinkTrader mode)",
        "time_riyadh": now_ksa().strftime("%Y-%m-%d %H:%M:%S"),
        "state": STATE,
    })


@app.get("/ping")
def ping():
    reset_state_if_newday()
    return jsonify({
        "status": "ok",
        "time_riyadh": now_ksa().strftime("%Y-%m-%d %H:%M:%S"),
    })


# ===== استقبال تنبيهات ThinkTrader =====
@app.post("/hook")
def hook():
    """
    Webhook من ThinkTrader.
    تستقبل JSON مثل:
    {
      "message": "تنبيه: شراء XAUUSD من 2400 ستوب 2385 ..."
    }
    """
    if not check_secret():
        return jsonify({"ok": False, "error": "Unauthorized"}), 403

    payload = request.get_json(silent=True) or {}
    text = payload.get("message") or payload.get("text") or str(payload)

    if not text:
        return jsonify({"ok": False, "error": "no message"}), 400

    sent = tg_send(f"📢 تنبيه من ThinkTrader:\n{text}")
    return jsonify({"ok": sent})


# ===== استقبال نتيجة الصفقة من ThinkTrader (ربح/خسارة) =====
@app.post("/report_fill")
def report_fill():
    """
    ThinkTrader يرسل نتيجة الصفقة بعد الإغلاق:
    {
      "pnl": -5.3,     # الربح/الخسارة بالدولار
      "symbol": "XAUUSD",
      "note": "صفقة لندن"
    }
    """
    if not check_secret():
        return jsonify({"ok": False, "error": "Unauthorized"}), 403

    reset_state_if_newday()

    data = request.get_json(silent=True) or {}
    pnl = float(data.get("pnl", 0.0))
    symbol = data.get("symbol", "UNKNOWN")
    note = data.get("note", "")

    STATE["pnl"] += pnl
    STATE["trades"] += 1
    if pnl >= 0:
        STATE["wins"] += 1
    else:
        STATE["losses"] += 1

    # نسبة الخسارة من رصيد 200$
    pnl_pct = (STATE["pnl"] / ACCOUNT_BALANCE) * 100.0

    msg = (
        f"📊 تحديث نتيجة صفقة:\n"
        f"الزوج/الأداة: {symbol}\n"
        f"PnL: {pnl:.2f}$\n"
        f"إجمالي اليوم: {STATE['pnl']:.2f}$ ({pnl_pct:.2f}%)\n"
        f"عدد الصفقات: {STATE['trades']} (ربح {STATE['wins']} / خسارة {STATE['losses']})"
    )
    if note:
        msg += f"\nملاحظة: {note}"

    tg_send(msg)

    # حد الخسارة اليومية
    if pnl_pct <= -DAILY_LOSS_LIMIT_PCT:
        tg_send("⛔ قف التداول الآن – وصلت حد الخسارة اليومية")
        return jsonify({"ok": True, "state": STATE, "stop_trading": True})

    return jsonify({"ok": True, "state": STATE, "stop_trading": False})


# ===== إعادة ضبط اليوم يدويًا =====
@app.get("/reset_session")
def reset_session():
    if not check_secret():
        return jsonify({"ok": False, "error": "Unauthorized"}), 403

    STATE["date"] = now_ksa().date()
    STATE["pnl"] = 0.0
    STATE["wins"] = 0
    STATE["losses"] = 0
    STATE["trades"] = 0

    return jsonify({"ok": True, "state": STATE})


# ===== إرسال رسالة اختبار للتليجرام =====
@app.route("/test")
def test():
    if not check_secret():
        return jsonify({"status": "error", "message": "Invalid secret"}), 403

    msg = request.args.get("msg", "Test message from trading bot")
    tg_send(msg)
    return jsonify({"status": "sent", "message": msg})


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)
