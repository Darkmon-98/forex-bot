import time
import datetime
import requests
import pandas as pd
import os
import json
import logging
import threading
from flask import Flask

# ═══════════════════════════════════════════════════════════════
# 📝 إعداد التسجيل (Logging)
# ═══════════════════════════════════════════════════════════════
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("sniper_bot")

# ═══════════════════════════════════════════════════════════════
# 🌐 إعداد خادم الويب لمنع الـ Timeout
# ═══════════════════════════════════════════════════════════════
app = Flask(__name__)

@app.route('/')
def home():
    return "🦅 نظام قناص السيولة السريع الآمن (1H + 15M) يعمل سحابياً بكفاءة وبدون أخطاء مؤشرات!"

# ═══════════════════════════════════════════════════════════════
# 🔑 الإعدادات الأساسية
# ═══════════════════════════════════════════════════════════════
BOT_TOKEN = ""
CHAT_ID   = "@Forexsignals908765"
LOG_FILE  = "/home/Xcaliber/signals_log.json"

# تثبيت بروكسي PythonAnywhere لضمان استقرار الاتصال المجاني سحابياً
PA_PROXY = {"http": "http://proxy.server:3128", "https": "http://proxy.server:3128"}

SYMBOLS_POOL = {
    "BTCUSDT": {"name": "بيتكوين (Bitcoin)", "type": "CRYPTO"},
    "ETHUSDT": {"name": "إيثيريوم (Ethereum)", "type": "CRYPTO"},
    "SOLUSDT": {"name": "سولانا (Solana)", "type": "CRYPTO"},
    "PAXGUSDT": {"name": "الذهب الفوري (Gold)", "type": "COMMODITY"},
    "EURUSDT": {"name": "اليورو دولار (EUR/USD)", "type": "FOREX"}
}

# ═══════════════════════════════════════════════════════════════
# 📂 إدارة السجلات (فترة الانتظار 4 ساعات)
# ═══════════════════════════════════════════════════════════════
def load_log():
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"فشل قراءة ملف السجل ({LOG_FILE}): {e}")
            return {}
    return {}

def save_log(log):
    try:
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"فشل حفظ ملف السجل ({LOG_FILE}): {e}")

def already_sent(log, symbol, hours=4):
    if symbol not in log:
        return False
    try:
        last_time = datetime.datetime.fromisoformat(log[symbol])
        return (datetime.datetime.now() - last_time).total_seconds() < hours * 3600
    except Exception as e:
        logger.warning(f"خطأ في تنسيق وقت السجل لـ {symbol}: {e}")
        return False

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        resp = requests.post(
            url,
            json={"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"},
            proxies=PA_PROXY,
            timeout=10
        )
        if resp.status_code != 200:
            logger.error(f"فشل إرسال رسالة تيليجرام: {resp.status_code} - {resp.text}")
    except Exception as e:
        logger.error(f"خطأ في الاتصال بتيليجرام: {e}")

# ═══════════════════════════════════════════════════════════════
# 📐 الحسابات الفنية للأطر الزمنية السريعة مع حماية البيانات
# ═══════════════════════════════════════════════════════════════
def extract_indicators(res):
    if not res or not isinstance(res, list) or len(res) < 25:
        return None

    try:
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
    except Exception as e:
        logger.warning(f"فشل حساب المؤشرات: {e}")
        return None

# ═══════════════════════════════════════════════════════════════
# 🌐 طلب آمن من Binance مع فحص الحالة
# ═══════════════════════════════════════════════════════════════
def fetch_klines(base_url, symbol, interval, limit=35):
    try:
        resp = requests.get(
            f"{base_url}{symbol}&interval={interval}&limit={limit}",
            proxies=PA_PROXY,
            timeout=5
        )
        if resp.status_code != 200:
            logger.warning(f"Binance رجع حالة غير متوقعة لـ {symbol} ({interval}): {resp.status_code}")
            return None
        data = resp.json()
        if not isinstance(data, list):
            logger.warning(f"رد Binance غير متوقع لـ {symbol} ({interval}): {data}")
            return None
        return data
    except Exception as e:
        logger.warning(f"فشل جلب بيانات {symbol} ({interval}): {e}")
        return None

# ═══════════════════════════════════════════════════════════════
# 🎯 محرك القنص والتحليل السريع الآمن من انهيار السطور
# ═══════════════════════════════════════════════════════════════
def sniper_analyze(symbol, info, log):
    if already_sent(log, symbol):
        return

    base_url = "https://api.binance.com/api/v3/klines?symbol="

    # 1️⃣ فريم الساعة (1H)
    res_h = fetch_klines(base_url, symbol, "1h")
    df_h = extract_indicators(res_h)
    if df_h is None or len(df_h) < 2:
        return

    price_h = df_h['Close'].iloc[-1]
    rsi_h = df_h['RSI'].iloc[-1]
    vol_ratio_h = df_h['Vol_Spike'].iloc[-1]
    lower_bb_h = df_h['Lower_BB'].iloc[-1]
    atr_h = df_h['ATR'].iloc[-1]

    # شرط فريم الساعة المخفف والذكي
    if not (rsi_h < 42 and price_h <= lower_bb_h * 1.01 and vol_ratio_h >= 1.0):
        return

    # 2️⃣ فريم الربع ساعة (15M)
    res_m = fetch_klines(base_url, symbol, "15m")
    df_m = extract_indicators(res_m)
    if df_m is None or len(df_m) < 2:
        return

    rsi_m = df_m['RSI'].iloc[-1]
    rsi_m_prev = df_m['RSI'].iloc[-2]

    # شرط الربع ساعة: انعكاس الزخم
    if not (rsi_m > rsi_m_prev):
        return

    # ═══════════════════════════════════════════════════════════
    # 💵 حساب النقاط وإرسال الرسالة للتلغرام
    # ═══════════════════════════════════════════════════════════
    current_price = round(price_h, 4)
    sl = round(current_price - (atr_h * 1.2), 4)
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
        f"💎 *ملاحظة:* تم تحديث الفلاتر بنجاح وتأمينها ضد أخطاء حزم البيانات الناتجة عن تذبذب السوق."
    )

    send_telegram_message(msg)
    log[symbol] = datetime.datetime.now().isoformat()
    save_log(log)
    logger.info(f"تم إرسال إشارة لـ {symbol} عند السعر {current_price}")

# ═══════════════════════════════════════════════════════════════
# 🔄 الحلقة المستمرة للفحص
# ═══════════════════════════════════════════════════════════════
def bot_loop():
    log = load_log()

    welcome_msg = (
        "🛡️ *تم تفعيل نسخة الحماية من أخطاء المؤشرات بنجاح!* 🛡️\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🚀 البوت محصن الآن تماماً ضد البيانات الفارغة أو الناقصة (Out-of-bounds).\n"
        "⏱️ تم ضبط دورة الفحص السريع لتعمل بانتظام وبأعلى درجات الاستقرار السحابي.\n\n"
        "الآن محرك الاصطياد منطلق بكامل قوته وبدون أي عوائق برمجية! 🔥"
    )
    send_telegram_message(welcome_msg)
    logger.info("تم بدء تشغيل البوت بنجاح")

    while True:
        try:
            for sym, info in SYMBOLS_POOL.items():
                sniper_analyze(sym, info, log)
            time.sleep(180)  # فحص دوري مستقر كل 3 دقائق
        except Exception as e:
            logger.error(f"خطأ في الحلقة الرئيسية: {e}")
            time.sleep(30)

# إطلاق محرك الفحص في الخلفية
threading.Thread(target=bot_loop, daemon=True).start()

# اترك النهاية فارغة تماماً بدون أسطر app.run ليتكفل بها السيرفر تلقائياً
