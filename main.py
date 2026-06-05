import time
import datetime
import requests
import yfinance as yf
import pandas as pd
from bs4 import BeautifulSoup
from threading import Thread
from flask import Flask
import os

# إعداد خادم ويب مصغر لإرضاء منصة Render ليبقى السيرفر يعمل دائماً
app = Flask(__name__)

@app.route('/')
def home():
    return "SMC Forex Bot is Running Successfully!", 200

# إعدادات التلغرام الخاصة بك
BOT_TOKEN = "8830911482:AAFnxsHB7uFLWxEtrc1KsGe6Txk5un6KUnk"
CHAT_ID = "@Forex_signals"

# الأصول المطلوبة
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

def check_us_news_block():
    """فحص الأخبار الاقتصادية الأمريكية عالية الأهمية"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        url = "https://sslecal.forexprostools.com/?columns=currency,importance&importance=3&currencies=5&calType=day&timeZone=8"
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return False
            
        soup = BeautifulSoup(response.text, 'html.parser')
        rows = soup.find_all('tr', class_='js-event-item')
        now = datetime.datetime.now()
        
        for row in rows:
            time_cell = row.find('td', class_='time')
            if not time_cell or ":" not in time_cell.text:
                continue
                
            try:
                hour, minute = map(int, time_cell.text.strip().split(':'))
                news_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                time_diff = (news_time - now).total_seconds() / 60
                
                if -30 <= time_diff <= 30:
                    print(f"⚠️ حظر الأخبار نشط! خبر قوي بعد {round(time_diff)} دقيقة.")
                    return True
            except ValueError:
                continue
    except Exception as e:
        print(f"خطأ فحص الأخبار: {e}")
    return False

def get_market_trend(symbol):
    """تحديد الاتجاه العام على فريم 4 ساعات باستخدام EMA 50"""
    try:
        ticker = yf.Ticker(symbol)
        df_4h = ticker.history(period="1mo", interval="4h")
        if df_4h.empty or len(df_4h) < 50:
            return "NEUTRAL"
        
        ema_50 = df_4h['Close'].ewm(span=50, adjust=False).mean()
        current_price = df_4h['Close'].iloc[-1]
        current_ema = ema_50.iloc[-1]
        
        if current_price > current_ema:
            return "BULLISH"
        elif current_price < current_ema:
            return "BEARISH"
    except Exception as e:
        print(f"خطأ في حساب الاتجاه لـ {symbol}: {e}")
    return "NEUTRAL"

def calculate_atr(df, period=14):
    """حساب مؤشر ATR لتحديد وقف الخسارة الديناميكي"""
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift()).abs()
    low_close = (df['Low'] - df['Close'].shift()).abs()
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    atr = true_range.rolling(period).mean()
    return atr.iloc[-1]

def analyze_smc_markets():
    if check_us_news_block():
        print("⛔ تجميد التحليل الفني مؤقتاً بسبب الأخبار القوية.")
        return

    print("🤖 جاري فحص الأسواق بالمعايير المؤسسية الاحترافية...")
    for symbol, name in SYMBOLS.items():
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="5d", interval="15m")
            
            if df.empty or len(df) < 20:
                continue
                
            current_price = round(df['Close'].iloc[-1], 2)
            recent_highs = df['High'].iloc[-15:-1]
            recent_lows = df['Low'].iloc[-15:-1]
            
            max_high = round(recent_highs.max(), 2)
            min_low = round(recent_lows.min(), 2)
            
            trend = get_market_trend(symbol)
            atr = calculate_atr(df)
            
            # 1. إشارة شراء ذكية
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
- متوافق مع الاتجاه الكلي لصناع السوق (EMA Trend Match).
- الوقف والاهداف ديناميكية ومحسوبة بدقة بناءً على التقلب الحالي (ATR).

💵 **سعر الدخول الحالي:** {current_price}

🛑 **وقف الخسارة (SL):** {sl}
🎯 **الهدف الأول (TP1):** {tp1}
🎯 **الهدف الثاني (TP2):** {tp2}
━━━━━━━━━━━━━━━━━━
⚠️ **إدارة رأس المال:** خاطر بـ 1% فقط من حسابك لكل صفقة."""
                send_telegram_message(msg)
                time.sleep(3)
                
            # 2. إشارة بيع ذكية
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
- متوافق مع التدفق المالي الهابط للمؤسسات (EMA Trend Match).
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
    """حلقة فحص السوق تعمل في خلفية خادم الويب"""
    while True:
        try:
            analyze_smc_markets()
        except Exception as e:
            print(f"Loop error: {e}")
        time.sleep(60) # فحص كل دقيقة

if __name__ == "__main__":
    # تشغيل حلقة الفحص الذكي في مسار منفصل (Thread) لكي لا تتعطل
    bot_thread = Thread(target=run_market_loop)
    bot_thread.daemon = True
    bot_thread.start()
    
    # تشغيل خادم الويب على المنفذ الذي تطلبه Render
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
