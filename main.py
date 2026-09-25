import os, requests, time
from datetime import datetime
from groq import Groq

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
NEWS_KEY = os.getenv("NEWS_KEY")
GROQ_KEY = os.getenv("GROQ_KEY")

client = Groq(api_key=GROQ_KEY)

KEYWORDS = ["kevin warsh", "fomc decision", "fed interest rate decision", "fomc statement", "fomc press conference", "fedwatch", "cme fedwatch"]
FECHAS = ["2026-01-28","2026-03-18","2026-05-06","2026-06-17","2026-07-29","2026-09-16","2026-11-04","2026-12-09"]

def ai_resumen(titulo, desc):
    p = f"Traduce al español y resume en 3 bullets cortos (hawkish/dovish, tipos): {titulo} - {desc}. Formato: TITULO_ES:... RESUMEN: -... "
    r = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"user","content":p}], temperature=0.2)
    return r.choices[0].message.content

def enviar(txt):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": txt, "parse_mode": "Markdown"})

print("BOT V4.0 INICIADO - SOLO WARSH / FOMC / FEDWATCH")
while True:
    try:
        url = f"https://newsapi.org/v2/everything?q=\"Kevin Warsh\" OR \"FOMC decision\" OR \"FedWatch\"&language=en&sortBy=publishedAt&pageSize=20&apiKey={NEWS_KEY}"
        data = requests.get(url).json()
        for art in data.get("articles", []):
            if any(k in art["title"].lower() for k in KEYWORDS):
                print(f"✅ {art['title']}")
                resumen = ai_resumen(art["title"], art.get("description",""))
                enviar(f"🚨 **FOMC / WARSH**\n\n{resumen}\n\n🔗 {art['url']}\n⏰ {datetime.now().strftime('%d/%m %H:%M')}")

        # Recordatorio fechas
        hoy = datetime.now()
        for f in FECHAS:
            dias = (datetime.strptime(f, "%Y-%m-%d") - hoy).days
            if dias in [7,1,0]:
                enviar(f"📅 **RECORDATORIO FOMC**\nQuedan {dias} dias para decision USA: {f} - 20:00 CET")

        time.sleep(900)
    except Exception as e:
        print(e)
        time.sleep(60)
