"""
بوت تلغرام - توصيات فوركس وعملات رقمية وسلع (مجاني 100%)
يستخدم: python-telegram-bot + yfinance + pandas_ta + matplotlib
تثبيت: pip install python-telegram-bot yfinance pandas pandas_ta matplotlib
"""

import logging
import io
import os
import json
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, JobQueue
)
from datetime import datetime

# ─── الإعدادات ──────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# ملف حفظ إعدادات التنبيهات
ALERTS_FILE = "alerts.json"

# ─── قائمة الأصول ───────────────────────────────────────────────
ASSETS = {
    "forex": {
        "EUR/USD": "EURUSD=X",
        "GBP/USD": "GBPUSD=X",
        "USD/JPY": "USDJPY=X",
        "USD/CHF": "USDCHF=X",
        "AUD/USD": "AUDUSD=X",
        "USD/CAD": "USDCAD=X",
        "NZD/USD": "NZDUSD=X",
        "EUR/GBP": "EURGBP=X",
    },
    "crypto": {
        "Bitcoin":  "BTC-USD",
        "Ethereum": "ETH-USD",
        "BNB":      "BNB-USD",
        "Solana":   "SOL-USD",
        "XRP":      "XRP-USD",
        "Cardano":  "ADA-USD",
        "DOGE":     "DOGE-USD",
        "MATIC":    "MATIC-USD",
    },
    "commodities": {
        "الذهب":      "GC=F",
        "الفضة":      "SI=F",
        "النفط":      "CL=F",
        "غاز طبيعي":  "NG=F",
        "نحاس":       "HG=F",
    },
}

EMOJI = {
    "forex": "💱",
    "crypto": "🪙",
    "commodities": "🛢️",
}

# قاموس عكسي: ticker → (category, name)
TICKER_LOOKUP = {}
for cat, items in ASSETS.items():
    for name, ticker in items.items():
        TICKER_LOOKUP[ticker] = (cat, name)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ─── إدارة التنبيهات (حفظ/تحميل) ────────────────────────────────

def load_alerts() -> dict:
    if os.path.exists(ALERTS_FILE):
        with open(ALERTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_alerts(alerts: dict):
    with open(ALERTS_FILE, "w", encoding="utf-8") as f:
        json.dump(alerts, f, ensure_ascii=False, indent=2)

def get_user_alerts(chat_id: str) -> dict:
    alerts = load_alerts()
    return alerts.get(str(chat_id), {"hourly": False, "rsi_watchlist": []})

def set_user_alerts(chat_id: str, data: dict):
    alerts = load_alerts()
    alerts[str(chat_id)] = data
    save_alerts(alerts)


# ─── التحليل التقني ─────────────────────────────────────────────

def get_signal(ticker: str) -> dict | None:
    try:
        df = yf.download(ticker, period="3mo", interval="1d", progress=False, auto_adjust=True)
        if df.empty or len(df) < 51:
            return None

        close = df["Close"].squeeze()

        rsi     = ta.rsi(close, length=14)
        ema20   = ta.ema(close, length=20)
        ema50   = ta.ema(close, length=50)
        macd_df = ta.macd(close, fast=12, slow=26, signal=9)

        if rsi is None or ema20 is None or ema50 is None or macd_df is None:
            return None

        last_rsi   = float(rsi.iloc[-1])
        last_ema20 = float(ema20.iloc[-1])
        last_ema50 = float(ema50.iloc[-1])
        last_price = float(close.iloc[-1])
        prev_price = float(close.iloc[-2])
        macd_val   = float(macd_df["MACD_12_26_9"].iloc[-1])
        macd_sig   = float(macd_df["MACDs_12_26_9"].iloc[-1])

        score = 0
        reasons = []

        if last_rsi < 35:
            score += 2
            reasons.append(f"RSI={last_rsi:.1f} (تشبع بيع 📉)")
        elif last_rsi > 65:
            score -= 2
            reasons.append(f"RSI={last_rsi:.1f} (تشبع شراء 📈)")
        else:
            reasons.append(f"RSI={last_rsi:.1f} (محايد)")

        if last_ema20 > last_ema50:
            score += 1
            reasons.append("EMA20 > EMA50 (اتجاه صاعد ↗️)")
        else:
            score -= 1
            reasons.append("EMA20 < EMA50 (اتجاه هابط ↘️)")

        if macd_val > macd_sig:
            score += 1
            reasons.append("MACD إيجابي ✅")
        else:
            score -= 1
            reasons.append("MACD سلبي ❌")

        if score >= 3:
            signal, action = "🟢 شراء قوي", "BUY"
        elif score >= 1:
            signal, action = "🔵 شراء", "BUY"
        elif score <= -3:
            signal, action = "🔴 بيع قوي", "SELL"
        elif score <= -1:
            signal, action = "🟠 بيع", "SELL"
        else:
            signal, action = "⚪ انتظار", "HOLD"

        change_pct = ((last_price - prev_price) / prev_price) * 100

        if action == "BUY":
            sl, tp = last_price * 0.99, last_price * 1.02
        elif action == "SELL":
            sl, tp = last_price * 1.01, last_price * 0.98
        else:
            sl = tp = None

        return {
            "price": last_price, "change_pct": change_pct,
            "signal": signal, "action": action,
            "reasons": reasons, "rsi": last_rsi,
            "sl": sl, "tp": tp, "score": score,
            "df": df, "ema20": ema20, "ema50": ema50, "rsi_series": rsi,
        }

    except Exception as e:
        logger.error(f"خطأ في {ticker}: {e}")
        return None


def format_price(price: float, ticker: str = "") -> str:
    if price < 0.01:
        return f"{price:.6f}"
    elif price < 1:
        return f"{price:.4f}"
    elif price > 1000:
        return f"{price:,.2f}"
    else:
        return f"{price:.4f}"


# ─── رسم الشارت ─────────────────────────────────────────────────

def build_chart(result: dict, name: str) -> io.BytesIO:
    df     = result["df"]
    ema20  = result["ema20"]
    ema50  = result["ema50"]
    rsi_s  = result["rsi_series"]

    close  = df["Close"].squeeze()
    dates  = df.index

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7),
                                    gridspec_kw={"height_ratios": [3, 1]},
                                    facecolor="#0d1117")
    fig.suptitle(f"📊 {name}", color="white", fontsize=14, fontweight="bold")

    # ── السعر + EMA ──
    ax1.set_facecolor("#0d1117")
    ax1.plot(dates, close,  color="#58a6ff", linewidth=1.5, label="السعر")
    ax1.plot(dates, ema20,  color="#f0a500", linewidth=1.2, linestyle="--", label="EMA20")
    ax1.plot(dates, ema50,  color="#ff6b6b", linewidth=1.2, linestyle="--", label="EMA50")

    # تلوين المنطقة تحت السعر
    ax1.fill_between(dates, close, close.min(), alpha=0.08, color="#58a6ff")

    ax1.tick_params(colors="white", labelsize=8)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax1.xaxis.set_major_locator(mdates.WeekdayLocator(interval=2))
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=30, ha="right")
    ax1.spines[:].set_color("#30363d")
    ax1.set_ylabel("السعر", color="white", fontsize=9)
    ax1.legend(loc="upper left", fontsize=8, facecolor="#161b22", labelcolor="white")
    ax1.grid(color="#21262d", linestyle="--", linewidth=0.5)

    # ── RSI ──
    ax2.set_facecolor("#0d1117")
    ax2.plot(dates, rsi_s, color="#a371f7", linewidth=1.3, label="RSI")
    ax2.axhline(70, color="#ff6b6b", linestyle=":", linewidth=0.8)
    ax2.axhline(30, color="#3fb950", linestyle=":", linewidth=0.8)
    ax2.fill_between(dates, rsi_s, 70, where=(rsi_s >= 70), alpha=0.2, color="#ff6b6b")
    ax2.fill_between(dates, rsi_s, 30, where=(rsi_s <= 30), alpha=0.2, color="#3fb950")
    ax2.set_ylim(0, 100)
    ax2.set_ylabel("RSI", color="white", fontsize=9)
    ax2.tick_params(colors="white", labelsize=8)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax2.xaxis.set_major_locator(mdates.WeekdayLocator(interval=2))
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=30, ha="right")
    ax2.spines[:].set_color("#30363d")
    ax2.grid(color="#21262d", linestyle="--", linewidth=0.5)
    ax2.legend(loc="upper left", fontsize=8, facecolor="#161b22", labelcolor="white")

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=130, bbox_inches="tight", facecolor="#0d1117")
    plt.close(fig)
    buf.seek(0)
    return buf


# ─── مهمة التنبيهات التلقائية (كل ساعة) ────────────────────────

async def hourly_job(context: ContextTypes.DEFAULT_TYPE):
    """ترسل إشارات قوية لكل مستخدم فعّل التنبيهات الساعية"""
    alerts = load_alerts()
    for chat_id, prefs in alerts.items():
        if not prefs.get("hourly", False):
            continue
        lines = ["⏰ *تنبيه ساعي - إشارات قوية*\n"]
        found = False
        for category, assets in ASSETS.items():
            for name, ticker in assets.items():
                result = get_signal(ticker)
                if result and result["action"] in ("BUY", "SELL") and abs(result["score"]) >= 3:
                    found = True
                    pf = format_price(result["price"], ticker)
                    lines.append(f"{result['signal']}  *{name}* @ {pf}")
        if found:
            lines.append(f"\n🕐 {datetime.now().strftime('%H:%M')} UTC")
            lines.append("⚠️ _للأغراض التعليمية فقط_")
            try:
                await context.bot.send_message(
                    chat_id=int(chat_id),
                    text="\n".join(lines),
                    parse_mode="Markdown",
                )
            except Exception as e:
                logger.warning(f"فشل إرسال تنبيه لـ {chat_id}: {e}")


async def rsi_alert_job(context: ContextTypes.DEFAULT_TYPE):
    """تنبيه RSI - يتحقق كل ساعة ويرسل عند تجاوز حدود RSI"""
    alerts = load_alerts()
    for chat_id, prefs in alerts.items():
        watchlist = prefs.get("rsi_watchlist", [])
        if not watchlist:
            continue
        for ticker in watchlist:
            result = get_signal(ticker)
            if not result:
                continue
            rsi_val = result["rsi"]
            cat, name = TICKER_LOOKUP.get(ticker, ("", ticker))
            if rsi_val < 30:
                msg = (f"🔔 *تنبيه RSI - تشبع بيع!*\n"
                       f"*{name}* | RSI = {rsi_val:.1f} (< 30)\n"
                       f"💰 السعر: {format_price(result['price'], ticker)}\n"
                       f"📡 {result['signal']}\n"
                       f"⚠️ _للأغراض التعليمية فقط_")
                try:
                    await context.bot.send_message(int(chat_id), msg, parse_mode="Markdown")
                except Exception as e:
                    logger.warning(f"فشل تنبيه RSI لـ {chat_id}: {e}")
            elif rsi_val > 70:
                msg = (f"🔔 *تنبيه RSI - تشبع شراء!*\n"
                       f"*{name}* | RSI = {rsi_val:.1f} (> 70)\n"
                       f"💰 السعر: {format_price(result['price'], ticker)}\n"
                       f"📡 {result['signal']}\n"
                       f"⚠️ _للأغراض التعليمية فقط_")
                try:
                    await context.bot.send_message(int(chat_id), msg, parse_mode="Markdown")
                except Exception as e:
                    logger.warning(f"فشل تنبيه RSI لـ {chat_id}: {e}")


# ─── معالجات البوت ──────────────────────────────────────────────

def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💱 فوركس",      callback_data="menu_forex"),
         InlineKeyboardButton("🪙 كريبتو",     callback_data="menu_crypto")],
        [InlineKeyboardButton("🛢️ سلع",        callback_data="menu_commodities"),
         InlineKeyboardButton("⚡ كل الإشارات", callback_data="all_signals")],
        [InlineKeyboardButton("🔔 التنبيهات",  callback_data="alerts_menu"),
         InlineKeyboardButton("ℹ️ كيف يعمل؟",  callback_data="how_it_works")],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *بوت توصيات التداول*\n\n"
        "مرحباً! أنا بوت تحليل تقني مجاني يعطيك:\n"
        "• إشارات شراء/بيع مبنية على بيانات حقيقية\n"
        "• رسم بياني مع RSI + EMA\n"
        "• تنبيهات تلقائية كل ساعة\n"
        "• تنبيه عند تشبع RSI\n\n"
        "⚠️ *تنبيه:* للأغراض التعليمية فقط.\n\n"
        "اختر فئة:",
        parse_mode="Markdown",
        reply_markup=main_keyboard(),
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data    = query.data
    chat_id = str(query.message.chat_id)

    # ── القوائم الرئيسية ──
    if data.startswith("menu_"):
        category = data.replace("menu_", "")
        assets   = ASSETS[category]
        emoji    = EMOJI[category]
        labels   = {"forex": "فوركس", "crypto": "كريبتو", "commodities": "سلع"}

        keyboard, row = [], []
        for name in assets:
            row.append(InlineKeyboardButton(name, callback_data=f"signal_{category}_{name}"))
            if len(row) == 2:
                keyboard.append(row); row = []
        if row:
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_main")])

        await query.edit_message_text(
            f"{emoji} *اختر {labels[category]}:*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    # ── إشارة + شارت ──
    elif data.startswith("signal_"):
        parts    = data.split("_", 2)
        category = parts[1]
        name     = parts[2]
        ticker   = ASSETS[category][name]

        await query.edit_message_text(f"⏳ جاري تحليل *{name}*...", parse_mode="Markdown")

        result = get_signal(ticker)
        if result is None:
            await query.edit_message_text(
                f"❌ تعذّر جلب بيانات {name}. حاول لاحقاً.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data=f"menu_{category}")
                ]]),
            )
            return

        pf          = format_price(result["price"], ticker)
        change      = result["change_pct"]
        change_icon = "🔺" if change >= 0 else "🔻"
        sl_text     = f"🛑 وقف الخسارة: {format_price(result['sl'], ticker)}\n" if result["sl"] else ""
        tp_text     = f"🎯 الهدف: {format_price(result['tp'], ticker)}\n"       if result["tp"] else ""
        reasons_txt = "\n".join(f"  • {r}" for r in result["reasons"])

        caption = (
            f"📊 *تحليل {name}*\n"
            f"{'─'*28}\n"
            f"💰 السعر: *{pf}*  {change_icon} {abs(change):.2f}%\n"
            f"📡 الإشارة: *{result['signal']}*\n"
            f"{'─'*28}\n"
            f"{sl_text}{tp_text}"
            f"{'─'*28}\n"
            f"🔍 *أسباب الإشارة:*\n{reasons_txt}\n"
            f"{'─'*28}\n"
            f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')} UTC\n"
            f"⚠️ _للأغراض التعليمية فقط_"
        )

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 تحديث",   callback_data=data),
             InlineKeyboardButton("📈 شارت",    callback_data=f"chart_{category}_{name}"),
             InlineKeyboardButton("🔙 رجوع",    callback_data=f"menu_{category}")],
        ])

        await query.edit_message_text(caption, parse_mode="Markdown", reply_markup=kb)

    # ── الشارت ──
    elif data.startswith("chart_"):
        parts    = data.split("_", 2)
        category = parts[1]
        name     = parts[2]
        ticker   = ASSETS[category][name]

        await query.edit_message_text(f"📈 جاري رسم شارت *{name}*...", parse_mode="Markdown")

        result = get_signal(ticker)
        if result is None:
            await query.edit_message_text("❌ تعذّر جلب البيانات.")
            return

        buf = build_chart(result, name)
        await query.message.reply_photo(
            photo=InputFile(buf, filename=f"{name}.png"),
            caption=f"📈 *{name}* - آخر 3 أشهر\nRSI الحالي: {result['rsi']:.1f}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 رجوع", callback_data=f"signal_{category}_{name}")
            ]]),
        )
        await query.delete_message()

    # ── كل الإشارات ──
    elif data == "all_signals":
        await query.edit_message_text("⏳ جاري تحليل جميع الأصول... قد يستغرق دقيقة.")

        lines = ["⚡ *ملخص إشارات اليوم*\n"]
        labels = {"forex": "فوركس", "crypto": "كريبتو", "commodities": "سلع"}
        for category, assets in ASSETS.items():
            lines.append(f"\n{EMOJI[category]} *{labels[category]}:*")
            for name, ticker in assets.items():
                result = get_signal(ticker)
                if result:
                    pf = format_price(result["price"], ticker)
                    lines.append(f"  {result['signal']}  *{name}* @ {pf}")
                else:
                    lines.append(f"  ❓ *{name}* - لا توجد بيانات")

        lines.append(f"\n🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')} UTC")
        lines.append("⚠️ _للأغراض التعليمية فقط_")

        await query.edit_message_text(
            "\n".join(lines),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 تحديث", callback_data="all_signals"),
                 InlineKeyboardButton("🔙 رجوع",  callback_data="back_main")],
            ]),
        )

    # ── قائمة التنبيهات ──
    elif data == "alerts_menu":
        prefs   = get_user_alerts(chat_id)
        hourly  = prefs.get("hourly", False)
        watch   = prefs.get("rsi_watchlist", [])
        h_label = "✅ تنبيه ساعي: مفعّل" if hourly else "🔕 تنبيه ساعي: معطّل"

        watch_names = []
        for t in watch:
            _, n = TICKER_LOOKUP.get(t, ("", t))
            watch_names.append(n)
        w_text = "، ".join(watch_names) if watch_names else "لا يوجد"

        await query.edit_message_text(
            f"🔔 *إعدادات التنبيهات*\n\n"
            f"⏰ *التنبيه الساعي:* {'مفعّل ✅' if hourly else 'معطّل ❌'}\n"
            f"  يرسل إشارات قوية كل ساعة تلقائياً\n\n"
            f"📊 *تنبيه RSI:* {w_text}\n"
            f"  يُنبّهك عند تشبع شراء/بيع (RSI > 70 أو < 30)",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(h_label, callback_data="toggle_hourly")],
                [InlineKeyboardButton("➕ أضف أصل لتنبيه RSI", callback_data="rsi_add_menu")],
                [InlineKeyboardButton("🗑️ أزل الكل من RSI",    callback_data="rsi_clear")],
                [InlineKeyboardButton("🔙 رجوع",               callback_data="back_main")],
            ]),
        )

    # ── تفعيل/إيقاف التنبيه الساعي ──
    elif data == "toggle_hourly":
        prefs          = get_user_alerts(chat_id)
        prefs["hourly"] = not prefs.get("hourly", False)
        set_user_alerts(chat_id, prefs)
        status = "مفعّل ✅" if prefs["hourly"] else "معطّل ❌"
        await query.answer(f"التنبيه الساعي: {status}", show_alert=True)
        # أعد فتح القائمة
        query.data = "alerts_menu"
        await button_handler(update, context)

    # ── قائمة إضافة RSI ──
    elif data == "rsi_add_menu":
        keyboard, row = [], []
        for category, assets in ASSETS.items():
            for name, ticker in assets.items():
                row.append(InlineKeyboardButton(name, callback_data=f"rsi_add_{ticker}"))
                if len(row) == 2:
                    keyboard.append(row); row = []
        if row:
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="alerts_menu")])

        await query.edit_message_text(
            "📊 *اختر أصل لإضافته لتنبيه RSI:*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    # ── إضافة أصل لـ RSI watchlist ──
    elif data.startswith("rsi_add_"):
        ticker = data.replace("rsi_add_", "")
        prefs  = get_user_alerts(chat_id)
        wl     = prefs.get("rsi_watchlist", [])
        _, name = TICKER_LOOKUP.get(ticker, ("", ticker))
        if ticker not in wl:
            wl.append(ticker)
            prefs["rsi_watchlist"] = wl
            set_user_alerts(chat_id, prefs)
            await query.answer(f"✅ تمت إضافة {name}", show_alert=True)
        else:
            await query.answer(f"⚠️ {name} موجود مسبقاً", show_alert=True)
        query.data = "alerts_menu"
        await button_handler(update, context)

    # ── مسح RSI watchlist ──
    elif data == "rsi_clear":
        prefs = get_user_alerts(chat_id)
        prefs["rsi_watchlist"] = []
        set_user_alerts(chat_id, prefs)
        await query.answer("🗑️ تم مسح قائمة RSI", show_alert=True)
        query.data = "alerts_menu"
        await button_handler(update, context)

    # ── كيف يعمل ──
    elif data == "how_it_works":
        await query.edit_message_text(
            "ℹ️ *كيف يعمل البوت؟*\n\n"
            "📌 *RSI* - مؤشر القوة النسبية\n"
            "  • < 30 = تشبع بيع → إشارة شراء\n"
            "  • > 70 = تشبع شراء → إشارة بيع\n\n"
            "📌 *EMA 20 vs EMA 50*\n"
            "  • EMA20 > EMA50 = اتجاه صاعد\n"
            "  • EMA20 < EMA50 = اتجاه هابط\n\n"
            "📌 *MACD*\n"
            "  • MACD > خط الإشارة = زخم إيجابي\n\n"
            "📈 *الشارت* - رسم بياني بـ 3 أشهر\n\n"
            "🔔 *التنبيهات التلقائية*\n"
            "  • ساعي: إشارات قوية كل ساعة\n"
            "  • RSI: تنبيه فوري عند تشبع\n\n"
            "⚠️ *مهم:* للأغراض التعليمية فقط.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 رجوع", callback_data="back_main")
            ]]),
        )

    # ── رجوع ──
    elif data == "back_main":
        await query.edit_message_text(
            "🤖 *بوت توصيات التداول*\n\n"
            "⚠️ *تنبيه:* للأغراض التعليمية فقط.\n\n"
            "اختر فئة:",
            parse_mode="Markdown",
            reply_markup=main_keyboard(),
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 *الأوامر المتاحة:*\n"
        "/start - القائمة الرئيسية\n"
        "/help  - المساعدة\n\n"
        "اضغط /start للبدء.",
        parse_mode="Markdown",
    )


# ─── تشغيل البوت ────────────────────────────────────────────────

def main():
    print("🚀 جاري تشغيل البوت...")
    app = Application.builder().token(BOT_TOKEN).build()

    # أوامر
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help",  help_command))
    app.add_handler(CallbackQueryHandler(button_handler))

    # مهام دورية
    jq: JobQueue = app.job_queue
    jq.run_repeating(hourly_job,    interval=3600, first=60)   # كل ساعة
    jq.run_repeating(rsi_alert_job, interval=3600, first=120)  # كل ساعة (بفارق دقيقتين)

    print("✅ البوت يعمل! افتح تلغرام وابدأ المحادثة.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
