import time
import datetime
import requests
import yfinance as yf
import pandas as pd
import os
import json

# ═══════════════════════════════════════════════════════════════
# 🔑 إعدادات البوت — ضع التوكن في متغير بيئي لحماية أمانك
# في الترمنل: export BOT_TOKEN="توكنك_هنا"
# ═══════════════════════════════════════════════════════════════
BOT_TOKEN = "8069323015:AAGy4haTvatdGF34R4ds0JZHHCsW0sqXkJw"
CHAT_ID   =   "@Forexsignals908765"

# ═══════════════════════════════════════════════════════════════
# 📊 الأصول المستهدفة
# ═══════════════════════════════════════════════════════════════
SYMBOLS = {
    "NQ=F":  "الميني ناسداك (E-mini Nasdaq)",
    "^NDX":  "الناسداك الرئيسي (Nasdaq 100)",
    "GC=F":  "الذهب اللحظي (Gold)",
}

# ═══════════════════════════════════════════════════════════════
# 💾 ملف اللوق لحفظ الإشارات ومنع التكرار
# ═══════════════════════════════════════════════════════════════
LOG_FILE = "signals_log.json"

def load_log():
    """تحميل سجل الإشارات السابقة"""
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_log(log):
    """حفظ سجل الإشارات"""
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

def already_sent(log, symbol, signal_type):
    """
    منع إرسال نفس الإشارة أكثر من مرة كل 4 ساعات
    """
    key = f"{symbol}_{signal_type}"
    if key not in log:
        return False
    last_time = datetime.datetime.fromisoformat(log[key])
    diff = datetime.datetime.now() - last_time
    return diff.total_seconds() < 4 * 3600  # 4 ساعات

def mark_sent(log, symbol, signal_type):
    """تسجيل وقت الإشارة"""
    key = f"{symbol}_{signal_type}"
    log[key] = datetime.datetime.now().isoformat()
    save_log(log)

# ═══════════════════════════════════════════════════════════════
# 📅 فلتر ساعات السوق
# ═══════════════════════════════════════════════════════════════
def is_market_open():
    """
    التحقق أن السوق مفتوح:
    - الأسواق الأمريكية: الاثنين–الجمعة، 9:30 صباحاً – 4:00 مساءً EST
    - الذهب يتداول 23 ساعة لكن نتجنب عطلة الأسبوع
    """
    now_utc = datetime.datetime.utcnow()
    # EST = UTC - 5
    now_est = now_utc - datetime.timedelta(hours=5)
    
    weekday = now_est.weekday()  # 0=الاثنين, 6=الأحد
    hour    = now_est.hour
    minute  = now_est.minute
    
    # عطلة نهاية الأسبوع
    if weekday >= 5:
        return False
    
    # قبل فتح السوق أو بعد إغلاقه
    market_open  = hour > 9 or (hour == 9 and minute >= 30)
    market_close = hour < 16
    
    return market_open and market_close

# ═══════════════════════════════════════════════════════════════
# 📨 إرسال التلغرام
# ═══════════════════════════════════════════════════════════════
def send_telegram_message(message):
    """إرسال الإشارة إلى قناة التلغرام"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id":    CHAT_ID,
        "text":       message,
        "parse_mode": "Markdown"
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code != 200:
            print(f"⚠️ تلغرام رجع: {resp.status_code} — {resp.text}")
    except Exception as e:
        print(f"❌ خطأ في الاتصال بالتلغرام: {e}")

# ═══════════════════════════════════════════════════════════════
# 📈 الاتجاه العام (MA20 على فريم 4H)
# ═══════════════════════════════════════════════════════════════
def get_market_trend(symbol):
    """تحديد اتجاه صناع السوق على فريم 4 ساعات"""
    try:
        df = yf.Ticker(symbol).history(period="1mo", interval="1h")
        if df.empty or len(df) < 20:
            return "NEUTRAL"
        ma20          = df['Close'].rolling(20).mean().iloc[-1]
        current_price = df['Close'].iloc[-1]
        if current_price > ma20:
            return "BULLISH"
        elif current_price < ma20:
            return "BEARISH"
    except Exception as e:
        print(f"⚠️ تعذر تحديد الاتجاه لـ {symbol}: {e}")
    return "NEUTRAL"

# ═══════════════════════════════════════════════════════════════
# 📐 ATR — وقف الخسارة الديناميكي
# ═══════════════════════════════════════════════════════════════
def calculate_atr(df, period=14):
    """حساب ATR لتحديد وقف خسارة يتماشى مع تقلبات السوق"""
    hl  = df['High'] - df['Low']
    hc  = (df['High'] - df['Close'].shift()).abs()
    lc  = (df['Low']  - df['Close'].shift()).abs()
    tr  = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.rolling(period).mean().iloc[-1]

# ═══════════════════════════════════════════════════════════════
# 📉 RSI — مؤشر القوة النسبية
# ═══════════════════════════════════════════════════════════════
def calculate_rsi(df, period=14):
    """حساب RSI للتأكيد على الدخول"""
    delta  = df['Close'].diff()
    gain   = delta.clip(lower=0).rolling(period).mean()
    loss   = (-delta.clip(upper=0)).rolling(period).mean()
    rs     = gain / loss
    rsi    = 100 - (100 / (1 + rs))
    return round(rsi.iloc[-1], 1)

# ═══════════════════════════════════════════════════════════════
# 🔀 MACD — تأكيد الزخم
# ═══════════════════════════════════════════════════════════════
def calculate_macd(df):
    """حساب MACD وإشارته"""
    ema12   = df['Close'].ewm(span=12, adjust=False).mean()
    ema26   = df['Close'].ewm(span=26, adjust=False).mean()
    macd    = ema12 - ema26
    signal  = macd.ewm(span=9, adjust=False).mean()
    hist    = macd - signal
    return round(macd.iloc[-1], 4), round(signal.iloc[-1], 4), round(hist.iloc[-1], 4)

# ═══════════════════════════════════════════════════════════════
# 🏦 قوة الإشارة (1–5 نجوم)
# ═══════════════════════════════════════════════════════════════
def signal_strength(rsi, macd_hist, trend, signal_type):
    """
    يحسب قوة الإشارة بناءً على:
    - RSI في المنطقة الصحيحة
    - MACD histogram في الاتجاه الصحيح
    - الاتجاه العام يتوافق
    """
    score = 0
    if signal_type == "BUY":
        if rsi < 40:            score += 2
        elif rsi < 50:          score += 1
        if macd_hist > 0:       score += 1
        if trend == "BULLISH":  score += 2
    else:  # SELL
        if rsi > 60:            score += 2
        elif rsi > 50:          score += 1
        if macd_hist < 0:       score += 1
        if trend == "BEARISH":  score += 2
    
    stars = "⭐" * min(score, 5)
    return stars if stars else "⚠️ ضعيفة"

# ═══════════════════════════════════════════════════════════════
# 🤖 المحرك الرئيسي — تحليل SMC الكامل
# ═══════════════════════════════════════════════════════════════
def analyze_smc_markets():
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n🤖 [فحص مؤسسي] {now}")

    # ✅ فلتر السوق
    if not is_market_open():
        print("⏰ السوق مغلق حالياً — لا إشارات خارج ساعات التداول.")
        return

    log = load_log()

    for symbol, name in SYMBOLS.items():
        try:
            ticker = yf.Ticker(symbol)
            df     = ticker.history(period="7d", interval="1h")

            if df.empty or len(df) < 30:
                print(f"⚠️ داتا غير كافية لـ {name}")
                continue

            current_price  = round(df['Close'].iloc[-1], 2)
            recent_highs   = df['High'].iloc[-15:-1]
            recent_lows    = df['Low'].iloc[-15:-1]
            max_high       = round(recent_highs.max(), 2)
            min_low        = round(recent_lows.min(), 2)

            trend          = get_market_trend(symbol)
            atr            = calculate_atr(df)
            rsi            = calculate_rsi(df)
            macd, sig, hist= calculate_macd(df)

            trend_ar = "📈 صاعد" if trend == "BULLISH" else "📉 هابط" if trend == "BEARISH" else "↔️ محايد"

            print(f"  {name}: السعر={current_price} | RSI={rsi} | MACD_hist={hist} | الاتجاه={trend}")

            # ══════════════════════════════════════
            # 🟢 إشارة شراء — Order Block + تأكيد RSI
            # ══════════════════════════════════════
            buy_condition = (
                current_price <= min_low * 1.002 and
                trend == "BULLISH" and
                rsi < 55  # تأكيد RSI ليس في منطقة تشبع شراء
            )

            if buy_condition and not already_sent(log, symbol, "BUY"):
                sl   = round(current_price - (atr * 1.5), 2)
                risk = current_price - sl
                tp1  = round(current_price + (risk * 1.5), 2)
                tp2  = round(current_price + (risk * 2.5), 2)
                tp3  = round(current_price + (risk * 4.0), 2)
                rr   = round(risk * 1.5 / risk, 1)  # نسبة المخاطرة للهدف الأول
                strength = signal_strength(rsi, hist, trend, "BUY")

                msg = f"""🛡️ *توصية هيرمز المؤسسية — SMC BUY* 🛡️
━━━━━━━━━━━━━━━━━━━━━━━
💱 *الأصل:* {name}
📊 *نوع الصفقة:* 🟢 شراء ذكي (Order Block)
⚡ *قوة الإشارة:* {strength}
━━━━━━━━━━━━━━━━━━━━━━━
💵 *سعر الدخول:* `{current_price}`
🛑 *وقف الخسارة (SL):* `{sl}`
🎯 *الهدف الأول (TP1):* `{tp1}`
🎯 *الهدف الثاني (TP2):* `{tp2}`
🎯 *الهدف الثالث (TP3):* `{tp3}`
📐 *نسبة المخاطرة/العائد:* 1:{rr}
━━━━━━━━━━━━━━━━━━━━━━━
📈 *الاتجاه العام:* {trend_ar}
📉 *RSI:* {rsi}
🔀 *MACD Histogram:* {hist}
⏱️ *الفريم:* 1H | *التوقيت:* {now}"""

                send_telegram_message(msg)
                mark_sent(log, symbol, "BUY")
                print(f"  ✅ إشارة BUY أُرسلت لـ {name}")
                time.sleep(3)

            # ══════════════════════════════════════
            # 🔴 إشارة بيع — Supply Block + تأكيد RSI
            # ══════════════════════════════════════
            sell_condition = (
                current_price >= max_high * 0.998 and
                trend == "BEARISH" and
                rsi > 45  # تأكيد RSI ليس في منطقة تشبع بيع
            )

            if sell_condition and not already_sent(log, symbol, "SELL"):
                sl   = round(current_price + (atr * 1.5), 2)
                risk = sl - current_price
                tp1  = round(current_price - (risk * 1.5), 2)
                tp2  = round(current_price - (risk * 2.5), 2)
                tp3  = round(current_price - (risk * 4.0), 2)
                strength = signal_strength(rsi, hist, trend, "SELL")

                msg = f"""🛡️ *توصية هيرمز المؤسسية — SMC SELL* 🛡️
━━━━━━━━━━━━━━━━━━━━━━━
💱 *الأصل:* {name}
📊 *نوع الصفقة:* 🔴 بيع ذكي (Supply Block)
⚡ *قوة الإشارة:* {strength}
━━━━━━━━━━━━━━━━━━━━━━━
💵 *سعر الدخول:* `{current_price}`
🛑 *وقف الخسارة (SL):* `{sl}`
🎯 *الهدف الأول (TP1):* `{tp1}`
🎯 *الهدف الثاني (TP2):* `{tp2}`
🎯 *الهدف الثالث (TP3):* `{tp3}`
━━━━━━━━━━━━━━━━━━━━━━━
📈 *الاتجاه العام:* {trend_ar}
📉 *RSI:* {rsi}
🔀 *MACD Histogram:* {hist}
⏱️ *الفريم:* 1H | *التوقيت:* {now}"""

                send_telegram_message(msg)
                mark_sent(log, symbol, "SELL")
                print(f"  ✅ إشارة SELL أُرسلت لـ {name}")
                time.sleep(3)

        except Exception as e:
            print(f"❌ خطأ أثناء تحليل {name}: {e}")

# ═══════════════════════════════════════════════════════════════
# 🚀 نقطة التشغيل
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 55)
    print("   🤖 بوت هيرمز للتداول المؤسسي — SMC Edition v2.0")
    print("=" * 55)

    # تحقق من وجود التوكن
    if "ضع_توكنك" in BOT_TOKEN:
        print("\n⚠️  تحذير: لم يتم ضبط BOT_TOKEN!")
        print("   شغّل:  export BOT_TOKEN='توكنك_هنا'")
        print("   ثم:    export CHAT_ID='@اسم_قناتك'\n")
    
    send_telegram_message(
        "🤖 *بوت هيرمز v2.0 شغّال!*\n"
        "✅ فلتر ساعات السوق مفعّل\n"
        "✅ منع تكرار الإشارات (4 ساعات)\n"
        "✅ RSI + MACD + ATR للتأكيد\n"
        "✅ 3 أهداف ربح لكل صفقة\n"
        "✅ قوة الإشارة بالنجوم ⭐"
    )

    while True:
        try:
            analyze_smc_markets()
        except Exception as e:
            print(f"🚨 خطأ رئيسي: {e}")
        
        print(f"  💤 انتظار 5 دقائق...")
        time.sleep(300)  # كل 5 دقائق بدل دقيقة واحدة
