# ==============================================================================
# BOT FOMC V3.6 - FINAL DEFINITIVO ANTI-CORVETTE - REINOSA / 25 SEPT 2026
# Fix: El V3.5 se colaba Corvette porque "fed" estaba dentro de "federal"
# Solución: Regex con \b para palabras enteras + lista negra directa
# Presidente FED: Kevin Warsh (desde 22 Mayo 2026)
# ==============================================================================

import os
import requests
import time
import json
import re # <--- NUEVO IMPORT PARA EL FIX ANTI-SUBSTRING
import telebot
from groq import Groq
from flask import Flask
import threading

print(">>> main.py V3.6 cargado... Fix anti-Corvette ON...", flush=True)

# --- 1. TRUCO ANTI-SUEÑO RENDER ---
app = Flask(__name__)

@app.route('/')
def pagina_principal():
    return "Bot FOMC v3.6 ON - Kevin Warsh - Regex + Blacklist - Activo 24/7"

def iniciar_web_falsa():
    print(">>> Web falsa arrancando en puerto 10000...", flush=True)
    app.run(host='0.0.0.0', port=10000)

threading.Thread(target=iniciar_web_falsa, daemon=True).start()
time.sleep(2)

# --- 2. CLAVES SECRETAS ---
print(">>> Leyendo claves...", flush=True)
TOKEN_TELEGRAM = os.getenv("TELEGRAM_TOKEN")
ID_CHAT = os.getenv("CHAT_ID")
CLAVE_GROQ = os.getenv("GROQ_KEY")
CLAVE_NOTICIAS = os.getenv("NEWS_KEY")

try:
    bot_telegram = telebot.TeleBot(TOKEN_TELEGRAM)
    cliente_ia = Groq(api_key=CLAVE_GROQ)
    print(">>> Clientes OK", flush=True)
except Exception as e:
    print(f"!!! ERROR INICIO: {e}!!!", flush=True)
    time.sleep(999999)

# --- 3. MEMORIA CON HISTORIAL EN DISCO ---
try:
    with open("historial.json", "r") as f:
        noticias_ya_enviadas = set(json.load(f))
    print(f">>> Historial cargado: {len(noticias_ya_enviadas)}", flush=True)
except:
    noticias_ya_enviadas = set()
    print(">>> Sin historial previo", flush=True)

# --- 4. CEREBRO V3.6: BLACKLIST + REGEX + ANALISIS FIJO ---
def es_relevante_y_traducir(titulo_en_ingles, descripcion_en_ingles):
    titulo_lower = titulo_en_ingles.lower()
    completo_lower = (titulo_en_ingles + " " + descripcion_en_ingles).lower()

    # PASO 1: LISTA NEGRA DIRECTA - Estos NUNCA pasan, ahorramos IA
    lista_negra = ["corvette", "taylor swift", "gift nifty", "wedded bliss", "chevrolet", "ipl", "baseball"]
    if any(palabra in titulo_lower for palabra in lista_negra):
        return None

    # PASO 2: PRE-FILTRO REGEX - Palabras ENTERAS en el TITULO
    # \b significa frontera de palabra. Así "fed" solo vale si es "fed", no si es "federal" o "offered"
    # Buscamos SOLO en el titulo, no en la descripcion
    patron_obligatorio = r'\b(fed|fomc|warsh|powell|federal reserve)\b'
    if not re.search(patron_obligatorio, titulo_lower):
        return None # No es FED directa, fuera sin gastar Groq

    # PASO 3: TRADUCCION DETERMINISTA
    prompt = f"""Traduce a español de España en 1 frase corta max 20 palabras: "{titulo_en_ingles}"
Si no es FED/FOMC/Warsh -> responde NO
Si es FED/FOMC/Warsh -> responde:
SI
[traducción]"""
    try:
        r = cliente_ia.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0 # 0.0 = siempre igual, no inventa
        )
        txt = r.choices[0].message.content.strip()
        if not txt.upper().startswith("SI"):
            return None

        traduccion = txt[2:].strip().split('\n')[0]

        # PASO 4: ANALISIS FIJO (nosotros, no la IA)
        if any(x in completo_lower for x in ["hike", "raise", "tighten", "hot", "inflation", "higher yield", "selloff", "bets"]):
            sentimiento = "🔴 HAWKISH (FED dura - posible subida)"
            analisis = "Bolsa: Negativo - tipos altos presionan\nBitcoin: Negativo - dólar/bonos más atractivos"
        elif any(x in completo_lower for x in ["cut", "pause", "dovish", "pivot", "lower rate"]):
            sentimiento = "🟢 DOVISH (FED blanda - posible bajada)"
            analisis = "Bolsa: Positivo - más liquidez\nBitcoin: Positivo - impulsa riesgo"
        else:
            sentimiento = "🟡 NEUTRAL / DECLARACIÓN"
            analisis = "Bolsa: A vigilar\nBitcoin: A vigilar"

        return f"{traduccion}\n\n📊 {sentimiento}\n{analisis}"

    except Exception as e:
        print(f"Error Groq: {e}", flush=True)
        return None

# --- 5. BUSCADOR NEWSAPI ---
def buscar_noticias_en_api():
    consulta = '"Federal Reserve" OR "FOMC" OR "Kevin Warsh" OR "Fed Chair"'
    url = f"https://newsapi.org/v2/everything?q={consulta}&language=en&sortBy=publishedAt&pageSize=10&apiKey={CLAVE_NOTICIAS}"
    try:
        return requests.get(url, timeout=15).json().get('articles', [])
    except Exception as e:
        print(f"Error NewsAPI: {e}", flush=True)
        return []

# --- 6. BUCLE 24/7 ---
print("=================================================", flush=True)
print("Bot FOMC v3.6 con REGEX iniciado", flush=True)
print("Filtro: \\b(fed|fomc|warsh|powell)\\b en TITULO obligatorio", flush=True)
print("Blacklist: corvette, taylor swift, gift nifty", flush=True)
print("=================================================", flush=True)

while True:
    try:
        noticias = buscar_noticias_en_api()
        print(f">>> NewsAPI devolvio {len(noticias)}", flush=True)

        for n in noticias:
            titulo = n['title']
            if titulo not in noticias_ya_enviadas:
                desc = n.get('description') or ""
                print(f"Analizando: {titulo[:90]}...", flush=True)

                res = es_relevante_y_traducir(titulo, desc)

                if res:
                    msg = f"🚨 *FED / FOMC - Kevin Warsh* 🚨\n\n{res}\n\n📰 *Original:* {titulo}\n🔗 {n['url']}"
                    bot_telegram.send_message(ID_CHAT, msg, parse_mode='Markdown')
                    print(f"✅ ENVIADO A TELEGRAM", flush=True)
                else:
                    print(f"❌ DESCARTADO (no es FED directa)", flush=True)

                noticias_ya_enviadas.add(titulo)
                try:
                    with open("historial.json", "w") as f:
                        json.dump(list(noticias_ya_enviadas)[-200:], f)
                except:
                    pass

        print("Durmiendo 15 min...", flush=True)
        time.sleep(900)

    except Exception as e:
        print(f"Error bucle: {e}", flush=True)
        time.sleep(60)
