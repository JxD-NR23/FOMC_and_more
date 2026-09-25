import os, requests, time, telebot
from groq import Groq
from datetime import datetime
from flask import Flask
import threading

# --- Truco para que Render no apague el free ---
app = Flask(__name__)
@app.route('/')
def home(): return "Bot FOMC 24/7 ON"
def run_web():
    app.run(host='0.0.0.0', port=10000)
threading.Thread(target=run_web, daemon=True).start()
# --- Fin truco ---

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
    except:
        return texto

def noticias_fomc():
    url = f"https://newsapi.org/v2/everything?q=FED OR FOMC OR Powell&language=en&sortBy=publishedAt&pageSize=5&apiKey={NEWS_KEY}"
    try:
        return requests.get(url).json().get('articles', [])
    except:
        return []

print("Bot FOMC iniciado...")
while True:
    try:
        for n in noticias_fomc():
            if n['title'] not in enviados:
                t = traducir(n['title'] + " - " + (n.get('description') or "")[:200])
                msg = f"🚨 FED/FOMC 🚨\n\n{t}\n\n📰 {n['title']}\n🔗 {n['url']}"
                bot.send_message(CHAT_ID, msg)
                enviados.add(n['title'])
        time.sleep(1800)
    except Exception as e:
        print(e)
        time.sleep(60)
