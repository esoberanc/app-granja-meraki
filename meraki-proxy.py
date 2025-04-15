
import os
import json
import time
import logging
import requests
import threading
from flask import Flask, jsonify, render_template, send_from_directory
from flask_cors import CORS
from google.oauth2 import service_account
from googleapiclient.discovery import build
import openai

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__)
CORS(app)

# API Keys y configuraciones
MERAKI_API_KEY = os.environ.get("MERAKI_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")
ORGANIZATION_ID = os.environ.get("ORGANIZATION_ID")
CREDENTIALS_FILE = "/etc/secrets/credentials.json"

# Inicializar OpenAI
openai.api_key = OPENAI_API_KEY

# Función para obtener datos desde Meraki
def obtener_datos_sensor():
    headers = {
        "X-Cisco-Meraki-API-Key": MERAKI_API_KEY,
        "Content-Type": "application/json"
    }
    url = f"https://api.meraki.com/api/v1/organizations/{ORGANIZATION_ID}/sensor/readings/latest"

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        datos = response.json()
        resultado = {}
        for sensor in datos:
            serial = sensor["serial"]
            readings = sensor.get("readings", {})
            for key, value in readings.items():
                resultado[f"{serial}_{key}"] = value.get("value")
        return resultado
    else:
        raise Exception(f"Error consultando Meraki: {response.text}")

# Función para guardar en Google Sheets
def guardar_en_sheets(datos):
    try:
        credentials = service_account.Credentials.from_service_account_file(CREDENTIALS_FILE)
        service = build("sheets", "v4", credentials=credentials)
        sheet = service.spreadsheets()

        fila = [str(time.strftime("%Y-%m-%d %H:%M:%S"))] + [str(v) for v in datos.values()]
        body = {"values": [fila]}

        sheet.values().append(
            spreadsheetId=SPREADSHEET_ID,
            range="Hoja1!A1",
            valueInputOption="RAW",
            body=body
        ).execute()
        logger.info("✅ Datos guardados en Google Sheets.")
    except Exception as e:
        logger.error(f"❌ Error guardando en Google Sheets: {e}")

# Ruta principal
@app.route("/")
def home():
    return send_from_directory("static", "index.html")

# Ruta para panel MT40
@app.route("/mt40")
def panel_mt40():
    return send_from_directory("static", "panel-mt40.html")

# Ruta de datos
@app.route("/sensor-data")
def sensor_data():
    try:
        datos = obtener_datos_sensor()
        return jsonify(datos)
    except Exception as e:
        logger.error(f"❌ Error general: {e}")
        return jsonify({"error": str(e)}), 500

# Función de guardado automático
def ciclo_guardado():
    while True:
        try:
            datos = obtener_datos_sensor()
            guardar_en_sheets(datos)
        except Exception as e:
            logger.error(f"❌ Error guardando automáticamente: {e}")
        time.sleep(60)

# Hilo de fondo
threading.Thread(target=ciclo_guardado, daemon=True).start()

# Ejecutar app
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
