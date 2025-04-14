
import os
import requests
import logging
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

app = Flask(__name__)
CORS(app)

API_KEY = os.environ.get("MERAKI_API_KEY")
NETWORK_ID = "L_3859584880656517373"
BASE_URL = f"https://api.meraki.com/api/v1/networks/{NETWORK_ID}/devices"

SENSORES = {
    "sensor1": "Q3CA-AT85-YJMB",
    "sensor2": "Q3CA-5FF6-XF84",
    "multi1": "Q3CQ-YVSZ-BHKR",
    "puerta1": "Q3CC-C9JS-4XB",
    "mt40_1": "Q3CJ-274W-5B5Z",
    "mt40_2": "Q3CJ-GN4K-8VS4"
}

HEADERS = {
    "X-Cisco-Meraki-API-Key": API_KEY,
    "Content-Type": "application/json"
}

def leer_metricas(serial, metricas):
    url = f"{BASE_URL}/{serial}/sensor/metrics/recent"
    response = requests.get(url, headers=HEADERS)
    logger.info(f"📡 Llamando a {url} -> status {response.status_code}")
    if response.status_code != 200:
        logger.error(f"❌ Error al obtener métricas de {serial}: {response.text}")
        return {}
    data = response.json()
    logger.info(f"✅ Datos crudos recibidos de {serial}: {data}")
    resultado = {}
    for lectura in data:
        if lectura["metric"] in metricas:
            resultado[lectura["metric"]] = lectura.get(lectura["metric"])
    return resultado

@app.route("/sensor-data")
def sensor_data():
    logger.info("📡 Endpoint /sensor-data fue llamado.")
    try:
        datos = {}

        # MT10 sensor 1
        mt10_1 = leer_metricas(SENSORES["sensor1"], ["temperature", "humidity"])
        datos["sensor1"] = mt10_1.get("temperature", {}).get("value")
        datos["sensor1_humidity"] = mt10_1.get("humidity", {}).get("value")

        # MT10 sensor 2
        mt10_2 = leer_metricas(SENSORES["sensor2"], ["temperature", "humidity"])
        datos["sensor2"] = mt10_2.get("temperature", {}).get("value")
        datos["sensor2_humidity"] = mt10_2.get("humidity", {}).get("value")

        # MT15
        multi1 = leer_metricas(SENSORES["multi1"], ["temperature", "co2", "pm25", "noise"])
        datos["multi1_temp"] = multi1.get("temperature", {}).get("value")
        datos["multi1_co2"] = multi1.get("co2", {}).get("concentration")
        datos["multi1_pm25"] = multi1.get("pm25", {}).get("concentration")
        datos["multi1_noise"] = multi1.get("noise", {}).get("ambient", {}).get("level")

        # MT20
        puerta = leer_metricas(SENSORES["puerta1"], ["door"])
        datos["puerta1"] = "open" if puerta.get("door", {}).get("open") else "closed"

        # MT40 1
        mt40_1 = leer_metricas(SENSORES["mt40_1"], ["realPower", "powerFactor", "voltage", "current", "apparentPower", "frequency"])
        datos["power1"] = mt40_1.get("realPower", {}).get("draw")
        datos["powerFactor1"] = mt40_1.get("powerFactor", {}).get("percentage")
        datos["voltage1"] = mt40_1.get("voltage", {}).get("level")
        datos["current1"] = mt40_1.get("current", {}).get("draw")
        datos["apparentPower1"] = mt40_1.get("apparentPower", {}).get("draw")
        datos["frequency1"] = mt40_1.get("frequency", {}).get("level")

        # MT40 2
        mt40_2 = leer_metricas(SENSORES["mt40_2"], ["realPower", "powerFactor", "voltage", "current", "apparentPower", "frequency"])
        datos["power2"] = mt40_2.get("realPower", {}).get("draw")
        datos["powerFactor2"] = mt40_2.get("powerFactor", {}).get("percentage")
        datos["voltage2"] = mt40_2.get("voltage", {}).get("level")
        datos["current2"] = mt40_2.get("current", {}).get("draw")
        datos["apparentPower2"] = mt40_2.get("apparentPower", {}).get("draw")
        datos["frequency2"] = mt40_2.get("frequency", {}).get("level")

        return jsonify(datos)
    except Exception as e:
        logger.exception("❌ Error procesando datos del sensor:")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
