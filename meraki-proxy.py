from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/mt40")
def panel_mt40():
    return render_template("panel-mt40.html")

# Aquí irían las otras rutas como /sensor-data y /resumen-semanal
# Por ejemplo:
# @app.route("/sensor-data")
# def sensor_data():
#     return jsonify(...)

port = int(os.environ.get("PORT", 5000))
app.run(host="0.0.0.0", port=port)