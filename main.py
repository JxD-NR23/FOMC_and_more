import os, requests, time, telebot
from groq import Groq
from datetime import datetime

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
GROQ_KEY = os.getenv("GROQ_KEY")
NEWS_KEY = os.getenv("NEWS_KEY")

bot = telebot.TeleBot(TOKEN)
ia = Groq(api_key=GROQ_KEY)
enviados = set()

def traducir(texto):
    try:
        r = ia.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role":"user","content":f"Traduce al español de España y dime en 2 líneas si es bueno o malo para bolsa y bitcoin. Simple y directo. Texto: {texto}"}]
        )
        return r.choices[0].message.content
    except Exception as e:
        print(f"Error IA: {e}")
        return texto

def noticias_fomc():
    url = f"https://newsapi.org/v2/everything?q=FED OR FOMC OR Powell&language=en&sortBy=publishedAt&pageSize=5&apiKey={NEWS_KEY}"
    try:
        data = requests.get(url).json()
        return data.get('articles', [])
    except:
        return []

print("Bot FOMC iniciado...")
while True:
    try:
        noticias = noticias_fomc()
        for n in noticias:
            titulo = n['title']
            if titulo not in enviados:
                desc = n.get('description') or ""
                traduccion = traducir(titulo + " - " + desc[:200])
                msg = f"🚨 NOTICIA FED/FOMC 🚨\n\n{traduccion}\n\n📰 Original: {titulo}\n🔗 {n['url']}"
                bot.send_message(CHAT_ID, msg)
                enviados.add(titulo)

        print(f"Revisado: {datetime.now()}")
        time.sleep(1800)
    except Exception as e:
        print(f"Error {e}")
        time.sleep(60)
