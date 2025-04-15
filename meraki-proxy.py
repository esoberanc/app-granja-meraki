
import json
import time
import logging
import threading
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
import requests
import os
import gspread
from google.oauth2 import service_account
from datetime import datetime

app = Flask(__name__)
CORS(app)

# --- CONFIGURACIÓN ---
MERAKI_API_KEY = os.environ.get("MERAKI_API_KEY")
ORG_ID = "1654515"
NETWORK_ID = "L_3859584880656517373"
SPREADSHEET_ID = "1tNx0hjnQzdUKoBvTmIsb9y3PaL3GYYNF3_bMDIIfgRA"
GOOGLE_CREDS_PATH = "/etc/secrets/credentials.json"
openai_api_key_path = "/etc/secrets/openai_key.txt"

try:
    with open(openai_api_key_path, "r") as f:
        os.environ["OPENAI_API_KEY"] = f.read().strip()
except Exception:
    pass

HEADERS = {
    "X-Cisco-Meraki-API-Key": MERAKI_API_KEY,
    "Content-Type": "application/json"
}

logging.basicConfig(level=logging.INFO)

def get_sensor_data():
    url = f"https://api.meraki.com/api/v1/networks/{NETWORK_ID}/sensor/readings/latest"
    response = requests.get(url, headers=HEADERS)
    if response.status_code != 200:
        raise Exception("Error al obtener datos de sensores")
    return response.json()

def extract_values(readings):
    values = {}
    for reading in readings:
        metric = reading.get("metric")
        if "temperature" in metric:
            values["temp"] = reading[metric]["value"]
        elif "humidity" in metric:
            values["humidity"] = reading[metric]["value"]
        elif "co2" in metric:
            values["co2"] = reading[metric]["ppm"]
        elif "pm25" in metric:
            values["pm25"] = reading[metric]["ugPerM3"]
        elif "noise" in metric:
            values["noise"] = reading[metric]["dB"]
        elif "state" in metric:
            values["door"] = reading[metric]["state"]
        elif "realPower" in metric:
            if "Q3CJ-274W-5B5Z" in reading["serial"]:
                values["power1"] = reading[metric]["draw"]
            else:
                values["power2"] = reading[metric]["draw"]
        elif "powerFactor" in metric:
            if "Q3CJ-274W-5B5Z" in reading["serial"]:
                values["powerFactor1"] = reading[metric]["percentage"]
            else:
                values["powerFactor2"] = reading[metric]["percentage"]
        elif "voltage" in metric:
            if "Q3CJ-274W-5B5Z" in reading["serial"]:
                values["voltage1"] = reading[metric]["level"]
            else:
                values["voltage2"] = reading[metric]["level"]
        elif "current" in metric:
            if "Q3CJ-274W-5B5Z" in reading["serial"]:
                values["current1"] = reading[metric]["draw"]
            else:
                values["current2"] = reading[metric]["draw"]
        elif "apparentPower" in metric:
            if "Q3CJ-274W-5B5Z" in reading["serial"]:
                values["apparentPower1"] = reading[metric]["draw"]
            else:
                values["apparentPower2"] = reading[metric]["draw"]
        elif "frequency" in metric:
            if "Q3CJ-274W-5B5Z" in reading["serial"]:
                values["frequency1"] = reading[metric]["level"]
            else:
                values["frequency2"] = reading[metric]["level"]
    return values

def get_sheets_service():
    credentials = service_account.Credentials.from_service_account_file(
        GOOGLE_CREDS_PATH,
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return gspread.authorize(credentials)

def guardar_en_google_sheets(datos):
    try:
        gc = get_sheets_service()
        sh = gc.open_by_key(SPREADSHEET_ID)
        worksheet = sh.sheet1
        fila = [
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            datos.get("sensor1", ""),
            datos.get("sensor2", ""),
            datos.get("sensor1_humidity", ""),
            datos.get("sensor2_humidity", ""),
            datos.get("multi1_temp", ""),
            datos.get("multi1_co2", ""),
            datos.get("multi1_pm25", ""),
            datos.get("multi1_noise", ""),
            datos.get("puerta1", ""),
            datos.get("power1", ""),
            datos.get("power2", ""),
            datos.get("powerFactor1", ""),
            datos.get("powerFactor2", ""),
            datos.get("apparentPower1", ""),
            datos.get("apparentPower2", ""),
            datos.get("voltage1", ""),
            datos.get("voltage2", ""),
            datos.get("current1", ""),
            datos.get("current2", ""),
            datos.get("frequency1", ""),
            datos.get("frequency2", "")
        ]
        worksheet.append_row(fila)
        logging.info("✅ Datos guardados en Google Sheets.")
    except Exception as e:
        logging.error(f"❌ Error guardando automáticamente: {e}")

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/sensor-data")
def sensor_data():
    try:
        response = get_sensor_data()
        datos = extract_values(response)
        guardar = request.args.get("guardar", "true").lower() == "true"
        if guardar:
            guardar_en_google_sheets(datos)
        return jsonify(datos)
    except Exception as e:
        logging.error(f"❌ Error general: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/mt40")
def panel_mt40():
    return render_template("panel-mt40.html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
