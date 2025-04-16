from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
import requests
import datetime
import os
import json

app = Flask(__name__)
CORS(app)

MERAKI_API_KEY = os.environ.get("MERAKI_API_KEY")
ORGANIZATION_ID = "1654515"
SHEET_ID = "1tNx0hjnQzdUKoBvTmIsb9y3PaL3GYYNF3_bMDIIfgRA"
CREDENTIALS_PATH = "/etc/secrets/credentials.json"

SENSORES = {
    "sensor1": "Q3CA-AT85-YJMB",
    "sensor2": "Q3CA-5FF6-XF84",
    "multi1": "Q3CQ-YVSZ-BHKR",
    "puerta1": "Q3CC-C9JS-4XB",
    "mt40_1": "Q3CJ-274W-5B5Z",
    "mt40_2": "Q3CJ-GN4K-8VS4"
}

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/panel-mt40")
def panel_mt40():
    return render_template("panel-mt40.html")

@app.route("/sensor-data")
def sensor_data():
    guardar = request.args.get("guardar") == "true"
    headers = {
        "X-Cisco-Meraki-API-Key": MERAKI_API_KEY,
        "Content-Type": "application/json"
    }
    url = f"https://api.meraki.com/api/v1/organizations/{ORGANIZATION_ID}/sensor/readings/latest"
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        return jsonify({"error": "Error al obtener datos"}), 500

    data = response.json()
    sensores = {d["serial"]: d for d in data}
    
    def get_val(serial, metric, key):
        return next((r[metric][key] for r in sensores[serial]["readings"] if r["metric"] == metric), None)

    payload = {
        "sensor1": get_val(SENSORES["sensor1"], "temperature", "value"),
        "sensor1_humidity": get_val(SENSORES["sensor1"], "humidity", "value"),
        "sensor2": get_val(SENSORES["sensor2"], "temperature", "value"),
        "sensor2_humidity": get_val(SENSORES["sensor2"], "humidity", "value"),
        "multi1_temp": get_val(SENSORES["multi1"], "temperature", "value"),
        "multi1_co2": get_val(SENSORES["multi1"], "airQuality", "concentration"),
        "multi1_pm25": get_val(SENSORES["multi1"], "airQuality", "pm25"),
        "multi1_noise": get_val(SENSORES["multi1"], "noise", "value"),
        "puerta1": get_val(SENSORES["puerta1"], "door", "state"),
        "power1": get_val(SENSORES["mt40_1"], "realPower", "draw"),
        "power2": get_val(SENSORES["mt40_2"], "realPower", "draw"),
        "apparentPower1": get_val(SENSORES["mt40_1"], "apparentPower", "draw"),
        "apparentPower2": get_val(SENSORES["mt40_2"], "apparentPower", "draw"),
        "current1": get_val(SENSORES["mt40_1"], "current", "draw"),
        "current2": get_val(SENSORES["mt40_2"], "current", "draw"),
        "voltage1": get_val(SENSORES["mt40_1"], "voltage", "level"),
        "voltage2": get_val(SENSORES["mt40_2"], "voltage", "level"),
        "powerFactor1": get_val(SENSORES["mt40_1"], "powerFactor", "percentage"),
        "powerFactor2": get_val(SENSORES["mt40_2"], "powerFactor", "percentage"),
        "frequency1": get_val(SENSORES["mt40_1"], "frequency", "level"),
        "frequency2": get_val(SENSORES["mt40_2"], "frequency", "level")
    }

    if guardar:
        guardar_en_google(payload)

    return jsonify(payload)

def guardar_en_google(data):
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        credentials = service_account.Credentials.from_service_account_file(
            CREDENTIALS_PATH,
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        service = build("sheets", "v4", credentials=credentials)
        sheet = service.spreadsheets()

        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        fila = [now] + list(data.values())
        valores = [fila]
        rango = "Hoja1!A1"

        sheet.values().append(
            spreadsheetId=SHEET_ID,
            range=rango,
            valueInputOption="RAW",
            body={"values": valores}
        ).execute()

    except Exception as e:
        print("❌ Error al guardar en Google Sheets:", str(e))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
