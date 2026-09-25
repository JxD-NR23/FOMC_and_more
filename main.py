# BOT FOMC V3.1 - FINAL CORREGIDO - KEVIN WARSH PRESIDENTE
import os, requests, time, telebot
from groq import Groq
from flask import Flask
import threading

# Print ANTES de todo para saber si el archivo se ejecuta
print(">>> main.py cargado...", flush=True)

app = Flask(__name__)
@app.route('/')
def home():
    return "Bot FOMC v3.1 ON - Kevin Warsh - Activo"

def run_web():
    print(">>> Flask arrancando en puerto 10000...", flush=True)
    app.run(host='0.0.0.0', port=10000)

threading.Thread(target=run_web, daemon=True).start()
time.sleep(2) # dejamos que Flask arranque

# --- LEER CLAVES CON COMPROBACIÓN ---
print(">>> Leyendo claves...", flush=True)
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
GROQ_KEY = os.getenv("GROQ_KEY")
NEWS_KEY = os.getenv("NEWS_KEY")

# Si falta alguna, lo decimos en Logs y no crasheamos a lo loco
if not TOKEN: print("!!! FALTA TELEGRAM_TOKEN en Render > Environment!!!", flush=True)
if not CHAT_ID: print("!!! FALTA CHAT_ID!!!", flush=True)
if not GROQ_KEY: print("!!! FALTA GROQ_KEY!!!", flush=True)
if not NEWS_KEY: print("!!! FALTA NEWS_KEY!!!", flush=True)

try:
    bot = telebot.TeleBot(TOKEN)
    ia = Groq(api_key=GROQ_KEY)
    print(">>> Clientes Telegram y Groq OK", flush=True)
except Exception as e:
    print(f"!!! ERROR INICIANDO CLIENTES: {e}!!!", flush=True)
    # No seguimos si no hay claves
    time.sleep(999999)

enviados = set()

def es_relevante_y_traducir(titulo, desc):
    prompt = f"""Eres analista español.
Noticia: "{titulo} - {desc}"
Presidente FED: Kevin Warsh desde Mayo 2026. Powell NO es presidente.
¿Es REALMENTE sobre FED/FOMC/Warsh/tipos EEUU?
Si es béisbol, Sensex, Trump-Xi sin FED -> NO.
Si es SI, traduce al español de España y di en 2 líneas si es bueno/malo para BOLSA y BITCOIN.
Formato:
SI
[traduccion]
O
NO
"""
    try:
        r = ia.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"user","content":prompt}], temperature=0.2)
        txt = r.choices[0].message.content.strip()
        return txt[2:].strip() if txt.upper().startswith("SI") else None
    except Exception as e:
        print(f"Error Groq: {e}", flush=True)
        return None

def buscar_noticias():
    q = '"Federal Reserve" OR "FOMC" OR "Kevin Warsh"'
    url = f"https://newsapi.org/v2/everything?q={q}&language=en&sortBy=publishedAt&pageSize=10&apiKey={NEWS_KEY}"
    try:
        return requests.get(url, timeout=15).json().get('articles', [])
    except Exception as e:
        print(f"Error NewsAPI: {e}", flush=True)
        return []

# --- BUCLE PRINCIPAL ---
print("=================================================", flush=True)
print("Bot FOMC v3.1 iniciado - Presidente Kevin Warsh", flush=True)
print("=================================================", flush=True)

while True:
    try:
        arts = buscar_noticias()
        print(f">>> NewsAPI devolvió {len(arts)} artículos", flush=True)
        for n in arts:
            titulo = n['title']
            if titulo not in enviados:
                print(f"Analizando: {titulo[:90]}", flush=True)
                res = es_relevante_y_traducir(titulo, n.get('description',''))
                if res:
                    bot.send_message(CHAT_ID, f"🚨 *FED - Warsh* 🚨\n\n{res}\n\n📰 {titulo}\n🔗 {n['url']}", parse_mode='Markdown')
                    print(f"✅ ENVIADO", flush=True)
                else:
                    print(f"❌ DESCARTADO (no es FED)", flush=True)
                enviados.add(titulo)
        print("Durmiendo 15 min...", flush=True)
        time.sleep(900)
    except Exception as e:
        print(f"Error bucle: {e}", flush=True)
        time.sleep(60)
