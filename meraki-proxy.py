
import os
import json
import logging
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from google.oauth2 import service_account
from googleapiclient.discovery import build
import openai

app = Flask(__name__)
CORS(app)

# Configuraciones
SPREADSHEET_ID = "1tNx0hjnQzdUKoBvTmIsb9y3PaL3GYYNF3_bMDIIfgRA"
RANGE_NAME = "Hoja1!A2:M"
GOOGLE_CREDS_PATH = "/etc/secrets/credentials.json"
OPENAI_KEY_PATH = "/etc/secrets/openai_key.txt"

# Inicializar OpenAI
with open(OPENAI_KEY_PATH, "r") as f:
    openai.api_key = f.read().strip()

def get_google_sheets_data():
    creds = service_account.Credentials.from_service_account_file(GOOGLE_CREDS_PATH)
    service = build("sheets", "v4", credentials=creds)
    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=RANGE_NAME).execute()
    values = result.get("values", [])
    return values

@app.route("/resumen-ia")
def resumen_ia():
    try:
        data = get_google_sheets_data()
        if not data:
            return jsonify({"error": "No hay datos"}), 400

        columnas = ["Fecha", "MT10 Temp1", "MT10 Temp2", "MT10 Hum1", "MT10 Hum2", "MT15 Temp3", "MT15 CO2", "MT15 PM2.5", "MT15 Noise", "Puerta", "Watts1 AC", "Watts2 Humid"]
        texto_datos = "\n".join([", ".join(f"{col}: {val}" for col, val in zip(columnas, fila)) for fila in data[-20:]])

        prompt = f"Genera un resumen en español sobre las últimas 20 lecturas de una granja automatizada. Cada fila incluye datos como temperatura, humedad, CO2, ruido, y consumo eléctrico. Los datos son:\n{texto_datos}"

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )

        resumen = response.choices[0].message["content"]
        return jsonify({"resumen": resumen})
    except Exception as e:
        logging.error(f"❌ Error generando resumen IA: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/mt40")
def mt40_panel():
    return render_template("panel-mt40.html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
