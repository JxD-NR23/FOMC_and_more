# ===============================================
# BOT FOMC V3 - EXPLICACIÓN ULTRA DETALLADA
# Creado para ti en Reinosa - Septiembre 2026
# Presidente actual FED: Kevin Warsh (desde 22 Mayo 2026)
# ===============================================

# --- LIBRERÍAS: Las herramientas que importamos ---
import os # Para leer las claves secretas que guardaste en Render
import requests # Para hacer peticiones a NewsAPI (pedir noticias)
import time # Para hacer pausas (que no se vuelva loco pidiendo noticias)
import telebot # La librería de Telegram para enviar mensajes
from groq import Groq # La IA gratis que traduce y filtra
from flask import Flask # Truco: creamos una mini-web falsa para que Render no nos apague el bot gratis
import threading # Para que la web falsa y el bot funcionen a la vez

# --- TRUCO ANTI-SUEÑO PARA RENDER GRATIS ---
# Render si ve un "Web Service" gratis lo apaga a los 15 min si no hay tráfico.
# Creamos una web que dice "ON" y la ponemos a correr en otro hilo.
app = Flask(__name__) # Creamos la app web

@app.route('/') # Cuando alguien entre a https://fomc-and-more.onrender.com
def home():
    return "Bot FOMC v3 ON - Presidente: Kevin Warsh - Filtrando noticias reales"

# Esta función arranca la web en el puerto 10000 que pide Render
def run_web():
    app.run(host='0.0.0.0', port=10000)

# threading.Thread = lo lanza en segundo plano, daemon=True = si el bot muere, la web también
threading.Thread(target=run_web, daemon=True).start()

# --- CLAVES SECRETAS ---
# os.getenv lee las variables que pusiste en Render > Environment. Así no se ven en GitHub.
TOKEN = os.getenv("TELEGRAM_TOKEN") # Token que te dio @BotFather
CHAT_ID = os.getenv("CHAT_ID") # Tu ID que sacaste con @userinfobot
GROQ_KEY = os.getenv("GROQ_KEY") # Clave de groq.com (IA gratis)
NEWS_KEY = os.getenv("NEWS_KEY") # Clave de newsapi.org

# --- INICIAMOS LOS BOTS ---
bot = telebot.TeleBot(TOKEN) # Cliente de Telegram listo para enviar
ia = Groq(api_key=GROQ_KEY) # Cliente de IA listo para pensar
enviados = set() # Una "bolsa" donde guardamos títulos ya enviados para no repetirlos

# --- CEREBRO DEL BOT: FILTRA Y TRADUCE ---
def es_relevante_y_traducir(titulo, desc):
    """
    Esta es la función más importante.
    Recibe un título en inglés y decide si es BASURA o es FED de verdad.
    """
    prompt = f"""
Eres un analista financiero español experto.

Noticia a analizar: "{titulo} - {desc}"

PRESIDENTE ACTUAL DE LA FED: Kevin Warsh (desde Mayo 2026). Jerome Powell ya NO es presidente, es solo gobernador.

INSTRUCCIONES:
1. ¿Esta noticia es REALMENTE sobre la Reserva Federal, FOMC, tipos de interés de EEUU, o declaraciones de Kevin Warsh?
   - SI es sobre béisbol (Astros), cricket indio (Sensex, Nifty), Trump-Xi sin mencionar a la FED, o bolsa de India, responde NO.
   - SI es sobre FED/FOMC/Warsh, responde SI.

2. Si es SI, haz esto en ESPAÑOL DE ESPAÑA:
   - Traduce el titular
   - En 2 líneas: ¿Qué significa? ¿Es bueno o malo para BOLSA y BITCOIN? (ej: si suben tipos es malo, si los bajan es bueno)

Formato OBLIGATORIO:
SI
[Tu traducción y análisis en español]
O
NO
"""
    try:
        # Llamamos a la IA Llama 3.1 que es rápida y gratis
        r = ia.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role":"user","content": prompt}],
            temperature=0.2 # 0.2 = más serio y preciso, no inventa
        )
        txt = r.choices[0].message.content.strip()
        # Si la IA dice que SI es relevante, devolvemos el texto. Si dice NO, devolvemos None (nada)
        if txt.upper().startswith("SI"):
            return txt[2:].strip() # Quitamos el "SI" y dejamos solo la traducción
        else:
            return None
    except Exception as e:
        print("Error Groq:", e)
        return None

def buscar_noticias():
    """
    Pide noticias a NewsAPI.
    Antes buscábamos "FED" y nos traía de todo. Ahora buscamos frases exactas con comillas.
    """
    # q= con comillas = solo frases exactas. Así evitamos "Federal" de béisbol.
    query = '"Federal Reserve" OR "FOMC" OR "Kevin Warsh" OR "Fed Chair Warsh"'
    url = f"https://newsapi.org/v2/everything?q={query}&language=en&sortBy=publishedAt&pageSize=10&apiKey={NEWS_KEY}"
    try:
        data = requests.get(url, timeout=15).json()
        return data.get('articles', [])
    except Exception as e:
        print("Error NewsAPI:", e)
        return []

# --- BUCLE INFINITO: EL CORAZÓN QUE NUNCA PARA ---
print("Bot FOMC v3 iniciado... Presidente actual Kevin Warsh. Esperando noticias reales...")
while True:
    try:
        for noticia in buscar_noticias():
            titulo = noticia['title']
            # Si no lo hemos enviado antes
            if titulo not in enviados:
                desc = noticia.get('description') or ""
                print(f"Analizando: {titulo[:80]}...")
                resultado = es_relevante_y_traducir(titulo, desc)

                if resultado: # Solo si la IA dijo SI
                    mensaje_final = f"🚨 *FED / FOMC - Kevin Warsh* 🚨\n\n{resultado}\n\n📰 *Original:* {titulo}\n🔗 {noticia['url']}"
                    bot.send_message(CHAT_ID, mensaje_final, parse_mode='Markdown')
                    print(f"✅ ENVIADO A TELEGRAM: {titulo}")
                else:
                    print(f"❌ DESCARTADO (no es FED): {titulo}")

                enviados.add(titulo) # Lo marcamos como visto para no repetir

        # Esperamos 15 minutos (900 segundos) antes de buscar otra vez. Así no gastamos cuota de NewsAPI.
        print("Durmiendo 15 min...")
        time.sleep(900)
    except Exception as e:
        print(f"Error en bucle principal: {e}")
        time.sleep(60) # Si falla, espera 1 min y reintenta
