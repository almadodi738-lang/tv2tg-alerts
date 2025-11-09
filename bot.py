import os
import json
import requests
from flask import Flask, request, jsonify, abort

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
SHARED_SECRET = os.getenv("SHARED_SECRET", "").strip()
TZ = os.getenv("TZ", "Asia/Riyadh")

API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage" if TELEGRAM_TOKEN else None

def send_telegram(text: str) -> dict:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return {"ok": False, "error": "Missing TELEGRAM_TOKEN or TELEGRAM_CHAT_ID"}
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    r = requests.post(API_URL, json=payload, timeout=20)
    try:
        data = r.json()
    except Exception:
        data = {"ok": False, "status_code": r.status_code, "text": r.text}
    return data

@app.get("/healthz")
def healthz():
    return "ok", 200

@app.get("/ping")
def ping():
    return jsonify({"ok": True, "msg": "pong"}), 200

@app.get("/test")
def test_get():
    secret = request.args.get("secret", "")
    if SHARED_SECRET and secret != SHARED_SECRET:
        return "Unauthorized", 403
    msg = request.args.get("msg", "Test message sent to Telegram!")
    res = send_telegram(f"🛠️ Test: {msg}")
    code = 200 if res.get("ok") else 500
    return jsonify(res), code

@app.post("/hook")
def hook():
    secret = request.args.get("secret", "")
    if SHARED_SECRET and secret != SHARED_SECRET:
        return "Method Not Allowed", 405

    try:
        data = request.get_json(force=True, silent=False)
    except Exception:
        abort(400, description="Invalid JSON")

    symbol = str(data.get("symbol", "N/A"))
    side = str(data.get("side", "N/A")).lower()
    entry = str(data.get("entry", "—"))
    sl = str(data.get("sl", "—"))
    tp1 = str(data.get("tp1", "—"))
    tp2 = str(data.get("tp2", "—"))
    risk = str(data.get("risk_usd", "—"))
    pos = str(data.get("position_units", "—"))

    arrow = "🟢 شراء" if side == "buy" else ("🔴 بيع" if side == "sell" else "ℹ️ تنبيه")
    text = (
        f"{arrow} | <b>{symbol}</b>\n"
        f"دخول: <b>{entry}</b>\n"
        f"وقف خسارة: <b>{sl}</b>\n"
        f"TP1: <b>{tp1}</b> | TP2: <b>{tp2}</b>\n"
        f"مخاطرة بالدولار: <b>{risk}</b>\n"
        f"حجم العقد: <b>{pos}</b>\n"
        f"⏱ المنطقة الزمنية: {TZ}"
    )

    res = send_telegram(text)
    code = 200 if res.get("ok") else 500
    return jsonify(res), code

@app.get("/hook")
def hook_get():
    return "Method Not Allowed", 405

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")), debug=False)
