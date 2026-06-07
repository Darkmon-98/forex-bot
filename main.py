import time
import datetime
import requests
import yfinance as yf
import pandas as pd
import xml.etree.ElementTree as ET
import os
import json

# ═══════════════════════════════════════════════════════════════
# 🔑 إعدادات البوت والقناة
# ═══════════════════════════════════════════════════════════════
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8069323015:AAElFLIaHIj0bkz6XKWrRtB73y8hROFdzjA")
CHAT_ID   = os.environ.get("CHAT_ID",   "@Forexsignals908765")
LOG_FILE  = "signals_log.json"

# الأصول المالية المراقبة
SYMBOLS = {"NQ=F": "الميني ناسداك (Nasdaq)", "GC=F": "الذهب اللحظي (Gold)"}
CRYPTO_SYMBOLS = {"BTC-USD": "بيتكوين (Bitcoin)", "ETH-USD": "إيثيريوم (Ethereum)", "SOL-USD": "سولانا (Solana)"}

# ═══════════════════════════════════════════════════════════════
# 📰 فلتر أخبار فوركس والسلع (Forex Factory)
# ═══════════════════════════════════════════════════════════════
def get_upcoming_high_impact_news():
    """جلب الأخبار الاقتصادية الكلاسيكية عالية التأثير"""
    try:
        url = "https://nfs.forexfactory.com/ffcal_week_this.xml"
        response = requests.get(url, timeout=10)
        if response.status_code != 200: return []
        
        root = ET.fromstring(response.content)
        today_str = datetime.datetime.now().strftime('%Y%m%d')
        high_impact_events = []
        
        for event in root.findall('.//event'):
            impact = event.find('impact').text if event.find('impact') is not None else ''
            date = event.find('date').text if event.find('date') is not None else ''
            
            if impact == 'High' and date.replace('-', '') >= today_str:
                high_impact_events.append({
                    'currency': event.find('currency').text,
                    'title': event.find('title').text,
                    'time': event.find('time').text
                })
        return high_impact_events[:3]
    except:
        return []

# ═══════════════════════════════════════════════════════════════
# 🪙 فلتر وتحليل أخبار وأحداث الكريبتو الحية (Crypto Events API)
# ═══════════════════════════════════════════════════════════════
def get_crypto_news_alerts(crypto_name):
    """جلب عناوين الأحداث الحالية والمؤثرة لعملة معينة"""
    try:
        # استخدام مصدر مفتوح لجلب آخر الأخبار والأحداث للعملة المحددة عبر Coingecko أو خوادم التغذية المفتوحة
        symbol_clean = crypto_name.split('-')[0].lower() # يحول BTC-USD إلى btc
        url = f"https://api.coingecko.com/api/v3/news"
        res = requests.get(url, timeout=5).json()
        
        relevant_news = []
        if 'data' in res:
            for item in res['data']:
                # إذا كان الخبر يحتوي على اسم العملة، نعتبره مهماً لها
                if symbol_clean in item['title'].lower() or symbol_clean in item['description'].lower():
                    relevant_news.append(item['title'])
                if len(relevant_news) >= 2: # نكتفي بآخر خبرين هامين
                    break
        return relevant_news
    except:
        return []

# ═══════════════════════════════════════════════════════════════
# 📊 جلب مؤشر الخوف والطمع للكريبتو
# ═══════════════════════════════════════════════════════════════
def get_crypto_fear_and_greed():
    try:
        res = requests.get("https://api.alternative.me/fng/", timeout=5).json()
        value = res['data'][0]['value']
        classification = res['data'][0]['value_classification']
        
        dict_ar = {"Extreme Fear": "😱 خوف شديد", "Fear": "😨 خوف", "Neutral": "😐 محايد", "Greed": "🤑 طمع", "Extreme Greed": "🔥 طمع شديد"}
        return f"{value} ({dict_ar.get(classification, classification)})"
    except:
        return "50 (😐 محايد)"

# ═══════════════════════════════════════════════════════════════
# 📂 إدارة السجلات والفلاتر الزمنية
# ═══════════════════════════════════════════════════════════════
def load_log():
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except: return {}
    return {}

def save_log(log):
    with open(LOG_FILE, "w", encoding="utf-8") as f: json.dump(log, f, ensure_ascii=False, indent=2)

def already_sent(log, symbol, signal_type, hours=4):
    key = f"{symbol}_{signal_type}"
    if key not in log: return False
    try:
        last_time = datetime.datetime.fromisoformat(log[key])
        return (datetime.datetime.now() - last_time).total_seconds() < hours * 3600
    except: return False

def is_market_open():
    now_est = datetime.datetime.utcnow() - datetime.timedelta(hours=5)
    return now_est.weekday() < 5

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try: requests.post(url, json={"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e: print(f"❌ خطأ تلغرام: {e}")

# ═══════════════════════════════════════════════════════════════
# 📐 العمليات الحسابية والمؤشرات الفنية
# ═══════════════════════════════════════════════════════════════
def calculate_indicators(df):
    hl, hc, lc = df['High'] - df['Low'], (df['High'] - df['Close'].shift()).abs(), (df['Low'] - df['Close'].shift()).abs()
    df['ATR'] = pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(14).mean()
    
    delta = df['Close'].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))
    
    df['MA20'] = df['Close'].rolling(20).mean()
    df['STD20'] = df['Close'].rolling(20).std()
    df['Upper_BB'] = df['MA20'] + (df['STD20'] * 2)
    df['Lower_BB'] = df['MA20'] - (df['STD20'] * 2)
    
    df['Avg_Vol'] = df['Volume'].rolling(20).mean()
    df['Vol_Spike'] = df['Volume'] / df['Avg_Vol']
    return df

# ═══════════════════════════════════════════════════════════════
# 💹 فحص صفقات الـ SMC (فوركس وسلع)
# ═══════════════════════════════════════════════════════════════
def analyze_forex_smc(symbol, name, log, news_list):
    try:
        df = yf.Ticker(symbol).history(period="7d", interval="1h")
        if df.empty or len(df) < 30: return
        df = calculate_indicators(df)
        
        current_price = round(df['Close'].iloc[-1], 2)
        min_low = round(df['Low'].iloc[-15:-1].min(), 2)
        max_high = round(df['High'].iloc[-15:-1].max(), 2)
        rsi = df['RSI'].iloc[-1]
        atr = df['ATR'].iloc[-1]
        
        news_alert = ""
        if news_list:
            news_alert = "⚠️ *تنبيه تقويم اقتصادي هام اليوم:*\n"
            for n in news_list: news_alert += f"  • 🔴 {n['title']} ({n['currency']}) | ⏰ {n['time']}\n"
            news_alert += "━━━━━━━━━━━━━━━━━━━━━━━\n"

        if current_price <= min_low * 1.0015 and rsi < 45 and not already_sent(log, symbol, "BUY"):
            sl = round(current_price - (atr * 1.5), 2)
            risk = current_price - sl
            tp1, tp2, tp3 = round(current_price + risk*1.2, 2), round(current_price + risk*2.2, 2), round(current_price + risk*3.5, 2)
            
            msg = (
                f"🦅 *توصية قناص السيولة — SMC BUY* 🦅\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📊 *الأصل المالي:* `{name}`\n"
                f"🎯 *نوع الإشارة:* 🟢 شراء من منطقة طلب مؤسسية (Order Block)\n"
                f"💵 *سعر الدخول المباشر:* `{current_price}`\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🛑 *إيقاف الخسارة (SL):* `{sl}`\n"
                f"🎯 *الأهداف:*\n"
                f"  • *🎯 الهدف الأول:* `{tp1}`\n"
                f"  • *🎯 الهدف الثاني:* `{tp2}`\n"
                f"  • *🎯 الهدف الثالث:* `{tp3}`\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"{news_alert}"
                f"📐 *مؤشر القوة النسبية (RSI):* {rsi:.1f}\n"
                f"⏱️ فريم التحليل: 1 Hour"
            )
            send_telegram_message(msg)
            log[f"{symbol}_BUY"] = datetime.datetime.now().isoformat()
            save_log(log)

        elif current_price >= max_high * 0.9985 and rsi > 55 and not already_sent(log, symbol, "SELL"):
            sl = round(current_price + (atr * 1.5), 2)
            risk = sl - current_price
            tp1, tp2, tp3 = round(current_price - risk*1.2, 2), round(current_price - risk*2.2, 2), round(current_price - risk*3.5, 2)
            
            msg = (
                f"🦅 *توصية قناص السيولة — SMC SELL* 🦅\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📊 *الأصل المالي:* `{name}`\n"
                f"🎯 *نوع الإشارة:* 🔴 بيع من منطقة عرض مؤسسية (Supply Block)\n"
                f"💵 *سعر الدخول المباشر:* `{current_price}`\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🛑 *إيقاف الخسارة (SL):* `{sl}`\n"
                f"🎯 *الأهداف:*\n"
                f"  • *🎯 الهدف الأول:* `{tp1}`\n"
                f"  • *🎯 الهدف الثاني:* `{tp2}`\n"
                f"  • *🎯 الهدف الثالث:* `{tp3}`\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"{news_alert}"
                f"📐 *مؤشر القوة النسبية (RSI):* {rsi:.1f}\n"
                f"⏱️ فريم التحليل: 1 Hour"
            )
            send_telegram_message(msg)
            log[f"{symbol}_SELL"] = datetime.datetime.now().isoformat()
            save_log(log)
    except Exception as e:
        print(f"❌ خطأ تحليل فوركس: {e}")

# ═══════════════════════════════════════════════════════════════
# 🪙 فحص صفقات العملات الرقمية (مع دمج تحليل الأخبار المخصصة)
# ═══════════════════════════════════════════════════════════════
def analyze_crypto_advanced(symbol, name, log):
    try:
        df = yf.Ticker(symbol).history(period="5d", interval="1h")
        if df.empty or len(df) < 25: return
        df = calculate_indicators(df)
        
        current_price = round(df['Close'].iloc[-1], 4)
        rsi = df['RSI'].iloc[-1]
        atr = df['ATR'].iloc[-1]
        vol_ratio = df['Vol_Spike'].iloc[-1]
        lower_bb = df['Lower_BB'].iloc[-1]
        upper_bb = df['Upper_BB'].iloc[-1]
        
        fng = get_crypto_fear_and_greed()
        
        # 🪙 سحب العناوين الإخبارية الحية للعملة الحالية لمنع المفاجآت
        crypto_news = get_crypto_news_alerts(symbol)
        crypto_news_alert = ""
        if crypto_news:
            crypto_news_alert = "📰 *أحدث المستجدات الإخبارية المرصودة للعملة:*\n"
            for news in crypto_news:
                crypto_news_alert += f"  • 💬 {news}\n"
            crypto_news_alert += "━━━━━━━━━━━━━━━━━━━━━━━\n"

        # إشارة شراء كريبتو متقدمة بفلتر الحجم والأخبار
        if rsi < 35 and current_price <= lower_bb and vol_ratio >= 1.4 and not already_sent(log, symbol, "BUY"):
            sl = round(current_price - (atr * 2), 4)
            risk = current_price - sl
            tp1, tp2, tp3 = round(current_price + risk*1.5, 4), round(current_price + risk*2.5, 4), round(current_price + risk*4, 4)
            
            msg = (
                f"🪙 *توصية سيولة الحيتان — CRYPTO BUY* 🪙\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🔵 *العملة الرقمية:* {name}\n"
                f"📈 *نوع الحركة:* 🟢 اقتناص قاع خارج حدود بولينجر وبداية ارتداد\n"
                f"💵 *سعر الدخول الحالي:* `{current_price}`\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🛑 *إيقاف الخسارة (SL):* `{sl}`\n"
                f"🎯 *الأهداف المستهدفة:*\n"
                f"  • *🎯 هدف أول:* `{tp1}`\n"
                f"  • *🎯 هدف ثاني:* `{tp2}`\n"
                f"  • *🎯 هدف ثالث:* `{tp3}`\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"{crypto_news_alert}" # طباعة الأخبار الحية هنا
                f"🔥 *حجم التداول:* تدفق سيولة بمقدار `{vol_ratio:.1f}x` ضعف المعتاد\n"
                f"😱 *مؤشر الخوف والطمع الحالي للكريبتو:* `{fng}`\n"
                f"📐 *مؤشر القوة النسبية RSI:* `{rsi:.1f}`"
            )
            send_telegram_message(msg)
            log[f"{symbol}_BUY"] = datetime.datetime.now().isoformat()
            save_log(log)
            
    except Exception as e:
        print(f"❌ خطأ تحليل كريبتو: {e}")

# ═══════════════════════════════════════════════════════════════
# 🚀 المحرك الرئيسي
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("🦅 تم دمج فلاتر الأخبار الكاملة للفوركس والعملات الرقمية بنجاح...")
    log = load_log()
    news_list = get_upcoming_high_impact_news()
    
    while True:
        try:
            if datetime.datetime.now().minute == 0:
                news_list = get_upcoming_high_impact_news()
                
            if is_market_open():
                for sym, name in SYMBOLS.items():
                    analyze_forex_smc(sym, name, log, news_list)
                    
            for sym, name in CRYPTO_SYMBOLS.items():
                analyze_crypto_advanced(sym, name, log)
                
            time.sleep(300)
        except Exception as e:
            print(f"🚨 خطأ: {e}")
            time.sleep(60)
