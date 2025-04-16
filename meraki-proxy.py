from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
import requests
import json
import os
from datetime import datetime
import threading
import time
from google.oauth2 import service_account
from googleapiclient.discovery import build

app = Flask(__name__)
CORS(app)

# === Configuración ===
ORGANIZATION_ID = "1654515"
MERAKI_API_KEY = os.getenv("MERAKI_API_KEY")
SHEET_ID = "1tNx0hjnQzdUKoBvTmIsb9y3PaL3GYYNF3_bMDIIfgRA"
CREDENTIALS_PATH = "/etc/secrets/credentials.json"  # Ruta en Render

datos_sensores = {}  # Estado global con los datos actuales

# === API Meraki ===
def obtener_datos_sensores():
    url = f"https://api.meraki.com/api/v1/organizations/{ORGANIZATION_ID}/sensor/readings/latest"
    headers = {"X-Cisco-Meraki-API-Key": MERAKI_API_KEY}
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print("❌ Error al obtener datos Meraki:", response.status_code)
        return {}

    data = response.json()
    datos = {
        "sensor1": None,
        "sensor1_humidity": None,
        "sensor2": None,
        "sensor2_humidity": None,
        "multi1_temp": None,
        "multi1_co2": None,
        "multi1_pm25": None,
        "multi1_noise": None,
        "puerta1": None,
        "power1": None,
        "power2": None
    }

    for lectura in data:
        serial = lectura["serial"]
        for lectura_individual in lectura["readings"]:
            tipo = lectura_individual["metric"]
            valor = list(lectura_individual.values())[-1]

            if serial == "Q3CA-AT85-YJMB":  # Sensor 1
                if tipo == "temperature":
                    datos["sensor1"] = valor
                if tipo == "humidity":
                    datos["sensor1_humidity"] = valor

            elif serial == "Q3CA-5FF6-XF84":  # Sensor 2
                if tipo == "temperature":
                    datos["sensor2"] = valor
                if tipo == "humidity":
                    datos["sensor2_humidity"] = valor

            elif serial == "Q3CQ-YVSZ-BHKR":  # Sensor MT15
                if tipo == "temperature":
                    datos["multi1_temp"] = valor
                if tipo == "co2":
                    datos["multi1_co2"] = valor
                if tipo == "pm25":
                    datos["multi1_pm25"] = valor
                if tipo == "noise":
                    datos["multi1_noise"] = valor

            elif serial == "Q3CC-C9JS-4XB":  # Sensor Puerta MT20
                if tipo == "door":
                    datos["puerta1"] = valor["state"]

            elif serial == "Q3CJ-274W-5B5Z":  # MT40 1
                if tipo == "realPower":
                    datos["power1"] = valor["draw"]

            elif serial == "Q3CJ-GN4K-8VS4":  # MT40 2
                if tipo == "realPower":
                    datos["power2"] = valor["draw"]

    return datos

# === Google Sheets ===
def guardar_en_google_sheets(datos):
    try:
        creds = service_account.Credentials.from_service_account_file(
            CREDENTIALS_PATH,
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        service = build("sheets", "v4", credentials=creds)
        sheet = service.spreadsheets()

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        values = [
            [
                now,
                datos.get("sensor1"),
                datos.get("sensor1_humidity"),
                datos.get("sensor2"),
                datos.get("sensor2_humidity"),
                datos.get("multi1_temp"),
                datos.get("multi1_co2"),
                datos.get("multi1_pm25"),
                datos.get("multi1_noise"),
                datos.get("puerta1"),
                datos.get("power1"),
                datos.get("power2")
            ]
        ]
        body = {"values": values}
        sheet.values().append(
            spreadsheetId=SHEET_ID,
            range="Hoja1!A1",
            valueInputOption="RAW",
            body=body
        ).execute()
        print("✅ Datos guardados automáticamente en Google Sheets.")
    except Exception as e:
        print("❌ Error guardando en Sheets:", e)

# === Hilo de guardado automático ===
def auto_guardado():
    global datos_sensores
    while True:
        try:
            datos = obtener_datos_sensores()
            datos_sensores = datos
            guardar_en_google_sheets(datos)
        except Exception as e:
            print("❌ Error general:", e)
        time.sleep(60)

# === Rutas ===
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/sensor-data")
def sensor_data():
    return jsonify(datos_sensores)

@app.route("/mt40")
def panel_mt40():
    return render_template("panel-mt40.html")

# === Inicia ===
if __name__ == "__main__":
    threading.Thread(target=auto_guardado, daemon=True).start()
    app.run(host="0.0.0.0", port=10000)
