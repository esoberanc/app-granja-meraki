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

@app.route("/sensor-data")
def get_sensor_data():
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

        if request.args.get("guardar") == "true":
            guardar_en_sheets(result)

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route("/resumen-semanal")
def resumen_semanal():
    datos = obtener_datos_google_sheets()
    hoy = datetime.now()
    hace_7_dias = hoy - timedelta(days=7)

    humedad_fuera = 0
    temperatura_critica = 0
    puerta_abierta = 0
    max_ac = 0
    max_humidificador = 0
    total = 0

    for fila in datos:
        try:
            fecha_str = fila[0]
            fecha = datetime.strptime(fecha_str, "%Y-%m-%d %H:%M:%S")
            if fecha < hace_7_dias:
                continue

            temp1 = float(fila[1])
            temp2 = float(fila[2])
            hum1 = float(fila[3])
            hum2 = float(fila[4])
            temp3 = float(fila[5])
            co2 = int(fila[6])
            pm25 = int(fila[7])
            noise = int(fila[8])
            puerta = fila[9].lower()
            watts_ac = float(fila[10])
            watts_humidificador = float(fila[11])

            if temp1 < 22 or temp1 > 30: temperatura_critica += 1
            if temp2 < 22 or temp2 > 30: temperatura_critica += 1
            if temp3 < 22 or temp3 > 30: temperatura_critica += 1

            if hum1 < 60 or hum1 > 70: humedad_fuera += 1
            if hum2 < 60 or hum2 > 70: humedad_fuera += 1

            if puerta == "open":
                puerta_abierta += 1

            if watts_ac > max_ac:
                max_ac = watts_ac
            if watts_humidificador > max_humidificador:
                max_humidificador = watts_humidificador

            total += 1
        except Exception as e:
            continue

    resumen = (
        "RESUMEN SEMANAL:\n"
        f"Total registros analizados: {total}\n"
        f"- Lecturas con humedad fuera de rango: {humedad_fuera}\n"
        f"- Lecturas con temperatura crítica: {temperatura_critica}\n"
        f"- Veces que se abrió la puerta: {puerta_abierta}\n"
        f"- Máximo consumo AC: {max_ac:.1f} W\n"
        f"- Máximo consumo Humidificador: {max_humidificador:.1f} W"
    )

    
    def calcular_kwh(potencia_watts, segundos):
        return (potencia_watts * (segundos / 3600)) / 1000

    kwh_ac = 0
    kwh_humidificador = 0
    SEGUNDOS_ENTRE_LECTURAS = 10

    for fila in datos:
        try:
            real1 = float(fila[11])  # power1
            real2 = float(fila[12])  # power2

            kwh_ac += calcular_kwh(real1, SEGUNDOS_ENTRE_LECTURAS)
            kwh_humidificador += calcular_kwh(real2, SEGUNDOS_ENTRE_LECTURAS)
        except:
            continue

    resumen += f"\n\nConsumo acumulado esta semana:\n"
    resumen += f"Aire acondicionado: {kwh_ac:.2f} kWh\n"
    resumen += f"Humidificador: {kwh_humidificador:.2f} kWh\n"
    resumen += f"Costo estimado total: €{(kwh_ac + kwh_humidificador) * 0.20:.2f} (a €0.20/kWh)\n"


    return jsonify({"resumen": resumen})

if __name__ == "__main__":
    app.run(port=5000)


if __name__ == "__main__":
    app.run(port=5000)


port = int(os.environ.get("PORT", 5000))
app.run(host="0.0.0.0", port=port)