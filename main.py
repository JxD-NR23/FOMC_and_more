# ==============================================================================
# BOT FOMC V3.5 - FINAL DEFINITIVO - REINOSA / 25 SEPTIEMBRE 2026
# Presidente FED: Kevin Warsh (desde 22 Mayo 2026)
# Corrige bug V3.4: Corvette se colaba por alucinación de la IA
# Solución: Pre-filtro duro ANTES de llamar a Groq
# ==============================================================================

import os
import requests
import time
import json
import telebot
from groq import Groq
from flask import Flask
import threading

print(">>> main.py V3.5 cargado... Pre-filtro ON...", flush=True)

# --- 1. TRUCO ANTI-SUEÑO RENDER ---
app = Flask(__name__)

@app.route('/')
def pagina_principal():
    return "Bot FOMC v3.5 ON - Kevin Warsh - Pre-filtro anti-basura - Activo 24/7"

def iniciar_web_falsa():
    print(">>> Web falsa arrancando en puerto 10000...", flush=True)
    app.run(host='0.0.0.0', port=10000)

threading.Thread(target=iniciar_web_falsa, daemon=True).start()
time.sleep(2)

# --- 2. CLAVES ---
print(">>> Leyendo claves...", flush=True)
TOKEN_TELEGRAM = os.getenv("TELEGRAM_TOKEN")
ID_CHAT = os.getenv("CHAT_ID")
CLAVE_GROQ = os.getenv("GROQ_KEY")
CLAVE_NOTICIAS = os.getenv("NEWS_KEY")

if not TOKEN_TELEGRAM: print("!!! FALTA TELEGRAM_TOKEN!!!", flush=True)
if not ID_CHAT: print("!!! FALTA CHAT_ID!!!", flush=True)
if not CLAVE_GROQ: print("!!! FALTA GROQ_KEY!!!", flush=True)
if not CLAVE_NOTICIAS: print("!!! FALTA NEWS_KEY!!!", flush=True)

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

# --- 4. CEREBRO V3.5: PRE-FILTRO + TRADUCCION + ANALISIS FIJO ---
def es_relevante_y_traducir(titulo_en_ingles, descripcion_en_ingles):
    texto_completo_lower = (titulo_en_ingles + " " + descripcion_en_ingles).lower()

    # --- PASO 1: PRE-FILTRO DURO ANTI-BASURA ---
    # Si el titular no contiene NINGUNA de estas palabras, ni gastamos IA
    # Esto evita que el Corvette de 1954 se cuele por alucinación
    # y ahorra cuota de Groq
    palabras_obligatorias = ["fed", "fomc", "warsh", "federal reserve", "powell"]
    if not any(p in texto_completo_lower for p in palabras_obligatorias):
        return None # Fuera directo, sin llamar a la IA

    # --- PASO 2: SI PASA EL PRE-FILTRO, TRADUCIMOS CON IA DETERMINISTA ---
    prompt_traduccion = f"""
Traduce a español de España en 1 frase corta (max 20 palabras): "{titulo_en_ingles}"

Si es sobre Taylor Swift, boda, Corvette, coche, béisbol, cricket -> responde NO.
Si es sobre FED/FOMC/Warsh -> responde SI + traducción.

Formato obligatorio:
SI
[traducción corta]
O
NO
"""
    try:
        respuesta_ia = cliente_ia.chat.completions.create(
            model="openai/gpt-oss-20b", # El unico que funciona con tu clave nueva
            messages=[{"role": "user", "content": prompt_traduccion}],
            temperature=0.0 # 0.0 = siempre misma traducción, no inventa razonamientos distintos
        )
        txt = respuesta_ia.choices[0].message.content.strip()
        if not txt.upper().startswith("SI"):
            return None

        traduccion = txt[2:].strip().split('\n')[0]

        # --- PASO 3: ANALISIS ECONOMICO FIJO (LO HACEMOS NOSOTROS, NO LA IA) ---
        # Así nunca te dirá "neutral" cuando es subida de tipos
        if any(x in texto_completo_lower for x in ["hike", "raise", "tighten", "hot", "inflation", "higher yield", "selloff"]):
            sentimiento = "🔴 HAWKISH (FED dura - sube tipos)"
            analisis_bolsa = "Bolsa: Negativo - subidas de tipos presionan y encarecen crédito"
            analisis_btc = "Bitcoin: Negativo - tasas altas favorecen dólar/bonos vs riesgo"
        elif any(x in texto_completo_lower for x in ["cut", "pause", "dovish", "pivot", "lower rate"]):
            sentimiento = "🟢 DOVISH (FED blanda - baja tipos)"
            analisis_bolsa = "Bolsa: Positivo - bajada tipos = más liquidez"
            analisis_btc = "Bitcoin: Positivo - dinero barato impulsa crypto"
        else:
            sentimiento = "🟡 NEUTRAL / DECLARACIÓN"
            analisis_bolsa = "Bolsa: A vigilar - pendiente de tono Warsh/FOMC"
            analisis_btc = "Bitcoin: A vigilar - pendiente de tono FED"

        return f"{traduccion}\n\n📊 {sentimiento}\n{analisis_bolsa}\n{analisis_btc}"

    except Exception as e:
        print(f"Error Groq: {e}", flush=True)
        return None

# --- 5. BUSCAR NOTICIAS ---
def buscar_noticias_en_api():
    consulta = '"Federal Reserve" OR "FOMC" OR "Kevin Warsh" OR "Fed Chair Warsh"'
    url = f"https://newsapi.org/v2/everything?q={consulta}&language=en&sortBy=publishedAt&pageSize=10&apiKey={CLAVE_NOTICIAS}"
    try:
        return requests.get(url, timeout=15).json().get('articles', [])
    except Exception as e:
        print(f"Error NewsAPI: {e}", flush=True)
        return []

# --- 6. BUCLE 24/7 ---
print("=================================================", flush=True)
print("Bot FOMC v3.5 FINAL con PRE-FILTRO iniciado", flush=True)
print("Presidente: Kevin Warsh", flush=True)
print("Modelo: openai/gpt-oss-20b | Temp 0.0", flush=True)
print("Filtro: Palabra FED/FOMC/Warsh obligatoria en titulo", flush=True)
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
                # Guardamos historial en disco
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
