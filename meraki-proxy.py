
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import os
import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build

app = Flask(__name__)
CORS(app)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/sensor-data")
def sensor_data():
    datos = {
        "sensor1": 26.1,
        "sensor1_humidity": 57,
        "sensor2": 26.5,
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
        "current2": 0.62
    }

    guardar = request.args.get("guardar", "").strip().lower() == "true"
    if guardar:
        try:
            print("✅ Guardando en Google Sheets...")
            guardar_en_google_sheets(datos)
            print("✅ Datos guardados correctamente en Sheets.")
        except Exception as e:
            print(f"❌ Error al guardar en Sheets: {e}")

    return jsonify(datos)

@app.route("/resumen-semanal")
def resumen_semanal():
    datos = obtener_datos_google_sheets()
    resumen = generar_resumen(datos)
    return jsonify(resumen)

@app.route("/mt40")
def panel_mt40():
    return render_template("panel-mt40.html")

SERVICE_ACCOUNT_FILE = "/etc/secrets/credentials.json"
SPREADSHEET_ID = "TU_SPREADSHEET_ID"
SHEET_NAME = "Hoja1"
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

def get_sheets_service():
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    service = build('sheets', 'v4', credentials=credentials)
    return service.spreadsheets()

def guardar_en_google_sheets(datos):
    sheets = get_sheets_service()
    fecha = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    fila = [
        fecha,
        datos["sensor1"],
        datos["sensor2"],
        datos["sensor1_humidity"],
        datos["sensor2_humidity"],
        datos["multi1_temp"],
        datos["multi1_co2"],
        datos["multi1_pm25"],
        datos["multi1_noise"],
        datos["puerta1"],
        datos["power1"],
        datos["power2"]
    ]

    sheets.values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!A1",
        valueInputOption="RAW",
        body={"values": [fila]}
    ).execute()

def obtener_datos_google_sheets():
    sheets = get_sheets_service()
    result = sheets.values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!A2:M"
    ).execute()
    return result.get("values", [])

def generar_resumen(filas):
    temperaturas = []
    humedades = []
    co2_niveles = []

    for fila in filas:
        try:
            temperaturas.append(float(fila[1]))
            humedades.append(float(fila[3]))
            co2_niveles.append(float(fila[6]))
        except:
            continue

    return {
        "lecturas": len(filas),
        "temp_promedio": round(sum(temperaturas)/len(temperaturas), 2) if temperaturas else 0,
        "hum_promedio": round(sum(humedades)/len(humedades), 2) if humedades else 0,
        "co2_promedio": round(sum(co2_niveles)/len(co2_niveles), 2) if co2_niveles else 0
    }

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
