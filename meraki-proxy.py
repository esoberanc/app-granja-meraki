import os
import time
import json
import logging
import requests
from flask import Flask, jsonify, render_template
from flask_cors import CORS
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Configuración
MERAKI_API_KEY = os.getenv("MERAKI_API_KEY")
ORGANIZATION_ID = "1654515"
SPREADSHEET_ID = "1tNx0hjnQzdUKoBvTmIsb9y3PaL3GYYNF3_bMDIIfgRA"
GOOGLE_CREDENTIALS_FILE = "/etc/secrets/credentials.json"

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)
CORS(app)

# === Funciones Google Sheets ===
def get_sheets_service():
    credentials = service_account.Credentials.from_service_account_file(
        GOOGLE_CREDENTIALS_FILE,
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return build("sheets", "v4", credentials=credentials).spreadsheets().values()

def guardar_en_google_sheets(datos):
    sheets = get_sheets_service()
    fila = [
        time.strftime("%Y-%m-%d %H:%M:%S"),
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
        datos.get("frequency1"),
        datos.get("frequency2"),
        datos.get("apparentPower1"),
        datos.get("apparentPower2")
    ]
    sheets.append(
        spreadsheetId=SPREADSHEET_ID,
        range="Hoja1!A1",
        valueInputOption="RAW",
        body={"values": [fila]}
    ).execute()
    logging.info("✅ Datos guardados correctamente en Google Sheets")

# === Función para obtener datos de sensores ===
def obtener_datos_sensores():
    url = f"https://api.meraki.com/api/v1/organizations/{ORGANIZATION_ID}/sensor/readings/latest"
    headers = {
        "X-Cisco-Meraki-API-Key": MERAKI_API_KEY,
        "Content-Type": "application/json"
    }

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        logging.error("❌ Error consultando Meraki")
        raise Exception("Error consultando Meraki")

    readings = response.json()
    datos = {}

    for lectura in readings:
        serial = lectura.get("serial")
        for r in lectura.get("readings", []):
            metric = r["metric"]
            valor = r.get(metric, {})
            if serial == "Q3CA-AT85-YJMB":
                if metric == "temperature":
                    datos["sensor1"] = valor.get("value")
                elif metric == "humidity":
                    datos["sensor1_humidity"] = valor.get("value")
            elif serial == "Q3CA-5FF6-XF84":
                if metric == "temperature":
                    datos["sensor2"] = valor.get("value")
                elif metric == "humidity":
                    datos["sensor2_humidity"] = valor.get("value")
            elif serial == "Q3CQ-YVSZ-BHKR":
                if metric == "temperature":
                    datos["multi1_temp"] = valor.get("value")
                elif metric == "co2":
                    datos["multi1_co2"] = valor.get("concentration")
                elif metric == "pm25":
                    datos["multi1_pm25"] = valor.get("concentration")
                elif metric == "noise":
                    datos["multi1_noise"] = valor.get("ambient", {}).get("level")
            elif serial == "Q3CC-C9JS-4XB":
                if metric == "door":
                    datos["puerta1"] = "open" if valor.get("open") else "closed"
            elif serial == "Q3CJ-274W-5B5Z":
                datos.update({
                    "power1": r.get("realPower", {}).get("draw"),
                    "powerFactor1": r.get("powerFactor", {}).get("percentage"),
                    "voltage1": r.get("voltage", {}).get("level"),
                    "current1": r.get("current", {}).get("draw"),
                    "frequency1": r.get("frequency", {}).get("level"),
                    "apparentPower1": r.get("apparentPower", {}).get("draw")
                })
            elif serial == "Q3CJ-GN4K-8VS4":
                datos.update({
                    "power2": r.get("realPower", {}).get("draw"),
                    "powerFactor2": r.get("powerFactor", {}).get("percentage"),
                    "voltage2": r.get("voltage", {}).get("level"),
                    "current2": r.get("current", {}).get("draw"),
                    "frequency2": r.get("frequency", {}).get("level"),
                    "apparentPower2": r.get("apparentPower", {}).get("draw")
                })

    return datos

# === Rutas ===
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/sensor-data")
def sensor_data():
    try:
        datos = obtener_datos_sensores()
        guardar_en_google_sheets(datos)
        return jsonify(datos)
    except Exception as e:
        logging.error(f"❌ Error general: {e}")
        return jsonify({"error": "Error obteniendo datos"}), 500

# === Main ===
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
