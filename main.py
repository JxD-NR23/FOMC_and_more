# ==============================================================================
# BOT FOMC V3.4 - FINAL DEFINITIVO - REINOSA / 25 SEPTIEMBRE 2026
# Presidente FED: Kevin Warsh (desde 22 Mayo 2026) - Powell ya NO es presidente
# Objetivo: Solo FED real, análisis económico FIJO y determinista
# Modelo IA que funciona con tu clave nueva: openai/gpt-oss-20b
# ==============================================================================

import os
import requests
import time
import json
import telebot
from groq import Groq
from flask import Flask
import threading

# --- PRINT INICIAL OBLIGATORIO ---
# flush=True hace que Render lo escriba al instante en Logs
print(">>> main.py V3.4 cargado...", flush=True)

# --- 1. TRUCO ANTI-SUEÑO RENDER GRATIS ---
# Render apaga los bots gratis si no hay tráfico web. Creamos una web falsa.
app = Flask(__name__)

@app.route('/')
def pagina_principal():
    return "Bot FOMC v3.4 ON - Kevin Warsh - Filtro Francotirador - Analisis Fijo - 24/7"

def iniciar_web_falsa():
    print(">>> Web falsa arrancando en puerto 10000...", flush=True)
    # 0.0.0.0 = escucha en todas las interfaces, puerto 10000 = el que pide Render
    app.run(host='0.0.0.0', port=10000)

# threading = lo lanzamos en segundo plano para que no bloquee el bot
hilo_web = threading.Thread(target=iniciar_web_falsa, daemon=True)
hilo_web.start()
time.sleep(2) # Esperamos 2 seg a que Flask arranque

# --- 2. LEER CLAVES SECRETAS DESDE RENDER > ENVIRONMENT ---
print(">>> Leyendo claves desde Environment...", flush=True)
TOKEN_TELEGRAM = os.getenv("TELEGRAM_TOKEN") # De @BotFather
ID_CHAT = os.getenv("CHAT_ID") # De @userinfobot
CLAVE_GROQ = os.getenv("GROQ_KEY") # De groq.com
CLAVE_NOTICIAS = os.getenv("NEWS_KEY") # De newsapi.org

# Si falta alguna, lo avisamos en logs y paramos para que lo veas
if not TOKEN_TELEGRAM: print("!!! FALTA TELEGRAM_TOKEN!!!", flush=True)
if not ID_CHAT: print("!!! FALTA CHAT_ID!!!", flush=True)
if not CLAVE_GROQ: print("!!! FALTA GROQ_KEY!!!", flush=True)
if not CLAVE_NOTICIAS: print("!!! FALTA NEWS_KEY!!!", flush=True)

# --- 3. INICIAR CLIENTES ---
try:
    bot_telegram = telebot.TeleBot(TOKEN_TELEGRAM)
    cliente_ia = Groq(api_key=CLAVE_GROQ)
    print(">>> Clientes Telegram y Groq OK", flush=True)
except Exception as e:
    print(f"!!! ERROR INICIANDO: {e}!!!", flush=True)
    time.sleep(999999)

# --- 4. MEMORIA PARA NO REPETIR NOTICIAS ---
# Intentamos cargar historial del disco por si reinicias Render
try:
    with open("historial.json", "r") as f:
        noticias_ya_enviadas = set(json.load(f))
    print(f">>> Historial cargado: {len(noticias_ya_enviadas)} noticias ya vistas", flush=True)
except:
    noticias_ya_enviadas = set()
    print(">>> No hay historial previo, empezamos de cero", flush=True)

# --- 5. CEREBRO V3.4: TRADUCCION IA + ANALISIS ECONOMICO FIJO (NOSOTROS) ---
def es_relevante_y_traducir(titulo_en_ingles, descripcion_en_ingles):
    """
    Esta función hace 2 cosas separadas para no fallar:
    1. La IA solo traduce, no opina.
    2. El análisis Bolsa/Bitcoin lo hacemos nosotros con reglas fijas de economía.
    Así nunca te dirá "neutral" cuando es una subida de tipos.
    """
    prompt_traduccion = f"""
Eres traductor financiero español de España.

Titulo a analizar: "{titulo_en_ingles} - {descripcion_en_ingles}"

Presidente FED actual: Kevin Warsh desde Mayo 2026.

Regla de filtrado ESTRICTA (MODO FRANCOTIRADOR):
- ¿El TITULO contiene EXPLICITAMENTE "FED" o "Federal Reserve" o "FOMC" o "Warsh" o "Fed Chair"?
- Si es "Global Market", "Asian stocks", "Japan bond", "Oil", "Bitcoin slips" sin decir FED/FOMC/Warsh -> responde NO.
- Si dice "Fed rate hikes", "FOMC meeting", "Warsh says" -> responde SI.

Si es SI, traduce a español de España en 1 frase corta (max 20 palabras).
Formato OBLIGATORIO:
SI
[traducción corta]
Si es NO:
NO
"""
    try:
        # Usamos el modelo que SI tiene tu clave. Temperature 0.0 = determinista, siempre igual.
        respuesta_ia = cliente_ia.chat.completions.create(
            model="openai/gpt-oss-20b", # Modelo corregido para cuentas nuevas de Groq
            messages=[{"role": "user", "content": prompt_traduccion}],
            temperature=0.0
        )
        texto_respuesta = respuesta_ia.choices[0].message.content.strip()

        if not texto_respuesta.upper().startswith("SI"):
            return None # No es FED directa, lo descartamos

        # Extraemos la traducción (quitamos el "SI" del principio)
        lineas = texto_respuesta[2:].strip().split('\n')
        traduccion_corta = lineas[0].strip()

        # --- ANALISIS ECONOMICO FIJO, LO HACEMOS NOSOTROS, NO LA IA ---
        # Esto es lógica de mercado real, no opinión de la IA
        titulo_lower = (titulo_en_ingles + " " + descripcion_en_ingles).lower()

        if any(p in titulo_lower for p in ["hike", "raise", "tighten", "hot pmi", "inflation fear", "higher yield"]):
            # HAWKISH = FED dura, sube tipos o habla de subirlos = MALO para activos de riesgo
            sentimiento = "🔴 HAWKISH (Duro)"
            analisis_bolsa = "Bolsa: Negativo, subidas de tipos presionan renta variable y encarecen crédito"
            analisis_btc = "Bitcoin: Negativo, tasas altas hacen más atractivo el dólar y bonos vs crypto"

        elif any(p in titulo_lower for p in ["cut", "pause", "dovish", "pivot", "lower rate", "rate cut"]):
            # DOVISH = FED blanda, baja tipos o pausa = BUENO para activos de riesgo
            sentimiento = "🟢 DOVISH (Blando)"
            analisis_bolsa = "Bolsa: Positivo, bajada de tipos = más liquidez y crédito barato"
            analisis_btc = "Bitcoin: Positivo, dinero barato impulsa activos de riesgo"

        else:
            # NEUTRAL solo si es noticia de FED pero sin dirección clara (ej: Warsh habla sin decir si sube/baja)
            sentimiento = "🟡 NEUTRAL / A VIGILAR"
            analisis_bolsa = "Bolsa: A vigilar, depende de lo que diga Warsh/FOMC"
            analisis_btc = "Bitcoin: A vigilar, pendiente de tono de la FED"

        # Construimos el mensaje final que te llegará a Telegram
        mensaje_final_analizado = f"{traduccion_corta}\n\n📊 {sentimiento}\n{analisis_bolsa}\n{analisis_btc}"
        return mensaje_final_analizado

    except Exception as e:
        print(f"Error en Groq: {e}", flush=True)
        return None

# --- 6. BUSCADOR DE NOTICIAS EN NEWSAPI ---
def buscar_noticias_en_api():
    # Usamos comillas para buscar frases exactas y no traer basura
    consulta_exacta = '"Federal Reserve" OR "FOMC" OR "Kevin Warsh" OR "Fed Chair Warsh"'
    url = f"https://newsapi.org/v2/everything?q={consulta_exacta}&language=en&sortBy=publishedAt&pageSize=10&apiKey={CLAVE_NOTICIAS}"
    try:
        respuesta = requests.get(url, timeout=15).json()
        return respuesta.get('articles', [])
    except Exception as e:
        print(f"Error NewsAPI: {e}", flush=True)
        return []

# --- 7. BUCLE INFINITO 24/7 ---
print("=================================================", flush=True)
print("Bot FOMC v3.4 FINAL DEFINITIVO iniciado", flush=True)
print("Presidente: Kevin Warsh", flush=True)
print("Filtro: Solo FED/FOMC/Warsh explicito", flush=True)
print("Modelo: openai/gpt-oss-20b | Temp: 0.0 determinista", flush=True)
print("Analisis: FIJO (no inventa la IA)", flush=True)
print("=================================================", flush=True)

while True:
    try:
        lista_noticias = buscar_noticias_en_api()
        print(f">>> NewsAPI devolvio {len(lista_noticias)} articulos", flush=True)

        for noticia in lista_noticias:
            titulo = noticia['title']

            if titulo not in noticias_ya_enviadas:
                desc = noticia.get('description') or ""
                print(f"Analizando: {titulo[:90]}...", flush=True)

                resultado = es_relevante_y_traducir(titulo, desc)

                if resultado:
                    texto_telegram = f"🚨 *FED / FOMC - Kevin Warsh* 🚨\n\n{resultado}\n\n📰 *Original:* {titulo}\n🔗 {noticia['url']}"
                    bot_telegram.send_message(ID_CHAT, texto_telegram, parse_mode='Markdown')
                    print(f"✅ ENVIADO A TELEGRAM", flush=True)
                else:
                    print(f"❌ DESCARTADO (no es FED directa)", flush=True)

                # Guardamos como visto
                noticias_ya_enviadas.add(titulo)
                # Guardamos en disco para que no se repita tras reinicio
                try:
                    with open("historial.json", "w") as f:
                        # Guardamos solo las ultimas 200 para no hacer el archivo enorme
                        json.dump(list(noticias_ya_enviadas)[-200:], f)
                except:
                    pass

        print("Durmiendo 15 min...", flush=True)
        time.sleep(900) # 15 minutos

    except Exception as e:
        print(f"Error en bucle principal: {e}", flush=True)
        time.sleep(60)
