from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import requests
import os
import datetime
import logging
import google.auth
from google.oauth2 import service_account
from googleapiclient.discovery import build

app = Flask(__name__)
CORS(app)

# Configuración básica de logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cargar variables de entorno
MERAKI_API_KEY = os.environ.get("MERAKI_API_KEY")
GOOGLE_SHEET_ID = os.environ.get("GOOGLE_SHEET_ID")
ORGANIZATION_ID = os.environ.get("MERAKI_ORG_ID")

CREDENTIALS_PATH = "/etc/secrets/credentials.json"  # Render location

def get_sensor_data():
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

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/panel-mt40")
def panel_mt40():
    return render_template("panel_mt40.html")

@app.route("/sensor-data")
def sensor_data():
    guardar = request.args.get("guardar", "false").lower() == "true"
    datos = procesar_datos()

    if guardar and datos:
        guardar_en_google_sheets(datos)
    return jsonify(datos or {})

def procesar_datos():
    data = get_sensor_data()
    if not data:
        return {}

    lectura = {}
    for s in data:
        sid = s["sensor"]["serial"]
        if sid == "Q3CA-AT85-YJMB":
            lectura["sensor1"] = s["readings"].get("temperature", {}).get("value")
            lectura["sensor1_humidity"] = s["readings"].get("humidity", {}).get("value")
        elif sid == "Q3CA-5FF6-XF84":
            lectura["sensor2"] = s["readings"].get("temperature", {}).get("value")
            lectura["sensor2_humidity"] = s["readings"].get("humidity", {}).get("value")
        elif sid == "Q3CQ-YVSZ-BHKR":
            lectura["multi1_temp"] = s["readings"].get("temperature", {}).get("value")
            lectura["multi1_co2"] = s["readings"].get("co2", {}).get("value")
            lectura["multi1_pm25"] = s["readings"].get("pm25", {}).get("value")
            lectura["multi1_noise"] = s["readings"].get("noise", {}).get("value")
        elif sid == "Q3CC-C9JS-4XB":
            lectura["puerta1"] = s["readings"].get("door", {}).get("value")
        elif sid == "Q3CJ-274W-5B5Z":
            lectura["power1"] = s["readings"].get("power", {}).get("value")
            lectura["voltage1"] = s["readings"].get("voltage", {}).get("value")
            lectura["current1"] = s["readings"].get("current", {}).get("value")
            lectura["powerFactor1"] = s["readings"].get("powerFactor", {}).get("value")
            lectura["apparentPower1"] = s["readings"].get("apparentPower", {}).get("value")
            lectura["frequency1"] = s["readings"].get("frequency", {}).get("value")
        elif sid == "Q3CJ-GN4K-8VS4":
            lectura["power2"] = s["readings"].get("power", {}).get("value")
            lectura["voltage2"] = s["readings"].get("voltage", {}).get("value")
            lectura["current2"] = s["readings"].get("current", {}).get("value")
            lectura["powerFactor2"] = s["readings"].get("powerFactor", {}).get("value")
            lectura["apparentPower2"] = s["readings"].get("apparentPower", {}).get("value")
            lectura["frequency2"] = s["readings"].get("frequency", {}).get("value")

    return lectura

def guardar_en_google_sheets(datos):
    try:
        creds = service_account.Credentials.from_service_account_file(
            CREDENTIALS_PATH,
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        service = build("sheets", "v4", credentials=creds)
        sheet = service.spreadsheets()

        valores = [
            datetime.datetime.now().isoformat(),
            datos.get("sensor1"),
            datos.get("sensor2"),
            datos.get("sensor1_humidity"),
            datos.get("sensor2_humidity"),
            datos.get("multi1_temp"),
            datos.get("multi1_co2"),
            datos.get("multi1_pm25"),
            datos.get("multi1_noise"),
            datos.get("puerta1"),
            datos.get("power1"),
            datos.get("power2"),
            datos.get("powerFactor1"),
            datos.get("powerFactor2"),
            datos.get("voltage1"),
            datos.get("voltage2"),
            datos.get("current1"),
            datos.get("current2"),
            datos.get("apparentPower1"),
            datos.get("apparentPower2"),
            datos.get("frequency1"),
            datos.get("frequency2"),
        ]

        sheet.values().append(
            spreadsheetId=GOOGLE_SHEET_ID,
            range="Hoja1!A1",
            valueInputOption="RAW",
            body={"values": [valores]}
        ).execute()
        logger.info("✅ Datos guardados correctamente.")
    except Exception as e:
        logger.error(f"❌ Error guardando en Google Sheets: {e}")

if __name__ == "__main__":
    app.run(debug=True, port=5000)
