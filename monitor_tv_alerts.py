import os
import requests
from flask import Flask, request, jsonify

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

app = Flask(__name__)


def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})


# ===== تنسيق الأسعار =====
def format_price(value, symbol):

    try:
        value = float(value)

        # SILVER
        if "XAG" in symbol:
            return f"{value:.2f}"

        # GOLD + BTC
        if "XAU" in symbol or "BTC" in symbol:
            return str(round(value))

        return str(value)

    except:
        return value


# ===== حساب RR =====
def calc_rr(entry, sl, tp1):

    try:

        entry = float(entry)
        sl = float(sl)
        tp1 = float(tp1)

        risk = abs(entry - sl)
        reward = abs(tp1 - entry)

        return round(reward / risk,2)

    except:
        return None


@app.route("/")
def home():
    return "Webhook Bot Running"


@app.route("/webhook", methods=["POST"])
def webhook():

    data = request.get_json(silent=True)

    if data is None:
        data = request.form.to_dict()

    if not data:
        try:
            data = eval(request.data.decode())
        except:
            data = {}

    print("Incoming:", data)

    symbol = data.get("symbol")
    signal = data.get("signal") or data.get("side")

    # ===== منع رسائل None =====
    if not signal:
        return jsonify({"status":"ignored"})


    entry_raw = data.get("price") or data.get("entry")

    sl_raw  = data.get("sl")
    tp1_raw = data.get("tp1")
    tp2_raw = data.get("tp2")
    tp3_raw = data.get("tp3")


    # ===== تنسيق الأرقام =====
    entry = format_price(entry_raw, symbol)

    sl  = format_price(sl_raw, symbol)
    tp1 = format_price(tp1_raw, symbol)
    tp2 = format_price(tp2_raw, symbol)
    tp3 = format_price(tp3_raw, symbol)


    rr = calc_rr(entry_raw, sl_raw, tp1_raw)


    try:
        distance = abs(float(tp1_raw) - float(entry_raw))
        distance = round(distance,2)
    except:
        distance = None


    msg = f"""
📊 {symbol}

🔥 Signal: {signal}
💰 Entry: {entry}
"""


    if signal.upper() != "EXIT":

        msg += f"""

🎯 Targets
TP1: {tp1}
TP2: {tp2}
TP3: {tp3}

🛑 Stop Loss: {sl}
"""

        if rr:
            msg += f"\n📈 RR: 1 : {rr}"

        if distance:
            msg += f"\n💎 TP1 Distance: {distance}"


    send_telegram(msg)

    return jsonify({"status":"ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
