import os
import time
import json
import threading
import requests
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Configuración
SPREADSHEET_ID = "1tNx0hjnQzdUKoBvTmIsb9y3PaL3GYYNF3_bMDIIfgRA"
RANGE_NAME = "Hoja1!A1"
ORGANIZATION_ID = "1654515"
SENSORES = {
    "sensor1": "Q3CA-AT85-YJMB",
    "sensor2": "Q3CA-5FF6-XF84",
    "multi1": "Q3CQ-YVSZ-BHKR",
    "puerta1": "Q3CC-C9JS-4XB",
    "mt40_1": "Q3CJ-274W-5B5Z",
    "mt40_2": "Q3CJ-GN4K-8VS4"
}

app = Flask(__name__)
CORS(app)

def obtener_datos_sensores():
    try:
        headers = {
            "X-Cisco-Meraki-API-Key": os.getenv("MERAKI_API_KEY"),
            "Content-Type": "application/json"
        }

        url = f"https://api.meraki.com/api/v1/organizations/{ORGANIZATION_ID}/sensor/readings/latest"
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            raise Exception("Error al consultar sensores")

        data = response.json()
        datos = {
            "sensor1": None,
            "sensor2": None,
            "sensor1_humidity": None,
            "sensor2_humidity": None,
            "multi1_temp": None,
            "multi1_co2": None,
            "multi1_pm25": None,
            "multi1_noise": None,
            "puerta1": None,
            "power1": None,
            "power2": None,
            "powerFactor1": None,
            "powerFactor2": None,
            "voltage1": None,
            "voltage2": None,
            "current1": None,
            "current2": None,
            "apparentPower1": None,
            "apparentPower2": None,
            "frequency1": None,
            "frequency2": None,
        }

        for sensor in data:
            serial = sensor["serial"]
            for lectura in sensor["readings"]:
                if serial == SENSORES["sensor1"] and lectura["metric"] == "temperature":
                    datos["sensor1"] = lectura["temperature"]["value"]
                if serial == SENSORES["sensor1"] and lectura["metric"] == "humidity":
                    datos["sensor1_humidity"] = lectura["humidity"]["value"]
                if serial == SENSORES["sensor2"] and lectura["metric"] == "temperature":
                    datos["sensor2"] = lectura["temperature"]["value"]
                if serial == SENSORES["sensor2"] and lectura["metric"] == "humidity":
                    datos["sensor2_humidity"] = lectura["humidity"]["value"]
                if serial == SENSORES["multi1"]:
                    if lectura["metric"] == "temperature":
                        datos["multi1_temp"] = lectura["temperature"]["value"]
                    if lectura["metric"] == "co2":
                        datos["multi1_co2"] = lectura["co2"]["value"]
                    if lectura["metric"] == "pm25":
                        datos["multi1_pm25"] = lectura["pm25"]["value"]
                    if lectura["metric"] == "noise":
                        datos["multi1_noise"] = lectura["noise"]["value"]
                if serial == SENSORES["puerta1"] and lectura["metric"] == "door":
                    datos["puerta1"] = lectura["door"]["value"]
                if serial == SENSORES["mt40_1"]:
                    if lectura["metric"] == "realPower":
                        datos["power1"] = lectura["realPower"]["draw"]
                    if lectura["metric"] == "powerFactor":
                        datos["powerFactor1"] = lectura["powerFactor"]["percentage"]
                    if lectura["metric"] == "voltage":
                        datos["voltage1"] = lectura["voltage"]["level"]
                    if lectura["metric"] == "current":
                        datos["current1"] = lectura["current"]["draw"]
                    if lectura["metric"] == "apparentPower":
                        datos["apparentPower1"] = lectura["apparentPower"]["draw"]
                    if lectura["metric"] == "frequency":
                        datos["frequency1"] = lectura["frequency"]["level"]
                if serial == SENSORES["mt40_2"]:
                    if lectura["metric"] == "realPower":
                        datos["power2"] = lectura["realPower"]["draw"]
                    if lectura["metric"] == "powerFactor":
                        datos["powerFactor2"] = lectura["powerFactor"]["percentage"]
                    if lectura["metric"] == "voltage":
                        datos["voltage2"] = lectura["voltage"]["level"]
                    if lectura["metric"] == "current":
                        datos["current2"] = lectura["current"]["draw"]
                    if lectura["metric"] == "apparentPower":
                        datos["apparentPower2"] = lectura["apparentPower"]["draw"]
                    if lectura["metric"] == "frequency":
                        datos["frequency2"] = lectura["frequency"]["level"]
        return datos
    except Exception as e:
        print("❌ Error general:", e)
        return {}

def guardar_en_google_sheets(datos):
    try:
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
        SERVICE_ACCOUNT_FILE = '/etc/secrets/credentials.json'
        credentials = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        service = build('sheets', 'v4', credentials=credentials)

        values = [[
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
            datos.get("apparentPower1"),
            datos.get("apparentPower2"),
            datos.get("frequency1"),
            datos.get("frequency2"),
        ]]

        body = {
            'values': values
        }
        service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=RANGE_NAME,
            valueInputOption='RAW',
            body=body
        ).execute()
        print("✅ Datos guardados en Google Sheets")
    except Exception as e:
        print("❌ Error al guardar en Sheets:", e)

def auto_guardado():
    while True:
        datos = obtener_datos_sensores()
        if datos:
            guardar_en_google_sheets(datos)
        time.sleep(10)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/sensor-data")
def sensor_data():
    datos = obtener_datos_sensores()
    return jsonify(datos)

@app.route("/mt40")
def mt40_panel():
    return render_template("panel-mt40.html")

if __name__ == "__main__":
    hilo = threading.Thread(target=auto_guardado)
    hilo.daemon = True
    hilo.start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
