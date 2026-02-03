import os
import time
import requests
import telegram
import math

TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
API_KEY = os.getenv("API_KEY")

bot = telegram.Bot(token=TOKEN)
bot.send_message(chat_id=CHAT_ID, text="🟡 Gold Smart Bot PRO Started")

FROM_SYMBOL = "XAU"
TO_SYMBOL = "USD"
INTERVAL = "15min"

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

def adx(candles, period=14):
    plus_dm=[]
    minus_dm=[]
    trs=[]
    for i in range(1,period+1):
        up=candles[i]["high"]-candles[i-1]["high"]
        down=candles[i-1]["low"]-candles[i]["low"]
        plus_dm.append(max(up,0) if up>down else 0)
        minus_dm.append(max(down,0) if down>up else 0)
        high=candles[i]["high"]
        low=candles[i]["low"]
        prev_close=candles[i-1]["close"]
        tr=max(high-low, abs(high-prev_close), abs(low-prev_close))
        trs.append(tr)
    tr_sum=sum(trs)
    plus_di=100*(sum(plus_dm)/tr_sum)
    minus_di=100*(sum(minus_dm)/tr_sum)
    dx=100*abs(plus_di-minus_di)/(plus_di+minus_di+0.0001)
    return dx

def detect_pattern(c1,c2):
    if c2["close"]>c2["open"] and c2["close"]>c1["open"] and c2["open"]<c1["close"]:
        return "bullish"
    if c2["close"]<c2["open"] and c2["open"]>c1["close"] and c2["close"]<c1["open"]:
        return "bearish"
    return None

def support_resistance(closes):
    return min(closes[-30:]), max(closes[-30:])

last_signal=""

while True:
    try:
        candles=get_data()
        closes=[c["close"] for c in candles]

        rsi_val=rsi(closes)
        ema_fast=ema(closes,9)
        ema_slow=ema(closes,21)
        atr_val=atr(candles)
        adx_val=adx(candles)
        support,resistance=support_resistance(closes)
        pattern=detect_pattern(candles[1],candles[0])

        price=closes[0]
        trend="up" if ema_fast>ema_slow else "down"

        signal=None
        confidence=0
        reason=[]

        if trend=="up": confidence+=20
        if trend=="down": confidence+=20

        if rsi_val<30:
            confidence+=20
            reason.append("RSI Oversold")
        if rsi_val>70:
            confidence+=20
            reason.append("RSI Overbought")

        if adx_val>20:
            confidence+=20
            reason.append("Strong Trend")

        if pattern=="bullish":
            confidence+=10
            reason.append("Bullish Candle")
        if pattern=="bearish":
            confidence+=10
            reason.append("Bearish Candle")

        if price<=support*1.01:
            confidence+=10
            reason.append("Near Support")
        if price>=resistance*0.99:
            confidence+=10
            reason.append("Near Resistance")

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
            msg=f"""
📊 GOLD PRO SIGNAL

Type: {signal}
Entry: {price:.2f}
Stop Loss: {sl:.2f}
TP1: {tp1:.2f}
TP2: {tp2:.2f}

Confidence: {confidence}%
RSI: {rsi_val:.2f}
ADX: {adx_val:.2f}
Trend: {trend}
Support: {support:.2f}
Resistance: {resistance:.2f}

Reasons:
- """+"\n- ".join(reason)
            bot.send_message(chat_id=CHAT_ID,text=msg)
            last_signal=signal

        time.sleep(300)

    except Exception as e:
        bot.send_message(chat_id=CHAT_ID,text=f"⚠️ Error: {e}")
        time.sleep(60)
