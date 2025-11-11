import os, math, time, logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Tuple
import yfinance as yf
from flask import Flask, request, jsonify
import requests

# ===== إعدادات عامة =====
KSA_TZ = timezone(timedelta(hours=3))

TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
SHARED_SECRET    = os.getenv("SHARED_SECRET", "Admin@1716")
ACCOUNT_BALANCE  = float(os.getenv("ACCOUNT_BALANCE", "200"))
RISK_PCT         = float(os.getenv("RISK_PCT", "1"))         # 1% إفتراضي
DAILY_LOSS_LIM   = float(os.getenv("DAILY_LOSS_LIMIT_PCT","3"))  # 3% إفتراضي

# رموز ياهو الصحيحة (مهم)
SYMBOLS = {
    "XAUUSD": "XAUUSD=X",   # ذهب
    "EURUSD": "EURUSD=X",   # يورو/دولار
    "WTI":    "CL=F"        # خام تكساس (فيوتشرز مستمر)
}

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# حالة اليوم (PnL)
STATE = {"date": None, "pnl": 0.0, "wins": 0, "losses": 0, "trades": 0}

# ===== أدوات مساعدة =====
def now_ksa():
    return datetime.now(KSA_TZ)

def tg_send(msg: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        app.logger.warning("❌ TELEGRAM_TOKEN/CHAT_ID مفقود")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=10)
        app.logger.info("Telegram: %s - %s", r.status_code, r.text)
        return r.ok
    except Exception as e:
        app.logger.exception("Telegram error: %s", e)
        return False

def reset_state_if_newday():
    d = now_ksa().date()
    if STATE["date"] != d:
        STATE.update({"date": d, "pnl": 0.0, "wins": 0, "losses": 0, "trades": 0})

def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def rsi(series, length=14):
    delta = series.diff()
    up = (delta.clip(lower=0)).ewm(alpha=1/length, adjust=False).mean()
    down = (-delta.clip(upper=0)).ewm(alpha=1/length, adjust=False).mean()
    rs = up / (down + 1e-9)
    return 100 - (100 / (1 + rs))

def atr(df, length=14):
    h, l, c = df["High"], df["Low"], df["Close"]
    prev_close = c.shift(1)
    tr = (h - l).abs().combine((h - prev_close).abs(), max).combine((l - prev_close).abs(), max)
    return tr.rolling(length).mean()

def fetch(symbol: str, minutes: int = 1440):
    # 1d = 1 minute data for last ~ day; نستخدم 5 دقائق لتقليل الضغط
    df = yf.download(symbol, period="2d", interval="5m", progress=False)
    if df is None or df.empty:
        raise RuntimeError(f"No data for {symbol}")
    return df.dropna().copy()

def position_units(sl_distance: float, symbol: str) -> float:
    """حساب حجم العقد على أساس المخاطرة بالدولار / مسافة وقف الخسارة.
       هذا حساب تقريبي للوحدات (CFD units)."""
    risk_usd = ACCOUNT_BALANCE * (RISK_PCT/100.0)
    if sl_distance <= 0:
        return 0.0
    units = risk_usd / sl_distance
    # قيد بسيط لكل أداة
    min_unit = 0.01 if symbol in ("XAUUSD", "WTI") else 100.0  # EURUSD وحدات أكبر
    return round(max(units, min_unit), 2)

def make_signal(df, name: str) -> Dict:
    """مزيج: اتجاه EMA21/EMA50 + RSI + مناطق دعم/مقاومة + ATR"""
    df["EMA21"] = ema(df["Close"], 21)
    df["EMA50"] = ema(df["Close"], 50)
    df["RSI"]   = rsi(df["Close"], 14)
    df["ATR"]   = atr(df, 14)

    last = df.iloc[-1]
    price = float(last["Close"])
    ema21 = float(last["EMA21"]); ema50 = float(last["EMA50"])
    rsi_v = float(last["RSI"]);   atr_v = max(float(last["ATR"]), 1e-6)

    # دعم/مقاومة بسيطة = قيعان/قمم آخر 1-2 جلسة
    sup = float(df["Low"].tail(60).min())
    res = float(df["High"].tail(60).max())

    bias = "neutral"
    if ema21 > ema50 and rsi_v > 52: bias = "bull"
    if ema21 < ema50 and rsi_v < 48: bias = "bear"

    # قواعد دخول/خروج
    setup = "none"
    entry = sl = tp1 = tp2 = invalidation = 0.0

    rr1 = 1.0; rr2 = 2.0   # 1R و 2R
    sl_dist = max(atr_v * 0.8, price*0.0005)  # مرن

    if bias == "bull" and price > ema21 and rsi_v >= 50:
        setup = "buy"
        entry = price
        sl = price - sl_dist
        tp1 = price + sl_dist*rr1
        tp2 = price + sl_dist*rr2
        invalidation = ema50
    elif bias == "bear" and price < ema21 and rsi_v <= 50:
        setup = "sell"
        entry = price
        sl = price + sl_dist
        tp1 = price - sl_dist*rr1
        tp2 = price - sl_dist*rr2
        invalidation = ema50

    units = position_units(abs(entry - sl), name)
    return {
        "symbol": name,
        "price": round(price, 4),
        "bias": bias,
        "setup": setup,
        "entry": round(entry, 4),
        "sl": round(sl, 4),
        "tp1": round(tp1, 4),
        "tp2": round(tp2, 4),
        "invalid": round(invalidation, 4),
        "atr": round(atr_v, 5),
        "support": round(sup, 4),
        "resist": round(res, 4),
        "units": units
    }

def news_box() -> str:
    # بدون مصادر مدفوعة/تصفح: تنبيه ثابت كفلتر مخاطرة
    return "⚠️ تذكير: تجنّب التداول قبل/بعد الأخبار الحمراء بـ 30–60 دقيقة."

def format_alert(s: Dict) -> str:
    if s["setup"] == "none":
        return f"🔎 {s['symbol']}: لا توجد فرصة واضحة الآن. (تحيز: {s['bias']})\n{news_box()}"
    side = "شراء" if s["setup"] == "buy" else "بيع"
    risk_usd = ACCOUNT_BALANCE*(RISK_PCT/100)
    return (
        f"ادخل الآن – فرصة قوية للربح\n"
        f"{s['symbol']} {side}\n"
        f"Entry: {s['entry']} | SL: {s['sl']} | TP1: {s['tp1']} | TP2: {s['tp2']}\n"
        f"Invalidation: {s['invalid']} | ATR: {s['atr']}\n"
        f"حجم الصفقة المقترح (حساب 200$ خطورة {RISK_PCT}%): {s['units']} وحدة (~{round(risk_usd,2)}$ مخاطرة)\n"
        f"مستويات: دعم {s['support']} / مقاومة {s['resist']}\n"
        f"{news_box()}"
    )

# ===== مسارات الويب =====
@app.get("/")
def root():
    return "✅ Trading helper running"

@app.get("/ping")
def ping():
    reset_state_if_newday()
    return jsonify({
        "status": "ok",
        "time_riyadh": now_ksa().strftime("%Y-%m-%d %H:%M:%S"),
        "state": STATE
    })

@app.get("/analyze")
def analyze():
    """يسحب الأسعار ويحلل XAUUSD/EURUSD/WTI ويرجع توصية مختصرة + يرسل تيليجرام لو لقي فرصة قوية"""
    reset_state_if_newday()
    out = {}
    try:
        for name, ysym in SYMBOLS.items():
            df = fetch(ysym)
            sig = make_signal(df, name)
            out[name] = sig

        # رسالة مختصرة
        lines = []
        for k in ("XAUUSD","EURUSD","WTI"):
            s = out[k]
            line = f"{k}: {s['setup']} @ {s['entry']} SL {s['sl']} TP1 {s['tp1']} TP2 {s['tp2']} (bias {s['bias']})"
            lines.append(line)
        text = "📊 تحليل سريع:\n" + "\n".join(lines) + f"\n{news_box()}"

        # إرسال تنبيه دخول فقط عند وجود setup
        for k in ("XAUUSD","EURUSD","WTI"):
            s = out[k]
            if s["setup"] != "none":
                tg_send(format_alert(s))

        return jsonify({"ok": True, "signals": out, "note": news_box(), "summary": text})
    except Exception as e:
        app.logger.exception("Analyze error: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500

@app.post("/report_fill")
def report_fill():
    """تحديث نتيجة صفقة يدوياً من ThinkTrader:
       body JSON: {"pl": -2.5}  بالدولار
    """
    secret = request.args.get("secret", "")
    if secret != SHARED_SECRET:
        return ("Unauthorized", 403)
    reset_state_if_newday()
    data = request.get_json(silent=True) or {}
    pl = float(data.get("pl", 0))
    STATE["pnl"] += pl
    STATE["trades"] += 1
    if pl >= 0: STATE["wins"] += 1
    else: STATE["losses"] += 1

    # حد الخسارة اليومية
    if (STATE["pnl"] / ACCOUNT_BALANCE) * 100 <= -DAILY_LOSS_LIM:
        tg_send("🚫 قف التداول الآن – وصلت حد الخسارة اليومية")
    return jsonify({"ok": True, "state": STATE})

@app.get("/reset_session")
def reset_session():
    """إعادة ضبط إحصائيات اليوم يدوياً"""
    secret = request.args.get("secret", "")
    if secret != SHARED_SECRET:
        return ("Unauthorized", 403)
    STATE.update({"date": now_ksa().date(), "pnl": 0.0, "wins": 0, "losses": 0, "trades": 0})
    return jsonify({"ok": True, "state": STATE})
@app.route("/test")
def test():
    secret = request.args.get("secret")
    msg = request.args.get("msg", "No message")
    if secret != SHARED_SECRET:
        return jsonify({"status": "error", "message": "Invalid secret"}), 403

    token = TELEGRAM_TOKEN
    chat_id = TELEGRAM_CHAT_ID
    send_url = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.post(send_url, json={"chat_id": chat_id, "text": msg})

    return jsonify({"status": "sent", "message": msg})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
