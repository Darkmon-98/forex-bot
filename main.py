import time
import datetime
import requests
import yfinance as yf
import pandas as pd
import os
import json

# ═══════════════════════════════════════════════════════════════
# 🔑 إعدادات البوت
# ملاحظة: لضمان عمل البوت على PythonAnywhere دون تعقيدات، 
# يمكنك وضع التوكن والـ ID الخاص بقناتك مباشرة بين علامات التنصيص.
# ═══════════════════════════════════════════════════════════════
BOT_TOKEN = ("BOT_TOKEN","8069323015:AAElFLIaHIj0bkz6XKWrRtB73y8hROFdzjA")
CHAT_ID   = ("CHAT_ID","@Forexsignals908765")

# ═══════════════════════════════════════════════════════════════
# 📊 أسواق الفوركس والسلع
# ═══════════════════════════════════════════════════════════════
SYMBOLS = {
    "NQ=F":  "الميني ناسداك (E-mini Nasdaq)",
    "^NDX":  "الناسداك الرئيسي (Nasdaq 100)",
    "GC=F":  "الذهب اللحظي (Gold)",
}

# ═══════════════════════════════════════════════════════════════
# 🪙 العملات الرقمية — 24/7
# ═══════════════════════════════════════════════════════════════
CRYPTO_SYMBOLS = {
    "BTC-USD": "بيتكوين (Bitcoin)",
    "ETH-USD": "إيثيريوم (Ethereum)",
    "BNB-USD": "بينانس كوين (BNB)",
    "SOL-USD": "سولانا (Solana)",
    "XRP-USD": "ريبل (XRP)",
}

# ═══════════════════════════════════════════════════════════════
# 💾 سجل الإشارات لمنع التكرار
# ═══════════════════════════════════════════════════════════════
LOG_FILE = "signals_log.json"

def load_log():
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_log(log):
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

def already_sent(log, symbol, signal_type, hours=4):
    key = f"{symbol}_{signal_type}"
    if key not in log:
        return False
    try:
        last_time = datetime.datetime.fromisoformat(log[key])
        return (datetime.datetime.now() - last_time).total_seconds() < hours * 3600
    except:
        return False

def mark_sent(log, symbol, signal_type):
    log[f"{symbol}_{signal_type}"] = datetime.datetime.now().isoformat()
    save_log(log)

# ═══════════════════════════════════════════════════════════════
# 📅 فلتر ساعات السوق (فوركس فقط)
# ═══════════════════════════════════════════════════════════════
def is_market_open():
    now_est = datetime.datetime.utcnow() - datetime.timedelta(hours=5)
    if now_est.weekday() >= 5:
        return False
    h, m = now_est.hour, now_est.minute
    return (h > 9 or (h == 9 and m >= 30)) and h < 16

# ═══════════════════════════════════════════════════════════════
# 📨 إرسال رسائل التلغرام
# ═══════════════════════════════════════════════════════════════
def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code != 200:
            print(f"⚠️ تلغرام: {resp.status_code} — {resp.text}")
    except Exception as e:
        print(f"❌ خطأ في إرسال رسالة التلغرام: {e}")

# ═══════════════════════════════════════════════════════════════
# 📐 المؤشرات الفنية المشتركة
# ═══════════════════════════════════════════════════════════════
def get_market_trend(symbol):
    try:
        df = yf.Ticker(symbol).history(period="1mo", interval="1h")
        if df.empty or len(df) < 20:
            return "NEUTRAL"
        ma20  = df['Close'].rolling(20).mean().iloc[-1]
        price = df['Close'].iloc[-1]
        if price > ma20:   return "BULLISH"
        elif price < ma20: return "BEARISH"
    except:
        pass
    return "NEUTRAL"

def calculate_atr(df, period=14):
    hl = df['High'] - df['Low']
    hc = (df['High'] - df['Close'].shift()).abs()
    lc = (df['Low']  - df['Close'].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.rolling(period).mean().iloc[-1]

def calculate_rsi(df, period=14):
    delta = df['Close'].diff()
    gain  = delta.clip(lower=0).rolling(period).mean()
    loss  = (-delta.clip(upper=0)).rolling(period).mean()
    if loss.iloc[-1] == 0:
        return 50.0
    rs    = gain / loss
    return round((100 - (100 / (1 + rs))).iloc[-1], 1)

def calculate_macd(df):
    ema12  = df['Close'].ewm(span=12, adjust=False).mean()
    ema26  = df['Close'].ewm(span=26, adjust=False).mean()
    macd   = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    hist   = macd - signal
    return round(macd.iloc[-1], 4), round(signal.iloc[-1], 4), round(hist.iloc[-1], 4)

def signal_strength_forex(rsi, macd_hist, trend, signal_type):
    """تقييم قوة الإشارة لأسواق الفوركس والسلع"""
    score = 0
    if signal_type == "BUY":
        if rsi < 40:            score += 2
        elif rsi < 50:          score += 1
        if macd_hist > 0:       score += 1
        if trend == "BULLISH":  score += 2
    else:
        if rsi > 60:            score += 2
        elif rsi > 50:          score += 1
        if macd_hist < 0:       score += 1
        if trend == "BEARISH":  score += 2
    stars = "⭐" * min(score, 5)
    return stars if stars else "⚠️ ضعيفة"

# ═══════════════════════════════════════════════════════════════
# 🪙 مؤشرات فنية مخصصة لأسواق الكريبتو
# ═══════════════════════════════════════════════════════════════
def calculate_bollinger(df, period=20, std_dev=2):
    """حساب حدود مؤشر بولينجر باندز لمراقبة المناطق المتطرفة"""
    ma     = df['Close'].rolling(period).mean()
    std    = df['Close'].rolling(period).std()
    upper  = ma + (std * std_dev)
    lower  = ma - (std * std_dev)
    return round(upper.iloc[-1], 4), round(ma.iloc[-1], 4), round(lower.iloc[-1], 4)

def calculate_volume_spike(df, period=20):
    """رصد الارتفاع المفاجئ في حجم التداول (دخول السيولة الحوتية)"""
    avg_vol     = df['Volume'].rolling(period).mean().iloc[-1]
    current_vol = df['Volume'].iloc[-1]
    if avg_vol == 0:
        return 1.0
    return round(current_vol / avg_vol, 2)

def detect_candle_pattern(df):
    """
    كشف أنماط الشموع اليابانية الانعكاسية (سلوك السعر اللحظي):
    تم تصحيح السطر range2 ليعمل برمجياً بدون أخطاء.
    """
    o1, c1, h1, l1 = df['Open'].iloc[-2], df['Close'].iloc[-2], df['High'].iloc[-2], df['Low'].iloc[-2]
    o2, c2, h2, l2 = df['Open'].iloc[-1], df['Close'].iloc[-1], df['High'].iloc[-1], df['Low'].iloc[-1]

    body1 = abs(c1 - o1)
    body2 = abs(c2 - o2)
    range2 = h2 - l2 if h2 != l2 else 0.0001  # تم التصحيح للحرف l بدلاً من الرقم 1

    # نمط الابتلاع الصاعد
    if c1 < o1 and c2 > o2 and c2 > o1 and o2 < c1:
        return "BULLISH_ENGULFING", "🕯️ ابتلاع صاعد"

    # نمط الابتلاع الهابط
    if c1 > o1 and c2 < o2 and c2 < o1 and o2 > c1:
        return "BEARISH_ENGULFING", "🕯️ ابتلاع هابط"

    # نمط شمعة المطرقة الصاعدة
    lower_wick = min(o2, c2) - l2
    upper_wick = h2 - max(o2, c2)
    if body2 > 0 and lower_wick > 2 * body2 and upper_wick < body2 * 0.5:
        return "HAMMER", "🔨 مطرقة صاعدة"

    # نمط شمعة النجمة الهابطة
    if body2 > 0 and upper_wick > 2 * body2 and lower_wick < body2 * 0.5:
        return "SHOOTING_STAR", "⭐ نجمة هابطة"

    return "NONE", "—"

def signal_strength_crypto(rsi, macd_hist, vol_ratio, candle, bb_position, trend, signal_type):
    """تقييم قوة الإشارة لأسواق العملات الرقمية"""
    score = 0
    if signal_type == "BUY":
        if rsi < 30:            score += 3
        elif rsi < 40:          score += 2
        elif rsi < 50:          score += 1
        if macd_hist > 0:       score += 1
        if vol_ratio >= 2.0:    score += 2
        elif vol_ratio >= 1.5:  score += 1
        if candle == "BULLISH_ENGULFING": score += 2
        elif candle == "HAMMER":          score += 1
        if bb_position == "BELOW_LOWER":  score += 2
        if trend == "BULLISH":  score += 1
    else:  # SELL
        if rsi > 75:            score += 3
        elif rsi > 65:          score += 2
        elif rsi > 55:          score += 1
        if macd_hist < 0:       score += 1
        if vol_ratio >= 2.0:    score += 2
        elif vol_ratio >= 1.5:  score += 1
        if candle == "BEARISH_ENGULFING": score += 2
        elif candle == "SHOOTING_STAR":   score += 1
        if bb_position == "ABOVE_UPPER":  score += 2
        if trend == "BEARISH":  score += 1

    stars = "⭐" * min(score, 5)
    return stars if stars else "⚠️ ضعيفة"

def get_bb_position(price, upper, lower):
    if price > upper:  return "ABOVE_UPPER",  "🔴 فوق النطاق العلوي"
    if price < lower:  return "BELOW_LOWER",  "🟢 تحت النطاق السفلي"
    return "INSIDE", "🟡 داخل النطاق الطبيعي"

# ═══════════════════════════════════════════════════════════════
# 💹 تحليل أسواق الفوركس والسلع (استراتيجية SMC)
# ═══════════════════════════════════════════════════════════════
def analyze_forex_symbol(symbol, name, log, now):
    try:
        df = yf.Ticker(symbol).history(period="7d", interval="1h")
        if df.empty or len(df) < 30:
            print(f"  ⚠️ بيانات غير كافية لتحليل {name}")
            return

        current_price = round(df['Close'].iloc[-1], 2)
        max_high      = round(df['High'].iloc[-15:-1].max(), 2)
        min_low       = round(df['Low'].iloc[-15:-1].min(), 2)
        trend         = get_market_trend(symbol)
        atr           = calculate_atr(df)
        rsi           = calculate_rsi(df)
        _, _, hist    = calculate_macd(df)
        trend_ar      = "📈 اتجاه صاعد" if trend=="BULLISH" else "📉 اتجاه هابط" if trend=="BEARISH" else "↔️ اتجاه محايد"

        print(f"  💹 {name}: {current_price} | RSI={rsi} | MACD={hist} | {trend_ar}")

        # 🟢 إشارة شراء فوركس
        if (current_price <= min_low * 1.002 and trend == "BULLISH"
                and rsi < 55 and not already_sent(log, symbol, "BUY")):
            sl   = round(current_price - atr * 1.5, 2)
            risk = current_price - sl
            tp1  = round(current_price + risk * 1.5, 2)
            tp2  = round(current_price + risk * 2.5, 2)
            tp3  = round(current_price + risk * 4.0, 2)
            strength = signal_strength_forex(rsi, hist, trend, "BUY")

            msg = (
                f"🛡️ *توصية هيرمز — SMC BUY* 🛡️\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💹 *الأصل المالي:* {name}\n"
                f"📊 *نوع الصفقة:* 🟢 شراء مؤسسي ذكي (Order Block)\n"
                f"⚡ *قوة الإشارة الفنية:* {strength}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💵 *سعر الدخول المباشر:* `{current_price}`\n"
                f"🛑 *مستوى وقف الخسارة (SL):* `{sl}`\n"
                f"🎯 *الأهداف المحققة:* \n"
                f"  • *🎯 الهدف الأول:* `{tp1}`\n"
                f"  • *🎯 الهدف الثاني:* `{tp2}`\n"
                f"  • *🎯 الهدف الثالث:* `{tp3}`\n"
                f"📐 *نسبة المخاطرة إلى العائد:* 1:1.5\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📈 *حالة الاتجاه:* {trend_ar} | *RSI:* {rsi} | *MACD:* {hist}\n"
                f"⏱️ *الإطار الزمني (الفريم):* 1H | {now}"
            )
            send_telegram_message(msg)
            mark_sent(log, symbol, "BUY")
            print(f"  ✅ تم إرسال إشارة الشراء لـ {name}")
            time.sleep(3)

        # 🔴 إشارة بيع فوركس
        elif (current_price >= max_high * 0.998 and trend == "BEARISH"
                and rsi > 45 and not already_sent(log, symbol, "SELL")):
            sl   = round(current_price + atr * 1.5, 2)
            risk = sl - current_price
            tp1  = round(current_price - risk * 1.5, 2)
            tp2  = round(current_price - risk * 2.5, 2)
            tp3  = round(current_price - risk * 4.0, 2)
            strength = signal_strength_forex(rsi, hist, trend, "SELL")

            msg = (
                f"🛡️ *توصية هيرمز — SMC SELL* 🛡️\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💹 *الأصل المالي:* {name}\n"
                f"📊 *نوع الصفقة:* 🔴 بيع مؤسسي ذكي (Supply Block)\n"
                f"⚡ *قوة الإشارة الفنية:* {strength}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💵 *سعر الدخول المباشر:* `{current_price}`\n"
                f"🛑 *مستوى وقف الخسارة (SL):* `{sl}`\n"
                f"🎯 *الأهداف المحققة:* \n"
                f"  • *🎯 الهدف الأول:* `{tp1}`\n"
                f"  • *🎯 الهدف الثاني:* `{tp2}`\n"
                f"  • *🎯 الهدف الثالث:* `{tp3}`\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📈 *حالة الاتجاه:* {trend_ar} | *RSI:* {rsi} | *MACD:* {hist}\n"
                f"⏱️ *الإطار الزمني (الفريم):* 1H | {now}"
            )
            send_telegram_message(msg)
            mark_sent(log, symbol, "SELL")
            print(f"  ✅ تم إرسال إشارة البيع لـ {name}")
            time.sleep(3)

    except Exception as e:
        print(f"  ❌ حدث خطأ أثناء تحليل {name}: {e}")

# ═══════════════════════════════════════════════════════════════
# 🪙 تحليل أسواق العملات الرقمية (استراتيجية مخصصة)
# ═══════════════════════════════════════════════════════════════
def analyze_crypto_symbol(symbol, name, log, now):
    try:
        df = yf.Ticker(symbol).history(period="7d", interval="1h")
        if df.empty or len(df) < 30:
            print(f"  ⚠️ بيانات غير كافية لتحليل {name}")
            return

        current_price        = round(df['Close'].iloc[-1], 4)
        trend                = get_market_trend(symbol)
        atr                  = calculate_atr(df)
        rsi                  = calculate_rsi(df)
        _, _, hist           = calculate_macd(df)
        upper, mid, lower    = calculate_bollinger(df)
        vol_ratio            = calculate_volume_spike(df)
        candle_key, candle_ar= detect_candle_pattern(df)
        bb_key, bb_ar        = get_bb_position(current_price, upper, lower)
        trend_ar             = "📈 اتجاه صاعد" if trend=="BULLISH" else "📉 اتجاه هابط" if trend=="BEARISH" else "↔️ اتجاه محايد"

        vol_icon = "🔥" if vol_ratio >= 2.0 else "📊" if vol_ratio >= 1.5 else "💤"
        print(f"  🪙 {name}: {current_price} | RSI={rsi} | الحجم={vol_ratio}x {vol_icon} | بولينجر={bb_key} | الشموع={candle_key}")

        # شروط الشراء للكريبتو
        buy_condition = (
            rsi < 40 and
            bb_key == "BELOW_LOWER" and
            vol_ratio >= 1.5 and
            trend != "BEARISH" and
            candle_key in ["BULLISH_ENGULFING", "HAMMER", "NONE"]
        )

        # شروط البيع للكريبتو
        sell_condition = (
            rsi > 65 and
            bb_key == "ABOVE_UPPER" and
            vol_ratio >= 1.5 and
            trend != "BULLISH" and
            candle_key in ["BEARISH_ENGULFING", "SHOOTING_STAR", "NONE"]
        )

        # 🟢 إشارة شراء كريبتو
        if buy_condition and not already_sent(log, symbol, "BUY"):
            sl   = round(current_price - atr * 2.0, 4)
            risk = current_price - sl
            tp1  = round(current_price + risk * 1.5, 4)
            tp2  = round(current_price + risk * 2.5, 4)
            tp3  = round(current_price + risk * 4.0, 4)
            strength = signal_strength_crypto(rsi, hist, vol_ratio, candle_key, bb_key, trend, "BUY")

            msg = (
                f"🪙 *توصية هيرمز — CRYPTO BUY* 🪙\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🔵 *الرمز المالي للعملة:* {name}\n"
                f"📊 *نوع الصفقة:* 🟢 شراء عملة رقمية متكامل الأركان\n"
                f"⚡ *قوة الإشارة الفنية:* {strength}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💵 *سعر الدخول المباشر:* `{current_price}`\n"
                f"🛑 *مستوى وقف الخسارة (SL):* `{sl}`\n"
                f"🎯 *الأهداف المحققة:* \n"
                f"  • *🎯 الهدف الأول:* `{tp1}`\n"
                f"  • *🎯 الهدف الثاني:* `{tp2}`\n"
                f"  • *🎯 الهدف الثالث:* `{tp3}`\n"
                f"📐 *نسبة المخاطرة إلى العائد:* 1:1.5\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📉 *مؤشر القوة النسبية RSI:* {rsi} ← منطقة ذروة البيع\n"
                f"📊 *مؤشر حدود بولينجر:* {bb_ar}\n"
                f"🔊 *حجم التداول الحالي:* {vol_ratio}x ضعف المتوسط {vol_icon}\n"
                f"🕯️ *سلوك الشموع اليابانية:* {candle_ar}\n"
                f"📈 *حالة الاتجاه العام للرسم:* {trend_ar}\n"
                f"⏱ Internet *الإطار الزمني:* 1H | {now}"
            )
            send_telegram_message(msg)
            mark_sent(log, symbol, "BUY")
            print(f"  ✅ تم إرسال إشارة شراء العملة الرقمية لـ {name}")
            time.sleep(3)

        # 🔴 إشارة بيع كريبتو
        elif sell_condition and not already_sent(log, symbol, "SELL"):
            sl   = round(current_price + atr * 2.0, 4)
            risk = sl - current_price
            tp1  = round(current_price - risk * 1.5, 4)
            tp2  = round(current_price - risk * 2.5, 4)
            tp3  = round(current_price - risk * 4.0, 4)
            strength = signal_strength_crypto(rsi, hist, vol_ratio, candle_key, bb_key, trend, "SELL")

            msg = (
                f"🪙 *توصية هيرمز — CRYPTO SELL* 🪙\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🔵 *الرمز المالي للعملة:* {name}\n"
                f"📊 *نوع الصفقة:* 🔴 بيع عملة رقمية متكامل الأركان\n"
                f"⚡ *قوة الإشارة الفنية:* {strength}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💵 *سعر الدخول المباشر:* `{current_price}`\n"
                f"🛑 *مستوى وقف الخسارة (SL):* `{sl}`\n"
                f"🎯 *الأهداف المحققة:* \n"
                f"  • *🎯 الهدف الأول:* `{tp1}`\n"
                f"  • *🎯 الهدف الثاني:* `{tp2}`\n"
                f"  • *🎯 الهدف الثالث:* `{tp3}`\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📈 *مؤشر القوة النسبية RSI:* {rsi} ← منطقة ذروة الشراء\n"
                f"📊 *مؤشر حدود بولينجر:* {bb_ar}\n"
                f"🔊 *حجم التداول الحالي:* {vol_ratio}x ضعف المتوسط {vol_icon}\n"
                f"🕯️ *سلوك الشموع اليابانية:* {candle_ar}\n"
                f"📈 *حالة الاتجاه العام للرسم:* {trend_ar}\n"
                f"⏱️ *الإطار الزمني:* 1H | {now}"
            )
            send_telegram_message(msg)
            mark_sent(log, symbol, "SELL")
            print(f"  ✅ تم إرسال إشارة بيع العملة الرقمية لـ {name}")
            time.sleep(3)

    except Exception as e:
        print(f"  ❌ حدث خطأ أثناء تحليل {name}: {e}")

# ═══════════════════════════════════════════════════════════════
# 🤖 المحرك الرئيسي للربط والفحص الدوري
# ═══════════════════════════════════════════════════════════════
def analyze_smc_markets():
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{'='*55}")
    print(f"🤖 فحص نظام هيرمز المؤسسي اللحظي | {now}")
    print(f"{'='*55}")

    log = load_log()

    # فحص الفوركس والسلع
    if is_market_open():
        print("\n💹 بدأ فحص أسواق الفوركس والسلع (استراتيجية SMC):")
        for symbol, name in SYMBOLS.items():
            analyze_forex_symbol(symbol, name, log, now)
    else:
        print("\n⏰ الأسواق العالمية للفوركس مغلقة حالياً — تم تخطي الفحص التلقائي لها.")

    # فحص العملات الرقمية 24/7
    print("\n🪙 بدأ فحص أسواق العملات الرقمية (بولينجر + حجم التداول + الشموع اليابانية):")
    for symbol, name in CRYPTO_SYMBOLS.items():
        analyze_crypto_symbol(symbol, name, log, now)

# ═══════════════════════════════════════════════════════════════
# 🚀 تشغيل البوت المباشر وحلقة الانتظار الدورية
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 55)
    print("  🤖 بوت هيرمز للتداول المؤسسي — الإصدار المطور v3.0")
    print("=" * 55)

    if "ضع_توكنك" in BOT_TOKEN:
        print("\n⚠️ تنبيه: لم يتم تعديل التوكن والمعرفات الخاصة بقناتك بداخل ملف الكود حتى الآن!")

    send_telegram_message(
        "🤖 *بوت هيرمز الإصدار v3.0 شغّال ومحدّث لغويّاً الآن!*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "💹 *أسواق الفوركس والسلع — تحليل SMC المطور:*\n"
        "  • رصد مناطق ومكعبات السيولة (Order Block / Supply)\n"
        "  • حسابات دقيقة بمؤشرات ATR + RSI + MACD\n\n"
        "🪙 *العملات الرقمية — استراتيجية مخصصة للتقلبات:*\n"
        "  • رصد الانفجارات السعرية بواسطة Bollinger Bands\n"
        "  • كشف طفرات السيولة الضخمة (Volume Spike)\n"
        "  • فلترة حية بسلوك السعر وأنماط الشموع اليابانية (المصححة ✅)\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🚫 تم تفعيل نظام منع التكرار التلقائي للإشارات كل 4 ساعات متتالية لضمان جودة الصفقات."
    )

    while True:
        try:
            analyze_smc_markets()
        except Exception as e:
            print(f"🚨 خطأ رئيسي غير متوقع في تشغيل السيرفر: {e}")
        print(f"\n💤 انتظار لمدة 5 دقائق لبدء الفحص الدوري القادم...\n")
        time.sleep(300)
