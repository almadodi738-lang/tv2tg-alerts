import os, json, requests
from flask import Flask, request, jsonify, abort

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
SHARED_SECRET = os.environ.get("SHARED_SECRET", "Admin@1716")

def send_telegram(text: str) -> bool:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
    r = requests.post(url, json=payload, timeout=15)
    return r.ok

@app.get("/")
def home():
    return "OK", 200

@app.get("/healthz")
def healthz():
    return jsonify(ok=True), 200

@app.get("/ping")
def ping():
    return "pong", 200

# /test?secret=...&msg=...
@app.get("/test")
def test():
    secret = request.args.get("secret", "")
    if secret != SHARED_SECRET:
        abort(403)
    msg = request.args.get("msg", "Test")
    ok = send_telegram(f"✅ Test: {msg}")
    return jsonify(sent=ok), 200 if ok else 500

# TradingView Webhook (POST JSON)
@app.post("/hook")
def hook():
    # تحقق من السر داخل الهيدر أو الكويري
    secret = request.args.get("secret") or request.headers.get("X-Webhook-Secret", "")
    if secret != SHARED_SECRET:
        abort(403)

    data = request.get_json(force=True, silent=True) or {}
    # فقط نمرر المحتوى كما هو إلى تيليجرام (للتحقق المبدئي)
    pretty = "<pre>" + (json.dumps(data, ensure_ascii=False, indent=2)) + "</pre>"
    ok = send_telegram(f"📥 Webhook:\n{pretty}")
    return jsonify(ok=ok), 200 if ok else 500
