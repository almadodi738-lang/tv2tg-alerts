import os
import time
import requests
from telegram import Bot
from flask import Flask
from threading import Thread
from datetime import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
API_KEY = os.getenv("API_KEY")

SYMBOL = "XAUUSD"
INTERVAL = "15min"

bot = Bot(token=BOT_TOKEN)
app = Flask(__name__)

def get_price_data():
    url = f"https://www.alphavantage.co/query?function=FX_INTRADAY&from_symbol=XAU&to_symbol=USD&interval=15min&apikey={API_KEY}"
    r = requests.get(url).json()
    data = list(r["Time Series FX (15min)"].values())
    closes = [float(x["4. close"]) for x in data[:50]]
    return closes

def rsi(prices, period=14):
    gains = []
    losses = []
    for i in range(1, period + 1):
        change = prices[i] - prices[i-1]
        if change > 0:
            gains.append(change)
        else:
            losses.append(abs(change))
    avg_gain = sum(gains)/period if gains else 0
    avg_loss = sum(losses)/period if losses else 0
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100/(1+rs))

def support_resistance(prices):
    return min(prices), max(prices)

def analyze():
    prices = get_price_data()
    current_price = prices[0]
    r = rsi(prices)
    support, resistance = support_resistance(prices)

    if r < 30 and current_price > support:
        return "BUY", current_price, support, resistance, r
    elif r > 70 and current_price < resistance:
        return "SELL", current_price, support, resistance, r
    else:
        return None

def run_bot():
    bot.send_message(chat_id=CHAT_ID, text="🤖 Gold Smart Bot Started")
    while True:
        try:
            result = analyze()
            if result:
                signal, price, sup, res, rsi_val = result
                sl = sup if signal == "BUY" else res
                tp = res if signal == "BUY" else sup

                msg = f"""
📊 XAUUSD (M15)
Signal: {signal}
Price: {price}
RSI: {round(rsi_val,2)}
Support: {sup}
Resistance: {res}

🎯 TP: {tp}
🛑 SL: {sl}
"""
                bot.send_message(chat_id=CHAT_ID, text=msg)
            time.sleep(900)
        except Exception as e:
            bot.send_message(chat_id=CHAT_ID, text=f"⚠️ Error: {e}")
            time.sleep(60)

@app.route("/")
def home():
    return "Bot is running"

if __name__ == "__main__":
    Thread(target=run_bot).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
