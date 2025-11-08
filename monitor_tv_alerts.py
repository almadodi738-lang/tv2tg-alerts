import os, json, requests
from flask import Flask, request, jsonify

TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
SHARED_SECRET    = os.getenv("SHARED_SECRET", "Admin@1716")

app = Flask(__name__)

def tg(text: str) -> bool:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram creds missing")
        return False
    try:
        url  = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
        r = requests.post(url, data=data, timeout=10)
        if not r.ok: print("TG send error:", r.text)
        return r.ok
    except Exception as e:
        print("TG exception:", e)
        return False

@app.get("/")
def root():
    return "OK", 200

@app.get("/ping")
def ping():
    return "pong", 200

@app.get("/test")
def test():
    ok = tg("✅ Test from Render: bot is connected.")
    return ("sent" if ok else "failed"), 200 if ok else 500

def authorized(req) -> bool:
    sec = req.args.get("secret")
    if not sec:
        try:
            body = req.get_json(silent=True) or {}
            sec = body.get("secret")
        except Exception:
            sec = None
    return sec == SHARED_SECRET

@app.post("/hook")
def hook():
    if not authorized(request):
        return "Unauthorized", 403

    payload = request.get_json(silent=True) or {}
    sym   = payload.get("symbol", "UNKNOWN")
    act   = (payload.get("action") or "").upper()
    entry = payload.get("entry")
    sl    = payload.get("sl")
    tp1   = payload.get("tp1")
    tp2   = payload.get("tp2")
    prob  = payload.get("setup_prob")
    loss  = payload.get("loss_pct")

    msgs = []
    if loss is not None and float(loss) <= -3:
        msgs.append("⚠️ قف التداول الآن – وصلت حد الخسارة اليومية")
    if prob is not None and float(prob) >= 0.80:
        size_line = ""
        if entry is not None and sl is not None:
            try:
                risk_usd   = 2.0  # 1% من 200$
                stop_dist  = abs(float(entry) - float(sl))
                if stop_dist > 0:
                    size = risk_usd / stop_dist
                    size_line = f"\nحجم العقد التقريبي: {size:.3f} وحدة (مخاطرة 1%)"
            except Exception:
                pass
        msgs.append(
            f"✅ ادخل الآن – فرصة قوية للربح\n{sym} {act}\n"
            f"Entry: {entry}\nSL: {sl}\nTP1: {tp1}\nTP2: {tp2}{size_line}"
        )
    if not msgs:
        msgs.append(f"📩 تنبيه وصل: {json.dumps(payload, ensure_ascii=False)}")

    for m in msgs: tg(m)
    return jsonify({"ok": True})
