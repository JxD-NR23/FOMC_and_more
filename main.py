import os, re, json, requests, time, threading, hashlib
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from groq import Groq
from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler

TZ = ZoneInfo("Europe/Madrid")
DATA_DIR = Path(os.getenv("DATA_DIR", "/tmp"))
DATA_FILE = DATA_DIR / "fomc_state.json"
DATA_DIR.mkdir(parents=True, exist_ok=True)

client = Groq(api_key=os.getenv("GROQ_KEY"))
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")

PALABRAS_PROTEGIDAS = ["FOMC", "FED", "SEC", "BTC", "ETH", "ETF", "CPI", "PCE", "NFP", "Powell", "Warsh", "FedWatch", "CME", "USA", "BCE", "FOMC", "FEDWATCH"]

def corregir_ortografia(texto: str) -> str:
    mapa = {}
    for palabra in sorted(PALABRAS_PROTEGIDAS, key=len, reverse=True):
        ph = f"__{palabra.upper().replace(' ', '_')}__"
        if re.search(re.escape(palabra), texto, re.IGNORECASE):
            mapa[ph] = palabra
            texto = re.sub(re.escape(palabra), ph, texto, flags=re.IGNORECASE)
    try:
        resp = requests.post("https://api.languagetool.org/v2/check", data={"text": texto, "language": "es-ES"}, timeout=10)
        for m in sorted(resp.json().get("matches", [])[:4], key=lambda x: x["offset"], reverse=True):
            if m.get("replacements"):
                o, l = m["offset"], m["length"]
                texto = texto[:o] + m["replacements"][0]["value"] + texto[o+l:]
    except: pass
    for ph, orig in mapa.items():
        texto = texto.replace(ph, orig)
    return texto

def load_state():
    if DATA_FILE.exists():
        try: return json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except: pass
    return {"enviadas": [], "fedwatch": "", "fomc_alerts": []}

state = load_state()
noticias_enviadas = set(state.get("enviadas", []))
lock = threading.Lock()

def save_state():
    with lock:
        state["enviadas"] = list(noticias_enviadas)[-500:]
        DATA_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

def enviar_telegram(texto: str):
    # FIX: sin parse_mode para que no pete si Groq mete un *
    if not TELEGRAM_TOKEN or not CHAT_ID: return
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                      json={"chat_id": CHAT_ID, "text": texto, "disable_web_page_preview": True}, timeout=15)
    except Exception as e:
        print(f"[TG] Error: {e}")

FECHAS_FOMC = ["2026-01-28","2026-03-18","2026-04-29","2026-06-17","2026-07-29","2026-09-16","2026-10-28","2026-12-09"]

def en_blackout(hoy: datetime) -> bool:
    for f in FECHAS_FOMC:
        fomc = datetime.fromisoformat(f).replace(tzinfo=TZ)
        if 0 <= (fomc.date() - hoy.date()).days <= 10: return True
    return False

def check_fedwatch():
    print(f"[FedWatch] {datetime.now(TZ)}")
    prompt = "Si no tienes datos reales de CME FedWatch hoy, responde exactamente NO_DISPONIBLE. No inventes porcentajes."
    try:
        r = client.chat.completions.create(model="llama-3.1-8b-instant", messages=[{"role":"user","content":prompt}], temperature=0.1)
        txt = r.choices[0].message.content.strip()
        if "NO_DISPONIBLE" in txt or txt == state.get("fedwatch"): return
        state["fedwatch"] = txt
        save_state()
        enviar_telegram(f"📊 FedWatch 09:00 ES\n{txt}")
    except Exception as e: print(e)

def traducir_y_resumir(titulo: str, desc: str):
    prompt = f"""Eres traductor FED para Telegram España. Resume en 3 bullets máx. Si NO es sobre FED/FOMC/tipos USA responde IGNORAR.
Título: {titulo} Desc: {desc}"""
    try:
        r = client.chat.completions.create(model="llama-3.1-8b-instant", messages=[{"role":"user","content":prompt}], temperature=0.2)
        txt = r.choices[0].message.content.strip()
        return None if "IGNORAR" in txt.upper() else corregir_ortografia(txt)
    except: return None

def check_news(query="FOMC OR Federal Reserve"):
    if not NEWSAPI_KEY: return
    try:
        r = requests.get("https://newsapi.org/v2/everything", params={"q": query, "language": "en", "sortBy": "publishedAt", "pageSize": 5}, headers={"X-Api-Key": NEWSAPI_KEY}, timeout=15)
        for art in r.json().get("articles", []):
            titulo = art.get("title","")
            # FIX: hashlib en vez de hash()
            h = hashlib.sha256(titulo.encode()).hexdigest()[:16]
            if h in noticias_enviadas: continue
            resumen = traducir_y_resumir(titulo, art.get("description",""))
            if not resumen: continue
            enviar_telegram(f"{resumen}\n\n🔗 {art.get('url','')}")
            noticias_enviadas.add(h)
            save_state()
            time.sleep(2)
    except Exception as e: print(f"[News] {e}")

def check_discursos():
    if en_blackout(datetime.now(TZ)): return
    check_news(query="Federal Reserve speech Powell")

def check_fechas_fomc():
    hoy = datetime.now(TZ).date()
    for f in FECHAS_FOMC:
        dias = (datetime.fromisoformat(f).date() - hoy).days
        if dias in [7,3,1,0]:
            clave = f"{dias}d_{f}"
            if clave in state.get("fomc_alerts",[]): continue
            enviar_telegram(f"⏰ FOMC en {dias} días - {f} 20:00 España")
            state.setdefault("fomc_alerts", []).append(clave)
            save_state()

app = Flask(__name__)
@app.route("/")
def home(): return "✅ FOMC Bot V7.1 ONLINE"

def run_flask():
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))

scheduler = BackgroundScheduler(timezone=TZ)

def iniciar_bot():
    scheduler.add_job(check_fedwatch, 'cron', hour=9, minute=0, id="fedwatch", replace_existing=True, coalesce=True, max_instances=1, misfire_grace_time=300)
    scheduler.add_job(check_discursos, 'cron', hour=8, minute=0, id="discursos", replace_existing=True, coalesce=True, max_instances=1)
    scheduler.add_job(check_news, 'interval', minutes=15, id="news", replace_existing=True, coalesce=True, max_instances=1, misfire_grace_time=300)
    scheduler.add_job(check_fechas_fomc, 'cron', hour=9, minute=5, id="fechas", replace_existing=True)
    scheduler.start()

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    iniciar_bot()
    while True: time.sleep(60)
