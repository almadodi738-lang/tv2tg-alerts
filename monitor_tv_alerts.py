import os
import time
import requests
from flask import Flask
from threading import Thread

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
DATA_API_KEY = os.getenv("DATA_API_KEY")  # TwelveData API

SYMBOL = "XAUUSD"
INTERVAL = "15min"

app = Flask(__name__)

# ===== Telegram =====
def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    requests.post(url, data=payload)

# ===== Data =====
def get_data():
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": SYMBOL,
        "interval": INTERVAL,
        "apikey": DATA_API_KEY,
        "outputsize": 100
    }
    r = requests.get(url, params=params, timeout=10).json()

    if "values" not in r:
        raise Exception(str(r))

    candles = []
    for c in r["values"]:
        candles.append({
            "open": float(c["open"]),
            "high": float(c["high"]),
            "low": float(c["low"]),
            "close": float(c["close"])
        })
    return candles

# ===== Indicators =====
def rsi(prices, period=14):
    gains, losses = [], []
    for i in range(1, period+1):
        diff = prices[i] - prices[i-1]
        if diff > 0:
            gains.append(diff)
        else:
            losses.append(abs(diff))
    avg_gain = sum(gains)/period if gains else 0.0001
    avg_loss = sum(losses)/period if losses else 0.0001
    rs = avg_gain / avg_loss
    return 100 - (100/(1+rs))

def ema(prices, period):
    k = 2/(period+1)
    ema_val = prices[0]
    for p in prices:
        ema_val = p*k + ema_val*(1-k)
    return ema_val

def atr(candles, period=14):
    trs=[]
    for i in range(1,period+1):
        high=candles[i]["high"]
        low=candles[i]["low"]
        prev_close=candles[i-1]["close"]
        tr=max(high-low, abs(high-prev_close), abs(low-prev_close))
        trs.append(tr)
    return sum(trs)/period

def support_resistance(closes):
    return min(closes[-30:]), max(closes[-30:])

def candle_pattern(c1, c2):
    if c2["close"] > c2["open"] and c2["close"] > c1["open"] and c2["open"] < c1["close"]:
        return "BULL"
    if c2["close"] < c2["open"] and c2["open"] > c1["close"] and c2["close"] < c1["open"]:
        return "BEAR"
    return None

# ===== Analysis =====
def analyze():
    candles = get_data()
    closes = [c["close"] for c in candles]

    price = closes[0]
    r = rsi(closes)
    ema_fast = ema(closes, 9)
    ema_slow = ema(closes, 21)
    atr_val = atr(candles)
    sup, res = support_resistance(closes)
    pattern = candle_pattern(candles[1], candles[0])

    trend = "UP" if ema_fast > ema_slow else "DOWN"

    if trend == "UP" and r < 30 and price <= sup*1.01 and pattern == "BULL":
        sl = price - atr_val
        tp = price + atr_val*2
        return "BUY", price, sl, tp, r

    if trend == "DOWN" and r > 70 and price >= res*0.99 and pattern == "BEAR":
        sl = price + atr_val
        tp = price - atr_val*2
        return "SELL", price, sl, tp, r

    return None

# ===== Bot Loop =====
def run_bot():
    send_telegram("✅ Gold Bot PRO (Full Analysis) Started")

    while True:
        try:
            result = analyze()
            if result:
                signal, price, sl, tp, r = result
                msg = f"""
📊 XAUUSD (M15)

Signal: {signal}
Price: {round(price,2)}
RSI: {round(r,2)}

🎯 TP: {round(tp,2)}
🛑 SL: {round(sl,2)}
"""
                send_telegram(msg)

            time.sleep(900)

        except Exception as e:
            send_telegram(f"⚠ Error: {e}")
            time.sleep(300)

@app.route("/")
def home():
    return "Bot is running"

if __name__ == "__main__":
    Thread(target=run_bot).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
