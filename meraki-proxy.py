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

@app.route("/energia")
def ver_energia():
    return render_template("energia.html")


@app.route("/mt40")
def mt40_panel():
    return render_template("panel-mt40.html")

@app.route("/resumen-ia")
def mostrar_resumen_ia():
    return render_template("resumen-ia.html")

def obtener_datos_consumo():
    try:
        # Leer desde Google Sheets
        cred_path = "/etc/secrets/credentials.json"
        spreadsheet_id = "1tNx0hjnQzdUKoBvTmIsb9y3PaL3GYYNF3_bMDIIfgRA"
        range_name = "Hoja1!A2:Z"

        credentials = service_account.Credentials.from_service_account_file(
            cred_path, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
        )
        service = build("sheets", "v4", credentials=credentials)
        sheet = service.spreadsheets()
        result = sheet.values().get(spreadsheetId=spreadsheet_id, range=range_name).execute()
        values = result.get("values", [])

        if not values:
            return None

        headers = [
            "Fecha", "MT10 Temp1", "MT10 Temp2", "MT10 Hum1", "MT10 Hum2",
            "MT15 Temp3", "MT15 CO2", "MT15 PM2.5", "MT15 Noise", "Puerta",
            "MT40 Watts1 AC", "MT40 Watts 2 Humidificador",
            "MT40 PowerFactor1", "MT40 PowerFactor2",
            "MT40 ApparentPower1", "MT40 ApparentPower2",
            "MT40 Voltage1", "MT40 Voltage2",
            "MT40 Current1", "MT40 Current2",
            "MT40 Frequency1", "MT40 Frequency2"
        ]

        df = pd.DataFrame(values, columns=headers)
        df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")

        now = pd.Timestamp.now()
        df = df[(df["Fecha"].dt.month == now.month) & (df["Fecha"].dt.year == now.year)]

        df["MT40 Watts1 AC"] = pd.to_numeric(df["MT40 Watts1 AC"], errors="coerce")
        df["MT40 Watts 2 Humidificador"] = pd.to_numeric(df["MT40 Watts 2 Humidificador"], errors="coerce")
        df["total_watts"] = df["MT40 Watts1 AC"].fillna(0) + df["MT40 Watts 2 Humidificador"].fillna(0)

        fechas_validas = df["Fecha"].dropna().sort_values()
        intervalos = [(fechas_validas.iloc[i] - fechas_validas.iloc[i - 1]).total_seconds() for i in range(1, len(fechas_validas))]
        frecuencia_s = round(sum(intervalos) / len(intervalos), 2) if intervalos else 11

        total_wh = df["total_watts"].sum() * (frecuencia_s / 3600)
        total_kwh = round(total_wh / 1000, 2)
        coste = round(total_kwh * 0.25, 2)

        estacion = "primavera"
        mes = now.month
        horas_solares = {"invierno": 2.5, "primavera": 4.5, "verano": 5.5, "otonio": 3.5}
        if mes in [12, 1, 2]: estacion = "invierno"
        elif mes in [3, 4, 5]: estacion = "primavera"
        elif mes in [6, 7, 8]: estacion = "verano"
        elif mes in [9, 10, 11]: estacion = "otonio"

        hs = horas_solares[estacion]
        kw_necesarios = round(total_kwh / (30 * hs), 2)

        return {
            "kwh": total_kwh,
            "coste_eur": coste,
            "estacion": estacion,
            "horas_solares": hs,
            "paneles_kw": kw_necesarios,
            "frecuencia_s": frecuencia_s,
            "recomendacion": f"Paneles de {kw_necesarios} kW funcionando {hs} h/día compensan el consumo mensual."
        }
    except:
        return None

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

@app.route("/api/frecuencia-muestreo")
def calcular_frecuencia_muestreo():
    try:
        cred_path = "/etc/secrets/credentials.json"
        spreadsheet_id = "1tNx0hjnQzdUKoBvTmIsb9y3PaL3GYYNF3_bMDIIfgRA"
        range_name = "Hoja1!A2:A300"  # Solo fechas, hasta 300 registros

        credentials = service_account.Credentials.from_service_account_file(
            cred_path, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
        )
        service = build("sheets", "v4", credentials=credentials)
        sheet = service.spreadsheets()
        result = sheet.values().get(spreadsheetId=spreadsheet_id, range=range_name).execute()
        values = result.get("values", [])

        if not values or len(values) < 2:
            return jsonify({"error": "No hay suficientes datos para calcular la frecuencia."})

        fechas = pd.to_datetime([fila[0] for fila in values if fila], errors="coerce")
        fechas = fechas.dropna().sort_values()

        if len(fechas) < 2:
            return jsonify({"error": "No hay suficientes fechas válidas."})

        intervalos = [(fechas[i] - fechas[i - 1]).total_seconds() for i in range(1, len(fechas))]
        promedio_segundos = round(sum(intervalos) / len(intervalos), 2)

        return jsonify({"frecuencia_media_segundos": promedio_segundos})

    except Exception as e:
        import logging
        logging.exception("Error en /api/frecuencia-muestreo")
        return jsonify({"error": str(e)}), 500
       

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

@app.route("/api/consumo-mensual")
def calcular_consumo_mensual():
    try:
        # Leer desde Google Sheets
        cred_path = "/etc/secrets/credentials.json"
        spreadsheet_id = "1tNx0hjnQzdUKoBvTmIsb9y3PaL3GYYNF3_bMDIIfgRA"
        range_name = "Hoja1!A2:Z"

        credentials = service_account.Credentials.from_service_account_file(
            cred_path, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
        )
        service = build("sheets", "v4", credentials=credentials)
        sheet = service.spreadsheets()
        result = sheet.values().get(spreadsheetId=spreadsheet_id, range=range_name).execute()
        values = result.get("values", [])

        if not values:
            return jsonify({"error": "No se encontraron datos."})

        headers = [
            "Fecha", "MT10 Temp1", "MT10 Temp2", "MT10 Hum1", "MT10 Hum2",
            "MT15 Temp3", "MT15 CO2", "MT15 PM2.5", "MT15 Noise", "Puerta",
            "MT40 Watts1 AC", "MT40 Watts 2 Humidificador",
            "MT40 PowerFactor1", "MT40 PowerFactor2",
            "MT40 ApparentPower1", "MT40 ApparentPower2",
            "MT40 Voltage1", "MT40 Voltage2",
            "MT40 Current1", "MT40 Current2",
            "MT40 Frequency1", "MT40 Frequency2"
        ]

        df = pd.DataFrame(values, columns=headers)
        df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")

        # Filtrar solo este mes
        now = pd.Timestamp.now()
        df = df[(df["Fecha"].dt.month == now.month) & (df["Fecha"].dt.year == now.year)]

        df["MT40 Watts1 AC"] = pd.to_numeric(df["MT40 Watts1 AC"], errors="coerce")
        df["MT40 Watts 2 Humidificador"] = pd.to_numeric(df["MT40 Watts 2 Humidificador"], errors="coerce")

        df["total_watts"] = df["MT40 Watts1 AC"].fillna(0) + df["MT40 Watts 2 Humidificador"].fillna(0)

        # 🔍 Calcular frecuencia real desde las fechas del mismo DataFrame
        fechas_validas = df["Fecha"].dropna().sort_values()
        intervalos = [(fechas_validas.iloc[i] - fechas_validas.iloc[i - 1]).total_seconds() for i in range(1, len(fechas_validas))]
        frecuencia_s = round(sum(intervalos) / len(intervalos), 2) if intervalos else 11

        # 🔢 Calcular consumo en Wh y kWh
        total_wh = df["total_watts"].sum() * (frecuencia_s / 3600)
        total_kwh = round(total_wh / 1000, 2)
        coste = round(total_kwh * 0.25, 2)

        # ☀️ Estación y recomendación solar
        estacion = "primavera"
        mes = now.month
        horas_solares = {"invierno": 2.5, "primavera": 4.5, "verano": 5.5, "otonio": 3.5}
        if mes in [12, 1, 2]: estacion = "invierno"
        elif mes in [3, 4, 5]: estacion = "primavera"
        elif mes in [6, 7, 8]: estacion = "verano"
        elif mes in [9, 10, 11]: estacion = "otonio"

        hs = horas_solares[estacion]
        kw_necesarios = round(total_kwh / (30 * hs), 2)

        return jsonify({
            "kwh": total_kwh,
            "coste_eur": coste,
            "estacion": estacion,
            "horas_solares": hs,
            "paneles_kw": kw_necesarios,
            "frecuencia_s": frecuencia_s,
            "recomendacion": f"Paneles de {kw_necesarios} kW funcionando {hs} h/día compensan el consumo mensual."
        })

    except Exception as e:
        import logging
        logging.exception("Error en /api/consumo-mensual")
        return jsonify({"error": str(e)}), 500

@app.route("/api/analisis-solar")
def analisis_solar():
    try:
        data = obtener_datos_consumo()
        if not data:
            return jsonify({"error": "No se pudo calcular el consumo."}), 500

        kwh = data.get("kwh", 0)
        ahorro_anual_eur = round(kwh * 12 * 0.25, 2)
        coste_paneles = round(data.get("paneles_kw", 0) * 700, 2)
        roi_anios = round(coste_paneles / ahorro_anual_eur, 1) if ahorro_anual_eur else None

        co2_mensual = round(kwh * 0.5, 2)
        co2_anual = round(co2_mensual * 12, 2)
        equivalente_arboles = round(co2_anual / 21, 1)

        horas_por_estacion = {
            "invierno": 2.5,
            "primavera": 4.5,
            "verano": 5.5,
            "otonio": 3.5
        }
        paneles_por_estacion = {
            est: round(kwh / (30 * hs), 2) for est, hs in horas_por_estacion.items()
        }

        return jsonify({
            **data,
            "ahorro_anual_eur": ahorro_anual_eur,
            "coste_paneles": coste_paneles,
            "roi_anios": roi_anios,
            "co2_mensual": co2_mensual,
            "co2_anual": co2_anual,
            "equivalente_arboles": equivalente_arboles,
            "paneles_por_estacion": paneles_por_estacion
        })
    except Exception as e:
        import logging
        logging.exception("Error en /api/analisis-solar")
        return jsonify({"error": str(e)}), 500

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
        fecha_limite = pd.Timestamp.now() - pd.Timedelta(days=7)
        df = df[df["Fecha"] >= fecha_limite]


        resumen_estadistico = df.describe().to_string()

        # Preparar prompt para OpenAI
        prompt = f"""Actúa como un analista experto en sensores ambientales y consumo energético.
A partir de este resumen estadístico generado a partir de los datos recolectados durante los últimos 
7 días, redacta un informe corto para el cliente (máximo 5 líneas) que resuma el estado de su sistema de monitoreo, resaltando anomalías o recomendaciones si las hay, recordando que estos sensores están en una granja de tenebrio:

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
