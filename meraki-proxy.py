from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import os
import requests
import datetime
import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build

app = Flask(__name__)
CORS(app)

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Leer claves desde variables de entorno
MERAKI_API_KEY = os.getenv("MERAKI_API_KEY")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
ORGANIZATION_ID = os.getenv("ORGANIZATION_ID")

# Función para obtener datos de Meraki
def obtener_datos_meraki():
    url = f"https://api.meraki.com/api/v1/organizations/{ORGANIZATION_ID}/sensor/readings/latest"
    headers = {
        "X-Cisco-Meraki-API-Key": MERAKI_API_KEY,
        "Content-Type": "application/json"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        logger.error(f"❌ Error consultando Meraki: {response.status_code} - {response.text}")
        return None

# Función para filtrar y estructurar datos por sensor
def procesar_datos_meraki(raw_data):
    data = {}
    sensores = {
        "Q3CA-AT85-YJMB": "sensor1",
        "Q3CA-5FF6-XF84": "sensor2",
        "Q3CQ-YVSZ-BHKR": "multi1",
        "Q3CC-C9JS-4XB": "puerta1",
        "Q3CJ-274W-5B5Z": "mt40_1",
        "Q3CJ-GN4K-8VS4": "mt40_2"
    }

    for reading in raw_data:
        serial = reading.get("serial")
        nombre = sensores.get(serial)
        if not nombre:
            continue

        for r in reading.get("readings", []):
            metric = r.get("metric")
            if nombre == "sensor1" and metric == "temperature":
                data["sensor1"] = r["temperature"]["value"]
            if nombre == "sensor1" and metric == "humidity":
                data["sensor1_humidity"] = r["humidity"]["value"]
            if nombre == "sensor2" and metric == "temperature":
                data["sensor2"] = r["temperature"]["value"]
            if nombre == "sensor2" and metric == "humidity":
                data["sensor2_humidity"] = r["humidity"]["value"]
            if nombre == "multi1":
                if metric == "temperature":
                    data["multi1_temp"] = r["temperature"]["value"]
                if metric == "co2":
                    data["multi1_co2"] = r["co2"]["value"]
                if metric == "pm25":
                    data["multi1_pm25"] = r["pm25"]["value"]
                if metric == "noise":
                    data["multi1_noise"] = r["noise"]["value"]
            if nombre == "puerta1" and metric == "door":
                data["puerta1"] = r["door"]["value"]
            if nombre == "mt40_1":
                if metric == "realPower":
                    data["power1"] = r["realPower"]["draw"]
                if metric == "apparentPower":
                    data["apparentPower1"] = r["apparentPower"]["draw"]
                if metric == "current":
                    data["current1"] = r["current"]["draw"]
                if metric == "voltage":
                    data["voltage1"] = r["voltage"]["level"]
                if metric == "powerFactor":
                    data["powerFactor1"] = r["powerFactor"]["percentage"]
                if metric == "frequency":
                    data["frequency1"] = r["frequency"]["level"]
            if nombre == "mt40_2":
                if metric == "realPower":
                    data["power2"] = r["realPower"]["draw"]
                if metric == "apparentPower":
                    data["apparentPower2"] = r["apparentPower"]["draw"]
                if metric == "current":
                    data["current2"] = r["current"]["draw"]
                if metric == "voltage":
                    data["voltage2"] = r["voltage"]["level"]
                if metric == "powerFactor":
                    data["powerFactor2"] = r["powerFactor"]["percentage"]
                if metric == "frequency":
                    data["frequency2"] = r["frequency"]["level"]

    return data

# Función para guardar en Google Sheets
def guardar_en_google_sheets(data):
    logger.info("✅ Guardando en Google Sheets...")
    try:
        SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
        SERVICE_ACCOUNT_FILE = "/etc/secrets/credentials.json"
        credentials = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )
        service = build("sheets", "v4", credentials=credentials)
        sheet = service.spreadsheets()

        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        valores = [
            now,
            data.get("sensor1"), data.get("sensor2"),
            data.get("sensor1_humidity"), data.get("sensor2_humidity"),
            data.get("multi1_temp"), data.get("multi1_co2"),
            data.get("multi1_pm25"), data.get("multi1_noise"),
            data.get("puerta1"),
            data.get("power1"), data.get("power2"),
            data.get("apparentPower1"), data.get("apparentPower2"),
            data.get("current1"), data.get("current2"),
            data.get("voltage1"), data.get("voltage2"),
            data.get("powerFactor1"), data.get("powerFactor2"),
            data.get("frequency1"), data.get("frequency2")
        ]

        body = {"values": [valores]}
        sheet.values().append(
            spreadsheetId=SPREADSHEET_ID,
            range="Hoja1!A1",
            valueInputOption="RAW",
            body=body,
        ).execute()
    except Exception as e:
        logger.error(f"❌ Error guardando automáticamente: {e}")

# Rutas
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/sensor-data")
def sensor_data():
    logger.info("📡 Llamando a sensor-data")
    data = obtener_datos_meraki()
    if data:
        parsed = procesar_datos_meraki(data)
        guardar_en_google_sheets(parsed)
        return jsonify(parsed)
    else:
        return jsonify({"error": "No se pudo obtener datos"}), 500

@app.route("/mt40")
def mt40_panel():
    return render_template("panel-mt40.html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
