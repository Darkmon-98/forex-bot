import time
import datetime
import requests
import yfinance as yf
import pandas as pd
import os
import json

# ═══════════════════════════════════════════════════════════════
# 🔑 إعدادات البوت
# في الترمنل: export BOT_TOKEN="8069323015:AAElFLIaHIj0bkz6XKWrRtB73y8hROFdzjA"
#             export CHAT_ID="@Forexsignals908765"
# ═══════════════════════════════════════════════════════════════
BOT_TOKEN = "BOT_TOKEN",("8069323015:AAElFLIaHIj0bkz6XKWrRtB73y8hROFdzjA")
CHAT_ID   = "CHAT_ID",("@Forexsignals908765")

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
# 💾 اللوق
# ═══════════════════════════════════════════════════════════════
LOG_FILE = "signals_log.json"

def load_log():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_log(log):
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

def already_sent(log, symbol, signal_type, hours=4):
    key = f"{symbol}_{signal_type}"
    if key not in log:
        return False
    last_time = datetime.datetime.fromisoformat(log[key])
    return (datetime.datetime.now() - last_time).total_seconds() < hours * 3600

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
# 📨 التلغرام
# ═══════════════════════════════════════════════════════════════
def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code != 200:
            print(f"⚠️ تلغرام: {resp.status_code} — {resp.text}")
    except Exception as e:
        print(f"❌ خطأ في التلغرام: {e}")

# ═══════════════════════════════════════════════════════════════
# 📐 المؤشرات المشتركة
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
    """قوة الإشارة للفوركس والسلع"""
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
# 🪙 مؤشرات مخصصة للكريبتو
# ═══════════════════════════════════════════════════════════════
def calculate_bollinger(df, period=20, std_dev=2):
    """
    Bollinger Bands — أفضل من High/Low للكريبتو
    يحدد مناطق الشراء (تحت الباند السفلي) والبيع (فوق العلوي)
    """
    ma     = df['Close'].rolling(period).mean()
    std    = df['Close'].rolling(period).std()
    upper  = ma + (std * std_dev)
    lower  = ma - (std * std_dev)
    return round(upper.iloc[-1], 4), round(ma.iloc[-1], 4), round(lower.iloc[-1], 4)

def calculate_volume_spike(df, period=20):
    """
    كشف ارتفاع غير طبيعي في الحجم
    الكريبتو يتحرك بقوة مع ارتفاع الحجم
    نسبة > 1.5 = حجم مرتفع ✅
    """
    avg_vol     = df['Volume'].rolling(period).mean().iloc[-1]
    current_vol = df['Volume'].iloc[-1]
    if avg_vol == 0:
        return 1.0
    return round(current_vol / avg_vol, 2)

def detect_candle_pattern(df):
    """
    كشف أنماط الشموع اليابانية للتأكيد:
    - Bullish Engulfing: شمعة خضراء تبتلع الحمراء السابقة
    - Bearish Engulfing: شمعة حمراء تبتلع الخضراء السابقة
    - Hammer: ذيل سفلي طويل = إشارة عكس صاعد
    - Shooting Star: ذيل علوي طويل = إشارة عكس هابط
    """
    o1, c1, h1, l1 = df['Open'].iloc[-2], df['Close'].iloc[-2], df['High'].iloc[-2], df['Low'].iloc[-2]
    o2, c2, h2, l2 = df['Open'].iloc[-1], df['Close'].iloc[-1], df['High'].iloc[-1], df['Low'].iloc[-1]

    body1 = abs(c1 - o1)
    body2 = abs(c2 - o2)
    range2 = h2 - l2 if h2 != l2 else 0.0001

    # Bullish Engulfing
    if c1 < o1 and c2 > o2 and c2 > o1 and o2 < c1:
        return "BULLISH_ENGULFING", "🕯️ ابتلاع صاعد"

    # Bearish Engulfing
    if c1 > o1 and c2 < o2 and c2 < o1 and o2 > c1:
        return "BEARISH_ENGULFING", "🕯️ ابتلاع هابط"

    # Hammer (ذيل سفلي > 2x الجسم، ذيل علوي صغير)
    lower_wick = min(o2, c2) - l2
    upper_wick = h2 - max(o2, c2)
    if body2 > 0 and lower_wick > 2 * body2 and upper_wick < body2 * 0.5:
        return "HAMMER", "🔨 مطرقة صاعدة"

    # Shooting Star (ذيل علوي > 2x الجسم)
    if body2 > 0 and upper_wick > 2 * body2 and lower_wick < body2 * 0.5:
        return "SHOOTING_STAR", "⭐ نجمة هابطة"

    return "NONE", "—"

def signal_strength_crypto(rsi, macd_hist, vol_ratio, candle, bb_position, trend, signal_type):
    """
    قوة الإشارة للكريبتو — معايير مختلفة:
    - RSI حدود أوسع (40 للشراء، 65 للبيع)
    - حجم التداول مهم جداً
    - نمط الشمعة يُضيف تأكيداً
    - موضع السعر من Bollinger Bands
    """
    score = 0
    if signal_type == "BUY":
        # RSI — الكريبتو يحتاج تشبع بيع أقوى
        if rsi < 30:            score += 3
        elif rsi < 40:          score += 2
        elif rsi < 50:          score += 1
        # MACD
        if macd_hist > 0:       score += 1
        # حجم مرتفع = تأكيد
        if vol_ratio >= 2.0:    score += 2
        elif vol_ratio >= 1.5:  score += 1
        # نمط الشمعة
        if candle == "BULLISH_ENGULFING": score += 2
        elif candle == "HAMMER":          score += 1
        # Bollinger — السعر تحت الباند السفلي
        if bb_position == "BELOW_LOWER":  score += 2
        # الاتجاه
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
    """موضع السعر من Bollinger Bands"""
    if price > upper:  return "ABOVE_UPPER",  "🔴 فوق الباند العلوي"
    if price < lower:  return "BELOW_LOWER",  "🟢 تحت الباند السفلي"
    return "INSIDE", "🟡 داخل النطاق"

# ═══════════════════════════════════════════════════════════════
# 💹 تحليل الفوركس والسلع (SMC الأصلي)
# ═══════════════════════════════════════════════════════════════
def analyze_forex_symbol(symbol, name, log, now):
    try:
        df = yf.Ticker(symbol).history(period="7d", interval="1h")
        if df.empty or len(df) < 30:
            print(f"  ⚠️ داتا غير كافية لـ {name}")
            return

        current_price = round(df['Close'].iloc[-1], 2)
        max_high      = round(df['High'].iloc[-15:-1].max(), 2)
        min_low       = round(df['Low'].iloc[-15:-1].min(), 2)
        trend         = get_market_trend(symbol)
        atr           = calculate_atr(df)
        rsi           = calculate_rsi(df)
        _, _, hist    = calculate_macd(df)
        trend_ar      = "📈 صاعد" if trend=="BULLISH" else "📉 هابط" if trend=="BEARISH" else "↔️ محايد"

        print(f"  💹 {name}: {current_price} | RSI={rsi} | MACD={hist} | {trend_ar}")

        # 🟢 شراء
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
                f"💹 *الأصل:* {name}\n"
                f"📊 *نوع الصفقة:* 🟢 شراء ذكي (Order Block)\n"
                f"⚡ *قوة الإشارة:* {strength}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💵 *سعر الدخول:* `{current_price}`\n"
                f"🛑 *وقف الخسارة (SL):* `{sl}`\n"
                f"🎯 *TP1:* `{tp1}` | *TP2:* `{tp2}` | *TP3:* `{tp3}`\n"
                f"📐 *نسبة المخاطرة/العائد:* 1:1.5\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📈 *الاتجاه:* {trend_ar} | *RSI:* {rsi} | *MACD:* {hist}\n"
                f"⏱️ *الفريم:* 1H | {now}"
            )
            send_telegram_message(msg)
            mark_sent(log, symbol, "BUY")
            print(f"  ✅ BUY أُرسلت لـ {name}")
            time.sleep(3)

        # 🔴 بيع
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
                f"💹 *الأصل:* {name}\n"
                f"📊 *نوع الصفقة:* 🔴 بيع ذكي (Supply Block)\n"
                f"⚡ *قوة الإشارة:* {strength}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💵 *سعر الدخول:* `{current_price}`\n"
                f"🛑 *وقف الخسارة (SL):* `{sl}`\n"
                f"🎯 *TP1:* `{tp1}` | *TP2:* `{tp2}` | *TP3:* `{tp3}`\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📈 *الاتجاه:* {trend_ar} | *RSI:* {rsi} | *MACD:* {hist}\n"
                f"⏱️ *الفريم:* 1H | {now}"
            )
            send_telegram_message(msg)
            mark_sent(log, symbol, "SELL")
            print(f"  ✅ SELL أُرسلت لـ {name}")
            time.sleep(3)

    except Exception as e:
        print(f"  ❌ خطأ في {name}: {e}")

# ═══════════════════════════════════════════════════════════════
# 🪙 تحليل الكريبتو المخصص
# ═══════════════════════════════════════════════════════════════
def analyze_crypto_symbol(symbol, name, log, now):
    try:
        df = yf.Ticker(symbol).history(period="7d", interval="1h")
        if df.empty or len(df) < 30:
            print(f"  ⚠️ داتا غير كافية لـ {name}")
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
        trend_ar             = "📈 صاعد" if trend=="BULLISH" else "📉 هابط" if trend=="BEARISH" else "↔️ محايد"

        vol_icon = "🔥" if vol_ratio >= 2.0 else "📊" if vol_ratio >= 1.5 else "💤"
        print(f"  🪙 {name}: {current_price} | RSI={rsi} | Vol={vol_ratio}x {vol_icon} | BB={bb_key} | {candle_key}")

        # ── شروط الشراء للكريبتو ────────────────────────────
        # RSI تشبع بيع أقوى + السعر تحت Bollinger السفلي + حجم مرتفع
        buy_condition = (
            rsi < 40 and
            bb_key == "BELOW_LOWER" and
            vol_ratio >= 1.5 and
            trend != "BEARISH" and
            candle_key in ["BULLISH_ENGULFING", "HAMMER", "NONE"]
        )

        # ── شروط البيع للكريبتو ─────────────────────────────
        # RSI تشبع شراء أقوى + السعر فوق Bollinger العلوي + حجم مرتفع
        sell_condition = (
            rsi > 65 and
            bb_key == "ABOVE_UPPER" and
            vol_ratio >= 1.5 and
            trend != "BULLISH" and
            candle_key in ["BEARISH_ENGULFING", "SHOOTING_STAR", "NONE"]
        )

        # 🟢 شراء
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
                f"🔵 *العملة:* {name}\n"
                f"📊 *نوع الصفقة:* 🟢 شراء كريبتو\n"
                f"⚡ *قوة الإشارة:* {strength}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💵 *سعر الدخول:* `{current_price}`\n"
                f"🛑 *وقف الخسارة (SL):* `{sl}`\n"
                f"🎯 *TP1:* `{tp1}` | *TP2:* `{tp2}` | *TP3:* `{tp3}`\n"
                f"📐 *نسبة المخاطرة/العائد:* 1:1.5\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📉 *RSI:* {rsi} ← تشبع بيع\n"
                f"📊 *Bollinger:* {bb_ar}\n"
                f"🔊 *حجم التداول:* {vol_ratio}x {vol_icon}\n"
                f"🕯️ *نمط الشمعة:* {candle_ar}\n"
                f"📈 *الاتجاه:* {trend_ar}\n"
                f"⏱️ *الفريم:* 1H | {now}"
            )
            send_telegram_message(msg)
            mark_sent(log, symbol, "BUY")
            print(f"  ✅ CRYPTO BUY أُرسلت لـ {name}")
            time.sleep(3)

        # 🔴 بيع
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
                f"🔵 *العملة:* {name}\n"
                f"📊 *نوع الصفقة:* 🔴 بيع كريبتو\n"
                f"⚡ *قوة الإشارة:* {strength}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💵 *سعر الدخول:* `{current_price}`\n"
                f"🛑 *وقف الخسارة (SL):* `{sl}`\n"
                f"🎯 *TP1:* `{tp1}` | *TP2:* `{tp2}` | *TP3:* `{tp3}`\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📈 *RSI:* {rsi} ← تشبع شراء\n"
                f"📊 *Bollinger:* {bb_ar}\n"
                f"🔊 *حجم التداول:* {vol_ratio}x {vol_icon}\n"
                f"🕯️ *نمط الشمعة:* {candle_ar}\n"
                f"📈 *الاتجاه:* {trend_ar}\n"
                f"⏱️ *الفريم:* 1H | {now}"
            )
            send_telegram_message(msg)
            mark_sent(log, symbol, "SELL")
            print(f"  ✅ CRYPTO SELL أُرسلت لـ {name}")
            time.sleep(3)

    except Exception as e:
        print(f"  ❌ خطأ في {name}: {e}")

# ═══════════════════════════════════════════════════════════════
# 🤖 المحرك الرئيسي
# ═══════════════════════════════════════════════════════════════
def analyze_smc_markets():
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{'='*55}")
    print(f"🤖 فحص هيرمز المؤسسي | {now}")
    print(f"{'='*55}")

    log = load_log()

    # ── الفوركس والسلع ──────────────────────────────────────
    if is_market_open():
        print("\n💹 فحص الفوركس والسلع (SMC):")
        for symbol, name in SYMBOLS.items():
            analyze_forex_symbol(symbol, name, log, now)
    else:
        print("\n⏰ السوق الأمريكي مغلق — تم تخطي الفوركس والسلع.")

    # ── العملات الرقمية 24/7 ────────────────────────────────
    print("\n🪙 فحص العملات الرقمية (Bollinger + Volume + Candles):")
    for symbol, name in CRYPTO_SYMBOLS.items():
        analyze_crypto_symbol(symbol, name, log, now)

# ═══════════════════════════════════════════════════════════════
# 🚀 نقطة التشغيل
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 55)
    print("  🤖 بوت هيرمز للتداول المؤسسي — SMC Edition v3.0")
    print("=" * 55)

    if "ضع_توكنك" in BOT_TOKEN:
        print("\n⚠️  تحذير: لم يتم ضبط BOT_TOKEN!")
        print("   export BOT_TOKEN='توكنك_هنا'")
        print("   export CHAT_ID='@اسم_قناتك'\n")

    send_telegram_message(
        "🤖 *بوت هيرمز v3.0 شغّال!*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "💹 *الفوركس والسلع — تحليل SMC:*\n"
        "  • Order Block + Supply Block\n"
        "  • ATR + RSI + MACD\n\n"
        "🪙 *الكريبتو — تحليل مخصص:*\n"
        "  • Bollinger Bands\n"
        "  • Volume Spike كشف الحجم\n"
        "  • أنماط الشموع اليابانية\n"
        "  • RSI حدود مخصصة (40/65)\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🚫 منع التكرار كل 4 ساعات\n"
        "⭐ قوة الإشارة بالنجوم\n"
        "⏰ فلتر ساعات السوق للفوركس"
    )

    while True:
        try:
            analyze_smc_markets()
        except Exception as e:
            print(f"🚨 خطأ رئيسي: {e}")
        print(f"\n💤 انتظار 5 دقائق...\n")
        time.sleep(300)
