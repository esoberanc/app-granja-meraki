
import os
import time
import logging
import threading
import requests
from flask import Flask, jsonify, render_template
from flask_cors import CORS
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Configuración inicial
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)

# Cargar claves desde archivos seguros
MERAKI_API_KEY = os.environ.get("MERAKI_API_KEY")
SHEET_ID = os.environ.get("SHEET_ID")
CREDENTIALS_PATH = "/etc/secrets/credentials.json"

# Parámetros Meraki
ORG_ID = "1654515"
SENSOR_IDS = {
    "sensor1": "Q3CA-AT85-YJMB",
    "sensor2": "Q3CA-5FF6-XF84",
    "multi1": "Q3CQ-YVSZ-BHKR",
    "puerta1": "Q3CC-C9JS-4XB",
    "mt40_1": "Q3CJ-274W-5B5Z",
    "mt40_2": "Q3CJ-GN4K-8VS4"
}
MERAKI_URL = f"https://api.meraki.com/api/v1/organizations/{ORG_ID}/sensor/readings/latest"

# Conexión a Google Sheets
def get_sheets_service():
    credentials = service_account.Credentials.from_service_account_file(
        CREDENTIALS_PATH,
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return build("sheets", "v4", credentials=credentials).spreadsheets().values()

# Función para consultar datos de sensores desde la API de Meraki
def obtener_datos():
    headers = {"X-Cisco-Meraki-API-Key": MERAKI_API_KEY}
    try:
        response = requests.get(MERAKI_URL, headers=headers)
        if response.status_code != 200:
            logger.error(f"❌ Error consultando Meraki: {response.status_code} - {response.text}")
            return None
        readings = response.json()
        datos = {}
        for lectura in readings:
            serial = lectura.get("serial")
            for key, sid in SENSOR_IDS.items():
                if serial == sid:
                    metric = lectura.get("metric")
                    valor = list(lectura.values())[2]
                    if isinstance(valor, dict):
                        datos[f"{key}_{metric}"] = list(valor.values())[0]
                    elif isinstance(valor, str):
                        datos[f"{key}_{metric}"] = valor
        logger.info("✅ Datos obtenidos correctamente")
        return datos
    except Exception as e:
        logger.error(f"❌ Error general: {e}")
        return None

# Función para guardar los datos en Google Sheets
def guardar_en_sheets(datos):
    try:
        sheets = get_sheets_service()
        valores = [
            time.strftime("%Y-%m-%d %H:%M:%S"),
            datos.get("sensor1_temperature", ""),
            datos.get("sensor1_humidity", ""),
            datos.get("sensor2_temperature", ""),
            datos.get("sensor2_humidity", ""),
            datos.get("multi1_temperature", ""),
            datos.get("multi1_co2", ""),
            datos.get("multi1_pm25", ""),
            datos.get("multi1_noise", ""),
            datos.get("puerta1_open", ""),
            datos.get("mt40_1_power", ""),
            datos.get("mt40_2_power", ""),
            datos.get("mt40_1_powerFactor", ""),
            datos.get("mt40_2_powerFactor", ""),
            datos.get("mt40_1_voltage", ""),
            datos.get("mt40_2_voltage", ""),
            datos.get("mt40_1_current", ""),
            datos.get("mt40_2_current", ""),
            datos.get("mt40_1_apparentPower", ""),
            datos.get("mt40_2_apparentPower", ""),
            datos.get("mt40_1_frequency", ""),
            datos.get("mt40_2_frequency", "")
        ]
        sheets.append(
            spreadsheetId=SHEET_ID,
            range="Hoja1!A1",
            body={"values": [valores]},
            valueInputOption="RAW"
        ).execute()
        logger.info("✅ Datos guardados en Google Sheets")
    except Exception as e:
        logger.error(f"❌ Error guardando en Sheets: {e}")

# Hilo en segundo plano para guardar automáticamente
def hilo_monitoreo():
    while True:
        datos = obtener_datos()
        if datos:
            guardar_en_sheets(datos)
        time.sleep(60)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/sensor-data")
def sensor_data():
    datos = obtener_datos()
    if not datos:
        return jsonify({"error": "No se pudo obtener información"}), 500
    return jsonify(datos)

@app.route("/mt40")
def panel_mt40():
    return render_template("panel-mt40.html")

# Lanzar hilo automático
if __name__ == "__main__":
    threading.Thread(target=hilo_monitoreo, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
