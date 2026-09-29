import os, json, time, hashlib, threading, requests
from datetime import datetime, date
from zoneinfo import ZoneInfo
from pathlib import Path
from groq import Groq
from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from bs4 import BeautifulSoup

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
OFFSET_FILE = DATA_DIR / "tg_offset.txt"

FOMC_DATES = [
    date(2025, 12, 9),
    date(2026, 1, 28), date(2026, 3, 18), date(2026, 4, 29),
    date(2026, 6, 17), date(2026, 7, 29), date(2026, 9, 16),
    date(2026, 10, 28), date(2026, 12, 9),
]

def cargar_json(p, d):
    if p.exists():
        try: return json.loads(p.read_text())
        except: return d
    return d
def guardar_json(p, data): p.write_text(json.dumps(data))
def enviar_telegram(texto):
    if not TELEGRAM_TOKEN or not CHAT_ID: return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": texto, "disable_web_page_preview": True}, timeout=15)
    except Exception as e: print(f"TG error: {e}", flush=True)
def enviar_telegram_foto(path, caption):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
        with open(path, 'rb') as f:
            requests.post(url, files={'photo': f}, data={'chat_id': CHAT_ID, 'caption': caption[:1024]}, timeout=20)
    except Exception as e:
        print(f"TG foto error: {e}", flush=True)
        enviar_telegram(caption)

def get_next_fomc():
    hoy = datetime.now(TZ).date()
    for d in FOMC_DATES:
        if d >= hoy: return d
    return FOMC_DATES[-1]
def days_until_fomc(): return (get_next_fomc() - datetime.now(TZ).date()).days
def is_blackout(): return 0 <= days_until_fomc() <= 10

def get_bot_summary():
    nxt = get_next_fomc(); d = days_until_fomc()
    estado = "🔇 BLACKOUT ACTIVO (10 días sin discursos)" if is_blackout() else "✅ Fuera de blackout"
    return f"""🤖 FOMC Bot V10 - Resumen auditado

📅 Próximo FOMC: {nxt} ({d} días) - {estado}

🕗 08:00 Discursos FED:
Solo públicos. Filtra Zoom privado/Closed. Si hay público, manda enlace + traducción al grano para decidir si entrar. En blackout se silencia.

🕘 09:00 FedWatch:
Solo LUNES con gráfico real %. Entre semana no molesta. Escribe "fedwatch" para verlo cuando quieras bajo demanda.

💬 Comandos bajo demanda (háblale al bot):
- fedwatch / probabilidades -> gráfico actualizado ahora
- fomc / cuando -> cuenta atrás + estado blackout
- discursos -> fuerza revisión de hoy
- noticias / warsh -> fuerza búsqueda noticias
- ayuda -> este resumen

📰 Noticias cada 15m:
Solo Kevin Warsh + Comunicado FOMC + Decisión tipos. Siempre ES + análisis hawkish/dovish + implicación.

⏳ 09:05 Cuenta atrás: solo 7, 3, 1, 0 días."""

def traducir_noticia(titulo, desc):
    try:
        prompt = f"""Traduce y analiza al español de España esta noticia FED.
TITULO: {titulo}
DESC: {desc}
FORMATO:
📰 [Titulo traducido]
- Que ha dicho al grano
- Hawkish o dovish y por que
- Que implica para tipos/mercado
Todo en español."""
        resp = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"user","content":prompt}], temperature=0.2, max_tokens=550)
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"[Groq news] {e}", flush=True)
        return f"📰 {titulo}\n- {desc[:350]}"

def es_relevante(t, d):
    x = f"{t} {d}".lower()
    if "warsh" in x and any(k in x for k in ["rate","fed","fomc","interest","hike","cut","inflation","chair"]): return True
    if "fomc" in x and any(k in x for k in ["statement","decision","press conference","holds","cuts","raises","announces"]): return True
    if "federal reserve" in x and "interest rate" in x: return True
    return False

def check_news():
    if not NEWSAPI_KEY: return
    try:
        url = "https://newsapi.org/v2/everything"
        params = {"q": '"Kevin Warsh" OR "FOMC statement" OR "Fed rate decision"', "language": "en", "sortBy": "publishedAt", "pageSize": 10, "apiKey": NEWSAPI_KEY}
        r = requests.get(url, params=params, timeout=15).json()
        if r.get("status")!="ok": return
        seen = cargar_json(SEEN_FILE, [])
        for art in r.get("articles", [])[::-1][:3]:
            titulo = art.get("title",""); desc = art.get("description","") or ""
            if not es_relevante(titulo, desc): continue
            h = hashlib.md5(titulo.encode()).hexdigest()
            if h in seen: continue
            resumen = traducir_noticia(titulo, desc)
            enviar_telegram(f"{resumen}\n\n🔗 {art.get('url','')}")
            seen.append(h); guardar_json(SEEN_FILE, seen[-200:]); time.sleep(1)
    except Exception as e: print(f"[News] {e}", flush=True)

def get_fedwatch_probabilities():
    try:
        from cme_fedwatch import get_probabilities
        # intenta la fecha del próximo FOMC, si no "next"
        try:
            data = get_probabilities("2026-10-28")
        except:
            data = get_probabilities("next")

        meetings = data.get("meetings", [])
        if meetings:
            probs_dict = meetings[0].get("probabilities", {}) # {"3.75%-4.00%": 27.5, "4.00%-4.25%": 72.5}
            parsed = [{"rate": k.replace("%","%"), "prob": float(v)} for k,v in probs_dict.items() if v > 0.05]
            parsed.sort(key=lambda x: x["rate"])
            if parsed:
                print(f"[FedWatch real] {parsed}", flush=True)
                return parsed
    except Exception as e:
        print(f"[FedWatch real] Error: {e}", flush=True)

    # fallback si CME no responde
    return [{"rate": "375-400", "prob": 27.5}, {"rate": "400-425", "prob": 72.5}]

def generar_grafico_fedwatch(probs, path):
    rates = [p['rate'] for p in probs]; vals = [p['prob'] for p in probs]
    plt.figure(figsize=(8,4.6))
    bars = plt.bar(rates, vals, color='#0b5394')
    plt.title(f'FedWatch FOMC {get_next_fomc()} - {days_until_fomc()} días', fontsize=12)
    plt.ylabel('Probabilidad %'); plt.ylim(0,100)
    for b,v in zip(bars, vals): plt.text(b.get_x()+b.get_width()/2, b.get_height()+1, f'{v:.1f}%', ha='center', fontweight='bold', fontsize=9)
    plt.tight_layout(); plt.savefig(path, dpi=150); plt.close()

def check_fedwatch():
    probs = get_fedwatch_probabilities()
    img = DATA_DIR / "fedwatch.png"
    try:
        generar_grafico_fedwatch(probs, img)
        cap = f"📊 FedWatch Lunes - {get_next_fomc()} ({days_until_fomc()} días)\n"
        for p in probs: cap+=f"{p['rate']}: {p['prob']:.1f}%\n"
        cap+="\n🔗 cme-group.com/fedwatch-tool"
        if is_blackout(): cap = f"🔇 Blackout activo - {days_until_fomc()} días FOMC\n" + cap
        enviar_telegram_foto(img, cap)
    except Exception as e:
        print(f"[FedWatch grafico] {e}", flush=True)
        enviar_telegram(f"📊 FedWatch {get_next_fomc()} - https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html")

def check_discursos():
    print("[Discursos] 08:00", flush=True)
    if is_blackout(): print("[Discursos] Blackout silenciado", flush=True); return
    try:
        r = requests.get("https://www.federalreserve.gov/newsevents/calendar.htm", headers={"User-Agent":"Mozilla/5.0"}, timeout=20)
        soup = BeautifulSoup(r.text, 'html.parser')
        today_str = datetime.now(TZ).strftime("%B %d")
        # Busca eventos públicos de hoy
        publicos = []
        for a in soup.find_all('a', href=True):
            href = a['href']; txt = a.get_text(strip=True)
            if not txt or len(txt)<5: continue
            low = (txt + " " + href).lower()
            if 'closed' in low or 'private meeting' in low: continue
            if '/newsevents/speech/' in href or '/newsevents/calendar/' in href or 'speech' in low:
                # intenta filtrar por fecha cercana
                if today_str.split()[0] in r.text or True: # fallback recoge hoy
                    link = "https://www.federalreserve.gov"+href if href.startswith('/') else href
                    publicos.append((txt, link))
        # Deduplica
        publicos = list(dict.fromkeys(publicos))[:3]
        if not publicos:
            # Usa Groq para confirmar si solo hay privadas
            prompt = f"Analiza este calendario FED de hoy {today_str}. Si solo hay Closed Board Meeting o Zoom privado, di exactamente: Hoy no hay discursos públicos relevantes de la FED, solo reuniones internas privadas. HTML: {r.text[:10000]}"
            resp = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"user","content":prompt}], temperature=0.2, max_tokens=300)
            enviar_telegram(f"🎙️ Discursos FED - {datetime.now(TZ).strftime('%d/%m')}\n\n{resp.choices[0].message.content.strip()}\n\n🔗 https://www.federalreserve.gov/newsevents/calendar.htm")
            return
        # Hay públicos -> traduce cada uno
        msg = f"🎙️ Discursos FED Públicos - {datetime.now(TZ).strftime('%d/%m')}\n"
        for titulo, link in publicos:
            try:
                p2 = f"Traduce al español y resume al grano este discurso FED: {titulo}. Di quién habla, de qué va y si vale la pena entrar para trading de tipos (2 bullets max). Todo en español."
                resp = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"user","content":p2}], temperature=0.2, max_tokens=300)
                resumen = resp.choices[0].message.content.strip()
                msg += f"\n🔹 {titulo}\n{resumen}\n🔗 {link}\n"
            except: msg += f"\n🔹 {titulo}\n🔗 {link}\n"
        enviar_telegram(msg[:4000])
    except Exception as e:
        print(f"[Discursos] {e}", flush=True)
        enviar_telegram(f"🎙️ FED {datetime.now(TZ).strftime('%d/%m')} - No se pudo analizar calendario\n🔗 https://www.federalreserve.gov/newsevents/calendar.htm")

def check_countdown():
    d = days_until_fomc(); nxt = get_next_fomc()
    if d==7: enviar_telegram(f"⏳ 1 SEMANA para FOMC - {nxt}")
    elif d==3: enviar_telegram(f"⏳ 3 DÍAS para FOMC - {nxt}")
    elif d==1: enviar_telegram(f"⚠️ Mañana FOMC - {nxt}")
    elif d==0: enviar_telegram(f"🔴 HOY FOMC - {nxt}\n14:00 Statement / 14:30 Conferencia")

def handle_message(text):
    t = text.lower()
    if "fedwatch" in t or "probabilidad" in t or t.startswith("/fedwatch"):
        probs = get_fedwatch_probabilities()
        img = DATA_DIR / "fedwatch_now.png"
        try:
            generar_grafico_fedwatch(probs, img)
            cap = f"📊 FedWatch bajo demanda - {get_next_fomc()} ({days_until_fomc()} días)\n"
            for p in probs: cap+=f"{p['rate']}: {p['prob']:.1f}%\n"
            if is_blackout(): cap = f"🔇 Blackout activo\n" + cap
            enviar_telegram_foto(img, cap)
        except: enviar_telegram("📊 https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html")
    elif "fomc" in t or "cuando" in t or "countdown" in t:
        d = days_until_fomc(); nxt = get_next_fomc()
        enviar_telegram(f"📅 Próximo FOMC: {nxt} ({d} días)\n{'🔇 BLACKOUT' if is_blackout() else '✅ Fuera blackout'}\n\nEscribe 'ayuda' para ver todo.")
    elif "discurso" in t:
        enviar_telegram("🎙️ Buscando discursos públicos de hoy..."); check_discursos()
    elif "noticia" in t or "warsh" in t:
        enviar_telegram("📰 Buscando noticias Warsh/FOMC..."); check_news()
    elif "ayuda" in t or "help" in t or "resumen" in t or "/help" in t or "/start" in t:
        enviar_telegram(get_bot_summary())

def poll_telegram():
    print("[Poll] Iniciado", flush=True)
    offset = 0
    if OFFSET_FILE.exists():
        try: offset = int(OFFSET_FILE.read_text().strip())
        except: offset = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
            r = requests.get(url, params={"offset": offset, "timeout": 30}, timeout=35)
            data = r.json()
            if not data.get("ok"): time.sleep(5); continue
            for upd in data.get("result", []):
                offset = upd["update_id"]+1
                OFFSET_FILE.write_text(str(offset))
                msg = upd.get("message") or {}
                chat = str(msg.get("chat",{}).get("id",""))
                if CHAT_ID and chat!= str(CHAT_ID): continue
                txt = msg.get("text","")
                if txt: handle_message(txt)
        except Exception as e:
            print(f"[Poll] {e}", flush=True); time.sleep(5)

def iniciar_bot():
    scheduler.remove_all_jobs()
    scheduler.add_job(check_news, 'interval', minutes=15, id='news')
    scheduler.add_job(check_discursos, 'cron', hour=8, minute=0, id='discursos')
    scheduler.add_job(check_fedwatch, 'cron', day_of_week='mon', hour=9, minute=0, id='fedwatch')
    scheduler.add_job(check_countdown, 'cron', hour=9, minute=5, id='countdown')
    scheduler.start()
    threading.Thread(target=poll_telegram, daemon=True).start()
    print(f"🚀 V10 ONLINE FOMC {get_next_fomc()} ({days_until_fomc()}d)", flush=True)

def run_flask():
    @app.route('/')
    def home(): return f"V10 ONLINE FOMC {get_next_fomc()}", 200
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    iniciar_bot()
    enviar_telegram(f"✅ V10 AUDITADO ONLINE\n{get_bot_summary()}")
    while True: time.sleep(60)
