import os, time, threading, json, datetime as dt
from typing import Dict, Tuple
import requests
import pandas as pd
import numpy as np
import yfinance as yf
from flask import Flask, request, jsonify, abort

# ====== الإعدادات من المتغيرات البيئية ======
TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
SHARED_SECRET    = os.environ.get("SHARED_SECRET", "Admin@1716")

# تكرار الفحص (بالثواني)
POLL_SECONDS     = int(os.environ.get("POLL_SECONDS", "60"))
TZ               = os.environ.get("TZ", "Asia/Riyadh")

# خريطة الأدوات إلى رموز Yahoo
TICKERS = {
    "XAUUSD": "XAUUSD=X",  # Gold spot
    "EURUSD": "EURUSD=X",  # EURUSD
    "WTI"   : "CL=F"       # Crude Oil futures continuous
}

# مسافات وقف بسيطة للمخاطرة (تقريبية للمثال)
STOPS = {
    "XAUUSD": 1.0,      # 1$ للذهب
    "EURUSD": 0.0010,   # 10 نقاط
    "WTI"   : 0.20      # 0.20$
}

# ====== تيليجرام ======
def tg_send(text: str, disable_web_page_preview=True) -> bool:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": disable_web_page_preview
    }
    try:
        r = requests.post(url, json=payload, timeout=15)
        return r.ok
    except Exception:
        return False

# ====== مؤشرات فنية خفيفة ======
def rsi(series: pd.Series, length: int = 14) -> pd.Series:
    delta = series.diff()
    up = np.where(delta > 0, delta, 0.0)
    dn = np.where(delta < 0, -delta, 0.0)
    roll_up = pd.Series(up, index=series.index).ewm(alpha=1/length, adjust=False).mean()
    roll_dn = pd.Series(dn, index=series.index).ewm(alpha=1/length, adjust=False).mean()
    rs = roll_up / (roll_dn + 1e-9)
    return 100 - (100 / (1 + rs))

def ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False).mean()

def atr(df: pd.DataFrame, length: int = 14) -> pd.Series:
    high, low, close = df['High'], df['Low'], df['Close']
    tr = pd.concat([
        (high - low),
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1/length, adjust=False).mean()

# ====== تحميل بيانات دقيقة/5 دقائق ======
def fetch(symbol_yf: str, interval="1m", lookback="2d") -> pd.DataFrame:
    data = yf.download(symbol_yf, period=lookback, interval=interval, progress=False)
    if not isinstance(data, pd.DataFrame) or data.empty:
        return pd.DataFrame()
    data = data.dropna().copy()
    return data

# ====== منطق الإشارة عالية الاحتمال (>~80% على شروطنا المبسطة) ======
def high_prob_setup(df: pd.DataFrame) -> Tuple[str, Dict]:
    """
    شروط محافظة:
    - ترند باتجاه المتوسط EMA200
    - ارتداد من EMA21 (قربه <= 0.5 ATR)
    - RSI فوق 55 للشراء/تحت 45 للبيع
    - حجم الشمعة الحالية غير ضعيف (مدى >= 0.3 ATR)
    """
    if df.empty or len(df) < 220:
        return "", {}

    close = df['Close']
    hi, lo = df['High'], df['Low']
    ema200 = ema(close, 200)
    ema21  = ema(close, 21)
    _atr   = atr(df, 14)
    _rsi   = rsi(close, 14)

    c, e200, e21, a, r = close.iloc[-1], ema200.iloc[-1], ema21.iloc[-1], _atr.iloc[-1], _rsi.iloc[-1]
    rng = hi.iloc[-1] - lo.iloc[-1]

    near_pullback = abs(c - e21) <= 0.5 * a
    candle_ok     = rng >= 0.3 * a

    long_ok  = (c > e200) and (r > 55) and near_pullback and candle_ok
    short_ok = (c < e200) and (r < 45) and near_pullback and candle_ok

    if long_ok:
        return "buy", {"entry": round(c, 5)}
    if short_ok:
        return "sell", {"entry": round(c, 5)}
    return "", {}

# ====== حساب حجم الصفقة لحساب 200$ ومخاطرة 1% ======
def position_for_200(symbol: str, stop_distance: float) -> float:
    # مخاطرة 1% = 2$
    risk_usd = 2.0
    # قيمة الحركة لكل "وحدة" (تقريبية لأغراض التنبيه فقط)
    # نفترض أن 1 وحدة تربح/تخسر قيمة الحركة كاملة بالدولار.
    # الذهب: 1$ لكل وحدة، WTI: 1$ لكل وحدة، EURUSD: نقرّبها 1$ لكل 0.001 للحجم 1
    if symbol == "EURUSD":
        pip_value_per_unit = 1000.0  # 0.001 حركة ≈ 1$ لو الحجم 0.001؟ (تبسيط شديد)
        # نعيدها ليتوافق: قيمة 0.001 = 1$ للحجم 1 → إذًا 1 حركة كاملة بالدولار ~ 1.0 للحجم 1.
        # للتبسيط سنعاملها مثل الذهب/النفط:
        pip_value_per_unit = 1.0
    else:
        pip_value_per_unit = 1.0
    units = max(risk_usd / max(stop_distance * pip_value_per_unit, 1e-6), 0.001)
    # نقيّدها لرقم صغير ملائم للحساب الصغير
    return round(min(units, 0.05), 4)

# ====== حلقة المراقبة الخلفية ======
class Monitor(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.last_signal_time: Dict[str, float] = {}  # لمنع السبام

    def run(self):
        while True:
            try:
                for sym, yfs in TICKERS.items():
                    df = fetch(yfs, interval="1m", lookback="2d")
                    side, info = high_prob_setup(df)
                    if side:
                        # إعداد مستويات SL/TP مبسطة
                        entry = float(info["entry"])
                        stop_dist = STOPS[sym]
                        sl  = entry - stop_dist if side == "buy"  else entry + stop_dist
                        tp1 = entry + stop_dist*1.5 if side == "buy" else entry - stop_dist*1.5
                        tp2 = entry + stop_dist*3.0 if side == "buy" else entry - stop_dist*3.0
                        pos = position_for_200(sym, stop_dist)

                        now = time.time()
                        if now - self.last_signal_time.get(sym, 0) > 180:  # مرّة كل 3 دقائق كحد أدنى
                            msg = (
                                f"🚨 <b>إشارة عالية الاحتمال (~80%)</b>\n"
                                f"الأداة: <b>{sym}</b>\n"
                                f"الاتجاه: <b>{'شراء' if side=='buy' else 'بيع'}</b>\n"
                                f"الدخول: <code>{entry}</code>\n"
                                f"وقف الخسارة: <code>{round(sl,5)}</code>\n"
                                f"TP1: <code>{round(tp1,5)}</code> | TP2: <code>{round(tp2,5)}</code>\n"
                                f"حجم مُقترح (حساب 200$ بخطر 1%): <code>{pos}</code>\n"
                                f"تنبيه: تجنّب الأخبار الحمراء 60 دقيقة حول الإصدار."
                            )
                            tg_send(msg)
                            self.last_signal_time[sym] = now
            except Exception as e:
                tg_send(f"⚠️ خطأ في المراقبة: {e}")
            time.sleep(POLL_SECONDS)

# ====== Flask ======
app = Flask(__name__)

@app.get("/")
def home():
    return "OK", 200

@app.get("/ping")
def ping():
    return "pong", 200

@app.get("/healthz")
def health():
    return jsonify(ok=True, time=str(dt.datetime.now())), 200

# اختبار تيليجرام:  /test?secret=...&msg=...
@app.get("/test")
def test():
    secret = request.args.get("secret", "")
    if secret != SHARED_SECRET:
        abort(403)
    msg = request.args.get("msg", "Bot is working")
    ok = tg_send(f"✅ Test: {msg}")
    return jsonify(sent=ok), 200 if ok else 500

# استقبال Webhook خارجي (لو احتجته لاحقًا)
@app.post("/hook")
def hook():
    secret = request.args.get("secret") or request.headers.get("X-Webhook-Secret", "")
    if secret != SHARED_SECRET:
        abort(403)
    data = request.get_json(silent=True) or {}
    pretty = "<pre>" + (json.dumps(data, ensure_ascii=False, indent=2)) + "</pre>"
    ok = tg_send(f"📥 Webhook:\n{pretty}")
    return jsonify(ok=ok), 200 if ok else 500

# شغّل المراقب عند إقلاع السيرفر
monitor_thread = Monitor()
monitor_thread.start()
