import requests
import time
import telegram
import os

# ===== مفاتيح البيئة (لا تكتب التوكن داخل الكود) =====
TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
API_KEY = os.environ.get("API_KEY")

bot = telegram.Bot(token=TOKEN)

SYMBOL = "EURUSD"   # تقدر تغيّره لأي زوج
INTERVAL = "15min"

# ===== جلب البيانات =====
def get_data():
    url = f"https://www.alphavantage.co/query?function=FX_INTRADAY&from_symbol=EUR&to_symbol=USD&interval={INTERVAL}&apikey={API_KEY}"
    r = requests.get(url).json()
    data = list(r[f"Time Series FX ({INTERVAL})"].values())
    closes = [float(x["4. close"]) for x in data[:50]]
    return closes

# ===== حساب RSI =====
def rsi(prices, period=14):
    gains = []
    losses = []

    for i in range(1, len(prices)):
        change = prices[i] - prices[i-1]
        if change > 0:
            gains.append(change)
        else:
            losses.append(abs(change))

    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period

    if avg_loss == 0:
        return 100

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

# ===== إرسال إشارة =====
def send_signal(signal, rsi_value):
    message = f"""
📊 Signal Alert
Pair: EUR/USD
RSI: {round(rsi_value,2)}

Signal: {signal}
"""
    bot.send_message(chat_id=CHAT_ID, text=message)

# ===== التشغيل =====
while True:
    try:
        prices = get_data()
        rsi_value = rsi(prices)

        if rsi_value < 30:
            send_signal("BUY 🟢", rsi_value)

        elif rsi_value > 70:
            send_signal("SELL 🔴", rsi_value)

        time.sleep(900)  # كل 15 دقيقة

    except Exception as e:
        print("Error:", e)
        time.sleep(60)
