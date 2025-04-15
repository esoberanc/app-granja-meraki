
import os
import requests
import logging
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

MERAKI_API_KEY = os.environ.get("MERAKI_API_KEY")
NETWORK_ID = "L_3859584880656517373"

HEADERS = {
    "X-Cisco-Meraki-API-Key": MERAKI_API_KEY,
    "Content-Type": "application/json",
    "Accept": "application/json"
}

@app.route("/sensor-data")
def sensor_data():
    try:
        logging.info("📡 Endpoint /sensor-data fue llamado.")
        url = f"https://api.meraki.com/api/v1/networks/{NETWORK_ID}/sensor/readings/latest"
        response = requests.get(url, headers=HEADERS)

        if response.status_code != 200:
            logging.error(f"❌ Error al obtener datos: status_code={response.status_code}")
            logging.error(f"❌ Cuerpo de respuesta: {response.text}")
            raise Exception("Error al obtener datos de sensores")

        data = response.json()
        logging.info("✅ Datos obtenidos correctamente.")
        return jsonify(data)

    except Exception as e:
        logging.exception("❌ Error general:")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
