import os
import requests
from flask import Flask, request, jsonify

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

app = Flask(__name__)

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    r = requests.post(
        url,
        data={
            "chat_id": CHAT_ID,
            "text": msg
        },
        timeout=15
    )
    print("Telegram:", r.status_code, r.text)
    return r

def format_price(value, symbol, market=""):
    try:
        if value is None:
            return "-"
        value = float(value)
        symbol = str(symbol).upper()
        market = str(market).upper()

        if "XAG" in symbol or "SILVER" in symbol or market == "SILVER":
            return f"{value:.2f}"

        if "XAU" in symbol or "GOLD" in symbol or market == "GOLD":
            return str(round(value))

        if "BTC" in symbol:
            return str(round(value))

        return str(value)
    except:
        return str(value)

def calc_rr(entry, sl, tp1):
    try:
        entry = float(entry)
        sl = float(sl)
        tp1 = float(tp1)

        risk = abs(entry - sl)
        reward = abs(tp1 - entry)

        if risk == 0:
            return None

        rr = reward / risk
        return round(rr, 2)
    except:
        return None

@app.route("/")
def home():
    return "Webhook Bot Running"

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True) or {}
    print("Incoming:", data)

    symbol = data.get("symbol")
    market = data.get("market", "")
    signal = data.get("signal") or data.get("side")
    event = data.get("event")

    if not symbol:
        return jsonify({"status": "ignored", "reason": "missing_symbol"})

    if signal:
        entry_raw = data.get("entry") or data.get("price")
        sl_raw = data.get("sl")
        tp1_raw = data.get("tp1")
        tp2_raw = data.get("tp2")
        tp3_raw = data.get("tp3")

        entry = format_price(entry_raw, symbol, market)
        sl = format_price(sl_raw, symbol, market)
        tp1 = format_price(tp1_raw, symbol, market)
        tp2 = format_price(tp2_raw, symbol, market)
        tp3 = format_price(tp3_raw, symbol, market)

        rr = calc_rr(entry_raw, sl_raw, tp1_raw)

        msg = f"""📊 {market or symbol}

🔥 Signal: {signal}
💰 Entry: {entry}

🎯 Targets
TP1: {tp1}
TP2: {tp2}
TP3: {tp3}

🛑 Stop Loss: {sl}"""

        if rr:
            msg += f"\n\n📈 RR: 1 : {rr}"

        tg = send_telegram(msg)
        return jsonify({"status": "ok", "type": "signal", "telegram_status": tg.status_code})

    if event:
        msg = f"""📊 {market or symbol}

⚡ Event: {event}"""

        tg = send_telegram(msg)
        return jsonify({"status": "ok", "type": "event", "telegram_status": tg.status_code})

    return jsonify({"status": "ignored", "reason": "missing_signal_and_event"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
