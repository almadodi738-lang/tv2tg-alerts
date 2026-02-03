import os
import time
import requests
import pandas as pd
from telegram import Bot
from flask import Flask

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
DATA_API_KEY = os.getenv("DATA_API_KEY")

SYMBOL = "XAU/USD"
INTERVAL = "15min"

bot = Bot(token=BOT_TOKEN)
app = Flask(__name__)

def get_data():
    url = f"https://api.twelvedata.com/time_series?symbol={SYMBOL}&interval={INTERVAL}&apikey={DATA_API_KEY}&outputsize=100"
    r = requests.get(url).json()
    if "values" not in r:
        raise Exception(r)
    df = pd.DataFrame(r["values"])
    df = df.astype(float)
    df = df[::-1]
    return df

def indicators(df):
    df["ema50"] = df["close"].ewm(span=50).mean()
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss
    df["rsi"] = 100 - (100 / (1 + rs))
    return df

def support_resistance(df):
    support = df["low"].tail(30).min()
    resistance = df["high"].tail(30).max()
    return support, resistance

def analyze():
    df = get_data()
    df = indicators(df)
    support, resistance = support_resistance(df)

    last = df.iloc[-1]
    prev = df.iloc[-2]

    trend_up = last["close"] > last["ema50"]
    trend_down = last["close"] < last["ema50"]

    bullish = last["close"] > last["open"]
    bearish = last["close"] < last["open"]

    if trend_up and last["rsi"] < 35 and last["close"] <= support * 1.002 and bullish:
        sl = support
        tp = last["close"] + (last["close"] - sl) * 2
        return "BUY", last["close"], sl, tp, last["rsi"]

    if trend_down and last["rsi"] > 65 and last["close"] >= resistance * 0.998 and bearish:
        sl = resistance
        tp = last["close"] - (sl - last["close"]) * 2
        return "SELL", last["close"], sl, tp, last["rsi"]

    return None

def run_bot():
    bot.send_message(chat_id=CHAT_ID, text="✅ Gold Bot PRO (Filtered Strategy) Started")
    while True:
        try:
            result = analyze()
            if result:
                signal, price, sl, tp, rsi = result
                msg = f"""
📊 XAUUSD (M15)

Signal: {signal}
Price: {round(price,2)}
RSI: {round(rsi,2)}
Support: {round(sl,2)}
Resistance: {round(tp,2)}

🎯 TP: {round(tp,2)}
🛑 SL: {round(sl,2)}
"""
                bot.send_message(chat_id=CHAT_ID, text=msg)
                time.sleep(900)
            time.sleep(60)
        except Exception as e:
            bot.send_message(chat_id=CHAT_ID, text=f"⚠ Error: {e}")
            time.sleep(120)

@app.route("/")
def home():
    return "Bot is running"

if __name__ == "__main__":
    from threading import Thread
    Thread(target=run_bot).start()
    app.run(host="0.0.0.0", port=10000)
