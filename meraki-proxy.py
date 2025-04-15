
import os
import json
import requests
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from datetime import datetime
import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Configuración básica
app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)

# Claves de entorno
MERAKI_API_KEY = os.environ.get("MERAKI_API_KEY")
GOOGLE_SHEET_ID = os.environ.get("GOOGLE_SHEET_ID")
ORGANIZATION_ID = os.environ.get("MERAKI_ORG_ID")

# Ruta del archivo de credenciales de Google
CREDENTIALS_PATH = "/etc/secrets/credentials.json"

# Sensores usados
SENSORES = {
    "sensor1": "Q3CA-AT85-YJMB",
    "sensor2": "Q3CA-5FF6-XF84",
    "multi1": "Q3CQ-YVSZ-BHKR",
    "puerta1": "Q3CC-C9JS-4XB",
    "mt40_1": "Q3CJ-274W-5B5Z",
    "mt40_2": "Q3CJ-GN4K-8VS4"
}

def get_google_service():
    credentials = service_account.Credentials.from_service_account_file(
        CREDENTIALS_PATH,
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return build("sheets", "v4", credentials=credentials).spreadsheets()

def obtener_datos():
    url = f"https://api.meraki.com/api/v1/organizations/{ORGANIZATION_ID}/sensor/readings/latest"
    headers = {"X-Cisco-Meraki-API-Key": MERAKI_API_KEY}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Error consultando Meraki: {response.status_code}")
    return response.json()

def parsear_datos(data):
    valores = {}
    for lectura in data:
        sensor = lectura.get("serial")
        metrics = lectura.get("metrics", {})
        if sensor == SENSORES["sensor1"]:
            valores["sensor1"] = metrics.get("temperature", {}).get("value")
            valores["sensor1_humidity"] = metrics.get("humidity", {}).get("value")
        elif sensor == SENSORES["sensor2"]:
            valores["sensor2"] = metrics.get("temperature", {}).get("value")
            valores["sensor2_humidity"] = metrics.get("humidity", {}).get("value")
        elif sensor == SENSORES["multi1"]:
            valores["multi1_temp"] = metrics.get("temperature", {}).get("value")
            valores["multi1_co2"] = metrics.get("airQuality", {}).get("concentration")
            valores["multi1_pm25"] = metrics.get("airQuality", {}).get("pm25")
            valores["multi1_noise"] = metrics.get("noise", {}).get("value")
        elif sensor == SENSORES["puerta1"]:
            valores["puerta1"] = metrics.get("door", {}).get("value")
        elif sensor == SENSORES["mt40_1"]:
            valores["power1"] = metrics.get("power", {}).get("apparent")
            valores["current1"] = metrics.get("current", {}).get("value")
            valores["voltage1"] = metrics.get("voltage", {}).get("value")
            valores["powerFactor1"] = metrics.get("power", {}).get("factor")
            valores["frequency1"] = metrics.get("frequency", {}).get("value")
        elif sensor == SENSORES["mt40_2"]:
            valores["power2"] = metrics.get("power", {}).get("apparent")
            valores["current2"] = metrics.get("current", {}).get("value")
            valores["voltage2"] = metrics.get("voltage", {}).get("value")
            valores["powerFactor2"] = metrics.get("power", {}).get("factor")
            valores["frequency2"] = metrics.get("frequency", {}).get("value")
    return valores

def guardar_en_google_sheets(valores):
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fila = [
        ahora,
        valores.get("sensor1"), valores.get("sensor1_humidity"),
        valores.get("sensor2"), valores.get("sensor2_humidity"),
        valores.get("multi1_temp"), valores.get("multi1_co2"), valores.get("multi1_pm25"), valores.get("multi1_noise"),
        valores.get("puerta1"),
        valores.get("power1"), valores.get("power2"),
        valores.get("powerFactor1"), valores.get("powerFactor2"),
        valores.get("voltage1"), valores.get("voltage2"),
        valores.get("current1"), valores.get("current2"),
        valores.get("frequency1"), valores.get("frequency2")
    ]
    service = get_google_service()
    service.values().append(
        spreadsheetId=GOOGLE_SHEET_ID,
        range="Hoja1!A1",
        body={"values": [fila]},
        valueInputOption="RAW"
    ).execute()

@app.route("/sensor-data")
def sensor_data():
    try:
        logging.info("✅ Backend Meraki activo.")
        datos = parsear_datos(obtener_datos())
        guardar_en_google_sheets(datos)
        return jsonify(datos)
    except Exception as e:
        logging.error(f"❌ Error guardando automáticamente: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
