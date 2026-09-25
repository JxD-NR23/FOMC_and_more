# BOT FOMC V4.0 - SOLO KEVIN WARSH / DECISION TIPOS / FOMC / FEDWATCH
# Requisitos: pip install requests python-telegram-bot deep-translator openai schedule

import requests, time, schedule
from datetime import datetime
from deep_translator import GoogleTranslator
import openai # para resumen

# ========== CONFIG ==========
TELEGRAM_TOKEN = "TU_TOKEN"
TELEGRAM_CHAT_ID = "TU_CHAT_ID"
NEWSAPI_KEY = "TU_NEWSAPI"
OPENAI_KEY = "TU_OPENAI"

# Palabras clave ULTRA ESTRICTAS - NADA MAS
KEYWORDS_PERMITIDOS = {
    "kevin_warsh": ["kevin warsh", "warsh"],
    "fomc_decision": ["fed interest rate decision", "fomc decision", "fed rate decision", "federal reserve announces rate"],
    "fomc_statement": ["fomc statement", "fomc comunicado"],
    "fomc_conference": ["powell press conference", "fomc press conference", "fed chair conference", "jerome powell conference", "warsh press conference"],
    "fedwatch": ["fedwatch", "cme fedwatch", "fed rate probabilities", "probabilidad tipos fed"]
}

# Fechas FOMC 2026 (actualiza cada año)
FECHAS_FOMC_2026 = [
    "2026-01-28", "2026-03-18", "2026-05-06",
    "2026-06-17", "2026-07-29", "2026-09-16",
    "2026-11-04", "2026-12-09"
]

traductor = GoogleTranslator(source='en', target='es')

def traducir(texto):
    try:
        return traductor.translate(texto)
    except:
        return texto

def resumir_con_ia(texto_en):
    """Resumen ultra corto de lo importante"""
    try:
        client = openai.OpenAI(api_key=OPENAI_KEY)
        prompt = f"Resume en 3 bullets en ESPAÑOL lo mas importante para traders de esta noticia FED, enfocado en tipos de interes, tono hawkish/dovish y impacto mercado. Noticia: {texto_en}"
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"user","content":prompt}],
            max_tokens=250
        )
        return resp.choices[0].message.content
    except Exception as e:
        return "Resumen no disponible"

def enviar_telegram(titulo_es, resumen_es, original_en, fuente):
    mensaje = f"""
🚨 **{titulo_es}**

📝 **RESUMEN CLAVE:**
{resumen_es}

📰 Original: {original_en}
🔗 {fuente}
⏰ {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": mensaje, "parse_mode": "Markdown"})

def es_noticia_valida(titulo):
    t = titulo.lower()
    # SOLO si contiene warsh o FOMC/decision/conferencia/fedwatch
    for categoria, palabras in KEYWORDS_PERMITIDOS.items():
        for p in palabras:
            if p in t:
                return True, categoria
    return False, None

def check_newsapi():
    url = f"https://newsapi.org/v2/everything?q=Federal Reserve OR FOMC OR Kevin Warsh OR FedWatch&language=en&sortBy=publishedAt&pageSize=20&apiKey={NEWSAPI_KEY}"
    r = requests.get(url).json()
    for art in r.get('articles', []):
        titulo = art['title']
        valido, cat = es_noticia_valida(titulo)
        if valido:
            print(f"✅ ENVIADO [{cat}]: {titulo}")
            titulo_es = traducir(titulo)
            desc_es = traducir(art.get('description',''))
            resumen = resumir_con_ia(titulo + " " + art.get('description',''))
            enviar_telegram(f"{cat.upper()} | {titulo_es}", resumen, titulo, art['url'])
        else:
            print(f"❌ DESCARTADO (no es lo pedido): {titulo}")

def recordatorio_fechas():
    hoy = datetime.now().strftime("%Y-%m-%d")
    for fecha in FECHAS_FOMC_2026:
        dias = (datetime.strptime(fecha, "%Y-%m-%d") - datetime.now()).days
        if dias == 7:
            enviar_telegram(f"RECORDATORIO FOMC - 7 DIAS", f"Quedan 7 dias para la decision de tipos USA: {fecha}", f"FOMC meeting on {fecha}", "FED Calendar")
        if dias == 1:
            enviar_telegram(f"RECORDATORIO FOMC - MAÑANA", f"Mañana {fecha} DECISION TIPOS FED + COMUNICADO + CONFERENCIA", f"FOMC tomorrow {fecha}", "FED Calendar")
        if dias == 0:
            enviar_telegram(f"HOY ES DIA FOMC", f"HOY {fecha} a las 20:00 CET decision, 20:30 conferencia. Atentos a Kevin Warsh si habla.", f"FOMC Today {fecha}", "FED Calendar")

# ========== LOOP PRINCIPAL ==========
def main():
    print("BOT V4.0 INICIADO - SOLO WARSH / FOMC / FEDWATCH")
    schedule.every().day.at("09:00").do(recordatorio_fechas)
    while True:
        try:
            check_newsapi()
            schedule.run_pending()
            print("Durmiendo 15 min...")
            time.sleep(900)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()
