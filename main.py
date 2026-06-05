import time
import datetime
import requests
import yfinance as yf
import pandas as pd
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# إعدادات التلغرام الخاصة بك
BOT_TOKEN = "8830911482:AAFnxsHB7uFLWxEtrc1KsGe6Txk5un6KUnk"
CHAT_ID = "@Forex_signals"

# الأصول المطلوبة للتحليل
SYMBOLS = {
    "NQ=F": "الميني ناسداك (E-mini Nasdaq)",
    "^NDX": "الناسداك الرئيسي (Nasdaq 100)",
    "GC=F": "الذهب اللحظي (Gold)"
}

# --- خادم ويب وهمي لإرضاء خطة Render المجانية ---
class WebServerHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write("🤖 البوت يعمل بكفاءة في الخلفية!".encode("utf-8"))

def run_web_server():
    server_address = ("", 10000) # المنصة تستخدم المنفذ 10000 افتراضياً
    httpd = HTTPServer(server_address, WebServerHandler)
    print("🌍 تم تشغيل خادم الويب الوهمي على المنفذ 10000")
    httpd.serve_forever()
# --------------------------------------------------

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Error sending to Telegram: {e}")

def get_market_trend(symbol):
    try:
        ticker = yf.Ticker(symbol)
        df_4h = ticker.history(period="1mo", interval="4h")
        if df_4h.empty or len(df_4h) < 20:
            return "NEUTRAL"
        ma_20 = df_4h['Close'].rolling(window=20).mean().iloc[-1]
        current_price = df_4h['Close'].iloc[-1]
        if current_price > ma_20: return "BULLISH"
        elif current_price < ma_20: return "BEARISH"
    except Exception as e:
        print(f"Trend error for {symbol}: {e}")
    return "NEUTRAL"

def calculate_atr(df, period=14):
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift()).abs()
    low_close = (df['Low'] - df['Close'].shift()).abs()
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    return true_range.rolling(period).mean().iloc[-1]

def analyze_smc_markets():
    print(f"🤖 [فحص مؤسسي] جاري مسح الأسواق... {datetime.datetime.now()}")
    for symbol, name in SYMBOLS.items():
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="3d", interval="15m")
            if df.empty or len(df) < 20: continue
                
            current_price = round(df['Close'].iloc[-1], 2)
            max_high = round(df['High'].iloc[-15:-1].max(), 2)
            min_low = round(df['Low'].iloc[-15:-1].min(), 2)
            trend = get_market_trend(symbol)
            atr = calculate_atr(df)
            
            if current_price <= min_low * 1.001 and trend == "BULLISH":
                sl = round(current_price - (atr * 1.5), 2)
                risk = current_price - sl
                msg = f"🛡️ **توصية شراء (SMC BUY)** 🛡️\n💱 **الزوج:** {name}\n💵 **الدخول:** {current_price}\n🛑 **الوقف:** {sl}\n🎯 **الهدف:** {round(current_price + (risk * 1.5), 2)}"
                send_telegram_message(msg)
                time.sleep(3)
            elif current_price >= max_high * 0.999 and trend == "BEARISH":
                sl = round(current_price + (atr * 1.5), 2)
                risk = sl - current_price
                msg = f"🛡️ **توصية بيع (SMC SELL)** 🛡️\n💱 **الزوج:** {name}\n💵 **الدخول:** {current_price}\n🛑 **الوقف:** {sl}\n🎯 **الهدف:** {round(current_price - (risk * 1.5), 2)}"
                send_telegram_message(msg)
                time.sleep(3)
        except Exception as e:
            print(f"خطأ في تحليل {name}: {e}")

if __name__ == "__main__":
    # تشغيل خادم الويب في خلفية الكود لكي لا يعطل حلقة الفحص
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()
    
    send_telegram_message("🤖 تم تشغيل بوت التداول المؤسسي (SMC) بنجاح على الخطة المجانية!")
    
    while True:
        try:
            analyze_smc_markets()
        except Exception as e:
            print(f"Loop error: {e}")
        time.sleep(60)
