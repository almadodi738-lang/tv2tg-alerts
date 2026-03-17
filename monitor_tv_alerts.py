import os
import requests
from flask import Flask, request, jsonify

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

app = Flask(__name__)

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(
        url,
        data={
            "chat_id": CHAT_ID,
            "text": msg
        }
    )

def format_price(value, symbol, market=""):
    try:
        value = float(value)
        symbol = str(symbol).upper()
        market = str(market).upper()

        # الفضة رقمين عشريين
        if "XAG" in symbol or "SILVER" in symbol or market == "SILVER":
            return f"{value:.2f}"

        # الذهب بدون كسور
        if "XAU" in symbol or "GOLD" in symbol or market == "GOLD":
            return str(round(value))

        # البتكوين بدون كسور
        if "BTC" in symbol:
            return str(round(value))

        return str(value)

    except:
        return value


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

        if rr < 1:
            rr = 1 / rr

        return round(rr, 2)

    except:
        return None


@app.route("/")
def home():
    return "Webhook Bot Running"


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json

    print("Incoming:", data)

    symbol = data.get("symbol")
    market = data.get("market", "")
    signal = data.get("signal") or data.get("side")

    if not symbol or not signal:
        return jsonify({"status": "ignored"})

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

    msg = f"""
📊 {market or symbol}

🔥 Signal: {signal}
💰 Entry: {entry}

🎯 Targets
TP1: {tp1}
TP2: {tp2}
TP3: {tp3}

🛑 Stop Loss: {sl}
"""

    if rr:
        msg += f"\n📈 RR: 1 : {rr}"

    send_telegram(msg)

    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
