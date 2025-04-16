import os
import json
import requests
from flask import Flask, jsonify, render_template
from threading import Thread
import time
from datetime import datetime
import logging

# ==== CONFIGURACIÓN ====
app = Flask(__name__)
ORGANIZATION_ID = "1654515"
SHEET_ID = "1tNx0hjnQzdUKoBvTmIsb9y3PaL3GYYNF3_bMDIIfgRA"
MERAKI_API_KEY = os.getenv("MERAKI_API_KEY")
cred_path = "/etc/secrets/credentials.json"

# ==== LOGGING ====
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==== VARIABLE GLOBAL ====
datos_sensores = {}

# ==== FUNCIONES ====

def obtener_datos_sensores():
    url = f"https://api.meraki.com/api/v1/organizations/{ORGANIZATION_ID}/sensor/readings/latest"
    headers = {"X-Cisco-Meraki-API-Key": MERAKI_API_KEY}
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return response.json()
    else:
        logger.error(f"❌ Error consultando Meraki: {response.status_code} - {response.text}")
        return []

def extraer_metricas(data):
    resultado = {
        "timestamp": datetime.now().isoformat(),
        "temp1": None, "hum1": None,
        "temp2": None, "hum2": None,
        "temp3": None, "co2": None,
        "pm25": None, "noise": None,
        "puerta": None,
        "watts1": None, "watts2": None
    }

    for sensor in data:
        sid = sensor.get("serial")
        readings = sensor.get("readings", {})

        if sid == "Q3CA-AT85-YJMB":
            resultado["temp1"] = readings.get("temperature")
            resultado["hum1"] = readings.get("humidity")
        elif sid == "Q3CA-5FF6-XF84":
            resultado["temp2"] = readings.get("temperature")
            resultado["hum2"] = readings.get("humidity")
        elif sid == "Q3CQ-YVSZ-BHKR":
            resultado["temp3"] = readings.get("temperature")
            resultado["co2"] = readings.get("co2")
            resultado["pm25"] = readings.get("pm25")
            resultado["noise"] = readings.get("noise")
        elif sid == "Q3CC-C9JS-4XB":
            resultado["puerta"] = readings.get("door")
        elif sid == "Q3CJ-274W-5B5Z":
            resultado["watts1"] = readings.get("power")
        elif sid == "Q3CJ-GN4K-8VS4":
            resultado["watts2"] = readings.get("power")

    return resultado

def guardar_en_google_sheets(datos):
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        scope = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_file(cred_path, scopes=scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SHEET_ID).sheet1

        fila = [
            datos.get("timestamp"),
            datos.get("temp1"), datos.get("hum1"),
            datos.get("temp2"), datos.get("hum2"),
            datos.get("temp3"), datos.get("co2"),
            datos.get("pm25"), datos.get("noise"),
            datos.get("puerta"),
            datos.get("watts1"), datos.get("watts2")
        ]
        sheet.append_row(fila)
        logger.info("✅ Datos guardados en Google Sheets.")
    except Exception as e:
        logger.error(f"❌ Error al guardar en Google Sheets: {e}")

def ciclo_autoguardado():
    global datos_sensores
    while True:
        datos_api = obtener_datos_sensores()
        datos = extraer_metricas(datos_api)
        datos_sensores = datos
        guardar_en_google_sheets(datos)
        time.sleep(60)

# ==== RUTAS ====

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/sensor-data")
def sensor_data():
    return jsonify(datos_sensores)

@app.route("/mt40")
def panel_mt40():
    return render_template("panel-mt40.html")

# ==== INICIO DEL HILO AUTOMÁTICO ====

if __name__ == "__main__":
    Thread(target=ciclo_autoguardado, daemon=True).start()
    app.run(host="0.0.0.0", port=10000)
