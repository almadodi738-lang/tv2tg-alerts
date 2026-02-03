import os
import time
import requests
import asyncio
from datetime import datetime
from telegram import Bot

# ====== متغيرات البيئة من Render ======
TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
API_KEY = os.getenv("API_KEY")

SYMBOL = "XAUUSD"
INTERVAL = "15min"

bot = Bot(token=TOKEN)

# ====== جلب البيانات ======
def get_prices():
    url = f"https://www.alphavantage.co/query?function=FX_INTRADAY&from_symbol=XAU&to_symbol=USD&interval={INTERVAL}&apikey={API_KEY}"
    r = requests.get(url).json()
    data = list(r["Time Series FX (15min)"].values())[:50]
    closes = [float(x["4. close"]) for x in data]
    highs = [float(x["2. high"]) for x in data]
    lows = [float(x["3. low"]) for x in data]
    return closes, highs, lows

# ====== RSI ======
def rsi(prices, period=14):
    gains, losses = [], []
    for i in range(1, period+1):
        diff = prices[i] - prices[i-1]
        if diff >= 0:
            gains.append(diff)
        else:
            losses.append(abs(diff))
    avg_gain = sum(gains)/period
    avg_loss = sum(losses)/period if losses else 0.0001
    rs = avg_gain/avg_loss
    return 100 - (100/(1+rs))

# ====== دعم ومقاومة ======
def support_resistance(highs, lows):
    support = min(lows[:10])
    resistance = max(highs[:10])
    return support, resistance

# ====== تحليل الشمعة ======
def candle_signal(op, hi, lo, cl):
    body = abs(cl - op)
    upper = hi - max(op, cl)
    lower = min(op, cl) - lo
    if lower > body*2:
        return "bullish"
    if upper > body*2:
        return "bearish"
    return "neutral"

# ====== التحليل الكامل ======
def analyze():
    closes, highs, lows = get_prices()
    price = closes[0]
    r = rsi(closes)
    sup, res = support_resistance(highs, lows)
    candle = candle_signal(closes[1], highs[0], lows[0], closes[0])

    if r < 30 and candle == "bullish" and price <= sup*1.002:
        sl = price - 10
        tp1 = price + 15
        tp2 = price + 30
        return f"""🟢 BUY SIGNAL (GOLD)
Price: {price}
RSI: {round(r,2)}
Support: {round(sup,2)}

SL: {round(sl,2)}
TP1: {round(tp1,2)}
TP2: {round(tp2,2)}
"""

    if r > 70 and candle == "bearish" and price >= res*0.998:
        sl = price + 10
        tp1 = price - 15
        tp2 = price - 30
        return f"""🔴 SELL SIGNAL (GOLD)
Price: {price}
RSI: {round(r,2)}
Resistance: {round(res,2)}

SL: {round(sl,2)}
TP1: {round(tp1,2)}
TP2: {round(tp2,2)}
"""

    return None

# ====== إرسال ======
async def send(msg):
    await bot.send_message(chat_id=CHAT_ID, text=msg)

# ====== تشغيل ======
async def main():
    await send("🟢 Gold Smart Bot Started")
    last = ""
    while True:
        try:
            signal = analyze()
            if signal and signal != last:
                await send(signal)
                last = signal
        except Exception as e:
            await send(f"⚠️ Error: {e}")
        time.sleep(300)

asyncio.run(main())
