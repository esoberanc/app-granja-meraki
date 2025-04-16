from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
import requests
import datetime
import os
import google.auth
from google.oauth2 import service_account
from googleapiclient.discovery import build

app = Flask(__name__)
CORS(app)

# Configuración
MERAKI_API_KEY = os.environ.get("MERAKI_API_KEY")
ORGANIZATION_ID = "1654515"
SHEET_ID = "1tNx0hjnQzdUKoBvTmIsb9y3PaL3GYYNF3_bMDIIfgRA"
CREDENTIALS_PATH = "/etc/secrets/credentials.json"

# Sensores
SERIALES = {
    "sensor1": "Q3CA-AT85-YJMB",
    "sensor2": "Q3CA-5FF6-XF84",
    "multi1": "Q3CQ-YVSZ-BHKR",
    "puerta1": "Q3CC-C9JS-4XB",
    "mt40_1": "Q3CJ-274W-5B5Z",
    "mt40_2": "Q3CJ-GN4K-8VS4",
}

def get_sensor_data():
    url = f"https://api.meraki.com/api/v1/organizations/{ORGANIZATION_ID}/sensor/readings/latest"
    headers = {
        "X-Cisco-Meraki-API-Key": MERAKI_API_KEY,
        "Content-Type": "application/json"
    }
    response = requests.get(url, headers=headers)
    data = response.json()

    parsed = {}
    for reading in data:
        serial = reading.get("serial")
        metric = reading.get("metric")
        value = reading.get(metric)
        if serial == SERIALES["sensor1"]:
            if metric == "temperature": parsed["sensor1"] = value.get("value")
            if metric == "humidity": parsed["sensor1_humidity"] = value.get("value")
        elif serial == SERIALES["sensor2"]:
            if metric == "temperature": parsed["sensor2"] = value.get("value")
            if metric == "humidity": parsed["sensor2_humidity"] = value.get("value")
        elif serial == SERIALES["multi1"]:
            if metric == "temperature": parsed["multi1_temp"] = value.get("value")
            if metric == "pm25": parsed["multi1_pm25"] = value.get("value")
            if metric == "noise": parsed["multi1_noise"] = value.get("value")
            if metric == "co2": parsed["multi1_co2"] = value.get("value")
        elif serial == SERIALES["puerta1"]:
            if metric == "door": parsed["puerta1"] = value.get("state")
        elif serial == SERIALES["mt40_1"]:
            if metric == "realPower": parsed["power1"] = value.get("draw")
            if metric == "apparentPower": parsed["apparentPower1"] = value.get("draw")
            if metric == "current": parsed["current1"] = value.get("draw")
            if metric == "voltage": parsed["voltage1"] = value.get("level")
            if metric == "frequency": parsed["frequency1"] = value.get("level")
            if metric == "powerFactor": parsed["powerFactor1"] = value.get("percentage")
        elif serial == SERIALES["mt40_2"]:
            if metric == "realPower": parsed["power2"] = value.get("draw")
            if metric == "apparentPower": parsed["apparentPower2"] = value.get("draw")
            if metric == "current": parsed["current2"] = value.get("draw")
            if metric == "voltage": parsed["voltage2"] = value.get("level")
            if metric == "frequency": parsed["frequency2"] = value.get("level")
            if metric == "powerFactor": parsed["powerFactor2"] = value.get("percentage")
    return parsed

def guardar_en_sheets(datos):
    creds = service_account.Credentials.from_service_account_file(CREDENTIALS_PATH, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    service = build("sheets", "v4", credentials=creds)
    sheet = service.spreadsheets()
    
    fecha = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fila = [
        fecha,
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
    body = {"values": [fila]}
    sheet.values().append(
        spreadsheetId=SHEET_ID,
        range="Hoja1!A1",
        valueInputOption="RAW",
        body=body
    ).execute()

@app.route("/sensor-data")
def sensor_data():
    datos = get_sensor_data()
    if request.args.get("guardar") == "true":
        guardar_en_sheets(datos)
    return jsonify(datos)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/mt40")
def panel_mt40():
    return render_template("panel-mt40.html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
