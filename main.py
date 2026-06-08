import time
import datetime
import requests
import pandas as pd
import os
import json
import threading
from flask import Flask

# ═══════════════════════════════════════════════════════════════
# 🌐 إعداد خادم الويب (Web App Bypass) لمنع الـ Timeout
# ═══════════════════════════════════════════════════════════════
app = Flask(__name__)

@app.route('/')
def home():
    return "🦅 نظام صائد السيولة الثلاثي الاحترافي (1D + 1H + 15M) يعمل سحابياً بنجاح!"

PA_PROXY = {"http": "http://proxy.server:3128", "https": "http://proxy.server:3128"}

# ═══════════════════════════════════════════════════════════════
# 🔑 الإعدادات الأساسية
# ═══════════════════════════════════════════════════════════════
BOT_TOKEN = "8069323015:AAElFLIaHIj0bkz6XKWrRtB73y8hROFdzjA"
CHAT_ID   = "@Forexsignals908765"
LOG_FILE  = "/home/Xcaliber/signals_log.json"

# الأصول المالية الموحدة والسريعة (كريبتو + ذهب + فوركس موازي)
SYMBOLS_POOL = {
    "BTCUSDT": {"name": "بيتكوين (Bitcoin)", "type": "CRYPTO"}, 
    "ETHUSDT": {"name": "إيثيريوم (Ethereum)", "type": "CRYPTO"}, 
    "SOLUSDT": {"name": "سولانا (Solana)", "type": "CRYPTO"},
    "PAXGUSDT": {"name": "الذهب الفوري (Gold)", "type": "COMMODITY"},
    "EURUSDT": {"name": "اليورو دولار (EUR/USD)", "type": "FOREX"}
}

# ═══════════════════════════════════════════════════════════════
# 📂 إدارة السجلات والتحكم بالتكرار
# ═══════════════════════════════════════════════════════════════
def load_log():
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except: return {}
    return {}

def save_log(log):
    with open(LOG_FILE, "w", encoding="utf-8") as f: json.dump(log, f, ensure_ascii=False, indent=2)

def already_sent(log, symbol, hours=8):
    if symbol not in log: return False
    try:
        last_time = datetime.datetime.fromisoformat(log[symbol])
        return (datetime.datetime.now() - last_time).total_seconds() < hours * 3600
    except: return False

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try: requests.post(url, json={"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}, proxies=PA_PROXY, timeout=10)
    except: pass

# ═══════════════════════════════════════════════════════════════
# 📐 دالة الحسابات الفنية للأطر الزمنية
# ═══════════════════════════════════════════════════════════════
def extract_indicators(res):
    df = pd.DataFrame(res, columns=['Time', 'Open', 'High', 'Low', 'Close', 'Volume', 'CT', 'AV', 'T', 'TB', 'TQ', 'I']).astype(float)
    
    # حساب ATR للنطاق الحركي
    hl, hc, lc = df['High'] - df['Low'], (df['High'] - df['Close'].shift()).abs(), (df['Low'] - df['Close'].shift()).abs()
    df['ATR'] = pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(14).mean()
    
    # حساب RSI
    delta = df['Close'].diff()
    gain = (delta.clip(lower=0)).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-10))))
    
    # حساب البولينجر باند
    df['MA20'] = df['Close'].rolling(20).mean()
    df['STD20'] = df['Close'].rolling(20).std()
    df['Lower_BB'] = df['MA20'] - (df['STD20'] * 2)
    
    # حساب طفرة السيولة
    df['Avg_Vol'] = df['Volume'].rolling(20).mean()
    df['Vol_Spike'] = df['Volume'] / (df['Avg_Vol'] + 1e-10)
    
    return df

# ═══════════════════════════════════════════════════════════════
# 🎯 محرك القنص والتحليل ثلاثي الأبعاد
# ═══════════════════════════════════════════════════════════════
def sniper_analyze(symbol, info, log):
    if already_sent(log, symbol): return
    
    try:
        base_url = "https://api.binance.com/api/v3/klines?symbol="
        
        # 1️⃣ جلب بيانات الفريم اليومي (1D) - هيكل السوق العام
        res_d = requests.get(f"{base_url}{symbol}&interval=1d&limit=30", proxies=PA_PROXY, timeout=5).json()
        df_d = extract_indicators(res_d)
        price_d = df_d['Close'].iloc[-1]
        lower_bb_d = df_d['Lower_BB'].iloc[-1]
        ma20_d = df_d['MA20'].iloc[-1]
        
        # شرط الفريم اليومي: السعر في النصف السفلي من البولينجر أو قريب من القاع اليومي لدعم الارتداد
        if price_d > ma20_d: return 

        # 2️⃣ جلب بيانات فريم الساعة (1H) - فلتر سيولة الحيتان والتأكيد
        res_h = requests.get(f"{base_url}{symbol}&interval=1h&limit=30", proxies=PA_PROXY, timeout=5).json()
        df_h = extract_indicators(res_h)
        price_h = df_h['Close'].iloc[-1]
        rsi_h = df_h['RSI'].iloc[-1]
        vol_ratio_h = df_h['Vol_Spike'].iloc[-1]
        lower_bb_h = df_h['Lower_BB'].iloc[-1]
        atr_h = df_h['ATR'].iloc[-1]
        
        # شرط الساعة: تشبع بيعي واضح مع بداية تدفق أحجام تداول عالية
        if not (rsi_h < 40 and price_h <= lower_bb_h * 1.005 and vol_ratio_h >= 1.2): return

        # 3️⃣ جلب بيانات فريم الربع ساعة (15M) - نقطة التنفيذ والدخول الدقيق
        res_m = requests.get(f"{base_url}{symbol}&interval=15m&limit=30", proxies=PA_PROXY, timeout=5).json()
        df_m = extract_indicators(res_m)
        rsi_m = df_m['RSI'].iloc[-1]
        rsi_m_prev = df_m['RSI'].iloc[-2]
        
        # شرط الربع ساعة: حدوث ارتداد إيجابي ميكروسكوبي مؤكد (الـ RSI بدأ يرتفع صعوداً)
        if not (rsi_m > rsi_m_prev): return
        
        # ═══════════════════════════════════════════════════════════
        # 💵 حساب النقاط الاحترافية وإرسال الصفقة القناصة
        # ═══════════════════════════════════════════════════════════
        current_price = round(price_h, 4)
        sl = round(current_price - (atr_h * 1.5), 4) # وقف خسارة صغير جداً ومحمي بـ ATR
        risk = current_price - sl
        
        tp1 = round(current_price + (risk * 1.5), 4)
        tp2 = round(current_price + (risk * 3.0), 4)
        tp3 = round(current_price + (risk * 5.0), 4) # أهداف واسعة لأن الاتجاه اليومي يدعمنا
        
        msg = (
            f"🦅 *قناص السيولة المحترف — إشارة ثلاثية الأبعاد* 🦅\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔵 *الأصل المالي:* {info['name']} (`{symbol}`)\n"
            f"🏷️ *تصنيف السوق:* {info['type']}\n"
            f"📈 *نوع الصفقة:* 🟢 شراء ارتدادي من قاع يومي مؤكد\n"
            f"💵 *سعر التنفيذ الحالي:* `{current_price}`\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🛑 *إيقاف الخسارة الصارم (SL):* `{sl}`\n"
            f"🎯 *الأهداف المستهدفة (معدل عائد عالي):*\n"
            f"  • *🎯 هدف أول (T1):* `{tp1}`\n"
            f"  • *🎯 هدف ثاني (T2):* `{tp2}`\n"
            f"  • *🎯 هدف ثالث (T3):* `{tp3}`\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔍 *التأكيدات الهيكلية الفنية:*\n"
            f"• 📅 *الفريم اليومي:* السعر مستقر في مناطق الخصم والشراء العميقة.\n"
            f"• ⏱️ *فريم الساعة:* رصد طفرة سيولة صناع السوق بمقدار `{vol_ratio_h:.1f}x` مع تشبع بيعي.\n"
            f"• ⚡ *فريم الربع ساعة:* تأكيد الدخول الفوري عبر انعكاس الزخم المصغر.\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💎 *إدارة المخاطر:* الصفقات مصفاة بالكامل ومحمية برمجياً."
        )
        
        send_telegram_message(msg)
        log[symbol] = datetime.datetime.now().isoformat()
        save_log(log)
        
    except:
        pass

# ═══════════════════════════════════════════════════════════════
# 🔄 الحلقة المستمرة للفحص المتقدم
# ═══════════════════════════════════════════════════════════════
def bot_loop():
    log = load_log()
    
    welcome_msg = (
        "🦅 *تم تفعيل نظام قناص السيولة ثلاثي الأبعاد المطور بنجاح!* 🦅\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🤖 المحرك السحابي الجديد يدمج الآن 3 أطر زمنية موحدة:\n"
        "1️⃣ تحليل هيكل السوق والخصم على *الفريم اليومي (1D)*\n"
        "2️⃣ رصد طفرات سيولة الحيتان والـ RSI على *فريم الساعة (1H)*\n"
        "3️⃣ اقتناص توقيت التنفيذ والدخول الدقيق على *فريم الربع ساعة (15M)*\n\n"
        "الفحص جارٍ الآن تلقائياً وبأعلى استقرار لكل الأصول المحددة! 🔥"
    )
    send_telegram_message(welcome_msg)
    
    while True:
        try:
            for sym, info in SYMBOLS_POOL.items():
                sniper_analyze(sym, info, log)
            time.sleep(300) # فحص متكامل ومستقر كل 5 دقائق
        except:
            time.sleep(60)

threading.Thread(target=bot_loop, daemon=True).start()
