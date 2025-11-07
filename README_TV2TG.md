# TV -> Telegram Alerts (Arabic)

خادم ويب بسيط يستقبل Webhook من TradingView ويرسل تنبيهات عربية إلى تيليجرام:
- تحذير "قف التداول الآن – وصلت حد الخسارة اليومية" إذا تجاوزت الخسارة اليومية −3%
- تنبيه "ادخل الآن – فرصة قوية للربح" إذا ظهرت إشارة باحتمال > 80% مع Entry/SL/TP1/TP2

## النشر السريع على Render
1) ارفع هذا المجلد لمستودع GitHub جديد.
2) أنشئ خدمة جديدة على render.com من المستودع.
3) أضف المتغيرات التالية من Settings → Environment:
   - TELEGRAM_TOKEN
   - TELEGRAM_CHAT_ID
   - SHARED_SECRET (اختر قيمة قوية)
   - ACCOUNT_BALANCE=200
   - DAILY_LOSS_LIMIT_PCT=3
   - TZ=Asia/Riyadh
4) بعد النشر ستحصل على رابط مثل:
   https://your-service.onrender.com
5) استخدم Webhook URL في TradingView:
   https://your-service.onrender.com/webhook/<SHARED_SECRET>

## أمثلة رسائل TradingView
### خسارة يومية (تراكمي بالدولار)
{
  "symbol": "XAUUSD",
  "realized_pl": -7.5
}

### نسبة مباشرة
{
  "symbol": "EURUSD",
  "pl_pct": -3.2
}

### فرصة عالية الاحتمال
{
  "symbol": "WTI",
  "pattern_winrate": 83,
  "entry": 77.85,
  "sl": 78.25,
  "tp1": 77.20,
  "tp2": 76.60
}

## اختبار يدوي
curl -X POST "https://your-service.onrender.com/webhook/<SHARED_SECRET>"   -H "Content-Type: application/json"   -d '{"symbol":"EURUSD","probability":0.83,"entry":1.0820,"sl":1.0850,"tp1":1.0780,"tp2":1.0740}'

## تشغيل محليًا
pip install -r requirements.txt
set TELEGRAM_TOKEN=...
set TELEGRAM_CHAT_ID=...
set SHARED_SECRET=...
set ACCOUNT_BALANCE=200
set DAILY_LOSS_LIMIT_PCT=3
set TZ=Asia/Riyadh
python monitor_tv_alerts.py
# health check: http://localhost:8000/health
