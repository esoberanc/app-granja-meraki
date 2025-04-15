from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
import os
import requests
import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build
import openai

# Configuración
MERAKI_API_KEY = os.environ.get("MERAKI_API_KEY")
ORGANIZATION_ID = "1654515"
SPREADSHEET_ID = "1tNx0hjnQzdUKoBvTmIsb9y3PaL3GYYNF3_bMDIIfgRA"
SHEET_NAME = "Hoja1"
OPENAI_API_KEY = open("/etc/secrets/openai_key.txt").read().strip()
openai.api_key = OPENAI_API_KEY

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO)

# Ruta principal
@app.route("/")
def home():
    return render_template("index-con-resumen-ia.html")

# Ruta del panel MT40
@app.route("/mt40")
def mt40_panel():
    return render_template("panel-mt40.html")

# Ruta para análisis por IA
@app.route("/resumen-ia")
def resumen_ia():
    prompt = "Haz un resumen analítico de los últimos datos de sensores de temperatura, humedad, consumo eléctrico, calidad del aire y movimiento para una granja de tenebrios. Da recomendaciones."
    try:
        completion = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            temperature=0.6,
            messages=[{"role": "user", "content": prompt}]
        )
        texto = completion.choices[0].message.content
        return jsonify({"resumen": texto})
    except Exception as e:
        logging.error(f"Error con OpenAI: {e}")
        return jsonify({"resumen": "❌ Error al generar resumen"}), 500

# Ruta de datos del sensor
@app.route("/sensor-data")
def sensor_data():
    try:
        url = f"https://api.meraki.com/api/v1/organizations/{ORGANIZATION_ID}/sensor/readings/latest"
        headers = {"X-Cisco-Meraki-API-Key": MERAKI_API_KEY}
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            raise Exception(f"Error al consultar Meraki: {response.status_code} - {response.text}")
        data = response.json()

        # Diccionario para guardar valores por serial
        valores = {}

        for sensor in data:
            serial = sensor["serial"]
            for lectura in sensor["readings"]:
                metrica = lectura["metric"]
                if metrica == "temperature":
                    valores[f"{serial}_temp"] = lectura["temperature"]["value"]
                elif metrica == "humidity":
                    valores[f"{serial}_hum"] = lectura["humidity"]["value"]
                elif metrica == "current":
                    valores[f"{serial}_current"] = lectura["current"]["draw"]
                elif metrica == "voltage":
                    valores[f"{serial}_voltage"] = lectura["voltage"]["level"]
                elif metrica == "apparentPower":
                    valores[f"{serial}_app"] = lectura["apparentPower"]["draw"]
                elif metrica == "realPower":
                    valores[f"{serial}_real"] = lectura["realPower"]["draw"]
                elif metrica == "powerFactor":
                    valores[f"{serial}_pf"] = lectura["powerFactor"]["percentage"]
                elif metrica == "frequency":
                    valores[f"{serial}_freq"] = lectura["frequency"]["level"]
                elif metrica == "ambientNoise":
                    valores[f"{serial}_noise"] = lectura["ambientNoise"]["avg"]
                elif metrica == "tvoc":
                    valores[f"{serial}_tvoc"] = lectura["tvoc"]["value"]
                elif metrica == "co2":
                    valores[f"{serial}_co2"] = lectura["co2"]["value"]
                elif metrica == "pm25":
                    valores[f"{serial}_pm25"] = lectura["pm25"]["value"]
                elif metrica == "door":
                    valores[f"{serial}_door"] = lectura["door"]["open"]

        # Enviar a Google Sheets si corresponde
        if request.args.get("guardar") == "true":
            guardar_en_google_sheets(valores)

        return jsonify(valores)

    except Exception as e:
        logging.error(f"❌ Error general: {e}")
        return "Error", 500

def guardar_en_google_sheets(valores):
    logging.info("✅ Guardando en Google Sheets...")
    try:
        creds = service_account.Credentials.from_service_account_file(
            "/etc/secrets/credentials.json",
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        service = build("sheets", "v4", credentials=creds)
        sheet = service.spreadsheets()

        fila = [valores.get(k, "") for k in sorted(valores.keys())]
        sheet.values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEET_NAME}!A1",
            valueInputOption="RAW",
            body={"values": [fila]}
        ).execute()
        logging.info("✅ Datos guardados correctamente.")
    except Exception as e:
        logging.error(f"❌ Error al guardar en Sheets: {e}")

# Inicio
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
