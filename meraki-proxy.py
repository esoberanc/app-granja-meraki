
import os
import json
import time
import threading
import logging
import openai
import pandas as pd
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from google.oauth2 import service_account
from googleapiclient.discovery import build
import requests

app = Flask(__name__)
CORS(app)

# Cargar API key de OpenAI
with open("/etc/secrets/openai_key.txt", "r") as f:
    openai.api_key = f.read().strip()

# Configurar ID y rango de Sheets
SPREADSHEET_ID = "1tNx0hjnQzdUKoBvTmIsb9y3PaL3GYYNF3_bMDIIfgRA"
RANGO = "Hoja1!A2"

# Autenticación con Google Sheets
def get_sheets_service():
    credentials = service_account.Credentials.from_service_account_file(
        "secrets/credentials.json",
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return build("sheets", "v4", credentials=credentials)

# Función para guardar en Google Sheets
def guardar_en_google_sheets(data):
    sheets = get_sheets_service()
    values = [[
        data.get("fecha", ""),
        data.get("sensor1", ""),
        data.get("sensor2", ""),
        data.get("sensor1_humidity", ""),
        data.get("sensor2_humidity", ""),
        data.get("multi1_temp", ""),
        data.get("multi1_co2", ""),
        data.get("multi1_pm25", ""),
        data.get("multi1_noise", ""),
        data.get("puerta1", ""),
        data.get("power1", ""),
        data.get("power2", ""),
        data.get("voltage1", ""),
        data.get("voltage2", ""),
        data.get("current1", ""),
        data.get("current2", ""),
        data.get("frequency1", ""),
        data.get("frequency2", ""),
        data.get("powerFactor1", ""),
        data.get("powerFactor2", ""),
        data.get("apparentPower1", ""),
        data.get("apparentPower2", "")
    ]]
    sheets.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=RANGO,
        valueInputOption="RAW",
        body={"values": values}
    ).execute()

# Ruta raíz
@app.route("/")
def home():
    return render_template("index.html")

# Ruta de IA
@app.route("/preguntar", methods=["POST"])
def preguntar_ia():
    try:
        datos = request.get_json()
        pregunta = datos.get("pregunta", "")

        df = obtener_datos_google_sheets()
        resumen = df.tail(10).to_string(index=False)

        prompt = (
            "Actúa como un analista experto de sensores de ambiente en una granja.\n"
            "Estos son los últimos datos registrados:\n"
            f"{resumen}\n\n"
            f"Ahora responde a la siguiente pregunta del usuario:\n{pregunta}"
        )

        respuesta = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )

        texto = respuesta.choices[0].message.content.strip()
        return jsonify({"respuesta": texto})

    except Exception as e:
        logging.error("Error al usar OpenAI: %s", e)
        return jsonify({"error": str(e)}), 500

# Ruta para ver datos actuales (solo para probar)
@app.route("/sensor-data", methods=["GET"])
def sensor_data():
    try:
        response = requests.get("https://api.meraki.com/api/v1/organizations/1654515/networks/L_3859584880656517373/sensor/stats/latest", headers={
            "X-Cisco-Meraki-API-Key": os.environ.get("MERAKI_API_KEY")
        })
        data = response.json()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Hilo automático para guardar cada 10 segundos
def guardar_periodicamente():
    while True:
        try:
            response = requests.get("https://api.meraki.com/api/v1/organizations/1654515/networks/L_3859584880656517373/sensor/stats/latest", headers={
                "X-Cisco-Meraki-API-Key": os.environ.get("MERAKI_API_KEY")
            })
            data = response.json()
            if isinstance(data, dict):
                guardar_en_google_sheets(data)
                logging.info("✅ Datos guardados automáticamente.")
        except Exception as e:
            logging.error("❌ Error guardando automáticamente: %s", e)
        time.sleep(10)

# Iniciar backend
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    threading.Thread(target=guardar_periodicamente, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
