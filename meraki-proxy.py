
import os
import logging
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Configuración
ORGANIZATION_ID = "1654515"
SPREADSHEET_ID = "1tNx0hjnQzdUKoBvTmIsb9y3PaL3GYYNF3_bMDIIfgRA"
SHEET_RANGE = "Hoja1!A1"

# Inicialización de Flask
app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)

# Cargar credenciales de Google Sheets
def get_sheets_service():
    credentials = service_account.Credentials.from_service_account_file(
        "/etc/secrets/credentials.json",
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    service = build("sheets", "v4", credentials=credentials)
    return service.spreadsheets()

# Obtener datos desde Meraki
def obtener_datos_sensores():
    api_key = os.environ.get("MERAKI_API_KEY")
    headers = {
        "X-Cisco-Meraki-API-Key": api_key,
        "Content-Type": "application/json"
    }

    url = f"https://api.meraki.com/api/v1/organizations/{ORGANIZATION_ID}/sensor/readings/latest"
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        logging.error(f"Meraki API error: {response.status_code} - {response.text}")
        raise Exception("Error al obtener datos de sensores")

    data = response.json()
    return data

# Extraer datos específicos
def parsear_datos(data):
    sensores = {}
    for item in data:
        serial = item.get("serial")
        readings = item.get("readings", [])
        for lectura in readings:
            tipo = lectura.get("metric")
            valor = list(lectura.values())[-1]
            if isinstance(valor, dict):
                for k, v in valor.items():
                    sensores[f"{tipo}_{k}_{serial}"] = v
            else:
                sensores[f"{tipo}_{serial}"] = valor
    return sensores

# Guardar en Google Sheets
def guardar_en_google_sheets(valores):
    try:
        sheets = get_sheets_service()
        fila = [valores.get(k, "") for k in sorted(valores)]
        fila.insert(0, valores.get("timestamp", ""))
        sheets.values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=SHEET_RANGE,
            valueInputOption="RAW",
            body={"values": [fila]}
        ).execute()
        logging.info("✅ Datos guardados en Google Sheets.")
    except Exception as e:
        logging.error(f"❌ Error al guardar en Sheets: {e}")

# Ruta principal
@app.route("/sensor-data")
def sensor_data():
    try:
        logging.info("📡 Obteniendo datos de sensores...")
        data = obtener_datos_sensores()
        valores = parsear_datos(data)

        if request.args.get("guardar") == "true":
            logging.info("📝 Guardando automáticamente en Google Sheets...")
            guardar_en_google_sheets(valores)

        return jsonify(valores)

    except Exception as e:
        logging.exception("❌ Error general:")
        return jsonify({"error": str(e)}), 500

@app.route("/")
def home():
    return "✅ Backend Meraki activo."

# Ejecutar app
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
