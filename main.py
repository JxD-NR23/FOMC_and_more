import os, requests, time, telebot
from groq import Groq
from flask import Flask
import threading

app = Flask(__name__)
@app.route('/')
def home(): return "Bot FOMC v2 ON - filtrado"
threading.Thread(target=lambda: app.run(host='0.0.0.0', port=10000), daemon=True).start()

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
GROQ_KEY = os.getenv("GROQ_KEY")
NEWS_KEY = os.getenv("NEWS_KEY")

bot = telebot.TeleBot(TOKEN)
ia = Groq(api_key=GROQ_KEY)
enviados = set()

def es_relevante_y_traducir(titulo, desc):
    prompt = f"""
Analiza esta noticia: "{titulo} - {desc}"

1. ¿Es REALMENTE sobre la FED, FOMC, Powell o tipos de interés de EEUU?
Responde SOLO SI o NO al inicio.
Si es sobre béisbol, cricket indio (Sensex), o Trump-Xi sin mencionar a la FED, di NO.

2. Si es SI, traduce al español de España y explica en 2 líneas simples:
- Que ha pasado
- Si es bueno/malo para BOLSA y BITCOIN

Formato:
SI
[Traducción + explicación en español]
"""
    try:
        r = ia.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role":"user","content": prompt}],
            temperature=0.3
        )
        txt = r.choices[0].message.content.strip()
        if txt.upper().startswith("SI"):
            return txt[2:].strip()
        else:
            return None
    except Exception as e:
        print("Error Groq:", e)
        return None

def buscar():
    # Búsqueda MUCHO más estricta
    url = f"https://newsapi.org/v2/everything?q=\"Federal Reserve\" OR \"FOMC\" OR \"Jerome Powell\"&language=en&sortBy=publishedAt&pageSize=10&apiKey={NEWS_KEY}"
    try:
        data = requests.get(url, timeout=10).json()
        return data.get('articles', [])
    except:
        return []

print("Bot FOMC v2 iniciado - con filtro IA...")
while True:
    try:
        for n in buscar():
            titulo = n['title']
            if titulo not in enviados:
                desc = n.get('description') or ""
                resultado = es_relevante_y_traducir(titulo, desc)
                if resultado: # Solo envía si la IA dijo SI
                    msg = f"🚨 *FED/FOMC REAL* 🚨\n\n{resultado}\n\n📰 {titulo}\n🔗 {n['url']}"
                    bot.send_message(CHAT_ID, msg, parse_mode='Markdown')
                    print(f"Enviado: {titulo}")
                else:
                    print(f"Descartado (basura): {titulo}")
                enviados.add(titulo)
        time.sleep(900) # cada 15 min
    except Exception as e:
        print(e)
        time.sleep(60)
