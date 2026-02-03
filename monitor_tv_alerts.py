import os
import requests
import asyncio
from telegram import Bot
from datetime import datetime

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
API_KEY = os.environ.get("API_KEY")

bot = Bot(token=BOT_TOKEN)

SYMBOL = "XAUUSD"
INTERVAL = "15min"

def get_data():
    url = f"https://www.alphavantage.co/query?function=FX_INTRADAY&from_symbol=XAU&to_symbol=USD&interval={INTERVAL}&apikey={API_KEY}"
    r = requests.get(url).json()
    data = list(r[f"Time Series FX ({INTERVAL})"].values())
    closes = [float(x["4. close"]) for x in data[:100]]
    highs = [float(x["2. high"]) for x in data[:100]]
    lows = [float(x["3. low"]) for x in data[:100]]
    return closes, highs, lows

def rsi(prices, period=14):
    gains = []
    losses = []
    for i in range(1, period+1):
        diff = prices[i] - prices[i-1]
        if diff > 0:
            gains.append(diff)
        else:
            losses.append(abs(diff))
    avg_gain = sum(gains)/period
    avg_loss = sum(losses)/period if losses else 0.0001
    rs = avg_gain / avg_loss
    return 100 - (100/(1+rs))

def support_resistance(highs, lows):
    return min(lows[:20]), max(highs[:20])

async def send_signal(text):
    await bot.send_message(chat_id=CHAT_ID, text=text)

async def analyze():
    closes, highs, lows = get_data()
    last = closes[0]
    prev = closes[1]

    r = rsi(closes[::-1])
    support, resistance = support_resistance(highs, lows)

    direction = None
    sl = tp1 = tp2 = None

    if last > prev and r < 35 and last <= support + 2:
        direction = "BUY"
        sl = last - 10
        tp1 = last + 15
        tp2 = last + 30

    elif last < prev and r > 65 and last >= resistance - 2:
        direction = "SELL"
        sl = last + 10
        tp1 = last - 15
        tp2 = last - 30

    if direction:
        msg = f"""
📊 GOLD SIGNAL (M15)
--------------------
Type: {direction}
Entry: {round(last,2)}
SL: {round(sl,2)}
TP1: {round(tp1,2)}
TP2: {round(tp2,2)}

RSI: {round(r,2)}
Support: {round(support,2)}
Resistance: {round(resistance,2)}

⏰ {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}
"""
        await send_signal(msg)

async def main():
    while True:
        try:
            await analyze()
        except Exception as e:
            await send_signal(f"⚠️ Error: {e}")
        await asyncio.sleep(900)  # كل 15 دقيقة

asyncio.run(main())
