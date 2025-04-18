from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
import requests
from datetime import datetime
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
import threading
import time

app = Flask(__name__)
CORS(app)

MERAKI_API_KEY = os.environ.get("MERAKI_API_KEY")
ORGANIZATION_ID = "1654515"
SPREADSHEET_ID = "1tNx0hjnQzdUKoBvTmIsb9y3PaL3GYYNF3_bMDIIfgRA"

SENSORS = {
    "sensor1": "Q3CA-AT85-YJMB",
    "sensor2": "Q3CA-5FF6-XF84",
    "puerta1": "Q3CC-C9JS-4XB8",
    "multi1": "Q3CQ-YVSZ-BHKR",
    "power1": "Q3CJ-274W-5B5Z",
    "power2": "Q3CJ-GN4K-8VS4"
}

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/mt40")
def mt40_panel():
    return render_template("panel-mt40.html")

def guardar_en_sheets(sensor_data):
    try:
        creds = service_account.Credentials.from_service_account_file(
            "/etc/secrets/credentials.json",
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        service = build('sheets', 'v4', credentials=creds)
        sheet = service.spreadsheets()

        fila = [
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            sensor_data.get("sensor1"),
            sensor_data.get("sensor2"),
            sensor_data.get("sensor1_humidity"),
            sensor_data.get("sensor2_humidity"),
            sensor_data.get("multi1_temp"),
            sensor_data.get("multi1_co2"),
            sensor_data.get("multi1_pm25"),
            sensor_data.get("multi1_noise"),
            sensor_data.get("puerta1"),
            sensor_data.get("power1"),
            sensor_data.get("power2"),
            sensor_data.get("powerFactor1"),
            sensor_data.get("powerFactor2"),
            sensor_data.get("apparentPower1"),
            sensor_data.get("apparentPower2"),
            sensor_data.get("voltage1"),
            sensor_data.get("voltage2"),
            sensor_data.get("current1"),
            sensor_data.get("current2"),
            sensor_data.get("frequency1"),
            sensor_data.get("frequency2"),
        ]
        body = {'values': [fila]}
        sheet.values().append(
            spreadsheetId=SPREADSHEET_ID,
            range='Hoja1!A1',
            valueInputOption='RAW',
            body=body
        ).execute()
    except Exception as e:
        print("❌ Error al guardar en Sheets:", e)

@app.route("/sensor-data")
def obtener_datos_y_guardar():
    url = f"https://api.meraki.com/api/v1/organizations/{ORGANIZATION_ID}/sensor/readings/latest"
    headers = {
        "X-Cisco-Meraki-API-Key": MERAKI_API_KEY,
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        result = {}

        for sensor in data:
            serial = sensor["serial"]
            if serial not in SENSORS.values():
                continue

            for reading in sensor["readings"]:
                metric = reading["metric"]

                if metric == "temperature":
                    temp = reading["temperature"]["celsius"]
                    if serial == SENSORS["sensor1"]:
                        result["sensor1"] = temp
                    elif serial == SENSORS["sensor2"]:
                        result["sensor2"] = temp
                    elif serial == SENSORS["multi1"]:
                        result["multi1_temp"] = temp

                elif metric == "humidity":
                    humedad = reading["humidity"]["relativePercentage"]
                    if serial == SENSORS["sensor1"]:
                        result["sensor1_humidity"] = humedad
                    elif serial == SENSORS["sensor2"]:
                        result["sensor2_humidity"] = humedad

                elif metric == "door" and serial == SENSORS["puerta1"]:
                    estado = reading["door"]["open"]
                    result["puerta1"] = "open" if estado else "closed"

                elif metric == "co2" and serial == SENSORS["multi1"]:
                    result["multi1_co2"] = reading["co2"]["concentration"]

                elif metric == "noise" and serial == SENSORS["multi1"]:
                    result["multi1_noise"] = reading["noise"]["ambient"]["level"]

                elif metric == "pm25" and serial == SENSORS["multi1"]:
                    result["multi1_pm25"] = reading["pm25"]["concentration"]

                elif metric == "powerFactor":
                    if serial == SENSORS["power1"]:
                        result["powerFactor1"] = reading["powerFactor"]["percentage"]
                    elif serial == SENSORS["power2"]:
                        result["powerFactor2"] = reading["powerFactor"]["percentage"]

                elif metric == "apparentPower":
                    if serial == SENSORS["power1"]:
                        result["apparentPower1"] = reading["apparentPower"]["draw"]
                    elif serial == SENSORS["power2"]:
                        result["apparentPower2"] = reading["apparentPower"]["draw"]

                elif metric == "voltage":
                    if serial == SENSORS["power1"]:
                        result["voltage1"] = reading["voltage"]["level"]
                    elif serial == SENSORS["power2"]:
                        result["voltage2"] = reading["voltage"]["level"]

                elif metric == "current":
                    if serial == SENSORS["power1"]:
                        result["current1"] = reading["current"]["draw"]
                    elif serial == SENSORS["power2"]:
                        result["current2"] = reading["current"]["draw"]

                elif metric == "frequency":
                    if serial == SENSORS["power1"]:
                        result["frequency1"] = reading["frequency"]["level"]
                    elif serial == SENSORS["power2"]:
                        result["frequency2"] = reading["frequency"]["level"]

                elif metric == "realPower":
                    draw = reading["realPower"]["draw"]
                    if serial == SENSORS["power1"]:
                        result["power1"] = draw
                    elif serial == SENSORS["power2"]:
                        result["power2"] = draw

        guardar_en_sheets(result)
        return jsonify(result)
    

    except Exception as e:
        print("❌ Error general:", e)
    
def iniciar_monitoreo_automatico():
    def loop():
        while True:
            obtener_datos_y_guardar()
            time.sleep(30)

    hilo = threading.Thread(target=loop, daemon=True)
    hilo.start()

if __name__ == "__main__":
    iniciar_monitoreo_automatico()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
