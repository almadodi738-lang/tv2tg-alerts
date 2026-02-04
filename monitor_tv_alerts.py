import os
import time
import requests
import pandas as pd
from flask import Flask
from threading import Thread

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
DATA_API_KEY = os.getenv("DATA_API_KEY")

SYMBOL = "XAU/USD"
INTERVAL = "15min"

app = Flask(__name__)

def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    requests.post(url, data=payload)

def get_data():
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": SYMBOL,
        "interval": INTERVAL,
        "apikey": DATA_API_KEY,
        "outputsize": 200
    }

    r = requests.get(url, params=params).json()
    if "values" not in r:
        raise Exception(r)

    df = pd.DataFrame(r["values"])
    for col in ["open","high","low","close"]:
        df[col] = df[col].astype(float)

    df = df[::-1]
    return df

def indicators(df):
    df["ema50"] = df["close"].ewm(span=50).mean()
    df["ema200"] = df["close"].ewm(span=200).mean()

    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss
    df["rsi"] = 100 - (100 / (1 + rs))

    df["tr"] = df["high"] - df["low"]
    df["atr"] = df["tr"].rolling(14).mean()

    return df

def support_resistance(df):
    support = df["low"].tail(40).min()
    resistance = df["high"].tail(40).max()
    return support, resistance

def analyze():
    df = get_data()
    df = indicators(df)
    support, resistance = support_resistance(df)

    last = df.iloc[-1]
    prev = df.iloc[-2]

    trend_up = last["ema50"] > last["ema200"]
    trend_down = last["ema50"] < last["ema200"]

    bullish = last["close"] > last["open"]
    bearish = last["close"] < last["open"]

    near_support = last["close"] <= support * 1.005
    near_resistance = last["close"] >= resistance * 0.995

    # BUY from support
    if trend_up and near_support and last["rsi"] < 40 and bullish:
        sl = last["close"] - last["atr"]
        tp = last["close"] + (last["atr"] * 2)
        return "BUY (Support)", last["close"], sl, tp, last["rsi"]

    # SELL from resistance
    if trend_down and near_resistance and last["rsi"] > 60 and bearish:
        sl = last["close"] + last["atr"]
        tp = last["close"] - (last["atr"] * 2)
        return "SELL (Resistance)", last["close"], sl, tp, last["rsi"]

    # Breakout BUY
    if trend_up and last["close"] > resistance and last["rsi"] > 55:
        sl = last["close"] - last["atr"]
        tp = last["close"] + (last["atr"] * 2)
        return "BUY (Breakout)", last["close"], sl, tp, last["rsi"]

    # Breakout SELL
    if trend_down and last["close"] < support and last["rsi"] < 45:
        sl = last["close"] + last["atr"]
        tp = last["close"] - (last["atr"] * 2)
        return "SELL (Breakout)", last["close"], sl, tp, last["rsi"]

    return None

def run_bot():
    send_telegram("✅ Gold Bot PRO (Full Analysis Mode) Started")

    while True:
        try:
            result = analyze()
            if result:
                signal, price, sl, tp, rsi = result

                msg = f"""
📊 XAU/USD (M15)

🔥 Signal: {signal}
💰 Price: {round(price,2)}
📈 RSI: {round(rsi,2)}

🎯 TP: {round(tp,2)}
🛑 SL: {round(sl,2)}
"""
                send_telegram(msg)
                time.sleep(900)

            time.sleep(60)

        except Exception as e:
            send_telegram(f"⚠ Error: {e}")
            time.sleep(120)

@app.route("/")
def home():
    return "Bot is running"

if __name__ == "__main__":
    Thread(target=run_bot).start()
    app.run(host="0.0.0.0", port=10000)
