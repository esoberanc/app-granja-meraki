from flask import Flask, jsonify, request, render_template, redirect, url_for, flash
from flask import current_app
from flask_cors import CORS
import requests
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
import threading
import time
import openai
import gspread
import pandas as pd
from openai import OpenAI
from flask_login import LoginManager, login_user, login_required, logout_user, UserMixin, current_user
import json
import smtplib
from email.mime.text import MIMEText
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from werkzeug.security import check_password_hash
from supabase import create_client
load_dotenv()

app = Flask(__name__)
app.secret_key = "clave-secreta-super-segura"  # para sesiones
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

CORS(app)

MERAKI_API_KEY = os.environ.get("MERAKI_API_KEY")
ORGANIZATION_ID = "1654515"
SPREADSHEET_ID = "1tNx0hjnQzdUKoBvTmIsb9y3PaL3GYYNF3_bMDIIfgRA"
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


SENSORS = {
    "sensor1": "Q3CA-AT85-YJMB",
    "sensor2": "Q3CA-5FF6-XF84",
    "puerta1": "Q3CC-C9JS-4XB8",
    "multi1": "Q3CQ-YVSZ-BHKR",
    "power1": "Q3CJ-274W-5B5Z",
    "power2": "Q3CJ-GN4K-8VS4"
}

class Usuario(UserMixin):
    def __init__(self, id, username, password):
        self.id = id
        self.username = username
        self.password = password

@login_manager.user_loader
def load_user(user_id):
    user_data = obtener_usuario_supabase(user_id)
    if user_data:
        return Usuario(user_data["id"], user_data["username"], user_data["password"])
    return None

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        # Verificar si ya existe
        if obtener_usuario_supabase(username):
            flash("El usuario ya existe", "warning")
            return redirect(url_for("register"))

        if registrar_usuario_supabase(username, password):
            flash("Registro exitoso. Ahora puedes iniciar sesión.", "success")
            return redirect(url_for("login"))
        else:
            flash("Error al registrar el usuario", "danger")

    return render_template("register.html")


@app.route("/")
@login_required
def home():
    return render_template("index.html")

@app.route("/energia")
@login_required
def ver_energia():
    return render_template("energia.html")


@app.route("/mt40")
@login_required
def mt40_panel():
    return render_template("panel-mt40.html")

@app.route("/resumen-ia")
@login_required
def mostrar_resumen_ia():
    return render_template("resumen-ia.html")

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        print(f"Intentando login con: {username}")

        # Consultar Supabase
        response = supabase.table("usuarios").select("*").eq("username", username).execute()

        if response.data:
            user = response.data[0]
            print(f"Usuario encontrado: {user}")
            if check_password_hash(user["password"], password):
                user_obj = Usuario(user["id"], user["username"], user["password"])

                login_user(user_obj)
                print("✅ Login exitoso")
                return redirect(url_for("home"))
            else:
                print("❌ Contraseña incorrecta")
        else:
            print("❌ Usuario no encontrado")

        return render_template("login.html", error="Usuario o contraseña incorrectos")
    return render_template("login.html")



@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

def get_worksheet():
    creds = service_account.Credentials.from_service_account_file(
        "/etc/secrets/credentials.json",
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    client = gspread.authorize(creds)
    return client.open_by_key(SPREADSHEET_ID).worksheet("Hoja1")


def obtener_usuario_supabase(username):
    url = f"{SUPABASE_URL}/rest/v1/usuarios?username=eq.{username}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }

    try:
        res = requests.get(url, headers=headers)
        res.raise_for_status()
        data = res.json()
        return data[0] if data else None
    except Exception as e:
        print(f"❌ Error al obtener usuario desde Supabase: {e}")
        return None

def registrar_usuario_supabase(username, password):
    from werkzeug.security import generate_password_hash
    hashed_password = generate_password_hash(password)

    payload = {
        "username": username,
        "password": hashed_password
    }

    url = f"{SUPABASE_URL}/rest/v1/usuarios"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }

    try:
        res = requests.post(url, headers=headers, json=payload)
        res.raise_for_status()
        print("✅ Usuario registrado en Supabase")
        return True
    except Exception as e:
        print(f"❌ Error al registrar usuario: {e}")
        return False


def obtener_datos_supabase(limit=500):
    url = f"{SUPABASE_URL}/rest/v1/lecturas?order=fecha.desc&limit={limit}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }

    try:
        res = requests.get(url, headers=headers)
        res.raise_for_status()
        data = res.json()
        if not data:
            return pd.DataFrame()

        df = pd.DataFrame(data)
        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
        df = df.sort_values("fecha")

        return df
    except Exception as e:
        print("❌ Error al leer desde Supabase:", e)
        return pd.DataFrame()


def obtener_datos_consumo():
    try:
        df = obtener_datos_supabase(limit=2000)
        if df.empty:
            return None

        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
        now = pd.Timestamp.now()
        df = df[(df["fecha"].dt.month == now.month) & (df["fecha"].dt.year == now.year)]

        df["power1"] = pd.to_numeric(df["power1"], errors="coerce").fillna(0)
        df["power2"] = pd.to_numeric(df["power2"], errors="coerce").fillna(0)
        df["total_watts"] = df["power1"] + df["power2"]

        fechas_validas = df["fecha"].dropna().sort_values()
        intervalos = [
            (fechas_validas.iloc[i] - fechas_validas.iloc[i - 1]).total_seconds()
            for i in range(1, len(fechas_validas))
        ]
        frecuencia_s = round(sum(intervalos) / len(intervalos), 2) if intervalos else 60

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

    except Exception as e:
        print(f"❌ Error en obtener_datos_consumo: {e}")
        return None

def guardar_en_supabase(data):
    url = f"{SUPABASE_URL}/rest/v1/lecturas"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }

    payload = {
        "fecha": datetime.now(ZoneInfo("Europe/Madrid")).isoformat(),
        "sensor1": data.get("sensor1"),
        "sensor2": data.get("sensor2"),
        "sensor1_hum": data.get("sensor1_humidity"),
        "sensor2_hum": data.get("sensor2_humidity"),
        "multi1_temp": data.get("multi1_temp"),
        "multi1_co2": data.get("multi1_co2"),
        "multi1_pm25": data.get("multi1_pm25"),
        "multi1_noise": data.get("multi1_noise"),
        "puerta": data.get("puerta1"),
        "power1": data.get("power1"),
        "power2": data.get("power2")
    }
    print("📦 Payload enviado a Supabase:", payload)  # 👈 Añádelo aquí
    try:
        res = requests.post(url, headers=headers, json=payload)
        res.raise_for_status()
        print("✅ Lectura guardada en Supabase")
    except Exception as e:
        print(f"❌ Error al guardar en Supabase: {e}")




def envio_automatico_informe():
    try:
        with current_app.app_context():
            enviar_informe()
    except Exception as e:
        print(f"❌ Error al enviar informe automático: {e}")

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

        # guardar_en_sheets(result)
        guardar_en_supabase(result)
        return jsonify(result)
    

    except Exception as e:
        print("❌ Error general:", e)

@app.route("/api/consumo-mensual")
def calcular_consumo_mensual():
    try:
        df = obtener_datos_supabase(limit=1000)  # puedes ajustar el límite si es necesario

        if df.empty:
            return jsonify({"error": "No se encontraron datos."})

        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
        df = df[df["fecha"].dt.month == pd.Timestamp.now().month]
        df = df[df["fecha"].dt.year == pd.Timestamp.now().year]

        df["power1"] = pd.to_numeric(df["power1"], errors="coerce").fillna(0)
        df["power2"] = pd.to_numeric(df["power2"], errors="coerce").fillna(0)
        df["total_watts"] = df["power1"] + df["power2"]

        fechas_validas = df["fecha"].dropna().sort_values()
        intervalos = [(fechas_validas.iloc[i] - fechas_validas.iloc[i - 1]).total_seconds()
                      for i in range(1, len(fechas_validas))]
        frecuencia_s = round(sum(intervalos) / len(intervalos), 2) if intervalos else 60

        total_wh = df["total_watts"].sum() * (frecuencia_s / 3600)
        total_kwh = round(total_wh / 1000, 2)
        coste = round(total_kwh * 0.25, 2)

        mes = pd.Timestamp.now().month
        estacion = "primavera"
        if mes in [12, 1, 2]: estacion = "invierno"
        elif mes in [3, 4, 5]: estacion = "primavera"
        elif mes in [6, 7, 8]: estacion = "verano"
        elif mes in [9, 10, 11]: estacion = "otonio"

        horas_solares = {"invierno": 2.5, "primavera": 4.5, "verano": 5.5, "otonio": 3.5}
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
        df = obtener_datos_supabase(limit=1000)

        if df.empty or "fecha" not in df.columns or "power1" not in df.columns or "power2" not in df.columns:
            return jsonify({"error": "Faltan columnas necesarias"}), 400

        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
        now = pd.Timestamp.now(tz="UTC")
        df = df[(df["fecha"].dt.month == now.month) & (df["fecha"].dt.year == now.year)]

        df["power1"] = pd.to_numeric(df["power1"], errors="coerce").fillna(0)
        df["power2"] = pd.to_numeric(df["power2"], errors="coerce").fillna(0)
        df["watts"] = df["power1"] + df["power2"]

        frecuencia_s = 60  # Ajusta si tienes otra frecuencia real
        total_wh = df["watts"].sum() * (frecuencia_s / 3600)
        total_kwh = round(total_wh / 1000, 2)
        coste = round(total_kwh * 0.25, 2)

        estacion = "primavera"
        mes = now.month
        if mes in [12, 1, 2]: estacion = "invierno"
        elif mes in [3, 4, 5]: estacion = "primavera"
        elif mes in [6, 7, 8]: estacion = "verano"
        elif mes in [9, 10, 11]: estacion = "otonio"

        horas_solares = {"invierno": 2.5, "primavera": 4.5, "verano": 5.5, "otonio": 3.5}
        hs = horas_solares[estacion]
        paneles_kw = round(total_kwh / (30 * hs), 2)

        return jsonify({
            "kwh": total_kwh,
            "coste_eur": coste,
            "estacion": estacion,
            "horas_solares": hs,
            "paneles_kw": paneles_kw,
            "frecuencia_s": frecuencia_s,
            "recomendacion": f"Paneles de {paneles_kw} kW funcionando {hs} h/día compensan el consumo mensual."
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/enviar-informe")
def enviar_informe():
    try:
        df = obtener_datos_supabase(limit=500)

        if df.empty:
            print("❌ No se encontraron datos en Supabase.")
            return

        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
        df = df[df["fecha"] > pd.Timestamp.now(tz=df["fecha"].dt.tz)]

        # Conversión de columnas numéricas
        for col in ["sensor1", "sensor2", "sensor1_hum", "sensor2_hum", "power1", "power2"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        resumen = {
            "temp_max": df[["sensor1", "sensor2"]].max().max().round(1),
            "temp_min": df[["sensor1", "sensor2"]].min().min().round(1),
            "hum_max": df[["sensor1_hum", "sensor2_hum"]].max().max().round(1),
            "hum_min": df[["sensor1_hum", "sensor2_hum"]].min().min().round(1),
            "kwh_total": round(((df["power1"] + df["power2"]).fillna(0).sum()) * 60 / 3600 / 1000, 2),
            "frecuencia_s": 60
        }

        # Composición del mensaje
        mensaje = f"""
        🐛 Informe Semanal - Granja Monitorizada 🐛

        🌡️ Temperatura Máxima: {resumen['temp_max']} °C
        🌡️ Temperatura Mínima: {resumen['temp_min']} °C

        💧 Humedad Máxima: {resumen['hum_max']} %
        💧 Humedad Mínima: {resumen['hum_min']} %

        ⚡ Consumo Energético Estimado: {resumen['kwh_total']} kWh

        ⏱ Frecuencia de Muestreo: {resumen['frecuencia_s']} s
        """

        asunto = "📊 Informe Semanal - Granja Inteligente"
        destinatario = os.getenv("EMAIL_DESTINO", "edu@edgefarming.cat")
        enviar_correo(asunto, mensaje, destinatario)

        print("✅ Informe semanal enviado correctamente.")
        return "✅ Informe enviado correctamente"
        
    except Exception as e:
        print(f"❌ Error al enviar informe automático: {e}")
        return f"❌ Error al enviar informe: {e}", 500

@app.route("/api/consumo-diario")
def consumo_diario():
    try:
        df = obtener_datos_supabase(limit=2000)  # Límite alto para cubrir 30 días

        if df.empty:
            return jsonify([])

        print("🧪 Columnas detectadas:", df.columns.tolist())

        if not {"fecha", "power1", "power2"}.issubset(df.columns):
            return jsonify({"error": "Faltan columnas necesarias"}), 400

        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
        df = df[df["fecha"] > pd.Timestamp.now(tz=timezone.utc) - pd.Timedelta(days=30)]
        df["fecha_dia"] = df["fecha"].dt.date

        df["power1"] = pd.to_numeric(df["power1"], errors="coerce").fillna(0)
        df["power2"] = pd.to_numeric(df["power2"], errors="coerce").fillna(0)
        df["watts_totales"] = df["power1"] + df["power2"]

        df_ordenado = df.sort_values("fecha")
        if len(df_ordenado) < 2:
            frecuencia_seg = 60
        else:
            tiempos = df_ordenado["fecha"].astype("int64") // 1_000_000_000
            diferencias = tiempos.diff().dropna()
            frecuencia_seg = diferencias.mean()

        df["kwh"] = df["watts_totales"] * frecuencia_seg / 3600000

        consumo_por_dia = df.groupby("fecha_dia")["kwh"].sum().reset_index()
        consumo_por_dia["kwh"] = consumo_por_dia["kwh"].round(2)

        resultado = consumo_por_dia.rename(columns={"fecha_dia": "fecha"}).to_dict(orient="records")

        del df  # liberar memoria
        import gc
        gc.collect()

        return jsonify(resultado)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/resumen-ia")
def resumen_ia():
    try:
        df = obtener_datos_supabase()
        if df.empty:
            return jsonify({"resumen": "No se encontraron datos."})

        # Convertir a datetime
        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
        df = df.dropna(subset=["fecha"])
        df = df[df["fecha"] > pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=15)]

        # Convertir columnas numéricas
        for col in ["sensor1", "sensor2", "sensor1_hum", "sensor2_hum", "multi1_temp", "multi1_co2", "multi1_pm25", "multi1_noise", "power1", "power2"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # Estadísticas para IA
        descripcion = df.describe().to_string()

        prompt = f"""Actúa como un experto en eficiencia ambiental y energía. Te paso un dataset con variables como temperatura, humedad, ruido, CO2, PM2.5 y consumo eléctrico.
Tu tarea es analizar las estadísticas, identificar anomalías o valores que se salgan de los rangos ideales, y dar una conclusión clara para el usuario final que opera una granja de insectos tenebrio.
redacta un informe corto para el cliente (máximo 5 líneas) que resuma el estado de su sistema de monitoreo, resaltando anomalías o recomendaciones si las hay,  agrega 5 bullets de plan de acción.. Aquí están los datos:

{descripcion}

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
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

def iniciar_monitoreo_automatico():
    def loop():
        with app.app_context():
            while True:
                obtener_datos_y_guardar()
                time.sleep(60)

    hilo = threading.Thread(target=loop, daemon=True)
    hilo.start()

if __name__ == "__main__":
    iniciar_monitoreo_automatico()

    def tarea_enviar_informe():
        with app.app_context():
            enviar_informe()

   # Programar envío automático
    scheduler = BackgroundScheduler()
    scheduler.add_job(tarea_enviar_informe, "interval", minutes=1)
    scheduler.start()
    
  #  scheduler.add_job(envio_automatico_informe, "cron", day_of_week="mon", hour=8, minute=0)
   

    
    print("✅ Scheduler iniciado correctamente")

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
