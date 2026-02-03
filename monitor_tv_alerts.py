import os
import time
import requests
import telegram
from datetime import datetime

TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
API_KEY = os.getenv("API_KEY")

bot = telegram.Bot(token=TOKEN)
bot.send_message(chat_id=CHAT_ID, text="🟡 Gold Smart Bot PRO+ Started")

FROM_SYMBOL = "XAU"
TO_SYMBOL = "USD"
INTERVAL = "15min"

# ===== إعدادات إدارة رأس المال =====
ACCOUNT_BALANCE = 100      # عدلها لرصيدك
RISK_PERCENT = 1          # 1% مخاطرة في الصفقة

# ===== أوقات أخبار قوية (تقريبية UTC) =====
HIGH_IMPACT_HOURS = [12, 13, 14]  # وقت أخبار أمريكية تقريباً

def news_filter():
    hour = datetime.utcnow().hour
    return hour not in HIGH_IMPACT_HOURS

def get_data():
    url = (
        "https://www.alphavantage.co/query?"
        f"function=FX_INTRADAY&from_symbol={FROM_SYMBOL}&to_symbol={TO_SYMBOL}"
        f"&interval={INTERVAL}&apikey={API_KEY}"
    )
    r = requests.get(url).json()
    data = list(r["Time Series FX (15min)"].values())
    candles = [{
        "open": float(x["1. open"]),
        "high": float(x["2. high"]),
        "low": float(x["3. low"]),
        "close": float(x["4. close"])
    } for x in data[:100]]
    return candles

def rsi(prices, period=14):
    gains, losses = [], []
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

def detect_pattern(c1,c2):
    if c2["close"]>c2["open"] and c2["close"]>c1["open"] and c2["open"]<c1["close"]:
        return "bullish"
    if c2["close"]<c2["open"] and c2["open"]>c1["close"] and c2["close"]<c1["open"]:
        return "bearish"
    return None

def support_resistance(closes):
    return min(closes[-30:]), max(closes[-30:])

def position_size(balance, risk_percent, sl_points):
    risk_amount = balance * (risk_percent/100)
    lot = risk_amount / sl_points if sl_points>0 else 0
    return round(lot,2)

last_signal=""

while True:
    try:
        if not news_filter():
            time.sleep(300)
            continue

        candles=get_data()
        closes=[c["close"] for c in candles]

        rsi_val=rsi(closes)
        ema_fast=ema(closes,9)
        ema_slow=ema(closes,21)
        atr_val=atr(candles)
        support,resistance=support_resistance(closes)
        pattern=detect_pattern(candles[1],candles[0])

        price=closes[0]
        trend="up" if ema_fast>ema_slow else "down"

        signal=None
        confidence=0
        reasons=[]

        if trend=="up":
            confidence+=20
            reasons.append("Uptrend")
        if trend=="down":
            confidence+=20
            reasons.append("Downtrend")

        if rsi_val<30:
            confidence+=20
            reasons.append("RSI Oversold")
        if rsi_val>70:
            confidence+=20
            reasons.append("RSI Overbought")

        if pattern=="bullish":
            confidence+=10
            reasons.append("Bullish Candle")
        if pattern=="bearish":
            confidence+=10
            reasons.append("Bearish Candle")

        if price<=support*1.01:
            confidence+=10
            reasons.append("Near Support")
        if price>=resistance*0.99:
            confidence+=10
            reasons.append("Near Resistance")

        if confidence>=70:
            if trend=="up" and rsi_val<30 and pattern=="bullish":
                signal="BUY"
                sl=price-atr_val*1.5
                tp1=price+atr_val*2
                tp2=price+atr_val*3
            elif trend=="down" and rsi_val>70 and pattern=="bearish":
                signal="SELL"
                sl=price+atr_val*1.5
                tp1=price-atr_val*2
                tp2=price-atr_val*3

        if signal and signal!=last_signal:
            sl_points = abs(price-sl)
            lot = position_size(ACCOUNT_BALANCE, RISK_PERCENT, sl_points)

            chart_url = f"https://www.tradingview.com/chart/?symbol=XAUUSD"

            msg=f"""
📊 GOLD PRO SIGNAL

Type: {signal}
Entry: {price:.2f}
Stop Loss: {sl:.2f}
TP1: {tp1:.2f}
TP2: {tp2:.2f}

Lot (Risk {RISK_PERCENT}%): {lot}
Confidence: {confidence}%

Reasons:
- """+"\n- ".join(reasons)+f"""

Chart:
{chart_url}
"""
            bot.send_message(chat_id=CHAT_ID,text=msg)
            last_signal=signal

        time.sleep(300)

    except Exception as e:
        bot.send_message(chat_id=CHAT_ID,text=f"⚠️ Error: {e}")
        time.sleep(60)
