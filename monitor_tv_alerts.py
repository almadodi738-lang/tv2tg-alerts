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

if value is None:
    return None

try:
    value = float(value)
except:
    return value

symbol = str(symbol).upper()

if "XAG" in symbol or "SILVER" in symbol:
    return f"{value:.2f}"

if "XAU" in symbol or "GOLD" in symbol:
    return str(round(value))

if "BTC" in symbol:
    return str(round(value))

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

if not symbol or not signal:
    return jsonify({"status": "ignored"})

entry_raw = data.get("price") or data.get("entry")
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

distance = None

try:
    if entry_raw and tp1_raw:
        distance_val = abs(float(tp1_raw) - float(entry_raw))
        distance = format_price(distance_val, symbol)
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

    if rr is not None:
        msg += f"\n📈 RR: 1 : {rr}"

    if distance is not None:
        msg += f"\n💎 TP1 Distance: {distance}"

send_telegram(msg)

return jsonify({"status": "ok"})

if name == "main":
app.run(host="0.0.0.0", port=10000)
