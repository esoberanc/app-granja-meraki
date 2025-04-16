
import os
import json
import requests
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import logging

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)

MERAKI_API_KEY = os.environ.get("MERAKI_API_KEY")
SHEET_ID = os.environ.get("SHEET_ID")
GOOGLE_SHEETS_URL = f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values/Hoja1!A1:append?valueInputOption=RAW"

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/sensor-data")
def sensor_data():
    guardar = request.args.get("guardar", "false").lower() == "true"
    try:
        headers = {
            "X-Cisco-Meraki-API-Key": MERAKI_API_KEY,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        org_id = "1654515"
        url = f"https://api.meraki.com/api/v1/organizations/{org_id}/sensor/readings/latest"
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            logging.error(f"❌ Error consultando Meraki: {response.status_code} - {response.text}")
            return "Error", 500

        sensores = response.json()
        logging.info("✅ Datos obtenidos correctamente")

        # Extraemos los datos necesarios
        data = {}
        for sensor in sensores:
            serial = sensor.get("serial")
            for reading in sensor.get("readings", []):
                metric = reading.get("metric")
                value = list(reading.values())[1]  # El segundo valor es el dict con datos
                if isinstance(value, dict):
                    for k, v in value.items():
                        data[f"{metric}_{k}_{serial}"] = v

        if guardar:
            logging.info("✅ Intentando guardar en Google Sheets...")
            fila = [str(data.get(k, "")) for k in sorted(data)]
            payload = {
                "values": [fila]
            }
            logging.info(f"🔍 Payload enviado: {json.dumps(payload)}")
            cred_path = "/etc/secrets/credentials.json"
            if not os.path.exists(cred_path):
                logging.error(f"❌ Archivo de credenciales no encontrado en {cred_path}")
                return "Error", 500
            access_token = json.load(open(cred_path))["access_token"]
            g_headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            g_response = requests.post(GOOGLE_SHEETS_URL, headers=g_headers, json=payload)
            if g_response.status_code != 200:
                logging.error(f"❌ Error guardando en Sheets: {g_response.status_code} - {g_response.text}")
                return "Error", 500
            logging.info("✅ Guardado exitoso en Google Sheets")

        return jsonify(data)
    except Exception as e:
        logging.exception("❌ Error general:")
        return "Error", 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
