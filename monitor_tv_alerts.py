import os
import requests
from flask import Flask, request, jsonify

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

app = Flask(__name__)

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})

@app.route("/")
def home():
    return "Webhook Bot Running"

@app.route("/webhook", methods=["POST"])
def webhook():

    data = request.json
    print("Incoming:", data)

    # دعم كل الصيغ
    symbol = data.get("symbol")
    signal = data.get("signal") or data.get("side")
    price  = data.get("price")  or data.get("entry")

    sl  = data.get("sl")
    tp1 = data.get("tp1")
    tp2 = data.get("tp2")
    tp3 = data.get("tp3")

    msg = f"""
📊 {symbol}

🔥 Signal: {signal}
💰 Price: {price}

🎯 TP1: {tp1}
🎯 TP2: {tp2}
🎯 TP3: {tp3}

🛑 SL: {sl}
"""

    send_telegram(msg)

    return jsonify({"status":"ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
