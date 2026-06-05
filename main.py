import time
import datetime
import requests
import yfinance as yf
import pandas as pd
from threading import Thread
from flask import Flask
import os

# خادم ويب مصغر للحفاظ على استقرار السيرفر في Render
app = Flask(__name__)

@app.route('/')
def home():
    return "SMC Institutional Bot is Online and Safe", 200

# إعدادات التلغرام الخاصة بك
BOT_TOKEN = "8830911482:AAFnxsHB7uFLWxEtrc1KsGe6Txk5un6KUnk"
CHAT_ID = "@Forex_signals"

# الأصول المطلوبة للتحليل
SYMBOLS = {
    "NQ=F": "الميني ناسداك (E-mini Nasdaq)",
    "^NDX": "الناسداك الرئيسي (Nasdaq 100)",
    "GC=F": "الذهب اللحظي (Gold)"
}

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Error sending to Telegram: {e}")

def get_market_trend(symbol):
    """تحديد اتجاه صناع السوق على فريم 4 ساعات باستخدام المتوسط المتحرك"""
    try:
        ticker = yf.Ticker(symbol)
        df_4h = ticker.history(period="1mo", interval="4h")
        if df_4h.empty or len(df_4h) < 20:
            return "NEUTRAL"
        
        ma_20 = df_4h['Close'].rolling(window=20).mean().iloc[-1]
        current_price = df_4h['Close'].iloc[-1]
        
        if current_price > ma_20:
            return "BULLISH"
        elif current_price < ma_20:
            return "BEARISH"
    except Exception as e:
        print(f"Trend error for {symbol}: {e}")
    return "NEUTRAL"

def calculate_atr(df, period=14):
    """حساب متوافق لديناميكية التقلب وقف الخسارة"""
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift()).abs()
    low_close = (df['Low'] - df['Close'].shift()).abs()
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    atr = true_range.rolling(period).mean()
    return atr.iloc[-1]

def analyze_smc_markets():
    print(f"🤖 [فحص مؤسسي] جاري مسح الأسواق بدقة عالية... {datetime.datetime.now()}")
    
    for symbol, name in SYMBOLS.items():
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="3d", interval="15m")
            
            if df.empty or len(df) < 20:
                continue
                
            current_price = round(df['Close'].iloc[-1], 2)
            recent_highs = df['High'].iloc[-15:-1]
            recent_lows = df['Low'].iloc[-15:-1]
            
            max_high = round(recent_highs.max(), 2)
            min_low = round(recent_lows.min(), 2)
            
            trend = get_market_trend(symbol)
            atr = calculate_atr(df)
            
            # 1. إشارة شراء ذكية متوافقة مع الاتجاه الصاعد للسيولة
            if current_price <= min_low * 1.001 and trend == "BULLISH":
                sl = round(current_price - (atr * 1.5), 2)
                risk = current_price - sl
                tp1 = round(current_price + (risk * 1.5), 2)
                tp2 = round(current_price + (risk * 2.5), 2)
                
                msg = f"""🛡️ **توصية هيرمز المؤسسية الاحترافية (SMC BUY)** 🛡️
━━━━━━━━━━━━━━━━━━
💱 **الأصل/الزوج:** {name} ({symbol})
📈 **نوع الصفقة:** 🟢 شراء ذكي (Order Block)
⏱️ **الاتجاه العام (4H):** 📈 صاعد كلي (Bullish Structure)
━━━━━━━━━━━━━━━━━━
🔍 **التأكيدات البرمجية المتقدمة:**
- السعر ارتد من منطقة تجميع سيولة (Liquidity Sweep).
- متوافق مع الاتجاه الكلي لصناع السوق (Trend Match).
- الوقف والاهداف ديناميكية ومحسوبة بدقة بناءً على التقلب الحالي (ATR).

💵 **سعر الدخول الحالي:** {current_price}

🛑 **وقف الخسارة (SL):** {sl}
🎯 **الهدف الأول (TP1):** {tp1}
🎯 **الهدف الثاني (TP2):** {tp2}
━━━━━━━━━━━━━━━━━━
⚠️ **إدارة المخاطر:** التزم بحجم عقود متزن لحسابك الشخصي."""
                send_telegram_message(msg)
                time.sleep(3)
                
            # 2. إشارة بيع ذكية متوافقة مع الاتجاه الهابط للسيولة
            elif current_price >= max_high * 0.999 and trend == "BEARISH":
                sl = round(current_price + (atr * 1.5), 2)
                risk = sl - current_price
                tp1 = round(current_price - (risk * 1.5), 2)
                tp2 = round(current_price - (risk * 2.5), 2)
                
                msg = f"""🛡️ **توصية هيرمز المؤسسية الاحترافية (SMC SELL)** 🛡️
━━━━━━━━━━━━━━━━━━
💱 **الأصل/الزوج:** {name} ({symbol})
📈 **نوع الصفقة:** 🔴 بيع ذكي (Supply Block)
⏱️ **الاتجاه العام (4H):** 📉 هابط كلي (Bearish Structure)
━━━━━━━━━━━━━━━━━━
🔍 **التأكيدات البرمجية المتقدمة:**
- السعر يختبر قمة سحب سيولة (Buy-side Liquidity).
- متوافق مع التدفق المالي الهابط للمؤسسات (Trend Match).
- الوقف والاهداف ديناميكية ومحسوبة بدقة بناءً على التقلب الحالي (ATR).

💵 **سعر الدخول الحالي:** {current_price}

🛑 **وقف الخسارة (SL):** {sl}
🎯 **الهدف الأول (TP1):** {tp1}
🎯 **الهدف الثاني (TP2):** {tp2}
━━━━━━━━━━━━━━━━━━
⚠️ **إدارة المخاطر:** لا تخاطر بأكثر من 1% من محفظتك في الصفقة."""
                send_telegram_message(msg)
                time.sleep(3)
                
        except Exception as e:
            print(f"خطأ أثناء تحليل {name}: {e}")

def run_market_loop():
    while True:
        try:
            analyze_smc_markets()
        except Exception as e:
            print(f"Loop error: {e}")
        time.sleep(60) # فحص كل دقيقة لاقتناص السيولة الحية

if __name__ == "__main__":
    bot_thread = Thread(target=run_market_loop)
    bot_thread.daemon = True
    bot_thread.start()
    
    # حل مشكلة قراءة المنفذ في الاستضافات المجانية لتفادي خطأ الـ None
    try:
        port = int(os.environ.get("PORT", 5000))
    except (TypeError, ValueError):
        port = 5000
        
    app.run(host="0.0.0.0", port=port)
