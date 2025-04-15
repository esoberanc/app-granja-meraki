
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
import requests
from datetime import datetime
import os
import threading
import time
from google.oauth2 import service_account
from googleapiclient.discovery import build

app = Flask(__name__)
CORS(app)

MERAKI_API_KEY = os.environ.get("MERAKI_API_KEY")
ORGANIZATION_ID = "1654515"

SENSORS = {
    "sensor1": "Q3CA-AT85-YJMB",
    "sensor2": "Q3CA-5FF6-XF84",
    "puerta1": "Q3CC-C9JS-4XB8",
    "multi1": "Q3CQ-YVSZ-BHKR",
    "power1": "Q3CJ-274W-5B5Z",
    "power2": "Q3CJ-GN4K-8VS4"
}

SPREADSHEET_ID = "1tNx0hjnQzdUKoBvTmIsb9y3PaL3GYYNF3_bMDIIfgRA"

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/mt40")
def mt40_panel():
    return render_template("panel-mt40.html")

@app.route("/sensor-data")
def sensor_data():
    try:
        headers = {
            "Authorization": f"Bearer {MERAKI_API_KEY}",
            "Content-Type": "application/json"
        }
        url = f"https://api.meraki.com/api/v1/organizations/{ORGANIZATION_ID}/sensor/readings/latest"
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            raise Exception("Error consultando Meraki")

        readings = response.json()

        data = {}
        for r in readings:
            serial = r["serial"]
            for item in r.get("readings", []):
                metric = item["metric"]
                value = list(item.values())[1]
                if serial == SENSORS["sensor1"]:
                    if metric == "temperature":
                        data["sensor1"] = value["value"]
                    elif metric == "humidity":
                        data["sensor1_humidity"] = value["value"]
                elif serial == SENSORS["sensor2"]:
                    if metric == "temperature":
                        data["sensor2"] = value["value"]
                    elif metric == "humidity":
                        data["sensor2_humidity"] = value["value"]
                elif serial == SENSORS["multi1"]:
                    if metric == "temperature":
                        data["multi1_temp"] = value["value"]
                    elif metric == "pm25":
                        data["multi1_pm25"] = value["value"]
                    elif metric == "noise":
                        data["multi1_noise"] = value["value"]
                    elif metric == "co2":
                        data["multi1_co2"] = value["value"]
                elif serial == SENSORS["puerta1"]:
                    if metric == "door":
                        data["puerta1"] = value["state"]
                elif serial == SENSORS["power1"]:
                    if metric == "realPower":
                        data["power1"] = value["draw"]
                    elif metric == "apparentPower":
                        data["apparentPower1"] = value["draw"]
                    elif metric == "voltage":
                        data["voltage1"] = value["level"]
                    elif metric == "current":
                        data["current1"] = value["draw"]
                    elif metric == "powerFactor":
                        data["powerFactor1"] = value["percentage"]
                    elif metric == "frequency":
                        data["frequency1"] = value["level"]
                elif serial == SENSORS["power2"]:
                    if metric == "realPower":
                        data["power2"] = value["draw"]
                    elif metric == "apparentPower":
                        data["apparentPower2"] = value["draw"]
                    elif metric == "voltage":
                        data["voltage2"] = value["level"]
                    elif metric == "current":
                        data["current2"] = value["draw"]
                    elif metric == "powerFactor":
                        data["powerFactor2"] = value["percentage"]
                    elif metric == "frequency":
                        data["frequency2"] = value["level"]

        return jsonify(data)

    except Exception as e:
        print(f"❌ Error general: {e}")
        return jsonify({"error": "Error al obtener datos"}), 500

def guardar_en_google_sheets(data):
    try:
        credentials = service_account.Credentials.from_service_account_file(
            "/etc/secrets/credentials.json",
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        service = build("sheets", "v4", credentials=credentials)
        sheet = service.spreadsheets()

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        fila = [
            now,
            data.get("sensor1"), data.get("sensor2"),
            data.get("sensor1_humidity"), data.get("sensor2_humidity"),
            data.get("multi1_temp"), data.get("multi1_co2"),
            data.get("multi1_pm25"), data.get("multi1_noise"),
            data.get("puerta1"),
            data.get("power1"), data.get("power2"),
            data.get("apparentPower1"), data.get("apparentPower2"),
            data.get("voltage1"), data.get("voltage2"),
            data.get("current1"), data.get("current2"),
            data.get("powerFactor1"), data.get("powerFactor2"),
            data.get("frequency1"), data.get("frequency2")
        ]

        sheet.values().append(
            spreadsheetId=SPREADSHEET_ID,
            range="Hoja1!A1",
            valueInputOption="RAW",
            body={"values": [fila]}
        ).execute()

        print("✅ Datos guardados automáticamente")

    except Exception as e:
        print(f"❌ Error guardando automáticamente: {e}")

def monitor_loop():
    while True:
        try:
            with app.test_request_context():
                response = sensor_data()
                if isinstance(response, tuple):
                    print("❌ No se obtuvieron datos válidos")
                else:
                    guardar_en_google_sheets(response.get_json())
        except Exception as e:
            print(f"❌ Error en loop de monitoreo: {e}")
        time.sleep(10)

if __name__ == "__main__":
    threading.Thread(target=monitor_loop, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
