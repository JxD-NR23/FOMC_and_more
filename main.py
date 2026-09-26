import os, requests, time, threading
from datetime import datetime
from groq import Groq
from flask import Flask

# ========= CONFIG ENV - Como lo tienes en tu foto =========
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
NEWS_KEY = os.getenv("NEWS_KEY")
GROQ_KEY = os.getenv("GROQ_KEY")

client = Groq(api_key=GROQ_KEY)

# ========= FILTRO ULTRA ESTRICTO - NADA MAS QUE ESTO =========
# Si no tiene estas palabras EXACTAS, se descarta
KEYWORDS_OBLIGATORIOS = [
    "kevin warsh",
    "fomc decision",
    "fed interest rate decision",
    "fomc statement",
    "fomc press conference",
    "powell press conference",
    "fedwatch",
    "cme fedwatch"
]

# Fechas oficiales FOMC 2026
FECHAS_FOMC = ["2026-01-28","2026-03-18","2026-05-06","2026-06-17","2026-07-29","2026-09-16","2026-11-04","2026-12-09"]

# Memoria anti-spam
noticias_enviadas = set()

# ========= TRADUCCION + RESUMEN CON GROQ =========
def traducir_y_resumir(titulo_en, desc_en):
    try:
        prompt = f"""
        Eres analista de la FED. Traduce y resume al ESPAÑOL de ESPAÑA.
        Titular: "{titulo_en}"
        Descripcion: "{desc_en}"
        Responde EXACTAMENTE asi:
        TITULO_ES: [titulo traducido]
        RESUMEN:
        - [bullet 1: que pasa con los tipos]
        - [bullet 2: tono hawkish o dovish]
        - [bullet 3: impacto mercado]
        """
        r = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role":"user","content":prompt}],
            temperature=0.2,
            max_tokens=350
        )
        return r.choices[0].message.content
    except Exception as e:
        return f"TITULO_ES: {titulo_en}\nRESUMEN:\n- Noticia FED importante\n- Revisar detalle\n- Error resumen: {e}"

def enviar_telegram(texto):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": texto, "parse_mode": "Markdown", "disable_web_page_preview": False}
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Error Telegram: {e}")

def es_valida(titulo):
    t = titulo.lower()
    # Tiene que contener ALGUNA de las keywords obligatorias
    return any(k in t for k in KEYWORDS_OBLIGATORIOS)

def check_news():
    try:
        query = '"Kevin Warsh" OR "FOMC decision" OR "FOMC statement" OR "FedWatch" OR "FOMC press conference"'
        url = f"https://newsapi.org/v2/everything?q={query}&language=en&sortBy=publishedAt&pageSize=10&apiKey={NEWS_KEY}"
        data = requests.get(url, timeout=15).json()

        for art in data.get("articles", []):
            titulo = art.get("title", "")
            url_art = art.get("url", "")

            # 1. Anti-spam: si ya la enviamos, saltar
            if url_art in noticias_enviadas:
                continue

            # 2. Filtro ultra estricto
            if es_valida(titulo):
                print(f"✅ VALIDA: {titulo}")
                traduccion = traducir_y_resumir(titulo, art.get("description",""))
                mensaje = f"""🚨 **ALERTA FED / WARSH / FEDWATCH**

{traduccion}

📰 Original: {titulo}
🔗 {url_art}
⏰ {datetime.now().strftime('%d/%m/%Y %H:%M')} CET
"""
                enviar_telegram(mensaje)
                noticias_enviadas.add(url_art)
            else:
                print(f"❌ DESCARTADA (SPAM): {titulo}")
    except Exception as e:
        print(f"Error check_news: {e}")

def check_fechas_fomc():
    try:
        hoy = datetime.now()
        for f in FECHAS_FOMC:
            dias = (datetime.strptime(f, "%Y-%m-%d") - hoy).days
            if dias == 7:
                enviar_telegram(f"📅 **RECORDATORIO FOMC - 7 DIAS**\nQuedan 7 dias para decision tipos USA: {f}\n20:00 CET decision, 20:30 rueda prensa. Atento a Kevin Warsh.")
            if dias == 1:
                enviar_telegram(f"📅 **RECORDATORIO FOMC - MAÑANA**\nMañana {f} DECISION TIPOS FED + COMUNICADO + CONFERENCIA. Dia de maxima volatilidad.")
            if dias == 0:
                enviar_telegram(f"📅 **HOY ES DIA FOMC**\nHOY {f} a las 20:00 CET decision, 20:30 Powell/Warsh conferencia. ¡Atentos!")
    except Exception as e:
        print(f"Error fechas: {e}")

# ========= SERVIDOR FALSO PARA RENDER (Para que no de timeout) =========
app = Flask(__name__)
@app.route('/')
def home():
    return "BOT FOMC V4.0 Running - SOLO WARSH/FOMC/FEDWATCH - Anti Spam ON"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# ========= LOOP PRINCIPAL =========
def main_loop():
    print("BOT V4.0 INICIADO - SOLO WARSH / FOMC / FEDWATCH - ANTI SPAM")
    enviar_telegram("✅ **BOT V4.0 CONECTADO**\nFiltro: SOLO Kevin Warsh, Decision Tipos, Comunicado FOMC, Conferencia y FedWatch. Anti-spam activo. Modo Web Service con puerto abierto.")
    while True:
        check_news()
        check_fechas_fomc()
        print("Durmiendo 15 min...")
        time.sleep(900) # 15 minutos

if __name__ == "__main__":
    # Hilo del Flask para abrir puerto 10000 y que Render no mate el servicio
    threading.Thread(target=run_flask, daemon=True).start()
    main_loop()
