import os
import re
import json
import time
import hashlib
import threading
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from groq import Groq
from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler

# --- CONFIG ---
TZ = ZoneInfo("Europe/Madrid")
DATA_DIR = Path(os.getenv("DATA_DIR", "/tmp"))
DATA_DIR.mkdir(exist_ok=True)

GROQ_KEY = os.getenv("GROQ_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY") or os.getenv("NEWS_KEY") # acepta las dos

client = Groq(api_key=GROQ_KEY)
app = Flask(__name__)
scheduler = BackgroundScheduler(timezone=TZ)

SEEN_FILE = DATA_DIR / "seen_news.json"

def cargar_seen():
    if SEEN_FILE.exists():
        try: return json.loads(SEEN_FILE.read_text())
        except: return []
    return []

def guardar_seen(lista):
    SEEN_FILE.write_text(json.dumps(lista[-200:]))

def enviar_telegram(texto: str):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={
            "chat_id": CHAT_ID,
            "text": texto,
            "disable_web_page_preview": True
        }, timeout=15)
    except Exception as e:
        print(f"Error Telegram: {e}")

def traducir_y_resumir(titulo, desc):
    try:
        prompt = f"""Traduce al español y resume en 3 bullets muy cortos esta noticia sobre la FED/FOMC.
        Título: {titulo}
        Descripción: {desc}
        Formato:
        📰 [Titulo traducido]
        • punto 1
        • punto 2
        • punto 3
        """
        resp = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        return resp.choices[0].message.content
    except Exception as e:
        return f"📰 {titulo}\n{desc[:250]}"

def check_news():
    print("[News] Buscando...", flush=True)
    if not NEWSAPI_KEY:
        print("[News] Falta NEWSAPI_KEY", flush=True)
        return
    try:
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": "FOMC OR Federal Reserve OR Powell",
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 5,
            "apiKey": NEWSAPI_KEY
        }
        r = requests.get(url, params=params, timeout=15).json()
        if r.get("status")!= "ok":
            print(f"[News] Error API: {r}", flush=True)
            return

        seen = cargar_seen()
        for art in r.get("articles", [])[::-1]: # del más viejo al nuevo
            titulo = art.get("title","")
            h = hashlib.md5(titulo.encode()).hexdigest()
            if h in seen: continue

            desc = art.get("description","") or ""
            texto_final = traducir_y_resumir(titulo, desc)
            texto_final += f"\n\n🔗 {art.get('url','')}"
            enviar_telegram(texto_final)
            seen.append(h)
            guardar_seen(seen)
            time.sleep(2) # para no saturar telegram
    except Exception as e:
        print(f"[News] Error: {e}", flush=True)

def check_fedwatch():
    # Aquí va tu lógica de FedWatch 09:00
    print("[FedWatch] Check", flush=True)
    # enviar_telegram("📊 FedWatch...")

def check_discursos():
    print("[Discursos] Check", flush=True)

def iniciar_bot():
    scheduler.remove_all_jobs()
    scheduler.add_job(check_news, 'interval', minutes=15, id='news')
    scheduler.add_job(check_fedwatch, 'cron', hour=9, minute=0, id='fedwatch')
    scheduler.add_job(check_discursos, 'cron', hour=8, minute=0, id='discursos')
    scheduler.start()
    print("🚀 Bot V7.1 iniciado con APScheduler", flush=True)

def run_flask():
    @app.route('/')
    def home(): return "FOMC Bot V7.1 ONLINE", 200
    @app.route('/health')
    def health(): return "OK", 200
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    iniciar_bot()
    enviar_telegram("✅ FOMC Bot V7.1 ONLINE - operativo")
    while True:
        time.sleep(60)
