
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import os
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build

app = Flask(__name__)
CORS(app)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/mt40")
def panel_mt40():
    return render_template("panel-mt40.html")

# Configuración de Sheets
SERVICE_ACCOUNT_FILE = "/etc/secrets/credentials.json"
SPREADSHEET_ID = "1tNx0hjnQzdUKoBvTmIsb9y3PaL3GYYNF3_bMDIIfgRA"
RANGE_NAME = "Hoja1!A2:X"

COLUMNAS = [
    "Fecha", "MT10 Temp1", "MT10 Temp2", "MT10 Hum1", "MT10 Hum2",
    "MT15 Temp3", "MT15 CO2", "MT15 PM2.5", "MT15 Noise", "Puerta",
    "MT40 Watts1 AC", "MT40 Watts 2 Humidificador",
    "MT40 PowerFactor1", "MT40 PowerFactor2",
    "MT40 Voltage1", "MT40 Voltage2",
    "MT40 Current1", "MT40 Current2",
    "MT40 ApparentPower1", "MT40 ApparentPower2",
    "MT40 Frequency1", "MT40 Frequency2"
]

def get_sheets_service():
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return build("sheets", "v4", credentials=credentials)

def guardar_en_google_sheets(datos):
    sheets = get_sheets_service()
    body = {
        "values": [[
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            datos["sensor1"], datos["sensor2"],
            datos["sensor1_humidity"], datos["sensor2_humidity"],
            datos["multi1_temp"], datos["multi1_co2"], datos["multi1_pm25"], datos["multi1_noise"],
            datos["puerta1"], datos["power1"], datos["power2"],
            datos["powerFactor1"], datos["powerFactor2"],
            datos["voltage1"], datos["voltage2"],
            datos["current1"], datos["current2"],
            datos["apparentPower1"], datos["apparentPower2"],
            datos["frequency1"], datos["frequency2"]
        ]]
    }
    sheets.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=RANGE_NAME,
        valueInputOption="RAW",
        body=body
    ).execute()

@app.route("/sensor-data")
def sensor_data():
    datos = {
        "sensor1": 26.1,
        "sensor2": 26.5,
        "sensor1_humidity": 57,
        "sensor2_humidity": 59,
        "multi1_temp": 26.8,
        "multi1_co2": 805,
        "multi1_pm25": 3,
        "multi1_noise": 33,
        "puerta1": "closed",
        "power1": 8.4,
        "power2": 140.2,
        "powerFactor1": 23,
        "powerFactor2": 97,
        "voltage1": 230.1,
        "voltage2": 231.7,
        "current1": 0.17,
        "current2": 0.62,
        "apparentPower1": 39.2,
        "apparentPower2": 142.6,
        "frequency1": 50.1,
        "frequency2": 50.0
    }

    if request.args.get("guardar") == "true":
        try:
            guardar_en_google_sheets(datos)
        except Exception as e:
            print(f"❌ Error al guardar en Sheets: {e}")

    return jsonify(datos)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
