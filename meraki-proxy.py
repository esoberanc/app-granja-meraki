from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
import requests
from datetime import datetime, timedelta
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
import threading
import time
import openai
import gspread
import pandas as pd
from openai import OpenAI



app = Flask(__name__)
CORS(app)

MERAKI_API_KEY = os.environ.get("MERAKI_API_KEY")
ORGANIZATION_ID = "1654515"
SPREADSHEET_ID = "1tNx0hjnQzdUKoBvTmIsb9y3PaL3GYYNF3_bMDIIfgRA"

SENSORS = {
    "sensor1": "Q3CA-AT85-YJMB",
    "sensor2": "Q3CA-5FF6-XF84",
    "puerta1": "Q3CC-C9JS-4XB8",
    "multi1": "Q3CQ-YVSZ-BHKR",
    "power1": "Q3CJ-274W-5B5Z",
    "power2": "Q3CJ-GN4K-8VS4"
}

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/mt40")
def mt40_panel():
    return render_template("panel-mt40.html")

@app.route("/resumen-ia")
def mostrar_resumen_ia():
    return render_template("resumen-ia.html")

def guardar_en_sheets(sensor_data):
    try:
        creds = service_account.Credentials.from_service_account_file(
            "/etc/secrets/credentials.json",
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        service = build('sheets', 'v4', credentials=creds)
        sheet = service.spreadsheets()

        fila = [
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            sensor_data.get("sensor1"),
            sensor_data.get("sensor2"),
            sensor_data.get("sensor1_humidity"),
            sensor_data.get("sensor2_humidity"),
            sensor_data.get("multi1_temp"),
            sensor_data.get("multi1_co2"),
            sensor_data.get("multi1_pm25"),
            sensor_data.get("multi1_noise"),
            sensor_data.get("puerta1"),
            sensor_data.get("power1"),
            sensor_data.get("power2"),
            sensor_data.get("powerFactor1"),
            sensor_data.get("powerFactor2"),
            sensor_data.get("apparentPower1"),
            sensor_data.get("apparentPower2"),
            sensor_data.get("voltage1"),
            sensor_data.get("voltage2"),
            sensor_data.get("current1"),
            sensor_data.get("current2"),
            sensor_data.get("frequency1"),
            sensor_data.get("frequency2"),
        ]
        body = {'values': [fila]}
        sheet.values().append(
            spreadsheetId=SPREADSHEET_ID,
            range='Hoja1!A1',
            valueInputOption='RAW',
            body=body
        ).execute()
    except Exception as e:
        print("❌ Error al guardar en Sheets:", e)

@app.route("/sensor-data")
def obtener_datos_y_guardar():
    url = f"https://api.meraki.com/api/v1/organizations/{ORGANIZATION_ID}/sensor/readings/latest"
    headers = {
        "X-Cisco-Meraki-API-Key": MERAKI_API_KEY,
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        result = {}

        for sensor in data:
            serial = sensor["serial"]
            if serial not in SENSORS.values():
                continue

            for reading in sensor["readings"]:
                metric = reading["metric"]

                if metric == "temperature":
                    temp = reading["temperature"]["celsius"]
                    if serial == SENSORS["sensor1"]:
                        result["sensor1"] = temp
                    elif serial == SENSORS["sensor2"]:
                        result["sensor2"] = temp
                    elif serial == SENSORS["multi1"]:
                        result["multi1_temp"] = temp

                elif metric == "humidity":
                    humedad = reading["humidity"]["relativePercentage"]
                    if serial == SENSORS["sensor1"]:
                        result["sensor1_humidity"] = humedad
                    elif serial == SENSORS["sensor2"]:
                        result["sensor2_humidity"] = humedad

                elif metric == "door" and serial == SENSORS["puerta1"]:
                    estado = reading["door"]["open"]
                    result["puerta1"] = "open" if estado else "closed"

                elif metric == "co2" and serial == SENSORS["multi1"]:
                    result["multi1_co2"] = reading["co2"]["concentration"]

                elif metric == "noise" and serial == SENSORS["multi1"]:
                    result["multi1_noise"] = reading["noise"]["ambient"]["level"]

                elif metric == "pm25" and serial == SENSORS["multi1"]:
                    result["multi1_pm25"] = reading["pm25"]["concentration"]

                elif metric == "powerFactor":
                    if serial == SENSORS["power1"]:
                        result["powerFactor1"] = reading["powerFactor"]["percentage"]
                    elif serial == SENSORS["power2"]:
                        result["powerFactor2"] = reading["powerFactor"]["percentage"]

                elif metric == "apparentPower":
                    if serial == SENSORS["power1"]:
                        result["apparentPower1"] = reading["apparentPower"]["draw"]
                    elif serial == SENSORS["power2"]:
                        result["apparentPower2"] = reading["apparentPower"]["draw"]

                elif metric == "voltage":
                    if serial == SENSORS["power1"]:
                        result["voltage1"] = reading["voltage"]["level"]
                    elif serial == SENSORS["power2"]:
                        result["voltage2"] = reading["voltage"]["level"]

                elif metric == "current":
                    if serial == SENSORS["power1"]:
                        result["current1"] = reading["current"]["draw"]
                    elif serial == SENSORS["power2"]:
                        result["current2"] = reading["current"]["draw"]

                elif metric == "frequency":
                    if serial == SENSORS["power1"]:
                        result["frequency1"] = reading["frequency"]["level"]
                    elif serial == SENSORS["power2"]:
                        result["frequency2"] = reading["frequency"]["level"]

                elif metric == "realPower":
                    draw = reading["realPower"]["draw"]
                    if serial == SENSORS["power1"]:
                        result["power1"] = draw
                    elif serial == SENSORS["power2"]:
                        result["power2"] = draw

        guardar_en_sheets(result)
        return jsonify(result)
    

    except Exception as e:
        print("❌ Error general:", e)

@app.route("/api/resumen-ia")
def leer_ultimos_registros_desde_sheets():
    try:
        # Leer credenciales desde Render
        cred_path = "/etc/secrets/credentials.json"
        spreadsheet_id = "1tNx0hjnQzdUKoBvTmIsb9y3PaL3GYYNF3_bMDIIfgRA"
        range_name = "Hoja1!A2:Z"

        scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
        credentials = service_account.Credentials.from_service_account_file(
            cred_path, scopes=scopes
        )
        service = build("sheets", "v4", credentials=credentials)
        sheet = service.spreadsheets()
        result = sheet.values().get(spreadsheetId=spreadsheet_id, range=range_name).execute()
        values = result.get("values", [])

        if not values:
            return jsonify({"resumen": "No se encontraron datos."})

        headers = ["Fecha", "MT10 Temp1", "MT10 Temp2", "MT10 Hum1", "MT10 Hum2",
                   "MT15 Temp3", "MT15 CO2", "MT15 PM2.5", "MT15 Noise", "Puerta",
                   "MT40 Watts1 AC", "MT40 Watts 2 Humidificador",
                   "MT40 PowerFactor1", "MT40 PowerFactor2",
                   "MT40 Voltage1", "MT40 Voltage2",
                   "MT40 Current1", "MT40 Current2",
                   "MT40 ApparentPower1", "MT40 ApparentPower2",
                   "MT40 Frequency1", "MT40 Frequency2"]

        df = pd.DataFrame(values, columns=headers)

        # Convertir columnas numéricas
        for col in headers[1:]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

       # df = df.tail(1000)  # Filtrar últimos 1000 registros

       df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce", format="%Y-%m-%d %H:%M:%S")
fecha_limite = pd.Timestamp.now() - pd.Timedelta(days=3)
df = df[df["Fecha"] >= fecha_limite]


        resumen_estadistico = df.describe().to_string()

        # Preparar prompt para OpenAI
        prompt = f"""Actúa como un analista experto en sensores ambientales y consumo energético.
A partir de este resumen estadístico generado a partir de los últimos 1000 registros de sensores, redacta un informe corto para el cliente (máximo 5 líneas) que resuma el estado de su sistema de monitoreo, resaltando anomalías o recomendaciones si las hay:

{resumen_estadistico}

Resumen:"""

        client = OpenAI(api_key=open("/etc/secrets/openai_key.txt").read().strip())

        response = client.chat.completions.create(
            model="gpt-4o-mini",
             messages=[
        {
"role": "system", "content": "Eres un analista experto en sensores ambientales y consumo energético."
},
        {
"role": "user", "content"
: prompt}
    ],
    max_tokens=250,
    temperature=0.7
)

        resumen = response.choices[0].message.content.strip()

       
        return jsonify({"resumen": resumen})

    except Exception as e:
        import logging
        logging.exception("❌ Error en análisis IA")
        return jsonify({"resumen": f"Error: {str(e)}"}), 500


    
def iniciar_monitoreo_automatico():
    def loop():
        while True:
            obtener_datos_y_guardar()
            time.sleep(10)

    hilo = threading.Thread(target=loop, daemon=True)
    hilo.start()

if __name__ == "__main__":
    iniciar_monitoreo_automatico()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)