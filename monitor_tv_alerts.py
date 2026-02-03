import os
import time
import requests
from telegram import Bot
from flask import Flask
from threading import Thread

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
API_KEY = os.getenv("API_KEY")

bot = Bot(token=BOT_TOKEN)
app = Flask(__name__)

SYMBOL = "XAUUSD"
INTERVAL = "15min"

def get_data():
    url = f"https://www.alphavantage.co/query?function=FX_INTRADAY&from_symbol=XAU&to_symbol=USD&interval=15min&apikey={API_KEY}"
    r = requests.get(url).json()
    data = list(r["Time Series FX (15min)"].values())[:60]

    candles = []
    for c in data:
        candles.append({
            "open": float(c["1. open"]),
            "high": float(c["2. high"]),
            "low": float(c["3. low"]),
            "close": float(c["4. close"])
        })
    return candles

def rsi(prices, period=14):
    gains, losses = [], []
    for i in range(1, period+1):
        change = prices[i] - prices[i-1]
        if change > 0:
            gains.append(change)
        else:
            losses.append(abs(change))
    avg_gain = sum(gains)/period if gains else 0.01
    avg_loss = sum(losses)/period if losses else 0.01
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def atr(candles, period=14):
    trs = []
    for i in range(1, period+1):
        high = candles[i]["high"]
        low = candles[i]["low"]
        prev_close = candles[i-1]["close"]
        tr = max(high-low, abs(high-prev_close), abs(low-prev_close))
        trs.append(tr)
    return sum(trs)/period

def trend(prices):
    short = sum(prices[:10])/10
    long = sum(prices[:30])/30
    if short > long:
        return "UP"
    elif short < long:
        return "DOWN"
    return "FLAT"

def support_resistance(prices):
    return min(prices), max(prices)

def candle_pattern(c1, c2):
    # Bullish Engulfing
    if c2["close"] > c2["open"] and c2["close"] > c1["open"] and c2["open"] < c1["close"]:
        return "BULL"
    # Bearish Engulfing
    if c2["close"] < c2["open"] and c2["open"] > c1["close"]:
        return "BEAR"
    return None

def analyze():
    candles = get_data()
    closes = [c["close"] for c in candles]
    price = closes[0]

    r = rsi(closes)
    atr_val = atr(candles)
    sup, res = support_resistance(closes)
    tr = trend(closes)
    pattern = candle_pattern(candles[1], candles[0])

    if tr == "UP" and r < 30 and price <= sup and pattern == "BULL":
        sl = price - atr_val
        tp = price + atr_val*2
        return "BUY", price, sl, tp, r

    if tr == "DOWN" and r > 70 and price >= res and pattern == "BEAR":
        sl = price + atr_val
        tp = price - atr_val*2
        return "SELL", price, sl, tp, r

    return None

def run_bot():
    bot.send_message(chat_id=CHAT_ID, text="✅ Gold Smart Bot PRO Started")

    while True:
        try:
            result = analyze()
            if result:
                signal, price, sl, tp, r = result
                msg = f"""
XAUUSD (M15)
Signal: {signal}
Price: {round(price,2)}
RSI: {round(r,2)}

TP: {round(tp,2)}
SL: {round(sl,2)}
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
    app.run(host="0.0.0.0", port=10000)
