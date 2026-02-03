import os
import time
import requests
import asyncio
from telegram import Bot

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
API_KEY = os.getenv("API_KEY")

SYMBOL = "XAUUSD"
INTERVAL = "15min"

bot = Bot(token=BOT_TOKEN)

def get_prices():
    url = f"https://www.alphavantage.co/query?function=FX_INTRADAY&from_symbol=XAU&to_symbol=USD&interval={INTERVAL}&apikey={API_KEY}"
    r = requests.get(url).json()
    data = list(r["Time Series FX (15min)"].values())
    closes = [float(x["4. close"]) for x in data[:100]]
    return closes

def rsi(prices, period=14):
    gains = []
    losses = []
    for i in range(1, period + 1):
        diff = prices[i] - prices[i - 1]
        if diff >= 0:
            gains.append(diff)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(diff))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def support_resistance(prices):
    support = min(prices[-20:])
    resistance = max(prices[-20:])
    return support, resistance

async def analyze():
    prices = get_prices()
    last_price = prices[0]
    rsi_value = rsi(prices)
    support, resistance = support_resistance(prices)

    signal = "⏸️ انتظار"
    tp = sl = "—"

    if rsi_value < 30 and last_price > support:
        signal = "🟢 شراء"
        sl = round(support, 2)
        tp = round(last_price + (last_price - support) * 2, 2)

    elif rsi_value > 70 and last_price < resistance:
        signal = "🔴 بيع"
        sl = round(resistance, 2)
        tp = round(last_price - (resistance - last_price) * 2, 2)

    msg = f"""
📊 XAUUSD M15

السعر: {last_price}
RSI: {round(rsi_value,2)}

الدعم: {round(support,2)}
المقاومة: {round(resistance,2)}

الإشارة: {signal}
TP: {tp}
SL: {sl}
"""

    await bot.send_message(chat_id=CHAT_ID, text=msg)

async def main():
    while True:
        try:
            await analyze()
        except Exception as e:
            await bot.send_message(chat_id=CHAT_ID, text=f"⚠️ خطأ: {e}")
        await asyncio.sleep(900)  # كل 15 دقيقة

if __name__ == "__main__":
    asyncio.run(main())
