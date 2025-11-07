import os, logging, requests
from datetime import datetime
from flask import Flask, request, jsonify
from zoneinfo import ZoneInfo

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
SHARED_SECRET = os.getenv("SHARED_SECRET", "supersecret123")
ACCOUNT_BALANCE = float(os.getenv("ACCOUNT_BALANCE", "200"))
DAILY_LOSS_LIMIT_PCT = float(os.getenv("DAILY_LOSS_LIMIT_PCT", "3.0"))
TZ = ZoneInfo(os.getenv("TZ", "Asia/Riyadh"))

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

daily_stats = {}

def today_key():
    return datetime.now(TZ).strftime("%Y-%m-%d")

def ensure_symbol_day(symbol, day):
    if day not in daily_stats:
        daily_stats[day] = {}
    if symbol not in daily_stats[day]:
        daily_stats[day][symbol] = {"realized_usd": 0.0, "start_balance": ACCOUNT_BALANCE}

def tg_send(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logging.warning("Telegram creds missing; not sending message")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=10)
        logging.info("Telegram %s %s", r.status_code, r.text[:200])
    except Exception as e:
        logging.exception("Telegram error: %s", e)

@app.get("/health")
def health():
    return {"ok": True, "time": datetime.now(TZ).isoformat()}

@app.post("/webhook/<secret>")
def webhook(secret):
    if secret != SHARED_SECRET:
        return jsonify({"ok": False, "error": "bad secret"}), 403

    data = request.get_json(force=True, silent=True) or {}
    logging.info("RX: %s", data)

    symbol = (data.get("symbol") or data.get("ticker") or data.get("instrument") or "").upper() or "SYMBOL"
    day = today_key()
    ensure_symbol_day(symbol, day)

    realized_usd = None
    if "realized_pl" in data:
        try: realized_usd = float(data["realized_pl"])
        except: pass
    if realized_usd is None and "pl_usd" in data:
        try: realized_usd = float(data["pl_usd"])
        except: pass

    pl_pct = None
    for k in ("pl_pct","pl_percent","realized_pct"):
        if k in data:
            try:
                pl_pct = float(data[k])
                break
            except: pass

    if realized_usd is not None:
        daily_stats[day][symbol]["realized_usd"] += realized_usd
        start_bal = daily_stats[day][symbol]["start_balance"]
        pl_pct = (daily_stats[day][symbol]["realized_usd"] / start_bal) * 100.0

    if pl_pct is not None and pl_pct <= -abs(DAILY_LOSS_LIMIT_PCT):
        msg = (
            "قف التداول الآن – وصلت حد الخسارة اليومية\n"
            f"رمز: {symbol}\n"
            f"الخسارة اليومية: {pl_pct:.2f}%\n"
            f"رصيد الأساس لليوم: ${daily_stats[day][symbol]['start_balance']:.2f}"
        )
        tg_send(msg)
        return {"ok": True, "action": "stop_sent"}

    prob = None
    for k in ("probability","prob","pattern_winrate","winrate"):
        if k in data:
            try:
                prob = float(data[k])
                break
            except: pass
    if prob is not None and 0 <= prob <= 1:
        prob *= 100.0

    if prob is not None and prob >= 80:
        entry = data.get("entry")
        sl = data.get("sl") or data.get("stop")
        tp1 = data.get("tp1")
        tp2 = data.get("tp2")

        risk_amount = ACCOUNT_BALANCE * 0.01
        pos_line = ""
        try:
            entry_f = float(entry); sl_f = float(sl)
            dist = abs(entry_f - sl_f)
            if dist > 0:
                units = risk_amount / dist
                lots = units / 100000.0
                pos_line = f"حجم مقترح (وحدات): {units:.4f}\nتقريبًا لوت: {lots:.4f}"
        except Exception:
            pos_line = "تعذّر حساب الحجم تلقائيًا (تحقق من entry و sl)."

        msg = (
            "ادخل الآن – فرصة قوية للربح\n"
            f"رمز: {symbol}\n"
            f"نسبة النجاح المعلنة: {prob:.1f}%\n"
            f"Entry: {entry}\nStop Loss: {sl}\nTP1: {tp1}\nTP2: {tp2}\n"
            f"مخاطرة للحساب: ${risk_amount:.2f} من ${ACCOUNT_BALANCE:.2f}\n"
            f"{pos_line}"
        )
        tg_send(msg)
        return {"ok": True, "action": "high_prob_sent"}

    return {"ok": True, "status": "received"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)
