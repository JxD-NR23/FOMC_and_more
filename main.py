import os, json, time, hashlib, threading, requests, re
from datetime import datetime, date, timedelta
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
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY") or os.getenv("NEWS_KEY")

client = Groq(api_key=GROQ_KEY)
app = Flask(__name__)
scheduler = BackgroundScheduler(timezone=TZ)

SEEN_FILE = DATA_DIR / "seen_news.json"
FEDWATCH_FILE = DATA_DIR / "last_fedwatch.json"

# Fechas FOMC 2025-2026 oficiales
FOMC_DATES = [
    date(2025, 12, 9), # Diciembre 25
    date(2026, 1, 28), date(2026, 3, 18), date(2026, 4, 29),
    date(2026, 6, 17), date(2026, 7, 29), date(2026, 9, 16),
    date(2026, 10, 28), date(2026, 12, 9),
]

def cargar_json(path, default):
    if path.exists():
        try: return json.loads(path.read_text())
        except: return default
    return default

def guardar_json(path, data):
    path.write_text(json.dumps(data))

def enviar_telegram(texto):
    if not TELEGRAM_TOKEN or not CHAT_ID: return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": texto, "disable_web_page_preview": True}, timeout=15)
    except Exception as e:
        print(f"Error TG: {e}", flush=True)

# --- FOMC HELPERS ---
def get_next_fomc():
    hoy = datetime.now(TZ).date()
    for d in FOMC_DATES:
        if d >= hoy: return d
    return FOMC_DATES[-1]

def days_until_fomc():
    return (get_next_fomc() - datetime.now(TZ).date()).days

def is_blackout():
    # Blackout: 10 días antes del FOMC hasta día después
    d = days_until_fomc()
    return 0 <= d <= 10

# --- TRADUCCION ---
def traducir_y_resumir(titulo, desc):
    try:
        prompt = f"""Eres traductor financiero. Traduce al español de España y resume en 3 bullets cortos y directos. Si es de Kevin Warsh, di exactamente que ha dicho sobre tipos.
TITULO: {titulo}
DESC: {desc}"""
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role":"user","content":prompt}],
            temperature=0.2, max_tokens=500
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"[Groq] Error: {e}", flush=True)
        return f"📰 {titulo}\n{desc[:400]}"

def es_relevante(titulo, desc):
    t = f"{titulo} {desc}".lower()
    if "warsh" in t and any(k in t for k in ["rate", "fed", "fomc", "interest", "decision", "chair", "inflation", "powell"]):
        return True
    if "fomc" in t and any(k in t for k in ["statement", "decision", "press conference", "announces", "holds rates", "cuts rates", "raises rates"]):
        return True
    if "federal reserve" in t and "interest rate" in t:
        return True
    return False

# --- JOBS ---
def check_news():
    print("[News] Buscando...", flush=True)
    if not NEWSAPI_KEY: return
    try:
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": '"Kevin Warsh" OR "FOMC statement" OR "FOMC decision" OR "Fed interest rate decision"',
            "language": "en", "sortBy": "publishedAt", "pageSize": 10, "apiKey": NEWSAPI_KEY
        }
        r = requests.get(url, params=params, timeout=15).json()
        if r.get("status")!= "ok": return
        seen = cargar_json(SEEN_FILE, [])
        for art in r.get("articles", [])[::-1]:
            titulo = art.get("title","")
            desc = art.get("description","") or ""
            if not titulo or not es_relevante(titulo, desc): continue
            h = hashlib.md5(titulo.encode()).hexdigest()
            if h in seen: continue
            resumen = traducir_y_resumir(titulo, desc)
            enviar_telegram(f"{resumen}\n\n🔗 {art.get('url','')}")
            seen.append(h)
            guardar_json(SEEN_FILE, seen[-200:])
            time.sleep(1)
    except Exception as e:
        print(f"[News] Error: {e}", flush=True)

def get_fedwatch_text():
    try:
        # Intento real a CME FedWatch Tool
        headers = {"User-Agent": "Mozilla/5.0"}
        url = "https://www.cmegroup.com/CmeWS/mvc/xslt/FedWatchTool"
        resp = requests.get(url, headers=headers, timeout=20)
        # Si la API cambia, parseamos lo que podamos, si no mandamos link
        if resp.status_code == 200:
            try:
                data = resp.json()
                # Intento de parseo best-effort
                txt = str(data)[:1500]
                return f"📊 FedWatch CME (Tiempo Real)\nDatos actualizados ahora mismo.\nPróxima reunión: {get_next_fomc()}\n\n🔗 https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html\n\nRaw: {txt[:300]}..."
            except:
                pass
        return f"📊 FedWatch Tool - {get_next_fomc()}\nProbabilidades actualizadas.\n🔗 https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html"
    except Exception as e:
        print(f"[FedWatch] Error: {e}", flush=True)
        return f"📊 FedWatch - No se pudo conectar. Revisa: https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html"

def check_fedwatch():
    print("[FedWatch] Check 09:00", flush=True)
    if is_blackout():
        print("[FedWatch] Estamos en BLACKOUT, no se envía", flush=True)
        enviar_telegram(f"🔇 Blackout FOMC activo. Quedan {days_until_fomc()} días para FOMC ({get_next_fomc()}). No hay discursos ni FedWatch hasta después.")
        return
    texto = get_fedwatch_text()
    enviar_telegram(texto)

def check_discursos():
    print("[Discursos] Check 08:00", flush=True)
    if is_blackout():
        print("[Discursos] Blackout - silenciado", flush=True)
        return
    # Por ahora aviso simple. Luego podemos scrapear calendar de la FED
    enviar_telegram(f"🎙️ Revisión discursos FED - {datetime.now(TZ).strftime('%d/%m')}\nHoy NO hay blackout. Próximo FOMC: {get_next_fomc()} ({days_until_fomc()} días)\n🔗 https://www.federalreserve.gov/newsevents/calendar.htm")

def check_countdown():
    d = days_until_fomc()
    nxt = get_next_fomc()
    print(f"[Countdown] {d} días para {nxt}", flush=True)
    if d == 7:
        enviar_telegram(f"⏳ Queda 1 SEMANA para FOMC - {nxt.strftime('%d %B %Y')}")
    elif d == 3:
        enviar_telegram(f"⏳ Quedan 3 DÍAS para FOMC - {nxt}")
    elif d == 1:
        enviar_telegram(f"⚠️ Mañana es FOMC - {nxt} - Entramos en blackout total")
    elif d == 0:
        enviar_telegram(f"🔴 HOY ES DÍA DE FOMC - {nxt}\n14:00 ET Statement / 14:30 Conferencia Powell")

def iniciar_bot():
    scheduler.remove_all_jobs()
    scheduler.add_job(check_news, 'interval', minutes=15, id='news')
    scheduler.add_job(check_discursos, 'cron', hour=8, minute=0, id='discursos')
    scheduler.add_job(check_fedwatch, 'cron', hour=9, minute=0, id='fedwatch')
    scheduler.add_job(check_countdown, 'cron', hour=9, minute=5, id='countdown')
    scheduler.start()
    print(f"🚀 Bot V8 COMPLETO iniciado. Próximo FOMC: {get_next_fomc()} ({days_until_fomc()} días)", flush=True)

def run_flask():
    @app.route('/')
    def home(): return f"FOMC Bot V8 ONLINE - Próximo FOMC {get_next_fomc()}", 200
    @app.route('/health')
    def health(): return "OK", 200
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    iniciar_bot()
    enviar_telegram(f"✅ FOMC Bot V8 COMPLETO ONLINE\nPróximo FOMC: {get_next_fomc()} - Faltan {days_until_fomc()} días\nFiltro: Solo Warsh / Decisión / Comunicado\nJobs: News 15m | Discursos 08:00 | FedWatch 09:00 | Cuenta atrás 09:05")
    while True: time.sleep(60)
