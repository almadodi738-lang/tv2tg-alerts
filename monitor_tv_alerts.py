import os
import requests
from flask import Flask, request, jsonify

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

app = Flask(__name__)

# ===== TELEGRAM =====
def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})


# ===== AUTO TARGET CALC =====
def calc_targets(price, signal):
    price = float(price)

    # تقدير ATR ذكي للذهب (متوازن)
    atr = price * 0.0025

    if signal.upper() == "BUY":
        tp1 = price + atr
        tp2 = price + atr * 2
        tp3 = price + atr * 3
        sl  = price - atr * 1.2

    elif signal.upper() == "SELL":
        tp1 = price - atr
        tp2 = price - atr * 2
        tp3 = price - atr * 3
        sl  = price + atr * 1.2

    else:
        return None, None, None, None

    return tp1, tp2, tp3, sl


# ===== ROUTES =====
@app.route("/")
def home():
    return "Webhook Bot Running"


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json

    symbol = data.get("symbol", "GOLD")
    signal = data.get("signal", "")
    price = data.get("price", 0)

    # لو TradingView ما أرسل أهداف — نحسبها
    tp1 = data.get("tp1")
    tp2 = data.get("tp2")
    tp3 = data.get("tp3")
    sl  = data.get("sl")

    if not tp1 or not tp2 or not tp3 or not sl:
        tp1, tp2, tp3, sl = calc_targets(price, signal)

    msg = f"""
📊 {symbol}

🔥 Signal: {signal}
💰 Price: {float(price):.2f}

🎯 TP1: {float(tp1):.2f}
🎯 TP2: {float(tp2):.2f}
🎯 TP3: {float(tp3):.2f}

🛑 SL: {float(sl):.2f}
"""

    send_telegram(msg)
    return jsonify({"status": "ok"})


# ===== START =====
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
