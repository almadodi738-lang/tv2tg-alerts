import requests
import time
import telegram

TOKEN = "8237336568:AAFX-91HZA2mxT7AwXORLeBdoxnvA4CGg9Q"
CHAT_ID = "64776285"
API_KEY = "UIAWK50Q406OIXUS"

bot = telegram.Bot(token=TOKEN)

def get_data():
    url = f"https://www.alphavantage.co/query?function=FX_INTRADAY&from_symbol=XAU&to_symbol=USD&interval=15min&apikey={API_KEY}"
    r = requests.get(url).json()
    data = list(r["Time Series FX (15min)"].values())
    closes = [float(x["4. close"]) for x in data[:50]]
    return closes

def rsi(prices, period=14):
    gains, losses = [], []
    for i in range(1, period+1):
        diff = prices[i] - prices[i-1]
        if diff > 0:
            gains.append(diff)
        else:
            losses.append(abs(diff))
    avg_gain = sum(gains)/period
    avg_loss = sum(losses)/period
    rs = avg_gain / avg_loss if avg_loss != 0 else 0
    return 100 - (100 / (1 + rs))

def send(msg):
    bot.send_message(chat_id=CHAT_ID, text=msg)

while True:
    prices = get_data()
    current = prices[0]
    ma50 = sum(prices[:50]) / 50
    r = rsi(prices[:15])

    if current > ma50 and r > 55:
        send(f"🟢 BUY GOLD\nPrice: {current}")
    elif current < ma50 and r < 45:
        send(f"🔴 SELL GOLD\nPrice: {current}")

    time.sleep(900)
