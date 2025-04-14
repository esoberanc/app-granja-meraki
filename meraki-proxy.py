
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import requests
import os
from datetime import datetime, timedelta
import pandas as pd
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

def obtener_datos_google_sheets():
    SERVICE_ACCOUNT_FILE = "/etc/secrets/credentials.json"
    SPREADSHEET_ID = "1tNx0hjnQzdUKoBvTmIsb9y3PaL3GYYNF3_bMDIIfgRA"
    RANGE_NAME = "Hoja1!A2:N"
    COLUMNAS = [
        "Fecha", "MT10 Temp1", "MT10 Temp2", "MT10 Hum1", "MT10 Hum2",
        "MT15 Temp3", "MT15 CO2", "MT15 PM2.5", "MT15 Noise", "Puerta",
        "MT40 Watts1 AC", "MT40 Watts 2 Humidificador", "MT40 PowerFactor1", "MT40 PowerFactor2"
    ]

    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
    )
    service = build("sheets", "v4", credentials=credentials)
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID, range=RANGE_NAME
    ).execute()

    values = result.get("values", [])
    df = pd.DataFrame(values, columns=COLUMNAS)
    df["Fecha"] = pd.to_datetime(df["Fecha"], errors='coerce')
    return df

@app.route("/resumen-semanal")
def resumen_semanal():
    try:
        df = obtener_datos_google_sheets()
        hoy = datetime.now()
        hace_7_dias = hoy - timedelta(days=7)
        df_ultimos = df[df["Fecha"] >= hace_7_dias]

        resumen = {
            "registros": len(df_ultimos),
            "temp_promedio": df_ultimos[["MT10 Temp1", "MT10 Temp2"]].astype(float).mean().mean(),
            "humedad_promedio": df_ultimos[["MT10 Hum1", "MT10 Hum2"]].astype(float).mean().mean(),
            "co2_max": df_ultimos["MT15 CO2"].astype(float).max(),
            "power_ac": df_ultimos["MT40 Watts1 AC"].astype(float).sum(),
            "power_humid": df_ultimos["MT40 Watts 2 Humidificador"].astype(float).sum()
        }

        return jsonify(resumen)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
        "apparentPower2": 142.6
    }
    return jsonify(datos)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
