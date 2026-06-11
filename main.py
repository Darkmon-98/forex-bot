import time
import datetime
import requests
import pandas as pd
import os
import json
import threading
from flask import Flask

# ═══════════════════════════════════════════════════════════════
# 🌐 إعداد خادم الويب لمنع الـ Timeout
# ═══════════════════════════════════════════════════════════════
app = Flask(__name__)

@app.route('/')
def home():
    return "🦅 نظام قناص السيولة السريع (1H + 15M) يعمل سحابياً بنجاح وبأعلى كفاءة!"

PA_PROXY = {"http": "http://proxy.server:3128", "https": "http://proxy.server:3128"}

# ═══════════════════════════════════════════════════════════════
# 🔑 الإعدادات الأساسية
# ═══════════════════════════════════════════════════════════════
BOT_TOKEN = "8069323015:AAElFLIaHIj0bkz6XKWrRtB73y8hROFdzjA"
CHAT_ID   = "@Forexsignals908765"
LOG_FILE  = "/home/Xcaliber/signals_log.json"

SYMBOLS_POOL = {
    "BTCUSDT": {"name": "بيتكوين (Bitcoin)", "type": "CRYPTO"}, 
    "ETHUSDT": {"name": "إيثيريوم (Ethereum)", "type": "CRYPTO"}, 
    "SOLUSDT": {"name": "سولانا (Solana)", "type": "CRYPTO"},
    "PAXGUSDT": {"name": "الذهب الفوري (Gold)", "type": "COMMODITY"},
    "EURUSDT": {"name": "اليورو دولار (EUR/USD)", "type": "FOREX"}
}

# ═══════════════════════════════════════════════════════════════
# 📂 إدارة السجلات (تقليص فترة الانتظار إلى 4 ساعات لزيادة الفرص)
# ═══════════════════════════════════════════════════════════════
def load_log():
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except: return {}
    return {}

def save_log(log):
    with open(LOG_FILE, "w", encoding="utf-8") as f: json.dump(log, f, ensure_ascii=False, indent=2)

def already_sent(log, symbol, hours=4):
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
# 📐 الحسابات الفنية للأطر الزمنية السريعة
# ═══════════════════════════════════════════════════════════════
def extract_indicators(res):
    df = pd.DataFrame(res, columns=['Time', 'Open', 'High', 'Low', 'Close', 'Volume', 'CT', 'AV', 'T', 'TB', 'TQ', 'I']).astype(float)
    
    hl, hc, lc = df['High'] - df['Low'], (df['High'] - df['Close'].shift()).abs(), (df['Low'] - df['Close'].shift()).abs()
    df['ATR'] = pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(14).mean()
    
    delta = df['Close'].diff()
    gain = (delta.clip(lower=0)).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-10))))
    
    df['MA20'] = df['Close'].rolling(20).mean()
    df['STD20'] = df['Close'].rolling(20).std()
    df['Lower_BB'] = df['MA20'] - (df['STD20'] * 2)
    
    df['Avg_Vol'] = df['Volume'].rolling(20).mean()
    df['Vol_Spike'] = df['Volume'] / (df['Avg_Vol'] + 1e-10)
    
    return df

# ═══════════════════════════════════════════════════════════════
# 🎯 محرك القنص والتحليل السريع المعدل
# ═══════════════════════════════════════════════════════════════
def sniper_analyze(symbol, info, log):
    if already_sent(log, symbol): return
    
    try:
        base_url = "https://api.binance.com/api/v3/klines?symbol="
        
        # 1️⃣ فريم الساعة (1H) - رصد ذروة البيع وتدفق سيولة الارتداد
        res_h = requests.get(f"{base_url}{symbol}&interval=1h&limit=30", proxies=PA_PROXY, timeout=5).json()
        df_h = extract_indicators(res_h)
        price_h = df_h['Close'].iloc[-1]
        rsi_h = df_h['RSI'].iloc[-1]
        vol_ratio_h = df_h['Vol_Spike'].iloc[-1]
        lower_bb_h = df_h['Lower_BB'].iloc[-1]
        atr_h = df_h['ATR'].iloc[-1]
        
        # شرط فريم الساعة المخفف والذكي: تشبع بيعي حقيقي وبداية ارتداد
        if not (rsi_h < 42 and price_h <= lower_bb_h * 1.01 and vol_ratio_h >= 1.0): return

        # 2️⃣ فريم الربع ساعة (15M) - التأكيد والدخول الفوري
        res_m = requests.get(f"{base_url}{symbol}&interval=15m&limit=30", proxies=PA_PROXY, timeout=5).json()
        df_m = extract_indicators(res_m)
        rsi_m = df_m['RSI'].iloc[-1]
        rsi_m_prev = df_m['RSI'].iloc[-2]
        
        # شرط الربع ساعة: انعكاس الزخم وبدء الشموع الخضراء الصاعدة
        if not (rsi_m > rsi_m_prev): return
        
        # ═══════════════════════════════════════════════════════════
        # 💵 حساب النقاط الفورية وإرسال الصفقة السريعة
        # ═══════════════════════════════════════════════════════════
        current_price = round(price_h, 4)
        sl = round(current_price - (atr_h * 1.2), 4) # وقف خسارة ضيق ومحسب بدقة لحماية رأس المال
        risk = current_price - sl
        
        tp1 = round(current_price + (risk * 1.2), 4)
        tp2 = round(current_price + (risk * 2.2), 4)
        tp3 = round(current_price + (risk * 3.5), 4)
        
        msg = (
            f"⚡ *قناص السيولة اللحظي — صفقة سكالبينج سريعة* ⚡\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔵 *الأصل المالي:* {info['name']} (`{symbol}`)\n"
            f"🏷️ *نوع الحركة:* 🟢 اقتناص ارتداد لحظي سريع (Scalping)\n"
            f"💵 *سعر الدخول الفوري:* `{current_price}`\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🛑 *إيقاف الخسارة (SL):* `{sl}`\n"
            f"🎯 *الأهداف اللحظية المستهدفة:*\n"
            f"  • *🎯 هدف أول (T1):* `{tp1}`\n"
            f"  • *🎯 هدف ثاني (T2):* `{tp2}`\n"
            f"  • *🎯 هدف ثالث (T3):* `{tp3}`\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔍 *مؤشرات التأكيد الحالية:*\n"
            f"• ⏱️ *فريم الساعة:* تراجع السعر أسفل البولينجر مع زخم بيعي منخفض لضمان الارتداد.\n"
            f"• ⚡ *فريم الربع ساعة:* رصد بدء صعود مؤشر RSI السريع للتنفيذ الحركي.\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💎 *ملاحظة:* تم تخفيف الفلاتر لاقتناص الفرص اليومية السريعة."
        )
        
        send_telegram_message(msg)
        log[symbol] = datetime.datetime.now().isoformat()
        save_log(log)
        
    except:
        pass

# ═══════════════════════════════════════════════════════════════
# 🔄 الحلقة المستمرة للفحص السريع
# ═══════════════════════════════════════════════════════════════
def bot_loop():
    log = load_log()
    
    welcome_msg = (
        "⚡ *تم تفعيل نظام قناص السيولة السريع (1H + 15M) بنجاح!* ⚡\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🚀 تم تخفيف الشروط وبدء الفحص السريع التكيفي مع السوق الحالي.\n"
        "⏱️ الفحص يتم الآن تلقائياً كل 3 دقائق للأصول الخمسة في الخلفية.\n\n"
        "ترقبوا أولى صفقات السكالبينج فور رصد الحركة! 🔥"
    )
    send_telegram_message(welcome_msg)
    
    while True:
        try:
            for sym, info in SYMBOLS_POOL.items():
                sniper_analyze(sym, info, log)
            time.sleep(180) # فحص سريع ومتكرر كل 3 دقائق
        except:
            time.sleep(30)

threading.Thread(target=bot_loop, daemon=True).start()
