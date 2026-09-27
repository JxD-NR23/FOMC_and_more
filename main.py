import os, re, json, requests, time, threading
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from groq import Groq
from flask import Flask

# ========= CONFIG =========
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
NEWS_KEY = os.getenv("NEWS_KEY")
GROQ_KEY = os.getenv("GROQ_KEY")
TZ = ZoneInfo("Europe/Madrid")
client = Groq(api_key=GROQ_KEY)

PALABRAS_PROTEGIDAS = ["FOMC", "FED", "SEC", "BTC", "ETH", "ETF", "CPI", "PCE", "NFP", "Powell", "Warsh", "FedWatch", "CME", "USA", "BCE", "FOMC", "FEDWATCH"]

def corregir_ortografia(texto):
    if not texto or len(texto) < 20:
        return texto
    try:
        mapa = {}
        texto_temp = texto
        for i, palabra in enumerate(PALABRAS_PROTEGIDAS):
            placeholder = f"__PROT{i}__"
            texto_temp = re.sub(rf'\b{palabra}\b', placeholder, texto_temp, flags=re.IGNORECASE)
            mapa[placeholder] = palabra

        r = requests.post("https://api.languagetool.org/v2/check",
                          data={"text": texto_temp, "language": "es-ES"}, timeout=8)
        data = r.json()
        corregido = texto_temp
        for m in reversed(data.get("matches", [])[:5]): # Solo 5 primeras para no liarla
            if m.get("replacements"):
                repl = m["replacements"][0]["value"]
                if len(repl) > 2: # Evita correcciones tontas
                    inicio = m["offset"]
                    largo = m["length"]
                    corregido = corregido[:inicio] + repl + corregido[inicio+largo:]

        for placeholder, original in mapa.items():
            corregido = corregido.replace(placeholder, original)
        return corregido
    except:
        return texto

# ========= DATOS BASE =========
KEYWORDS_OBLIGATORIOS = ["kevin warsh", "fomc decision", "fed interest rate decision", "fomc statement", "fomc press conference", "fedwatch", "cme fedwatch"]
FECHAS_FOMC_BASE = ["2026-01-28","2026-03-18","2026-04-29","2026-06-17","2026-07-29","2026-09-16","2026-10-28","2026-12-09"]
DATA_FILE = "/tmp/fomc_dates.json"
noticias_enviadas = set()
ultimo_fedwatch_enviado = ""
ultimo_blackout_aviso = ""

# ========= FUNCIONES CORE =========
def enviar_telegram(texto, corregir=True):
    if corregir:
        texto = corregir_ortografia(texto)
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": texto, "parse_mode": "Markdown"}
        r = requests.post(url, json=payload, timeout=10)
        print(f"Telegram {r.status_code}", flush=True)
    except Exception as e:
        print(f"Error TG: {e}", flush=True)

def cargar_fechas_fomc():
    try:
        with open(DATA_FILE, 'r') as f:
            fechas = json.load(f)
            hoy = datetime.now(TZ).date()
            futuras = [d for d in fechas if datetime.strptime(d, "%Y-%m-%d").date() >= hoy]
            if futuras:
                return sorted(list(set(FECHAS_FOMC_BASE + fechas)))
    except:
        pass
    try:
        hoy = datetime.now(TZ)
        if len([d for d in FECHAS_FOMC_BASE if datetime.strptime(d, "%Y-%m-%d").date() >= hoy.date()]) == 0:
            año = hoy.year + 1 if hoy.month >= 11 else hoy.year
            prompt = f"Devuelve SOLO JSON array con 8 fechas FOMC {año} formato YYYY-MM-DD"
            r = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"user","content":prompt}], temperature=0)
            m = re.search(r'\[.*?\]', r.choices[0].message.content, re.DOTALL)
            if m:
                nuevas = json.loads(m.group(0))
                with open(DATA_FILE, 'w') as f:
                    json.dump(nuevas, f)
                return sorted(list(set(FECHAS_FOMC_BASE + nuevas)))
    except:
        pass
    return FECHAS_FOMC_BASE

def get_next_fomc():
    hoy = datetime.now(TZ).date()
    fechas = cargar_fechas_fomc()
    for f in sorted(fechas):
        d = datetime.strptime(f, "%Y-%m-%d").date()
        if d >= hoy:
            return d
    return None

# ========= NUEVO 1: FEDWATCH TIEMPO REAL 09:00 ESPAÑA =========
def check_fedwatch():
    global ultimo_fedwatch_enviado
    try:
        hoy_str = datetime.now(TZ).strftime("%Y-%m-%d")
        if ultimo_fedwatch_enviado == hoy_str:
            return
        # Si no son las 9h España no envia
        if datetime.now(TZ).hour!= 9:
            return

        query = "CME FedWatch probability Fed interest rate"
        url = f"https://newsapi.org/v2/everything?q={query}&language=en&sortBy=publishedAt&pageSize=5&apiKey={NEWS_KEY}"
        data = requests.get(url, timeout=10).json()
        titulo = data.get("articles", [{}])[0].get("title","")

        # Pedimos a Groq que resuma la probabilidad actual
        prompt = f"Con esta noticia '{titulo}', dime la probabilidad actual CME FedWatch para la proxima reunion FOMC el {get_next_fomc()}. Formato corto: % subida, % pausa, % bajada. Fecha hoy {hoy_str}"
        r = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"user","content":prompt}], temperature=0.2, max_tokens=200)
        resumen = r.choices[0].message.content

        next_fomc = get_next_fomc()
        msg = f"""📊 **FEDWATCH DIARIO - 09:00 España**

Próximo FOMC: {next_fomc} a las 20:00 España
{resumen}

🔗 Fuente: CME FedWatch
⏰ {datetime.now(TZ).strftime('%d/%m %H:%M')} España"""

        enviar_telegram(msg)
        ultimo_fedwatch_enviado = hoy_str
    except Exception as e:
        print(f"Error FedWatch: {e}", flush=True)

# ========= NUEVO 2: BLACKOUT FOMC (10 dias silencio) =========
def check_blackout():
    global ultimo_blackout_aviso
    try:
        next_fomc = get_next_fomc()
        if not next_fomc:
            return
        hoy = datetime.now(TZ).date()
        dias = (next_fomc - hoy).days

        if dias == 10 and ultimo_blackout_aviso!= str(next_fomc):
            enviar_telegram(f"🤫 **BLACKOUT FOMC INICIA HOY**\nDesde hoy y hasta el {next_fomc} los miembros de la FED no pueden hablar. Se acabaron pistas. Volatilidad por posicionamiento hasta decisión 20:00 España.", corregir=False)
            ultimo_blackout_aviso = str(next_fomc)
        if dias == 2:
            enviar_telegram(f"🤫 **BLACKOUT ACTIVO - 2 DIAS PARA FOMC**\nEstamos en blackout total. Sin discursos. Mercado a ciegas hasta {next_fomc} 20:00 España.", corregir=False)
    except Exception as e:
        print(f"Error blackout: {e}", flush=True)

# ========= NUEVO 3: CALENDARIO DISCURSOS =========
def check_discursos():
    try:
        if datetime.now(TZ).hour!= 8: # A las 8:00 España
            return
        # Busca discursos de hoy
        query = '"Fed speech" OR "Powell speech" OR "Warsh speech" OR "FOMC member"'
        url = f"https://newsapi.org/v2/everything?q={query}&language=en&sortBy=publishedAt&pageSize=5&apiKey={NEWS_KEY}"
        data = requests.get(url, timeout=10).json()

        for art in data.get("articles", [])[:2]:
            titulo = art.get("title","")
            if any(k in titulo.lower() for k in ["powell", "warsh", "fed"]):
                if art.get("url") in noticias_enviadas:
                    continue
                prompt = f"Traduce corto al español España: '{titulo}'. Di hora si la hay y por que es importante para tipos."
                r = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"user","content":prompt}], temperature=0.2, max_tokens=200)
                tradu = r.choices[0].message.content

                enviar_telegram(f"🎤 **DISCURSO FED HOY**\n{tradu}\n🔗 {art.get('url')}\n⏰ Revisa hora ET -> España +6h")
                noticias_enviadas.add(art.get("url"))
    except Exception as e:
        print(f"Error discursos: {e}", flush=True)

# ========= NOTICIAS Y FECHAS (LO QUE YA TENIAS) =========
def traducir_y_resumir(titulo_en, desc_en):
    try:
        prompt = f"""Eres analista FED. Titular: "{titulo_en}" Desc: "{desc_en}" Responde:
TÍTULO_ES: [traducido]
RESUMEN:
- [tipos]
- [hawkish/dovish]
- [impacto]"""
        r = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"user","content":prompt}], temperature=0.2, max_tokens=350)
        return r.choices[0].message.content
    except Exception as e:
        return f"TÍTULO_ES: {titulo_en}\nRESUMEN: Revisar"

def es_valida(titulo):
    return any(k in titulo.lower() for k in KEYWORDS_OBLIGATORIOS)

def check_news():
    try:
        query = '"Kevin Warsh" OR "FOMC decision" OR "FOMC statement" OR "FedWatch"'
        url = f"https://newsapi.org/v2/everything?q={query}&language=en&sortBy=publishedAt&pageSize=15&apiKey={NEWS_KEY}"
        data = requests.get(url, timeout=10).json()
        for art in data.get("articles", []):
            titulo = art.get("title","")
            url_art = art.get("url","")
            if url_art in noticias_enviadas or not es_valida(titulo):
                continue
            traduccion = traducir_y_resumir(titulo, art.get("description",""))
            mensaje = f"""🚨 **ALERTA FED / WARSH / FEDWATCH**
{traduccion}
📰 Original: {titulo}
🔗 {url_art}
⏰ {datetime.now(TZ).strftime('%d/%m/%Y %H:%M')} España"""
            enviar_telegram(mensaje)
            noticias_enviadas.add(url_art)
    except Exception as e:
        print(f"Error news: {e}", flush=True)

def check_fechas_fomc():
    try:
        fechas = cargar_fechas_fomc()
        hoy = datetime.now(TZ).date()
        for f in fechas:
            fecha_fomc = datetime.strptime(f, "%Y-%m-%d").date()
            dias = (fecha_fomc - hoy).days
            if dias == 7:
                enviar_telegram(f"📅 **FOMC EN 7 DÍAS - {f} 20:00 España**\nQuedan 7 días para tipos USA. Semana de posicionamiento.", corregir=False)
            if dias == 1:
                enviar_telegram(f"⏰ **MAÑANA FOMC {f} 20:00 España**\nMañana decisión. Volatilidad máxima.", corregir=False)
            if dias == 0:
                enviar_telegram(f"🔥 **HOY FOMC {f} 20:00 España**\nHOY 20:00 decisión, 20:30 Warsh. ¡Directo!", corregir=False)
    except Exception as e:
        print(f"Error fechas: {e}", flush=True)

app = Flask(__name__)
@app.route('/')
def home():
    return "BOT FOMC V6.0 - FedWatch + Discursos + Blackout + Anti-cuelgue ON"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

def main_loop():
    print("BOT V6.0 INICIADO", flush=True)
    enviar_telegram("💥 Bot FOMC V6.0 activo: Noticias + FedWatch 09:00 + Discursos 08:00 + Blackout + Auto 2027-2030 💥", corregir=False)
    while True:
        try: check_discursos()
        except: pass
        try: check_fedwatch()
        except: pass
        try: check_blackout()
        except: pass
        try: check_news()
        except: pass
        try: check_fechas_fomc()
        except: pass

        if len(noticias_enviadas) > 300:
            noticias_enviadas.clear()

        print("Durmiendo 15 min...", flush=True)
        time.sleep(900)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    main_loop()
