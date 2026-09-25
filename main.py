# ==============================================================================
# BOT FOMC V3.3 - VERSION FINAL FRANCOTIRADOR - REINOSA / SEPTIEMBRE 2026
# Presidente actual de la FED: Kevin Warsh (desde el 22 de Mayo de 2026)
# Jerome Powell ya NO es presidente, ahora es solo gobernador.
# Objetivo: Que solo te avise de la FED de verdad, en español de España.
# ==============================================================================

# --- 1. IMPORTAMOS LAS HERRAMIENTAS ---
import os # Para leer las claves secretas que guardas en Render sin enseñarlas en GitHub
import requests # Para pedirle las noticias a NewsAPI.org
import time # Para dormir el bot 15 minutos y no gastar la cuota
import telebot # Librería oficial para hablar con Telegram
from groq import Groq # La Inteligencia Artificial gratis y rápida que usamos para filtrar y traducir
from flask import Flask # TRUCO: Creamos una web falsa para que Render no apague el bot
import threading # Para que la web falsa y el bot puedan funcionar a la vez en paralelo

# --- 2. TRUCO ANTI-SUEÑO PARA RENDER GRATIS ---
# Render, en su plan gratis, apaga los bots si no reciben visitas web.
# Por eso creamos una mini página web que dice "ON". Render la ve y no nos apaga.
print(">>> Cargando main.py... Iniciando sistema...", flush=True) # flush=True = que lo escriba ya en los logs

app = Flask(__name__) # Creamos la aplicación web

@app.route('/') # Esto es lo que verá la gente si entra en https://fomc-and-more.onrender.com
def pagina_principal():
    return "Bot FOMC v3.3 ON - Presidente: Kevin Warsh - Filtrando solo FED real - Activo 24/7"

def iniciar_web_falsa():
    # Esta función arranca la web en el puerto 10000, que es el que exige Render
    print(">>> Web falsa arrancando en puerto 10000...", flush=True)
    app.run(host='0.0.0.0', port=10000)

# Lanzamos la web falsa en un hilo secundario (segundo plano)
# daemon=True significa: si el bot principal muere, la web también se apaga.
hilo_web = threading.Thread(target=iniciar_web_falsa, daemon=True)
hilo_web.start()
time.sleep(2) # Esperamos 2 segundos a que la web arranque bien

# --- 3. LEEMOS TUS CLAVES SECRETAS DE RENDER ---
print(">>> Leyendo claves secretas desde Render > Environment...", flush=True)
TOKEN_TELEGRAM = os.getenv("TELEGRAM_TOKEN") # El token que te dio @BotFather
ID_CHAT = os.getenv("CHAT_ID") # Tu ID personal que sacaste con @userinfobot
CLAVE_GROQ = os.getenv("GROQ_KEY") # Clave de groq.com para la IA
CLAVE_NOTICIAS = os.getenv("NEWS_KEY") # Clave de newsapi.org

# Comprobación por si te falta alguna clave, así lo verás en los Logs de Render
if not TOKEN_TELEGRAM: print("!!! ERROR: FALTA TELEGRAM_TOKEN en Render!!!", flush=True)
if not ID_CHAT: print("!!! ERROR: FALTA CHAT_ID en Render!!!", flush=True)
if not CLAVE_GROQ: print("!!! ERROR: FALTA GROQ_KEY en Render!!!", flush=True)
if not CLAVE_NOTICIAS: print("!!! ERROR: FALTA NEWS_KEY en Render!!!", flush=True)

# --- 4. INICIAMOS LOS CLIENTES DE TELEGRAM Y DE LA IA ---
try:
    bot_telegram = telebot.TeleBot(TOKEN_TELEGRAM) # Cliente listo para enviarte mensajes
    cliente_ia = Groq(api_key=CLAVE_GROQ) # Cliente de IA listo para pensar
    print(">>> Clientes de Telegram y Groq conectados correctamente OK", flush=True)
except Exception as error_inicio:
    print(f"!!! ERROR GRAVE INICIANDO CLIENTES: {error_inicio}!!!", flush=True)
    print("Revisa que las 4 claves estén bien puestas en Render > Environment", flush=True)
    time.sleep(999999) # Paramos todo para que veas el error en logs

# --- 5. MEMORIA PARA NO REPETIR NOTICIAS ---
noticias_ya_enviadas = set() # Aquí guardamos los títulos que ya te hemos enviado

# --- 6. EL CEREBRO: FILTRA LA BASURA Y TRADUCE SOLO LO IMPORTANTE ---
def es_relevante_y_traducir(titulo_en_ingles, descripcion_en_ingles):
    """
    Esta es la función más importante de todo el bot.
    Decide si una noticia es BASURA o si es de la FED de verdad.
    """
    # Este es el prompt que le mandamos a la IA. Es super estricto (MODO FRANCOTIRADOR)
    prompt_para_ia = f"""
Eres un analista financiero español, muy estricto y serio.

Noticia a analizar: "{titulo_en_ingles} - {descripcion_en_ingles}"

DATO CLAVE: El presidente actual de la Reserva Federal es Kevin Warsh desde Mayo 2026. Jerome Powell ya NO es presidente.

INSTRUCCIONES DE FILTRADO (MODO FRANCOTIRADOR):
1. ¿El TITULO menciona EXPLICITAMENTE "Federal Reserve" o "FED" o "FOMC" o "Kevin Warsh" o "Fed Chair"?
2. SI el título es genérico como "Global Market Today", "Asian stocks", "Japan bond yield", "Oil gains" aunque hable de "rate concerns" o "Treasury yield" -> responde NO. Queremos solo noticias DIRECTAS de la FED.
3. SI el título dice "Fed rate hikes", "FOMC meeting", "Warsh says" -> responde SI.
4. Si es basura como Taylor Swift, béisbol, Corvettes, Sensex indio -> responde NO.

Si es SI, haz esto en ESPAÑOL DE ESPAÑA, muy corto (maximo 4 lineas):
- Traduce la idea principal
- Luego en 2 lineas:
  Bolsa: [bueno / malo / neutral y por que]
  Bitcoin: [bueno / malo / neutral y por que]

Formato de respuesta OBLIGATORIO, no te salgas de esto:
SI
[Tu traducción corta en español de España + análisis Bolsa y Bitcoin]
O
NO
"""
    try:
        # Llamamos a Groq con el modelo que SI funciona con tu clave nueva
        # El modelo openai/gpt-oss-20b es el único que Groq deja gratis a cuentas nuevas
        respuesta_ia = cliente_ia.chat.completions.create(
            model="openai/gpt-oss-20b", # <--- MODELO CORREGIDO, ANTES DABA ERROR
            messages=[{"role": "user", "content": prompt_para_ia}],
            temperature=0.2 # 0.2 = lo hacemos más serio, que no invente cosas
        )
        texto_respuesta = respuesta_ia.choices[0].message.content.strip()

        # Si la IA empieza con "SI", devolvemos la traducción. Si empieza con "NO", devolvemos nada (None)
        if texto_respuesta.upper().startswith("SI"):
            return texto_respuesta[2:].strip() # Quitamos el "SI" del principio y dejamos solo el contenido
        else:
            return None # No es relevante, no lo enviamos
    except Exception as e:
        print(f"Error hablando con Groq: {e}", flush=True)
        return None

# --- 7. BUSCADOR DE NOTICIAS ---
def buscar_noticias_en_api():
    """
    Pide noticias a NewsAPI. Usamos comillas para buscar frases exactas y evitar basura.
    """
    # q= con comillas = buscamos frases exactas. Así no nos trae "Federal" de béisbol.
    consulta = '"Federal Reserve" OR "FOMC" OR "Kevin Warsh" OR "Fed Chair Warsh"'
    url_api = f"https://newsapi.org/v2/everything?q={consulta}&language=en&sortBy=publishedAt&pageSize=10&apiKey={CLAVE_NOTICIAS}"
    try:
        datos = requests.get(url_api, timeout=15).json()
        return datos.get('articles', [])
    except Exception as e:
        print(f"Error pidiendo noticias a NewsAPI: {e}", flush=True)
        return []

# --- 8. BUCLE INFINITO: EL CORAZON QUE NUNCA PARA (24/7) ---
print("=================================================", flush=True)
print("Bot FOMC v3.3 FRANCO TIRADOR iniciado", flush=True)
print("Presidente actual: Kevin Warsh (Mayo 2026)", flush=True)
print("Filtro: Solo FED/FOMC/Warsh explicito", flush=True)
print("Modelo IA: openai/gpt-oss-20b (corregido)", flush=True)
print("=================================================", flush=True)

while True: # Bucle infinito, nunca se acaba
    try:
        lista_noticias = buscar_noticias_en_api()
        print(f">>> NewsAPI ha devuelto {len(lista_noticias)} articulos", flush=True)

        for noticia in lista_noticias:
            titulo = noticia['title']

            # Si este titulo no lo hemos enviado antes...
            if titulo not in noticias_ya_enviadas:
                descripcion = noticia.get('description') or ""
                print(f"Analizando: {titulo[:90]}...", flush=True)

                resultado_traduccion = es_relevante_y_traducir(titulo, descripcion)

                if resultado_traduccion: # Si la IA dijo que SI es relevante
                    mensaje_para_ti = f"🚨 *FED / FOMC - Kevin Warsh* 🚨\n\n{resultado_traduccion}\n\n📰 *Original:* {titulo}\n🔗 {noticia['url']}"
                    bot_telegram.send_message(ID_CHAT, mensaje_para_ti, parse_mode='Markdown')
                    print(f"✅ ENVIADO A TELEGRAM: {titulo[:60]}", flush=True)
                else:
                    print(f"❌ DESCARTADO (no es FED directa)", flush=True)

                noticias_ya_enviadas.add(titulo) # Lo guardamos para no repetirlo nunca más

        print("Durmiendo 15 min hasta la proxima busqueda...", flush=True)
        time.sleep(900) # 900 segundos = 15 minutos

    except Exception as error_bucle:
        print(f"Error en el bucle principal: {error_bucle}", flush=True)
        print("Reintentando en 60 segundos...", flush=True)
        time.sleep(60) # Si algo falla, espera 1 minuto y sigue
