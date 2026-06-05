from flask import Flask, request
import requests

app = Flask(__name__)

# التوكن وقناتك مضافين بشكل صحيح وجاهز
BOT_TOKEN = "8830911482:AAFnxsHB7uFLWxEtrc1KsGe6Txk5un6KUnk"
CHAT_ID = "@Forex_signals"

@app.route('/webhook', methods=['POST'])
def telegram_webhook():
    try:
        data = request.json
        if not data:
            return "No data", 400
            
        action = data.get('action', 'buy').lower()
        if action == 'buy':
            action_title = "🟢 شراء ذكي (SMC BUY)"
            zone_type = "منطقة طلب مؤسسية (Demand Order Block)"
            confirmation = "تغيير اتجاه صاعد (CHoCH الصاعد)"
        else:
            action_title = "🔴 بيع ذكي (SMC SELL)"
            zone_type = "منطقة عرض مؤسسية (Supply Order Block)"
            confirmation = "تغيير اتجاه هابط (CHoCH الهابط)"
            
        message = f"""🛡️ **توصية SMC عالية الدقة (مخاطرة منخفضة)** 🛡️
━━━━━━━━━━━━━━━━━━
💱 **الأداة/الزوج:** {data.get('pair', 'GOLD')}
📈 **نوع الصفقة:** {action_title}
🎯 **إستراتيجية:** هيرمز للمضاربة المتزنة (SMC)
━━━━━━━━━━━━━━━━━━
🔍 **شروط التأكيد المحققة تلقائياً:**
1. السعر ارتد من {zone_type}.
2. تم رصد سيولة وتأكيد كسر البنية {confirmation}.
3. نسبة المخاطرة إلى العائد متزنة (1:2 حداً أدنى).

💵 **سعر الدخول (Entry):** {data.get('entry', 'N/A')}

🛑 **وقف الخسارة (SL):** {data.get('sl', 'N/A')}
🎯 **الهدف الأول (TP1):** {data.get('tp1', 'N/A')}
🎯 **الهدف الثاني (TP2):** {data.get('tp2', 'N/A')}
━━━━━━━━━━━━━━━━━━
⚠️ **إدارة رأس المال:** خاطر بـ 1% فقط من حسابك لكل صفقة.
⚡ _نظام أوتوماتيكي منتقى بعناية لتقليل الانعكاس._"""
        
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }
        requests.post(url, json=payload)
        return "Success", 200

    except Exception as e:
        print(f"Error: {e}")
        return "Error", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
