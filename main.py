import os, re, json, requests, time, threading
from datetime import datetime
from zoneinfo import ZoneInfo
from groq import Groq
from flask import Flask

# ========= 1. CORRECCIÓN ORTOGRÁFICA INTELIGENTE =========
# No toca siglas ni tickers
PALABRAS_PROTEGIDAS = ["FOMC", "FED", "SEC", "BTC", "ETH", "ETF", "CPI", "PCE", "NFP", "Powell", "Warsh", "FedWatch", "CME", "USA"]

def corregir_ortografia(texto):
    if not texto:
        return texto
    try:
        # Protegemos siglas con placeholders
        mapa = {}
        for i, palabra in enumerate(PALABRAS_PROTEGIDAS):
            placeholder = f"__PROT{i}__"
            # Reemplaza sin importar mayúsculas/minúsculas
            texto = re.sub(palabra, placeholder, texto, flags=re.IGNORECASE)
            mapa[placeholder] = palabra

        r = requests.post("https://api.languagetool.org/v2/check",
                          data={"text": texto, "language": "es-ES"},
                          timeout=15)
        data = r.json()
        corregido = texto
        for m in reversed(data.get("matches", [])):
            if m.get("replacements"):
                repl = m["replacements"][0]["value"]
                inicio = m["offset"]
                largo = m["length"]
                corregido = corregido[:inicio] + repl + corregido[inicio+largo:]

        # Devolvemos las siglas
        for placeholder, original in mapa.items():
            corregido = corregido.replace(placeholder, original)
        return corregido
    except:
        return texto

# ========= 2. CONFIG =========
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
NEWS_KEY = os.getenv("NEWS_KEY")
GROQ_KEY = os.getenv("GROQ_KEY")
TZ = ZoneInfo("Europe/Madrid") # Hora España
client = Groq(api_key=GROQ_KEY)

KEYWORDS_OBLIGATORIOS = [
    "kevin warsh", "fomc decision", "fed interest rate decision",
    "fomc statement", "fomc press conference", "fedwatch", "cme fedwatch"
]

FECHAS_FOMC_BASE = ["2026-01-28","2026-03-18","2026-04-29","2026-06-17","2026-07-29","2026-09-16","2026-10-28","2026-12-09"]
DATA_FOMC_FILE = "/tmp/fomc_dates.json"
noticias_enviadas = set()

# ========= 3. FECHAS AUTOMÁTICAS PARA SIEMPRE (2027-2030) =========
def cargar_fechas_fomc():
    try:
        with open(DATA_FOMC_FILE, 'r') as f:
            fechas = json.load(f)
            hoy = datetime.now(TZ).date()
            futuras = [d for d in fechas if datetime.strptime(d, "%Y-%m-%d").date() >= hoy]
            if futuras:
                return sorted(list(set(FECHAS_FOMC_BASE + fechas)))
    except:
        pass

    try:
        hoy = datetime.now(TZ)
        año = hoy.year
        if hoy.month >= 11: # Si es noviembre/diciembre ya pide el año que viene
            año += 1

        # Solo pide si ya no quedan fechas futuras
        todas_futuras = [d for d in FECHAS_FOMC_BASE if datetime.strptime(d, "%Y-%m-%d").date() >= hoy.date()]
        if not todas_futuras:
            prompt = f"Dame SOLO un array JSON con las 8 fechas FOMC de {año} en formato YYYY-MM-DD. Sin explicación."
            r = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"user","content":prompt}], temperature=0)
            match = re.search(r'\[.*?\]', r.choices[0].message.content, re.DOTALL)
            if match:
                nuevas = json.loads(match.group(0))
                with open(DATA_FOMC_FILE, 'w') as f:
                    json.dump(nuevas, f)
                return sorted(list(set(FECHAS_FOMC_BASE + nuevas)))
    except Exception as e:
        print(f"Error auto-update: {e}")

    return FECHAS_FOMC_BASE

# ========= 4. TRADUCCIÓN =========
def traducir_y_resumir(titulo_en, desc_en):
    try:
        prompt = f"""
        Eres analista de la FED. Traduce al ESPAÑOL DE ESPAÑA.
        Titular: "{titulo_en}"
        Descripción: "{desc_en}"
        Responde EXACTAMENTE así:
        TÍTULO_ES: [título traducido]
        RESUMEN:
        - [qué pasa con los tipos]
        - [tono hawkish o dovish]
        - [impacto en mercado / volatilidad]
        """
        r = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"user","content":prompt}], temperature=0.2, max_tokens=400)
        return r.choices[0].message.content
    except Exception as e:
        return f"TÍTULO_ES: {titulo_en}\nRESUMEN:\n- Noticia FED importante\n- Error: {e}"

def enviar_telegram(texto):
    texto = corregir_ortografia(texto)
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": texto, "parse_mode": "Markdown"}
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Error Telegram: {e}")

def es_valida(titulo):
    return any(k in titulo.lower() for k in KEYWORDS_OBLIGATORIOS)

# ========= 5. LO QUE HACE EL BOT =========
def check_news():
    try:
        query = '"Kevin Warsh" OR "FOMC decision" OR "FOMC statement" OR "FedWatch"'
        url = f"https://newsapi.org/v2/everything?q={query}&language=en&sortBy=publishedAt&pageSize=15&apiKey={NEWS_KEY}"
        data = requests.get(url, timeout=15).json()
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
⏰ {datetime.now(TZ).strftime('%d/%m/%Y %H:%M')} España (20:00 es la hora oficial de decisión)
"""
            enviar_telegram(mensaje)
            noticias_enviadas.add(url_art)
    except Exception as e:
        print(f"Error news: {e}")

def check_fechas_fomc():
    try:
        fechas = cargar_fechas_fomc()
        hoy = datetime.now(TZ).date()
        for f in fechas:
            fecha_fomc = datetime.strptime(f, "%Y-%m-%d").date()
            dias = (fecha_fomc - hoy).days
            if dias == 7:
                enviar_telegram(f"📅 **FOMC EN 7 DÍAS - {f}**\nDecisión tipos USA el {f} a las 20:00 España / 14:00 ET. Rueda de prensa 20:30 España. Semana de posicionamiento.")
            if dias == 1:
                enviar_telegram(f"⏰ **MAÑANA ES FOMC - {f}**\nMañana a las 20:00 España decisión de tipos FED. Volatilidad máxima asegurada. Cuidado con apalancamiento.")
            if dias == 0:
                enviar_telegram(f"🔥 **HOY ES DÍA FOMC - {f}**\nHOY a las 20:00 España (14:00 ET) decisión + comunicado. 20:30 conferencia Warsh. ¡Atentos al directo!")
    except Exception as e:
        print(f"Error fechas: {e}")

# EXTRA ÚTIL: Limpieza automática de memoria cada 24h
def limpiar_memoria():
    if len(noticias_enviadas) > 200:
        noticias_enviadas.clear()

app = Flask(__name__)
@app.route('/')
def home():
    return "BOT FOMC V5.0 - Auto 2027-2030 - Hora España - ON"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

def main_loop():
    print("BOT V5.0 INICIADO")
    enviar_telegram("💥 Bot FOMC V5.0 activo: Noticias + Avisos 20:00 España + Auto-actualización 2027-2030 💥")
    while True:
        check_news()
        check_fechas_fomc()
        limpiar_memoria()
        time.sleep(900)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    main_loop()
