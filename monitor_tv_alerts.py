import os
import time
import requests
import pandas as pd
from flask import Flask
from threading import Thread
from datetime import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
TD_KEY = os.getenv("DATA_API_KEY")
FH_KEY = os.getenv("FINNHUB_KEY")

SYMBOLS = ["XAU/USD","BINANCE:BTCUSDT","BINANCE:ETHUSDT"]

app = Flask(__name__)
last_signal={}

# Telegram
def send(msg):
    url=f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url,data={"chat_id":CHAT_ID,"text":msg})

# Session filter
def liquid():
    h=datetime.utcnow().hour
    return (7<=h<=16) or (12<=h<=21)

# ===== GOLD (TwelveData) =====
def gold_candles(interval):
    url="https://api.twelvedata.com/time_series"
    r=requests.get(url,params={
        "symbol":"XAU/USD",
        "interval":interval,
        "apikey":TD_KEY,
        "outputsize":200
    }).json()
    if "values" not in r:
        raise Exception(r)
    df=pd.DataFrame(r["values"])
    for c in ["open","high","low","close"]:
        df[c]=df[c].astype(float)
    return df[::-1]

# ===== CRYPTO (Finnhub) =====
def crypto_price(symbol):
    sym=symbol.replace("BINANCE:","")
    url=f"https://finnhub.io/api/v1/quote?symbol=BINANCE:{sym}&token={FH_KEY}"
    r=requests.get(url).json()
    return float(r["c"])

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
    df["avg"]=df["body"].rolling(5).mean()
    return df

# Strategy GOLD
def analyze_gold():
    if not liquid():
        return None

    df=enrich(gold_candles("15min"))
    htf=enrich(gold_candles("1h"))

    L=df.iloc[-1]
    H=htf.iloc[-1]

    up=L["ema50"]>L["ema200"] and H["ema50"]>H["ema200"]
    dn=L["ema50"]<L["ema200"] and H["ema50"]<H["ema200"]
    strong=L["body"]>L["avg"]

    if up and 35<L["rsi"]<50 and L["close"]>L["open"] and strong:
        sl=df["low"].tail(4).min()
        r=L["close"]-sl
        return ("XAU/USD","BUY",L["close"],sl,L["close"]+r,L["close"]+2*r,L["close"]+3*r)

    if dn and 50<L["rsi"]<65 and L["close"]<L["open"] and strong:
        sl=df["high"].tail(4).max()
        r=sl-L["close"]
        return ("XAU/USD","SELL",L["close"],sl,L["close"]-r,L["close"]-2*r,L["close"]-3*r)

    return None

# Strategy CRYPTO (Lightweight)
def analyze_crypto(sym):
    price=crypto_price(sym)

    # فلترة بسيطة اتجاه
    if price is None:
        return None

    # pseudo TP/SL
    sl=price*0.992
    tp1=price*1.005
    tp2=price*1.01
    tp3=price*1.02

    return (sym,"SCAN",price,sl,tp1,tp2,tp3)

# Loop
def run():
    send("🚀 Hybrid PRO Bot Started")

    while True:
        try:
            g=analyze_gold()
            if g:
                s,e,entry,sl,t1,t2,t3=g
                if last_signal.get(s)!=e:
                    last_signal[s]=e
                    send(f"""
📊 {s}
🔥 {e}

Entry {round(entry,2)}
TP1 {round(t1,2)}
TP2 {round(t2,2)}
TP3 {round(t3,2)}
SL {round(sl,2)}
""")

            for c in SYMBOLS[1:]:
                res=analyze_crypto(c)
                if res:
                    s,e,entry,sl,t1,t2,t3=res
                    send(f"""
🪙 {s}
Price {round(entry,2)}
TP1 {round(t1,2)}
TP2 {round(t2,2)}
TP3 {round(t3,2)}
""")

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
