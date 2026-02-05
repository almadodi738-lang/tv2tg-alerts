import os
import time
import requests
import pandas as pd
from flask import Flask
from threading import Thread
from datetime import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
API_KEY = os.getenv("DATA_API_KEY")

SYMBOLS = ["XAU/USD","BTC/USD","ETH/USD"]
INTERVAL = "15min"
HTF = "1h"

app = Flask(__name__)

last_signals = {}

# Telegram
def send(msg):
    url=f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url,data={"chat_id":CHAT_ID,"text":msg})

# Session Filter
def liquid_session():
    h=datetime.utcnow().hour
    return (7<=h<=16) or (12<=h<=21)

# Fetch Data
def candles(symbol,interval):
    url="https://api.twelvedata.com/time_series"
    r=requests.get(url,params={
        "symbol":symbol,
        "interval":interval,
        "apikey":API_KEY,
        "outputsize":200
    }).json()

    if "values" not in r:
        raise Exception(r)

    df=pd.DataFrame(r["values"])
    for c in ["open","high","low","close"]:
        df[c]=df[c].astype(float)
    return df[::-1]

# Indicators
def enrich(df):
    df["ema50"]=df["close"].ewm(span=50).mean()
    df["ema200"]=df["close"].ewm(span=200).mean()

    delta=df["close"].diff()
    gain=delta.where(delta>0,0)
    loss=-delta.where(delta<0,0)
    rs=gain.rolling(14).mean()/loss.rolling(14).mean()
    df["rsi"]=100-(100/(1+rs))

    df["body"]=abs(df["close"]-df["open"])
    df["body_avg"]=df["body"].rolling(5).mean()

    return df

# Strategy
def signal(symbol):
    if not liquid_session():
        return None

    df=enrich(candles(symbol,INTERVAL))
    htf=enrich(candles(symbol,HTF))

    L=df.iloc[-1]
    H=htf.iloc[-1]

    trend_up=L["ema50"]>L["ema200"] and H["ema50"]>H["ema200"]
    trend_dn=L["ema50"]<L["ema200"] and H["ema50"]<H["ema200"]

    strong=L["body"]>L["body_avg"]

    # BUY
    if trend_up and 35<L["rsi"]<50 and L["close"]>L["open"] and strong:
        sl=df["low"].tail(4).min()
        risk=L["close"]-sl
        tp1=L["close"]+risk
        tp2=L["close"]+risk*2
        tp3=L["close"]+risk*3
        return ("BUY",L["close"],sl,tp1,tp2,tp3)

    # SELL
    if trend_dn and 50<L["rsi"]<65 and L["close"]<L["open"] and strong:
        sl=df["high"].tail(4).max()
        risk=sl-L["close"]
        tp1=L["close"]-risk
        tp2=L["close"]-risk*2
        tp3=L["close"]-risk*3
        return ("SELL",L["close"],sl,tp1,tp2,tp3)

    return None

# Bot Loop
def run():
    send("🚀 Institutional Grade Bot Started")

    while True:
        try:
            for s in SYMBOLS:
                sig=signal(s)
                if sig:
                    if last_signals.get(s)==sig[0]:
                        continue

                    last_signals[s]=sig[0]

                    side,e,sl,t1,t2,t3=sig
                    msg=f"""
📊 {s}
🔥 {side}

Entry {round(e,2)}
TP1 {round(t1,2)}
TP2 {round(t2,2)}
TP3 {round(t3,2)}
SL {round(sl,2)}
"""
                    send(msg)
                    time.sleep(4)

            time.sleep(900)

        except Exception as ex:
            send(f"⚠ {ex}")
            time.sleep(120)

@app.route("/")
def home():
    return "Running"

if __name__=="__main__":
    Thread(target=run).start()
    app.run(host="0.0.0.0",port=10000)
