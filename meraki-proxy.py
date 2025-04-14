
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
import requests
import os
from datetime import datetime, timedelta
from google.oauth2 import service_account
from googleapiclient.discovery import build

app = Flask(__name__, static_url_path="/static", static_folder="static", template_folder="templates")
CORS(app)

SPREADSHEET_ID = "1tNx0hjnQzdUKoBvTmIsb9y3PaL3GYYNF3_bMDIIfgRA"
RANGO = "Hoja1!A1"

def get_sheets_service():
    credentials = service_account.Credentials.from_service_account_file(
        "/etc/secrets/credentials.json",
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return build("sheets", "v4", credentials=credentials).spreadsheets().values()

def guardar_en_google_sheets(datos):
    sheets = get_sheets_service()
    fila = [[
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        datos.get("sensor1"), datos.get("sensor2"),
        datos.get("sensor1_humidity"), datos.get("sensor2_humidity"),
        datos.get("multi1_temp"), datos.get("multi1_co2"),
        datos.get("multi1_pm25"), datos.get("multi1_noise"),
        datos.get("puerta1"),
        datos.get("power1"), datos.get("power2"),
        datos.get("powerFactor1"), datos.get("powerFactor2"),
        datos.get("apparentPower1"), datos.get("apparentPower2"),
        datos.get("voltage1"), datos.get("voltage2"),
        datos.get("current1"), datos.get("current2"),
        datos.get("frequency1"), datos.get("frequency2")
    ]]
    sheets.append(spreadsheetId=SPREADSHEET_ID, range=RANGO, valueInputOption="RAW", body={"values": fila}).execute()

@app.route("/")
def home():
    return render_template("index.html")

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
        "apparentPower1": 39.2,
        "apparentPower2": 142.6,
        "voltage1": 230.1,
        "voltage2": 231.7,
        "current1": 0.17,
        "current2": 0.62,
        "frequency1": 50.1,
        "frequency2": 50.0
    }

    if request.args.get("guardar") == "true":
        try:
            guardar_en_google_sheets(datos)
        except Exception:
            pass

    return jsonify(datos)

@app.route("/resumen-semanal")
def resumen_semanal():
    try:
        service = get_sheets_service()
        result = service.get(spreadsheetId=SPREADSHEET_ID, range="Hoja1!A2:Z1000").execute()
        valores = result.get("values", [])

        ahora = datetime.now()
        hace_7_dias = ahora - timedelta(days=7)
        registros = [
            fila for fila in valores
            if len(fila) > 0 and datetime.strptime(fila[0], "%Y-%m-%d %H:%M:%S") >= hace_7_dias
        ]

        return jsonify({"filas": len(registros)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/mt40")
def panel_mt40():
    return render_template("panel-mt40.html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
