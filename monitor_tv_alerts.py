import os
import time
import requests
import telegram

# قراءة المتغيرات من Render
TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
API_KEY = os.getenv("API_KEY")

bot = telegram.Bot(token=TOKEN)

# رسالة عند تشغيل البوت
bot.send_message(chat_id=CHAT_ID, text="✅ Bot started successfully")

SYMBOL = "EURUSD"
INTERVAL = "15min"

def get_data():
    url = f"https://www.alphavantage.co/query?function=FX_INTRADAY&from_symbol=EUR&to_symbol=USD&interval=15min&apikey={API_KEY}"
    r = requests.get(url).json()
    data = list(r["Time Series FX (15min)"].values())
    closes = [float(x["4. close"]) for x in data[:50]]
    return closes

def rsi(prices, period=14):
    gains = []
    losses = []
    for i in range(1, period+1):
        diff = prices[i-1] - prices[i]
        if diff >= 0:
            gains.append(diff)
        else:
            losses.append(abs(diff))
    avg_gain = sum(gains)/period
    avg_loss = sum(losses)/period if losses else 0.0001
    rs = avg_gain / avg_loss
    return 100 - (100/(1+rs))

last_signal = ""

while True:
    try:
        prices = get_data()
        current_rsi = rsi(prices)

        if current_rsi < 30 and last_signal != "BUY":
            bot.send_message(chat_id=CHAT_ID, text=f"🟢 BUY SIGNAL\nRSI: {current_rsi:.2f}")
            last_signal = "BUY"

        elif current_rsi > 70 and last_signal != "SELL":
            bot.send_message(chat_id=CHAT_ID, text=f"🔴 SELL SIGNAL\nRSI: {current_rsi:.2f}")
            last_signal = "SELL"

        time.sleep(300)  # كل 5 دقائق

    except Exception as e:
        bot.send_message(chat_id=CHAT_ID, text=f"⚠️ Error: {e}")
        time.sleep(60)
