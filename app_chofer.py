from flask import Flask, request, render_template_string, redirect, url_for, session, flash, send_from_directory
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta
import os
import base64
import requests
import urllib.parse
import json

app = Flask(__name__)
app.secret_key = "secreto_super_seguro_choferes_ek"

# 🔥 CONFIGURACIÓN DE MEMORIA PERMANENTE (30 DÍAS SIN DESLOGUEARSE) 🔥
app.permanent_session_lifetime = timedelta(days=30)

# --- CONFIGURACIÓN DE SEGURIDAD ---
DATABASE_URL = os.environ.get("DB_URL") 
if not DATABASE_URL:
    from dotenv import load_dotenv
    load_dotenv()
    DATABASE_URL = os.getenv("DB_URL")

BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "") 
EMAIL_REMITENTE = "eklogistica19@gmail.com" 
NUMERO_BASE_RAW = "2613672674" 

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
if not os.path.exists(UPLOAD_FOLDER): os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def hora_arg():
    return datetime.now() - timedelta(hours=3)

# --- RUTAS DE LA APP ---

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/', methods=['GET', 'POST'])
def index():
    if 'chofer' in session:
        return redirect(url_for('chofer_dashboard'))
        
    if request.method == 'POST':
        sucursal = request.form.get('sucursal')
        if sucursal:
            return redirect(url_for('login_chofer', sucursal=sucursal))
            
    html = """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>App Choferes</title>
        <style>
            body { font-family: Arial, sans-serif; background-color: #f4f7f6; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
            .login-box { background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); width: 90%; max-width: 400px; text-align: center; }
            .logo-img { width: 150px; margin-bottom: 20px; }
            select { width: 100%; padding: 15px; margin-bottom: 20px; border-radius: 5px; border: 1px solid #ccc; font-size: 18px; }
            button { background-color: #0d6efd; color: white; border: none; padding: 15px; width: 100%; border-radius: 5px; font-size: 18px; font-weight: bold; cursor: pointer; }
        </style>
    </head>
    <body>
        <div class="login-box">
            <img src="/uploads/eklogo.png" alt="Logo EK" class="logo-img" onerror="this.style.display='none'">
            <h2 style="color: #0d6efd; margin-top:0;">Selecciona tu Base</h2>
            <form method="POST">
                <select name="sucursal" required>
                    <option value="">-- Elige la Sucursal --</option>
                    <option value="Mendoza">Mendoza</option>
                    <option value="San Juan">San Juan</option>
                </select>
                <button type="submit">CONTINUAR ➡</button>
            </form>
        </div>
    </body>
    </html>
    """
    return render_template_string(html)

@app.route('/login_chofer/<sucursal>', methods=['GET', 'POST'])
def login_chofer(sucursal):
    if 'chofer' in session:
        return redirect(url_for('chofer_dashboard'))
        
    engine = create_engine(DATABASE_URL)
    
    if request.method == 'POST':
        nombre_chofer = request.form.get('chofer')
        dni_ingresado = request.form.get('dni')
        
        if nombre_chofer and dni_ingresado:
            try:
                with engine.connect() as conn:
                    result = conn.execute(text("SELECT dni FROM choferes WHERE nombre = :n AND sucursal = :s"), {"n": nombre_chofer, "s": sucursal}).fetchone()
                    
                    if result:
                        dni_real = str(result[0]).strip()
                        if dni_ingresado.strip() == dni_real:
                            session.permanent = True
                            session['chofer'] = nombre_chofer
                            session['sucursal'] = sucursal
                            return redirect(url_for('chofer_dashboard'))
                        else:
                            flash("❌ Contraseña (DNI) incorrecta.", "error")
                    else:
                        flash("❌ Error al verificar chofer.", "error")
            except Exception as e:
                flash("❌ Error de conexión.", "error")
                
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT nombre FROM choferes WHERE sucursal = :s ORDER BY nombre ASC"), {"s": sucursal}).fetchall()
            choferes = [row[0] for row in result]
    except:
        choferes = []

    html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>Ingreso - {sucursal}</title>
        <style>
            body {{ font-family: Arial, sans-serif; background-color: #f4f7f6; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }}
            .login-box {{ background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); width: 90%; max-width: 400px; text-align: center; }}
            .logo-img {{ width: 120px; margin-bottom: 10px; }}
            select, input {{ width: 100%; padding: 15px; margin-bottom: 20px; border-radius: 5px; border: 1px solid #ccc; font-size: 16px; box-sizing: border-box; }}
            button {{ background-color: #198754; color: white; border: none; padding: 15px; width: 100%; border-radius: 5px; font-size: 18px; font-weight: bold; cursor: pointer; margin-bottom: 15px; }}
            .btn-back {{ display: block; text-decoration: none; color: #666; font-weight: bold; font-size: 14px; margin-top: 10px; }}
        </style>
    </head>
    <body>
        <div class="login-box">
            <img src="/uploads/eklogo.png" alt="Logo EK" class="logo-img" onerror="this.style.display='none'">
            <h3 style="color: #333; margin-top:0;">Base: {sucursal}</h3>
            
            {{% with messages = get_flashed_messages(with_categories=true) %}}
              {{% if messages %}}
                {{% for category, message in messages %}}
                  <div style="padding: 10px; margin-bottom: 15px; border-radius: 5px; background-color: #f8d7da; color: #721c24;">
                    {{{{ message }}}}
                  </div>
                {{% endfor %}}
              {{% endif %}}
            {{% endwith %}}
            
            <form method="POST">
                <select name="chofer" required>
                    <option value="">-- Soy el Chofer --</option>
                    {''.join([f'<option value="{c}">{c}</option>' for c in choferes])}
                </select>
                <input type="password" name="dni" placeholder="Contraseña (Tu DNI)" required autocomplete="off">
                <button type="submit">INGRESAR</button>
            </form>
            <a href="/" class="btn-back">⬅ Cambiar Sucursal</a>
        </div>
    </body>
    </html>
    """
    return render_template_string(html)

@app.route('/logout')
def logout():
    session.pop('chofer', None)
    session.pop('sucursal', None)
    return redirect(url_for('index'))

@app.route('/chofer')
def chofer_dashboard():
    if 'chofer' not in session:
        return redirect(url_for('index'))
    
    chofer_nombre = session['chofer']
    engine = create_engine(DATABASE_URL)
    
    try:
        with engine.connect() as conn:
            query = text("""
                SELECT id, guia_remito, destinatario, domicilio, localidad, estado, tipo_servicio, bultos, bultos_frio, es_contra_reembolso, monto_recaudacion 
                FROM operaciones 
                WHERE chofer_asignado = :chofer 
                AND estado IN ('EN REPARTO', 'En Reparto')
                ORDER BY localidad ASC, domicilio ASC
            """)
            result = conn.execute(query, {"chofer": chofer_nombre}).fetchall()
            entregas = [dict(row._mapping) for row in result]
    except Exception as e:
        entregas = []

    html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>Mi Ruta</title>
        <style>
            body {{ font-family: Arial, sans-serif; background-color: #f4f7f6; margin: 0; padding-bottom: 20px; }}
            .header-banner {{ background-color: #ffffff; padding: 10px 15px; border-bottom: 3px solid #0d6efd; display: flex; align-items: center; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }}
            .header-banner img {{ height: 40px; margin-right: 15px; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 0 15px; }}
            .card {{ background-color: white; border-radius: 10px; padding: 15px; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); border-left: 5px solid #0d6efd; }}
            .card-retiro {{ border-left: 5px solid #ffc107; background-color: #fffdf5; }}
            .btn-gestionar {{ display: inline-block; background-color: #198754; color: white; padding: 10px; text-decoration: none; border-radius: 5px; font-weight: bold; width: 100%; text-align: center; margin-top: 10px; box-sizing: border-box; }}
            .tag {{ display: inline-block; padding: 3px 8px; border-radius: 15px; font-size: 12px; font-weight: bold; margin-right: 5px; margin-bottom: 5px; }}
            .tag-zona {{ background-color: #e9ecef; color: #495057; }}
            .tag-bultos {{ background-color: #cff4fc; color: #055160; }}
            .tag-cobro {{ background-color: #f8d7da; color: #721c24; }}
        </style>
    </head>
    <body>
        <div class="header-banner">
            <img src="/uploads/eklogo.png" alt="EK" onerror="this.style.display='none'">
            <h2 style="color: #0d6efd; margin: 0; font-size: 20px; font-weight: bold;">Plataforma Móvil</h2>
        </div>
        <div class="container">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                <h3 style="color: #333; margin-top: 0;">👋 Hola, {chofer_nombre}</h3>
                <a href="/logout" style="background-color: #dc3545; color: white; padding: 8px 15px; text-decoration: none; border-radius: 5px; font-weight: bold;">Salir</a>
            </div>
            
            {{% with messages = get_flashed_messages(with_categories=true) %}}
              {{% if messages %}}
                {{% for category, message in messages %}}
                  <div style="padding: 15px; margin-bottom: 20px; border-radius: 5px; background-color: {{% if category == 'error' %}}#f8d7da{{% else %}}#d4edda{{% endif %}}; color: {{% if category == 'error' %}}#721c24{{% else %}}#155724{{% endif %}};">
                    {{{{ message }}}}
                  </div>
                {{% endfor %}}
              {{% endif %}}
            {{% endwith %}}

            <a href="/scan" style="display: block; background-color: #ff9800; color: black; padding: 15px; text-align: center; text-decoration: none; border-radius: 8px; font-weight: bold; font-size: 18px; margin-bottom: 20px; border: 2px solid #e68a00;">
                📷 ESCANEAR CÓDIGO DE BARRAS
            </a>

            <div style="background-color: white; padding: 15px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center; border: 1px solid #17a2b8;">
                <p style="margin: 0 0 10px 0; color: #555; font-size: 14px; font-weight: bold;">Mantenimiento de Vehículo</p>
                <a href="/update_km" style="display: block; background-color: #17a2b8; color: white; padding: 12px; text-align: center; text-decoration: none; border-radius: 8px; font-weight: bold; font-size: 16px;">
                    🚗 Actualizar Kilómetros
                </a>
            </div>

            <h4 style="border-bottom: 2px solid #ddd; padding-bottom: 10px;">📋 Tu Hoja de Ruta ({len(entregas)})</h4>
    """

    if not entregas:
        html += """
        <div style="text-align: center; padding: 30px; background-color: white; border-radius: 10px;">
            <p style="font-size: 40px; margin: 0;">🎉</p>
            <p style="color: #666; font-size: 18px;">No tienes guías pendientes.</p>
        </div>
        """
    else:
        for op in entregas:
            es_retiro = "Retiro" in (op['tipo_servicio'] or "")
            clase_card = "card-retiro" if es_retiro else ""
            icono = "🔄 RETIRO" if es_retiro else "📦 ENTREGA"
            
            b_tot = op['bultos'] or 1
            b_fr = op['bultos_frio'] or 0
            txt_bultos = f"{b_tot} Bultos" if b_fr == 0 else f"{b_tot} Totales ({b_fr} Frío)"
            
            html += f"""
            <div class="card {clase_card}">
                <div style="font-size: 12px; color: #666; margin-bottom: 5px;">
                    <b>ID:</b> {op['id']} | <b>Guía:</b> {op['guia_remito'] or 'S/G'}
                </div>
                <div style="font-size: 18px; font-weight: bold; margin-bottom: 5px; color: #333;">
                    {icono}: {op['destinatario']}
                </div>
                <div style="font-size: 16px; margin-bottom: 10px; color: #444;">
                    📍 {op['domicilio']}
                </div>
                <div>
                    <span class="tag tag-zona">{op['localidad']}</span>
                    <span class="tag tag-bultos">{txt_bultos}</span>
            """
            
            if op['es_contra_reembolso'] and op['monto_recaudacion']:
                html += f'<span class="tag tag-cobro">💵 COBRAR: ${op["monto_recaudacion"]}</span>'

            html += f"""
                </div>
                <a href="/gestion/{op['id']}" class="btn-gestionar">ESTADO / ENTREGAR</a>
            </div>
            """

    html += """
        </div>
    </body>
    </html>
    """
    return render_template_string(html)

# 🔥 NUEVA RUTA PARA ACTUALIZAR KILOMETRAJE 🔥
@app.route('/update_km', methods=['GET', 'POST'])
def update_km():
    if 'chofer' not in session:
        return redirect(url_for('index'))
    
    chofer_nombre = session['chofer']
    engine = create_engine(DATABASE_URL)
    
    if request.method == 'POST':
        nuevo_km = request.form.get('km_actual')
        if nuevo_km and nuevo_km.isdigit():
            try:
                with engine.connect() as conn:
                    chofer_res = conn.execute(text("SELECT id FROM choferes WHERE nombre = :n"), {"n": chofer_nombre}).fetchone()
                    if chofer_res:
                        ch_id = chofer_res[0]
                        veh_res = conn.execute(text("SELECT id FROM vehiculos WHERE chofer_id = :cid AND estado = 'ACTIVO'"), {"cid": ch_id}).fetchone()
                        if veh_res:
                            conn.execute(text("UPDATE vehiculos SET kilometraje_actual = :km WHERE id = :vid"), {"km": int(nuevo_km), "vid": veh_res[0]})
                            conn.commit()
                            flash(f"✅ Kilometraje actualizado exitosamente a {nuevo_km} km.", "success")
                        else:
                            flash("❌ No tienes ningún vehículo activo asignado en el sistema.", "error")
                    else:
                        flash("❌ Error de identificación de usuario.", "error")
            except Exception as e:
                flash("❌ Error de base de datos al guardar.", "error")
        else:
            flash("❌ Por favor, ingresa un número válido.", "error")
            
        return redirect(url_for('chofer_dashboard'))
    
    km_actual = ""
    patente = "Buscando vehículo..."
    tiene_vehiculo = False
    
    try:
        with engine.connect() as conn:
            chofer_res = conn.execute(text("SELECT id FROM choferes WHERE nombre = :n"), {"n": chofer_nombre}).fetchone()
            if chofer_res:
                veh_res = conn.execute(text("SELECT patente, marca, modelo, kilometraje_actual FROM vehiculos WHERE chofer_id = :cid AND estado = 'ACTIVO'"), {"cid": chofer_res[0]}).fetchone()
                if veh_res:
                    tiene_vehiculo = True
                    patente = f"{veh_res[1]} {veh_res[2]} (Patente: {veh_res[0]})"
                    km_actual = veh_res[3] if veh_res[3] else ""
                else:
                    patente = "Ningún vehículo asignado"
    except:
        pass
        
    html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>Actualizar Kilometraje</title>
        <style>
            body {{ font-family: Arial, sans-serif; background-color: #f4f7f6; padding: 20px; display: flex; justify-content: center; align-items: center; min-height: 80vh; margin: 0; }}
            .container {{ width: 100%; max-width: 400px; background: white; padding: 25px; border-radius: 12px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }}
            h3 {{ color: #0d6efd; text-align: center; margin-top: 0; font-size: 24px; }}
            .info-box {{ background-color: #e9ecef; padding: 15px; border-radius: 8px; text-align: center; margin-bottom: 20px; border: 1px solid #ced4da; }}
            input[type="number"] {{ width: 100%; padding: 15px; margin: 10px 0 20px 0; border: 2px solid #17a2b8; border-radius: 8px; font-size: 24px; font-weight: bold; text-align: center; box-sizing: border-box; }}
            .btn-save {{ background-color: #17a2b8; color: white; padding: 15px; border: none; border-radius: 8px; width: 100%; font-size: 18px; font-weight: bold; cursor: pointer; text-transform: uppercase; }}
            .btn-save:disabled {{ background-color: #ccc; cursor: not-allowed; }}
            .btn-back {{ display: block; text-align: center; background-color: #6c757d; color: white; padding: 15px; border-radius: 8px; text-decoration: none; font-weight: bold; font-size: 16px; margin-top: 15px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h3>🚗 Actualizar Tablero</h3>
            
            <div class="info-box">
                <p style="margin: 0; color: #666; font-size: 14px;">Vehículo actual:</p>
                <p style="margin: 5px 0 0 0; font-weight: bold; color: #333; font-size: 16px;">{patente}</p>
            </div>
            
            <form method="POST">
                <label style="font-weight: bold; color: #444; font-size: 16px; display: block; text-align: center;">¿Qué KM marca la camioneta ahora?</label>
                <input type="number" name="km_actual" value="{km_actual}" placeholder="Ej: 125000" required autofocus>
                <button type="submit" class="btn-save" {'disabled' if not tiene_vehiculo else ''}>💾 Guardar Kilómetros</button>
            </form>
            
            <a href="/chofer" class="btn-back">⬅ Cancelar y Volver</a>
            
            {"" if tiene_vehiculo else "<p style='color: #dc3545; text-align: center; margin-top: 20px; font-weight: bold; border: 1px solid #dc3545; padding: 10px; border-radius: 5px;'>⚠️ Para usar esta función, el administrador debe asignarte un vehículo desde la PC.</p>"}
        </div>
    </body>
    </html>
    """
    return render_template_string(html)

@app.route('/scan', methods=['GET', 'POST'])
def scan():
    if 'chofer' not in session:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        codigo = request.form.get('codigo_guia')
        if codigo:
            chofer_nombre = session['chofer']
            engine = create_engine(DATABASE_URL)
            try:
                with engine.connect() as conn:
                    query = text("""
                        SELECT id FROM operaciones 
                        WHERE (guia_remito = :codigo OR CAST(id AS TEXT) = :codigo)
                        AND chofer_asignado = :chofer
                        AND estado IN ('EN REPARTO', 'En Reparto')
                    """)
                    result = conn.execute(query, {"codigo": codigo.strip(), "chofer": chofer_nombre}).fetchone()
                    
                    if result:
                        return redirect(url_for('gestion', id_op=result[0]))
                    else:
                        flash(f"❌ La guía '{codigo}' no se encontró en tu ruta activa.", "error")
            except Exception as e:
                flash("❌ Error de base de datos.", "error")
                
        return redirect(url_for('scan'))

    html = """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>Escanear Guía</title>
        <style>
            body { font-family: Arial, sans-serif; background-color: #333; color: white; display: flex; flex-direction: column; align-items: center; height: 100vh; margin: 0; padding: 20px; box-sizing: border-box; }
            .header-banner { width: 100%; background-color: #ffffff; padding: 10px 15px; border-bottom: 3px solid #ff9800; display: flex; align-items: center; margin-bottom: 20px; box-sizing: border-box; position: absolute; top: 0; left: 0; }
            .header-banner img { height: 40px; margin-right: 15px; }
            h3 { color: #ff9800; margin-bottom: 20px; margin-top: 80px; }
            input[type="text"] { width: 100%; max-width: 400px; padding: 15px; margin-bottom: 20px; border-radius: 5px; border: none; font-size: 18px; text-align: center; }
            button { background-color: #198754; color: white; border: none; padding: 15px; width: 100%; max-width: 400px; border-radius: 5px; font-size: 18px; font-weight: bold; cursor: pointer; margin-bottom: 15px; }
            .btn-back { background-color: #6c757d; color: white; padding: 15px; width: 100%; max-width: 400px; text-align: center; text-decoration: none; border-radius: 5px; font-weight: bold; box-sizing: border-box; }
        </style>
    </head>
    <body>
        <div class="header-banner">
            <img src="/uploads/eklogo.png" alt="EK" onerror="this.style.display='none'">
            <h2 style="color: #ff9800; margin: 0; font-size: 20px; font-weight: bold;">Escáner Móvil</h2>
        </div>
        <h3>📷 Lector de Guías</h3>
        
        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            {% for category, message in messages %}
              <div style="padding: 15px; margin-bottom: 20px; border-radius: 5px; background-color: #f8d7da; color: #721c24; width: 100%; max-width: 400px; text-align: center;">
                {{ message }}
              </div>
            {% endfor %}
          {% endif %}
        {% endwith %}

        <form method="POST" style="width: 100%; max-width: 400px; display: flex; flex-direction: column; align-items: center;">
            <p style="text-align: center; color: #ccc;">Haz clic en el recuadro abajo y usa tu lector láser, o escribe el número a mano:</p>
            <input type="text" name="codigo_guia" placeholder="Pistolear aquí..." autofocus required autocomplete="off">
            <button type="submit">BUSCAR GUÍA</button>
        </form>
        <br>
        <a href="/chofer" class="btn-back">⬅ Volver a Mi Ruta</a>
    </body>
    </html>
    """
    return render_template_string(html)

def enviar_mail_brevo(destinatario, asunto, mensaje_html, adjuntos_base64=None):
    if not BREVO_API_KEY:
        print("⚠️ No hay API KEY de Brevo configurada. Correo omitido.")
        return
        
    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "accept": "application/json",
        "api-key": BREVO_API_KEY,
        "content-type": "application/json"
    }
    
    data = {
        "sender": {"email": EMAIL_REMITENTE, "name": "E.K. Logística"},
        "to": [{"email": destinatario}],
        "subject": asunto,
        "htmlContent": mensaje_html
    }
    
    if adjuntos_base64:
        data["attachment"] = []
        for i, foto_b64 in enumerate(adjuntos_base64):
            data["attachment"].append({
                "content": foto_b64,
                "name": f"Remito_Firmado_{i+1}.jpg"
            })
            
    try:
        response = requests.post(url, headers=headers, data=json.dumps(data))
        if response.status_code in [200, 201, 202]:
            print(f"✅ Correo enviado exitosamente a {destinatario}")
        else:
            print(f"❌ Error al enviar correo: {response.text}")
    except Exception as e:
        print(f"❌ Error de red al enviar correo: {e}")

@app.route('/gestion/<int:id_op>', methods=['GET', 'POST'])
def gestion(id_op):
    if 'chofer' not in session:
        return redirect(url_for('index'))
        
    chofer_nombre = session['chofer']
    engine = create_engine(DATABASE_URL)
    
    if request.method == 'POST':
        estado_nuevo = request.form.get('estado')
        motivo = request.form.get('motivo', '').strip().upper()
        recibe = request.form.get('recibe', '').strip().upper()
        lat = request.form.get('lat')
        lng = request.form.get('lng')
        
        fotos = request.files.getlist('foto_remito')
        fotos_base64 = []
        
        for foto in fotos:
            if foto and foto.filename:
                foto_bytes = foto.read()
                if len(foto_bytes) > 0:
                    fotos_base64.append(base64.b64encode(foto_bytes).decode('utf-8'))
        
        detalle_historial = ""
        link_maps = ""
        if lat and lng:
            link_maps = f"https://www.google.com/maps?q={lat},{lng}"
            
        if estado_nuevo == "ENTREGADO":
            detalle_historial = f"Recibio: {recibe} "
            if link_maps: detalle_historial += f"| GPS: {link_maps} "
            if fotos_base64: detalle_historial += f"| 📸 {len(fotos_base64)} Foto(s) Adjunta(s)"
        else:
            detalle_historial = f"Motivo: {motivo} "
            if link_maps: detalle_historial += f"| GPS: {link_maps}"
                
        try:
            with engine.connect() as conn:
                op_data = conn.execute(text("""
                    SELECT o.guia_remito, o.destinatario, o.proveedor, o.fecha_ingreso, c.email_reportes, c.enviar_mail
                    FROM operaciones o
                    LEFT JOIN clientes_principales c ON o.proveedor = c.nombre
                    WHERE o.id = :id AND o.chofer_asignado = :chofer
                """), {"id": id_op, "chofer": chofer_nombre}).fetchone()
                
                conn.execute(text("""
                    UPDATE operaciones 
                    SET estado = :est, fecha_entrega = :fech 
                    WHERE id = :id AND chofer_asignado = :chofer
                """), {
                    "est": estado_nuevo, 
                    "fech": hora_arg().date(),
                    "id": id_op, 
                    "chofer": chofer_nombre
                })
                
                conn.execute(text("""
                    INSERT INTO historial_movimientos (operacion_id, fecha_hora, usuario, accion, detalle) 
                    VALUES (:op_id, :fh, :usu, :acc, :det)
                """), {
                    "op_id": id_op,
                    "fh": hora_arg(),
                    "usu": chofer_nombre,
                    "acc": estado_nuevo,
                    "det": detalle_historial[:250]
                })
                
                conn.commit()
                
                if op_data and estado_nuevo == "ENTREGADO" and op_data[5] and op_data[4]:
                    guia_n = op_data[0] or str(id_op)
                    dest_n = op_data[1]
                    email_dest = op_data[4]
                    fecha_str = hora_arg().strftime("%d/%m/%Y %H:%M")
                    
                    asunto = f"Aviso de Entrega: Guía {guia_n} - E.K. Logística"
                    html_mail = f"""
                    <div style="font-family: Arial, sans-serif; padding: 20px; border: 1px solid #ccc; max-width: 600px;">
                        <h2 style="color: #0d6efd;">Confirmación de Entrega</h2>
                        <p>Estimado cliente,</p>
                        <p>Le informamos que su envío <b>{guia_n}</b> a nombre de <b>{dest_n}</b> ha sido <b>ENTREGADO</b> satisfactoriamente.</p>
                        <ul style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; list-style-type: none;">
                            <li>📅 <b>Fecha y Hora:</b> {fecha_str}</li>
                            <li>👤 <b>Recibió:</b> {recibe}</li>
                            <li>🚚 <b>Entregado por:</b> {chofer_nombre}</li>
                        </ul>
                        <p>Gracias por confiar en <b>E.K. Logística</b>.</p>
                    </div>
                    """
                    
                    try:
                        import threading
                        thread = threading.Thread(target=enviar_mail_brevo, args=(email_dest, asunto, html_mail, fotos_base64))
                        thread.start()
                    except Exception as email_e:
                        print("Fallo al iniciar el hilo del correo:", email_e)
                
                flash(f"✅ Guía {id_op} marcada como {estado_nuevo}.", "success")
        except Exception as e:
            flash(f"❌ Error al guardar en base de datos: {e}", "error")
            
        return redirect(url_for('chofer_dashboard'))

    try:
        with engine.connect() as conn:
            op = conn.execute(text("""
                SELECT guia_remito, destinatario, domicilio, localidad, celular, bultos, monto_recaudacion, es_contra_reembolso
                FROM operaciones 
                WHERE id = :id AND chofer_asignado = :chofer
            """), {"id": id_op, "chofer": chofer_nombre}).fetchone()
            
            if not op:
                flash("❌ La guía no existe o ya no está en tu ruta.", "error")
                return redirect(url_for('chofer_dashboard'))
    except:
        flash("❌ Error de conexión.", "error")
        return redirect(url_for('chofer_dashboard'))

    link_wsp = ""
    if op[4]:
        num = "".join(filter(str.isdigit, str(op[4])))
        if num:
            if not num.startswith("54"): num = "549" + num
            mensaje = urllib.parse.quote(f"Hola, soy el repartidor de EK Logística. Estoy en camino a entregar tu paquete en {op[2]}.")
            link_wsp = f"https://wa.me/{num}?text={mensaje}"

    html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>Gestionar Guía</title>
        <style>
            body {{ font-family: Arial, sans-serif; background-color: #f4f7f6; padding: 15px; margin: 0; }}
            .header-banner {{ background-color: #ffffff; padding: 10px 15px; border-bottom: 3px solid #198754; display: flex; align-items: center; margin-bottom: 15px; margin-top: -15px; margin-left: -15px; margin-right: -15px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }}
            .header-banner img {{ height: 40px; margin-right: 15px; }}
            .container {{ max-width: 600px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }}
            h3 {{ color: #0d6efd; margin-top: 0; border-bottom: 2px solid #ddd; padding-bottom: 10px; }}
            .info {{ margin-bottom: 20px; font-size: 16px; color: #444; line-height: 1.6; }}
            .cobro {{ background-color: #f8d7da; color: #721c24; padding: 10px; border-radius: 5px; font-weight: bold; text-align: center; margin-bottom: 20px; border: 1px solid #f5c6cb; }}
            select, input[type="text"] {{ width: 100%; padding: 15px; margin-bottom: 15px; border-radius: 5px; border: 1px solid #ccc; font-size: 16px; box-sizing: border-box; }}
            button {{ background-color: #198754; color: white; border: none; padding: 15px; width: 100%; border-radius: 5px; font-size: 18px; font-weight: bold; cursor: pointer; margin-bottom: 10px; }}
            .btn-wsp {{ display: block; background-color: #25D366; color: white; padding: 12px; text-align: center; text-decoration: none; border-radius: 5px; font-weight: bold; margin-bottom: 20px; font-size: 16px; }}
            .btn-back {{ display: block; background-color: #6c757d; color: white; padding: 15px; text-align: center; text-decoration: none; border-radius: 5px; font-weight: bold; box-sizing: border-box; }}
            #div_entregado, #div_no_entregado {{ display: none; background-color: #f8f9fa; padding: 15px; border-radius: 5px; border: 1px solid #ddd; margin-bottom: 15px; }}
        </style>
    </head>
    <body>
        <div class="header-banner">
            <img src="/uploads/eklogo.png" alt="EK" onerror="this.style.display='none'">
            <h2 style="color: #198754; margin: 0; font-size: 20px; font-weight: bold;">Gestión de Entrega</h2>
        </div>
        <div class="container">
            <h3>📦 Guía: {op[0] or 'S/G'} (ID: {id_op})</h3>
            
            <div class="info">
                <b>Destinatario:</b> {op[1]}<br>
                <b>Domicilio:</b> {op[2]}<br>
                <b>Zona:</b> {op[3]}<br>
                <b>Bultos:</b> {op[5]}<br>
            </div>
            
            {f'<div class="cobro">💵 COBRAR EN PUERTA: ${op[6]}</div>' if op[7] and op[6] else ''}
            
            {f'<a href="{link_wsp}" target="_blank" class="btn-wsp">💬 Avisar por WhatsApp</a>' if link_wsp else ''}

            <form method="POST" enctype="multipart/form-data" id="gestionForm">
                <input type="hidden" name="lat" id="lat_gps">
                <input type="hidden" name="lng" id="lng_gps">
                
                <label style="font-weight: bold;">¿Qué pasó con el paquete?</label>
                <select name="estado" id="estado_select" onchange="mostrarOpciones()" required>
                    <option value="">-- Seleccionar --</option>
                    <option value="ENTREGADO">✅ ENTREGADO (Éxito)</option>
                    <option value="EN DEPOSITO">❌ NO ENTREGADO (Vuelve a base)</option>
                </select>

                <div id="div_entregado">
                    <label style="font-weight: bold; color: #198754;">Nombre de quien recibe (Obligatorio):</label>
                    <input type="text" name="recibe" id="in_recibe" placeholder="Ej: Juan Perez (Familiar)..." autocomplete="off">
                    
                    <label style="font-weight: bold; color: #198754; margin-top:10px; display:block;">Opcional: Subir foto(s) del remito firmado</label>
                    <input type="file" name="foto_remito" accept="image/*" capture="environment" multiple style="margin-bottom:10px;">
                    <p style="font-size: 12px; color: #666; margin-top: 0;">(Puedes seleccionar varias fotos a la vez)</p>
                </div>

                <div id="div_no_entregado">
                    <label style="font-weight: bold; color: #dc3545;">Motivo por el que NO se entregó:</label>
                    <select name="motivo" id="in_motivo">
                        <option value="">-- Seleccionar Motivo --</option>
                        <option value="CERRADO / NO RESPONDEN">Cerrado / No responden el timbre</option>
                        <option value="DIRECCION INCORRECTA">Dirección Incorrecta / No existe</option>
                        <option value="RECHAZADO">Rechazado por el destinatario</option>
                        <option value="SE MUDO">Se mudó / Ya no vive ahí</option>
                        <option value="FALTA TIEMPO">Falta de tiempo en la ruta</option>
                        <option value="OTRO">Otro motivo (Avisar a base)</option>
                    </select>
                </div>

                <button type="button" onclick="validarYEnviar()" id="btn_guardar">💾 GUARDAR Y CERRAR GUÍA</button>
            </form>
            
            <a href="/chofer" class="btn-back">⬅ Cancelar y Volver</a>
        </div>

        <script>
            function mostrarOpciones() {{
                var est = document.getElementById("estado_select").value;
                document.getElementById("div_entregado").style.display = (est === "ENTREGADO") ? "block" : "none";
                document.getElementById("div_no_entregado").style.display = (est === "EN DEPOSITO") ? "block" : "none";
            }}

            function validarYEnviar() {{
                var estado = document.getElementById("estado_select").value;
                if (!estado) {{
                    alert("Por favor selecciona un estado de la guía.");
                    return;
                }}
                
                // Evita que el chofer toque dos veces rápido el botón
                var btn = document.getElementById("btn_guardar");
                btn.innerHTML = "ENVIANDO... ⏳";
                btn.style.opacity = "0.5";
                btn.style.pointerEvents = "none";
                
                document.getElementById("gestionForm").submit();
            }}

            function obtenerGPS() {{
                if (navigator.geolocation) {{
                    navigator.geolocation.getCurrentPosition(function(position) {{
                        document.getElementById('lat_gps').value = position.coords.latitude;
                        document.getElementById('lng_gps').value = position.coords.longitude;
                    }}, function(error) {{
                        console.log("No se pudo obtener GPS", error);
                    }}, {{ enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }});
                }}
            }}
            
            window.onload = obtenerGPS;
        </script>
    </body>
    </html>
    """
    return render_template_string(html)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)