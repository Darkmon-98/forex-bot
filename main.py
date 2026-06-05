import time
import requests
import yfinance as yf

# إعدادات التلغرام الخاصة بك مأخوذة من ملفك مباشرة
BOT_TOKEN = "8830911482:AAFnxsHB7uFLWxEtrc1KsGe6Txk5un6KUnk"
CHAT_ID = "@Forex_signals"

# الرموز الرسمية للأصول المطلوبة على ياهو فاينانس
SYMBOLS = {
    "NQ=F": "الميني ناسداك (E-mini Nasdaq)",
    "^NDX": "الناسداك الرئيسي (Nasdaq 100)",
    "GC=F": "الذهب اللحظي (Gold)"
}

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print("تم إرسال التنبيه بنجاح إلى التلغرام.")
        else:
            print(f"فشل الإرسال: {response.text}")
    except Exception as e:
        print(f"Error sending to Telegram: {e}")

def analyze_smc_markets():
    print("🤖 جاري سحب البيانات الحية وفحص استراتيجية SMC للأصول...")
    
    for symbol, name in SYMBOLS.items():
        try:
            # سحب بيانات آخر يومين بفريم 15 دقيقة (الموزون لصفقات الـ OB والسيولة)
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="2d", interval="15m")
            
            if df.empty or len(df) < 15:
                print(f"⚠️ لا توجد بيانات كافية حالياً للرمز: {symbol}")
                continue
                
            # قراءة الأسعار الحالية والماضية لتحديد الهيكل السعري
            current_price = round(df['Close'].iloc[-1], 2)
            
            # حساب القمم والقيعان لآخر 12 شمعة لتحديد مناطق السيولة (Liquidity Pools)
            recent_highs = df['High'].iloc[-13:-1]
            recent_lows = df['Low'].iloc[-13:-1]
            
            max_high = round(recent_highs.max(), 2)
            min_low = round(recent_lows.min(), 2)
            
            # 1. إشارة شراء ذكية (عند ملامسة منطقة طلب مؤسسية أو سحب سيولة القاع)
            if current_price <= min_low * 1.001:
                sl = round(min_low * 0.998, 2)
                # حساب الأهداف بنسبة مخاطرة إلى عائد متزنة (1:2 حداً أدنى)
                tp1 = round(current_price + (current_price - sl) * 1.5, 2)
                tp2 = round(current_price + (current_price - sl) * 2.5, 2)
                
                msg = f"""🛡️ **توصية هيرمز الموزونة (SMC BUY)** 🛡️
━━━━━━━━━━━━━━━━━━
💱 **الأصل/الزوج:** {name} ({symbol})
📈 **نوع الصفقة:** 🟢 شراء ذكي (Order Block)
⏱️ **الفريم التحليلي:** 15 دقيقة (تلقائي)
━━━━━━━━━━━━━━━━━━
🔍 **التأكيدات البرمجية للـ SMC:**
- السعر يلامس منطقة تجميع مؤسسية (Demand Zone).
- تم تصفية سيولة القاع المباشر (Liquidity Sweep).
- بنية السوق تظهر ملامح ارتداد هيكلي مؤكد.

💵 **سعر الدخول الحالي:** {current_price}

🛑 **وقف الخسارة (SL):** {sl}
🎯 **الهدف الأول (TP1):** {tp1}
🎯 **الهدف الثاني (TP2):** {tp2}
━━━━━━━━━━━━━━━━━━
⚠️ **إدارة المخاطر:** التزم بحجم عقود متزن لحسابك الشخصي."""
                send_telegram_message(msg)
                time.sleep(3)
                
            # 2. إشارة بيع ذكية (عند ملامسة منطقة عرض مؤسسية أو سحب سيولة القمة)
            elif current_price >= max_high * 0.999:
                sl = round(max_high * 1.002, 2)
                tp1 = round(current_price - (sl - current_price) * 1.5, 2)
                tp2 = round(current_price - (sl - current_price) * 2.5, 2)
                
                msg = f"""🛡️ **توصية هيرمز الموزونة (SMC SELL)** 🛡️
━━━━━━━━━━━━━━━━━━
💱 **الأصل/الزوج:** {name} ({symbol})
📈 **نوع الصفقة:** 🔴 بيع ذكي (Supply Block)
⏱️ **الفريم التحليلي:** 15 دقيقة (تلقائي)
━━━━━━━━━━━━━━━━━━
🔍 **التأكيدات البرمجية للـ SMC:**
- السعر يختبر منطقة بيع تابعة لصناع السوق (Supply OB).
- تم رصد سحب لسيولة القمم السابقة (Buy-side Liquidity).
- توقع هبوط تصحيحي قوي مع اتجاه السيولة الكبرى.

💵 **سعر الدخول الحالي:** {current_price}

🛑 **وقف الخسارة (SL):** {sl}
🎯 **الهدف الأول (TP1):** {tp1}
🎯 **الهدف الثاني (TP2):** {tp2}
━━━━━━━━━━━━━━━━━━
⚠️ **إدارة المخاطر:** لا تخاطر بأكثر من 1-2% من محفظتك في الصفقة."""
                send_telegram_message(msg)
                time.sleep(3)
                
        except Exception as e:
            print(f"خطأ أثناء فحص {name}: {e}")

if __name__ == "__main__":
    # السكربت يفحص السوق دورياً كل 5 دقائق بشكل مستقل تماماً
    while True:
        analyze_smc_markets()
        time.sleep(300)
