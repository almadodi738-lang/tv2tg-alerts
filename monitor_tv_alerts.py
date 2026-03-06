import os
import requests
from flask import Flask, request, jsonify

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

app = Flask(name)

def send_telegram(msg):
url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
requests.post(
url,
data={
"chat_id": CHAT_ID,
"text": msg
}
)

def format_price(value, symbol):
try:
value = float(value)
symbol = str(symbol).upper()

    if "XAG" in symbol:
        return f"{value:.2f}"

    if "BTC" in symbol or "XAU" in symbol:
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
signal = data.get("signal") or data.get("side")

if not symbol or not signal:
    return jsonify({"status": "ignored"})

entry_raw = data.get("entry") or data.get("price")
sl_raw = data.get("sl")
tp1_raw = data.get("tp1")
tp2_raw = data.get("tp2")
tp3_raw = data.get("tp3")

entry = format_price(entry_raw, symbol)
sl = format_price(sl_raw, symbol)
tp1 = format_price(tp1_raw, symbol)
tp2 = format_price(tp2_raw, symbol)
tp3 = format_price(tp3_raw, symbol)

rr = calc_rr(entry_raw, sl_raw, tp1_raw)

msg = f"""

📊 {symbol}

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

if name == "main":
app.run(host="0.0.0.0", port=10000)
