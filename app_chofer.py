from flask import Flask, request, render_template_string, redirect, url_for, session, flash
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta
import os
import base64
import requests
import urllib.parse
import re

app = Flask(__name__)
app.secret_key = "secreto_super_seguro_choferes_ek"

# --- CONFIGURACIÓN DE SEGURIDAD (LEE DE RENDER O .ENV) ---
DATABASE_URL = os.environ.get("DB_URL") 
if not DATABASE_URL:
    from dotenv import load_dotenv
    load_dotenv()
    DATABASE_URL = os.getenv("DB_URL")

BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "") 
EMAIL_REMITENTE = "eklogistica19@gmail.com" 
NUMERO_BASE_RAW = "2615555555" 

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
if not os.path.exists(UPLOAD_FOLDER): os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def get_db():
    try: return create_engine(DATABASE_URL, pool_pre_ping=True).connect()
    except Exception as e:
        print("Error de DB:", e)
        return None

def limpiar_telefono_wsp(telefono):
    if not telefono: return ""
    nums = "".join(filter(str.isdigit, str(telefono)))
    if len(nums) == 10: return "549" + nums
    return nums

NUMERO_BASE_FINAL = limpiar_telefono_wsp(NUMERO_BASE_RAW)

# --- FUNCIÓN REPARADORA DE ZONA HORARIA (ARGENTINA UTC-3) ---
def get_now():
    return datetime.utcnow() - timedelta(hours=3)

def enviar_email(destinatario, guia, rutas_fotos, proveedor, link_mapa=""):
    if not BREVO_API_KEY: return
    conn = get_db()
    email_prov = None
    if conn:
        try:
            res = conn.execute(text("SELECT email_reportes FROM clientes_principales WHERE nombre = :n"), {"n": proveedor}).fetchone()
            if res: email_prov = res[0]
        except: pass
        finally: conn.close()
    
    destinatarios_lista = []
    if email_prov:
        destinatarios_lista.append({"email": email_prov})
    
    if not destinatarios_lista:
        print("⚠️ Proveedor sin mail. Enviando solo copia interna.")
    
    adjuntos = []
    for ruta in rutas_fotos:
        if ruta and os.path.exists(ruta):
            try:
                with open(ruta, "rb") as f:
                    content = base64.b64encode(f.read()).decode('utf-8')
                    adjuntos.append({"content": content, "name": os.path.basename(ruta)})
            except: pass

    url = "https://api.brevo.com/v3/smtp/email"
    # USA LA HORA ARGENTINA
    fecha_hora = get_now().strftime('%d/%m/%Y %H:%M')
    
    texto_gps = f"<li><b>Ubicación (GPS):</b> <a href='{link_mapa}'>Ver en Google Maps</a></li>" if link_mapa else ""

    html_content = f"""
    <html><body>
    <h3>Hola,</h3>
    <p>Se informa la entrega exitosa. <b>Adjuntamos las fotos del remito/guía conformado o comprobantes.</b></p>
    <ul>
        <li><b>Fecha:</b> {fecha_hora}</li>
        <li><b>Guía:</b> {guia}</li>
        <li><b>Proveedor:</b> {proveedor}</li>
        <li><b>Recibió:</b> {destinatario}</li>
        {texto_gps}
    </ul>
    <p>Atte.<br><b>Equipo JetPaq / EK Logística</b></p>
    </body></html>
    """
    
    payload = {
        "sender": {"name": "Logistica JetPaq", "email": EMAIL_REMITENTE},
        "subject": f"ENTREGA REALIZADA - Guía: {guia}",
        "htmlContent": html_content,
        "bcc": [{"email": EMAIL_REMITENTE, "name": "Archivo EK Logistica"}]
    }

    if destinatarios_lista: payload["to"] = destinatarios_lista
    else: payload["to"] = [{"email": EMAIL_REMITENTE}]

    if adjuntos: payload["attachment"] = adjuntos
    
    headers = {"accept": "application/json", "api-key": BREVO_API_KEY, "content-type": "application/json"}
    try: requests.post(url, json=payload, headers=headers)
    except: pass

HTML_HEAD = """
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Choferes EK</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #f0f2f5; margin: 0; padding: 0; font-size: 16px; padding-bottom: 80px; }
        .header { background: #1565C0; color: white; padding: 15px; text-align: center; position: sticky; top: 0; z-index: 100; box-shadow: 0 2px 4px rgba(0,0,0,0.2); display: flex; justify-content: space-between; align-items: center; }
        .header h2 { margin: 0; font-size: 1.1rem; flex-grow: 1; text-align: center; font-weight: 600; }
        .container { padding: 15px; max-width: 600px; margin: 0 auto; }
        .card { background: white; padding: 20px; margin-bottom: 15px; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        
        details.accordion-card { background: white; margin-bottom: 15px; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); overflow: hidden; }
        details.accordion-card summary { padding: 20px; font-size: 1.1rem; font-weight: bold; cursor: pointer; list-style: none; outline: none; transition: background-color 0.3s; }
        details.accordion-card summary::-webkit-details-marker { display: none; }
        details.accordion-card summary::after { content: '▼'; float: right; color: inherit; font-size: 0.9rem; margin-top: 2px; }
        details.accordion-card[open] summary::after { content: '▲'; }
        
        .success-accordion summary { background-color: #e8f5e9; color: #2E7D32; border-left: 5px solid #43A047; }
        .error-accordion summary { background-color: #ffebee; color: #c62828; border-left: 5px solid #D32F2F; }
        .accordion-content { padding: 20px; border-top: 1px solid #eee; }

        .btn { display: block; width: 100%; padding: 14px; border: none; border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer; text-align: center; text-decoration: none; box-sizing: border-box; margin-top: 10px; transition: all 0.2s; }
        .btn:active { transform: scale(0.98); opacity: 0.9; }
        .btn-blue { background: #1976D2; color: white; }
        .btn-green { background: #43A047; color: white; }
        .btn-wa { background: #25D366; color: white; }
        .btn-red { background: #D32F2F; color: white; }
        .btn-orange { background: #F57C00; color: white; }
        .btn-purple { background: #7B1FA2; color: white; }
        .btn-grey { background: #757575; color: white; }
        .btn-outline { background: transparent; border: 1px solid #999; color: #555; }
        input, select { width: 100%; padding: 12px; margin-top: 8px; border: 1px solid #ddd; border-radius: 8px; font-size: 16px; background: #fff; box-sizing: border-box; }
        label { font-weight: 600; color: #444; margin-top: 15px; display: block; font-size: 0.9rem; }
        .tag { padding: 4px 8px; border-radius: 4px; font-size: 0.75rem; color: white; float: right; font-weight: bold; text-transform: uppercase; letter-spacing: 0.5px; }
        .tag-blue { background: #1976D2; } .tag-purple { background: #7B1FA2; } .tag-orange { background: #F57C00; }
        .camera-btn { background-color: #E3F2FD; color: #1565C0; border: 2px solid #1976D2; border-radius: 8px; padding: 12px; text-align: center; cursor: pointer; margin-top: 5px; display: block; font-weight: bold; width: 100%; box-sizing: border-box; }
        .alert { padding: 12px; margin-bottom: 15px; border-radius: 8px; font-weight: 500; text-align: center; font-size: 0.9rem; }
        .alert-success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .alert-error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        .bottom-nav { position: fixed; bottom: 0; left: 0; width: 100%; background: white; border-top: 1px solid #eee; display: flex; justify-content: space-around; padding: 12px 0; z-index: 99; box-shadow: 0 -2px 5px rgba(0,0,0,0.05); }
        .nav-item { text-decoration: none; color: #777; text-align: center; font-size: 0.75rem; font-weight: 500; }
        .nav-icon { font-size: 1.4rem; display: block; margin-bottom: 3px; }
        .truck-icon { width: 80px; height: 80px; margin-bottom: 10px; fill: #1976D2; }
    </style>
    <script>
        function handleAccordion(clickedId) {
            var exito = document.getElementById('acc_exito');
            var falla = document.getElementById('acc_falla');
            if (clickedId === 'exito' && exito.open) {
                falla.open = false;
            } else if (clickedId === 'falla' && falla.open) {
                exito.open = false;
            }
        }
        
        function toggleReprogramar() {
            var val = document.getElementById('estado_select').value;
            var repDiv = document.getElementById('div_reprogramar');
            if (val === 'Reprogramado') {
                repDiv.style.display = 'block';
            } else {
                repDiv.style.display = 'none';
            }
        }
        
        function obtenerGPS() {
            if (navigator.geolocation) {
                navigator.geolocation.getCurrentPosition(function(position) {
                    var lat = position.coords.latitude;
                    var lng = position.coords.longitude;
                    var latInputs = document.querySelectorAll('input[name="lat"]');
                    var lngInputs = document.querySelectorAll('input[name="lng"]');
                    latInputs.forEach(input => input.value = lat);
                    lngInputs.forEach(input => input.value = lng);
                }, function(error) {
                    console.log("No se pudo obtener GPS", error);
                }, {
                    enableHighAccuracy: true, timeout: 10000, maximumAge: 0
                });
            }
        }
        window.onload = obtenerGPS;

        let fotoCount = 0;
        function agregarFoto() {
            fotoCount++;
            var input = document.createElement('input');
            input.type = 'file';
            input.name = 'foto'; 
            input.accept = 'image/*';
            input.setAttribute('capture', 'environment'); 
            input.style.display = 'none';
            
            input.onchange = function() {
                if (this.files && this.files[0]) {
                    var lista = document.getElementById('fotosList');
                    var item = document.createElement('div');
                    item.style.backgroundColor = '#d4edda';
                    item.style.color = '#155724';
                    item.style.padding = '10px';
                    item.style.borderRadius = '5px';
                    item.style.marginTop = '8px';
                    item.style.fontSize = '0.95rem';
                    item.style.fontWeight = 'bold';
                    item.innerHTML = '✅ Foto ' + fotoCount + ' capturada y lista.';
                    lista.appendChild(item);
                    
                    var btnTxt = document.getElementById('btnFotoTexto');
                    btnTxt.innerText = '➕ AÑADIR OTRA FOTO';
                    var btn = document.getElementById('cameraBtn');
                    btn.style.borderColor = '#43A047';
                    btn.style.color = '#43A047';
                    btn.style.backgroundColor = '#e8f5e9';
                } else {
                    this.remove();
                    fotoCount--;
                }
            };
            
            document.getElementById('fotosContainer').appendChild(input);
            input.click(); 
        }
    </script>
</head>
"""

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        session['chofer'] = request.form.get('chofer')
        return redirect(url_for('lista_viajes'))
    
    conn = get_db()
    choferes = []
    if conn:
        try:
            res = conn.execute(text("SELECT nombre FROM choferes ORDER BY nombre")).fetchall()
            choferes = [r[0] for r in res]
        except: pass
        finally: conn.close()
        
    svg_truck = """<svg class="truck-icon" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M20,8h-3V4H3C2.45,4,2,4.45,2,5v11h2c0,1.66,1.34,3,3,3s3-1.34,3-3h6c0,1.66,1.34,3,3,3s3-1.34,3-3h2v-5L20,8z M6,13.5 c-0.83,0-1.5-0.67-1.5-1.5s0.67-1.5,1.5-1.5s1.5,0.67,1.5,1.5S6.83,13.5,6,13.5z M19,17c-0.55,0-1-0.45-1-1s0.45-1,1-1s1,0.45,1,1 S19.55,17,19,17z M18,11V8.5h1.75L21,11H18z"/></svg>"""
        
    html = f"""
    <!DOCTYPE html>
    <html>
    {HTML_HEAD}
    <body style="background:white;">
        <div class="container" style="display:flex; flex-direction:column; justify-content:center; height:90vh;">
            <div style="text-align: center;">
                {svg_truck}
                <h1 style="color: #1565C0; margin-bottom: 5px;">JetPaq Logística</h1>
                <p style="color: #777; margin-top: 0;">Portal de Choferes</p>
                <br>
                <form method="POST" style="background: #f9f9f9; padding: 30px; border-radius: 15px; border: 1px solid #eee;">
                    <label style="text-align: left;">Conductor:</label>
                    <select name="chofer" required style="margin-bottom: 20px; padding: 15px;">
                        <option value="">Selecciona tu nombre...</option>
                        {"".join([f'<option value="{c}">{c}</option>' for c in choferes])}
                    </select>
                    <button type="submit" class="btn btn-blue">INGRESAR</button>
                </form>
            </div>
        </div>
    </body>
    </html>
    """
    return render_template_string(html)

@app.route('/viajes')
def lista_viajes():
    chofer = session.get('chofer')
    if not chofer: return redirect(url_for('index'))
    
    mensajes_html = ""
    mensajes = session.pop('_flashes', [])
    for categoria, mensaje in mensajes:
        clase = "alert-success" if categoria == "success" else "alert-error"
        mensajes_html += f'<div class="alert {clase}">{mensaje}</div>'
    
    conn = get_db()
    viajes = []
    if conn:
        try:
            sql = text("SELECT id, guia_remito, destinatario, domicilio, localidad, bultos, estado, proveedor, tipo_servicio FROM operaciones WHERE chofer_asignado = :c AND UPPER(estado) IN ('EN REPARTO', 'PENDIENTE') ORDER BY id ASC")
            viajes = conn.execute(sql, {"c": chofer}).fetchall()
        except Exception as e: 
            print("Error cargando viajes:", e)
        finally: conn.close()
        
    cards_html = ""
    if not viajes:
        cards_html = "<div class='card' style='text-align:center; padding: 40px; border: 2px dashed #ddd;'><div style='font-size: 2rem;'>🎉</div><h3>¡Todo Entregado!</h3><p style='color:#666;'>No tienes viajes pendientes.</p></div>"
    else:
        for v in viajes:
            tipo_srv = v[8] if v[8] else ""
            es_retiro = "Retiro" in tipo_srv
            es_guardia = "Guardia" in tipo_srv
            
            lbl_tipo = "🔄 RETIRO" if es_retiro else "🚚 ENTREGA"
            color_tipo = "tag-purple" if es_retiro else "tag-blue"
            
            if es_guardia:
                lbl_tipo = "🚨 GUARDIA"
                color_tipo = "tag-orange"
                
            proveedor_txt = v[7] if v[7] else "Otro"
                
            q = f"{v[3]}, {v[4]}"
            mapa_url = f"https://www.google.com/maps/search/?api=1&query={q}"
            
            cards_html += f"""
            <div class="card">
                <div style="margin-bottom: 10px; overflow: hidden;">
                    <span class="tag {color_tipo}">{lbl_tipo}</span>
                    <h3 style="margin: 0; font-size: 1.1rem; color:#333;">{v[2]}</h3>
                </div>
                <div style="color: #555; font-size: 0.95rem; margin-bottom: 12px;">
                    📍 {v[3]} <small>({v[4]})</small><br>
                    🏢 Proveedor: <b>{proveedor_txt}</b>
                </div>
                <div style="background: #f0f7ff; padding: 10px; border-radius: 6px; font-size: 0.85rem; color: #444; margin-bottom: 15px; border-left: 4px solid #1976D2;">
                    📦 Guía: <b>{v[1]}</b>  |  Bultos: {v[5]}
                </div>
                <div style="display:flex; gap:10px;">
                    <a href="{mapa_url}" target="_blank" class="btn btn-outline" style="flex:1; margin-top:0;">🗺️ Mapa</a>
                    <a href="/gestion/{v[0]}" class="btn btn-blue" style="flex:2; margin-top:0;">Gestionar</a>
                </div>
            </div>
            """
            
    html = f"""
    <!DOCTYPE html>
    <html>
    {HTML_HEAD}
    <body>
        <div class="header">
            <div>🚛 <b>{chofer}</b></div>
            <a href="/" style="color:white; font-size:0.8rem; background:rgba(255,255,255,0.2); padding: 4px 10px; border-radius: 20px; text-decoration:none;">Salir</a>
        </div>
        <div class="container">
            {mensajes_html}
            
            <a href="/guardia" class="btn btn-orange" style="margin-bottom: 20px; font-size: 1.1rem; box-shadow: 0 4px 6px rgba(245, 124, 0, 0.3);">
                ➕ CARGAR ENVÍO DE GUARDIA
            </a>
            <hr style="border: 0; height: 1px; background-image: linear-gradient(to right, rgba(0, 0, 0, 0), rgba(0, 0, 0, 0.15), rgba(0, 0, 0, 0)); margin-bottom: 20px;">
            
            {cards_html}
            <br>
            <a href="/viajes" class="btn btn-green" style="margin-bottom: 60px;">🔄 ACTUALIZAR LISTA</a>
        </div>
        <div class="bottom-nav">
            <a href="/viajes" class="nav-item" style="color: #1976D2; font-weight:bold;">
                <span class="nav-icon">📦</span>Ruta
            </a>
            <a href="/historial" class="nav-item">
                <span class="nav-icon">📜</span>Historial
            </a>
            <a href="https://wa.me/{NUMERO_BASE_FINAL}" class="nav-item" style="color:#D32F2F;">
                <span class="nav-icon">🆘</span>Base
            </a>
        </div>
    </body>
    </html>
    """
    return render_template_string(html)

@app.route('/guardia', methods=['GET', 'POST'])
def guardia():
    chofer = session.get('chofer')
    if not chofer: return redirect(url_for('index'))

    conn = get_db()
    proveedores = ["JetPaq", "DHL", "Andreani", "MercadoLibre"] 
    if conn:
        try:
            res = conn.execute(text("SELECT nombre FROM clientes_principales ORDER BY nombre")).fetchall()
            if res: proveedores = [r[0] for r in res]
        except: pass
        
    if request.method == 'POST':
        guia = request.form.get('guia', '').strip()
        prov = request.form.get('proveedor', 'Otro')
        dest = request.form.get('destinatario', '').strip()
        dom = request.form.get('domicilio', '').strip()
        loc = request.form.get('localidad', '').strip()
        sucursal = request.form.get('sucursal', 'Mendoza')
        
        try: bultos = int(request.form.get('bultos', 1))
        except: bultos = 1
            
        try: peso = float(request.form.get('peso', 0.0))
        except: peso = 0.0
            
        es_frio = request.form.get('es_frio') == 'on'

        if not guia or not dest or not dom:
            flash("❌ Faltan datos obligatorios.", "error")
            return redirect(url_for('guardia'))

        bultos_frio = bultos if es_frio else 0
        tipo_carga = "REFRIGERADO (GUARDIA)" if es_frio else "COMUN (GUARDIA)"

        if conn:
            try:
                sql_insert = text("""
                    INSERT INTO operaciones
                    (fecha_ingreso, fecha_salida, sucursal, guia_remito, proveedor, destinatario, domicilio, localidad, bultos, bultos_frio, peso, tipo_carga, estado, chofer_asignado, tipo_servicio, monto_servicio, facturado)
                    VALUES
                    (:f_in, :f_sal, :suc, :guia, :prov, :dest, :dom, :loc, :bultos, :bfrio, :peso, :tcarga, 'EN REPARTO', :chof, 'Entrega (Guardia)', 0.0, FALSE)
                    RETURNING id
                """)
                # HORA CORREGIDA ACÁ TAMBIÉN
                now = get_now()
                params = {
                    "f_in": now.date(), "f_sal": now, "suc": sucursal, "guia": guia, "prov": prov, 
                    "dest": dest, "dom": dom, "loc": loc, "bultos": bultos, "bfrio": bultos_frio, 
                    "peso": peso, "tcarga": tipo_carga, "chof": chofer
                }
                res_id = conn.execute(sql_insert, params).fetchone()
                new_id = res_id[0]

                sql_hist = text("INSERT INTO historial_movimientos (operacion_id, usuario, accion, detalle, fecha_hora) VALUES (:o, :u, 'INGRESO GUARDIA', 'Cargado por chofer en Fin de Semana/Feriado', :f)")
                conn.execute(sql_hist, {"o": new_id, "u": chofer, "f": now})
                conn.commit()

                flash(f"✅ ¡Guardia cargada exitosamente! Ya está en tu ruta.", "success")
                return redirect(url_for('lista_viajes'))
            except Exception as e:
                print("Error al guardar guardia:", e)
                flash("❌ Error interno al guardar la guardia.", "error")
            finally:
                conn.close()

    mensajes_html = ""
    mensajes = session.pop('_flashes', [])
    for categoria, mensaje in mensajes:
        clase = "alert-success" if categoria == "success" else "alert-error"
        mensajes_html += f'<div class="alert {clase}">{mensaje}</div>'

    html = f"""
    <!DOCTYPE html>
    <html>
    {HTML_HEAD}
    <body>
        <div class="header" style="background:#F57C00;">
            <h2>🚨 Cargar Guardia (Urgencia)</h2>
        </div>
        <div class="container">
            {mensajes_html}
            <div class="card" style="border-top: 5px solid #F57C00;">
                <p style="color:#666; font-size:0.9rem; margin-top:0;">Completá estos datos rápidos para añadir el envío a tu ruta actual.</p>
                <form method="POST">
                    <label>Sucursal:</label>
                    <select name="sucursal" required>
                        <option value="Mendoza">Mendoza</option>
                        <option value="San Juan">San Juan</option>
                    </select>

                    <label>Guía / Remito:</label>
                    <input type="text" name="guia" placeholder="N° de remito..." required>
                    
                    <label>Proveedor:</label>
                    <select name="proveedor" required>
                        {"".join([f'<option value="{p}">{p}</option>' for p in proveedores])}
                    </select>
                    
                    <label>Destinatario:</label>
                    <input type="text" name="destinatario" placeholder="Nombre de quien recibe..." required>
                    
                    <label>Domicilio exacto:</label>
                    <input type="text" name="domicilio" placeholder="Calle, número, piso..." required>
                    
                    <label>Localidad / Zona:</label>
                    <input type="text" name="localidad" placeholder="Ej: Godoy Cruz, Capital..." required>
                    
                    <div style="display:flex; gap:10px;">
                        <div style="flex:1;">
                            <label>Bultos:</label>
                            <input type="number" name="bultos" value="1" min="1" required>
                        </div>
                        <div style="flex:1;">
                            <label>Peso (Kg):</label>
                            <input type="number" step="0.1" name="peso" value="0.0">
                        </div>
                    </div>
                    
                    <div style="margin-top: 20px; background: #e3f2fd; padding: 15px; border-radius: 8px; display: flex; align-items: center; gap: 10px;">
                        <input type="checkbox" name="es_frio" id="es_frio" style="width: 25px; height: 25px; margin:0;">
                        <label for="es_frio" style="margin:0; font-size:1.1rem; color:#0d47a1; cursor:pointer;">❄️ Requiere Frío / Contingencia</label>
                    </div>

                    <button type="submit" class="btn btn-orange" style="margin-top:25px; font-size:1.2rem;">🚀 GUARDAR Y REPARTIR</button>
                </form>
            </div>
            <a href="/viajes" class="btn btn-outline" style="border:1px solid #ccc; color:#666;">← Cancelar</a>
            <br><br>
        </div>
    </body>
    </html>
    """
    return render_template_string(html)

@app.route('/historial')
def historial():
    chofer = session.get('chofer')
    if not chofer: return redirect(url_for('index'))
    
    conn = get_db()
    movimientos = []
    if conn:
        try:
            # HORA CORREGIDA AL PEDIR EL HISTORIAL DE HOY
            sql = text("SELECT detalle, fecha_hora, accion FROM historial_movimientos WHERE usuario = :u AND (fecha_hora - interval '3 hours')::date = (CURRENT_TIMESTAMP - interval '3 hours')::date ORDER BY fecha_hora DESC")
            movimientos = conn.execute(sql, {"u": chofer}).fetchall()
        except: pass
        finally: conn.close()
    
    filas_html = ""
    if not movimientos:
        filas_html = "<div style='text-align:center; padding:20px; color:#888;'>No hay movimientos hoy.</div>"
    else:
        for m in movimientos:
            # RESTAR LAS 3 HORAS VISUALMENTE EN EL HISTORIAL
            hora = (m[1] - timedelta(hours=3)).strftime('%H:%M')
            color = "#43A047"
            
            detalle_limpio = m[0]
            if "https://maps.google.com" in detalle_limpio:
                partes = detalle_limpio.split(" | GPS:")
                texto_base = partes[0]
                link_mapa = partes[1].strip() if len(partes) > 1 else ""
                detalle_limpio = f"{texto_base} <br><a href='{link_mapa}' target='_blank' style='color:#1976D2; font-size:0.8rem; font-weight:bold;'>📍 Ver ubicación GPS</a>"
            
            if "No Entregado" in m[0] or "Motivo" in m[0]: color = "#D32F2F"
            elif "Pendiente" in m[0]: color = "#F57C00"
            filas_html += f"""
            <div style="background:white; padding:15px; border-radius:8px; margin-bottom:10px; border-left: 5px solid {color}; box-shadow: 0 1px 2px rgba(0,0,0,0.1);">
                <div style="display:flex; justify-content:space-between;">
                    <span style="font-weight:bold; color:#333;">{hora} hs</span>
                    <span style="font-size:0.8rem; color:#888;">{m[2]}</span>
                </div>
                <div style="margin-top:5px; color:#555; font-size:0.9rem;">{detalle_limpio}</div>
            </div>
            """

    html = f"""
    <!DOCTYPE html>
    <html>
    {HTML_HEAD}
    <body>
        <div class="header" style="background:#546E7A;">
            <div style="width:100%; text-align:center;">📜 Historial de Hoy</div>
        </div>
        <div class="container">
            {filas_html}
        </div>
        <div class="bottom-nav">
            <a href="/viajes" class="nav-item">
                <span class="nav-icon">📦</span>Ruta
            </a>
            <a href="/historial" class="nav-item" style="color: #1976D2; font-weight:bold;">
                <span class="nav-icon">📜</span>Historial
            </a>
            <a href="https://wa.me/{NUMERO_BASE_FINAL}" class="nav-item" style="color:#D32F2F;">
                <span class="nav-icon">🆘</span>Base
            </a>
        </div>
    </body>
    </html>
    """
    return render_template_string(html)

@app.route('/gestion/<int:id_op>', methods=['GET', 'POST'])
def gestion(id_op):
    chofer = session.get('chofer')
    if not chofer: return redirect(url_for('index'))
    
    conn = get_db()
    op = None
    if conn:
        try:
            sql = text("SELECT guia_remito, destinatario, domicilio, localidad, celular, tipo_urgencia, tipo_carga, es_contra_reembolso, monto_recaudacion, info_intercambio, proveedor, tipo_servicio FROM operaciones WHERE id = :i")
            op = conn.execute(sql, {"i": id_op}).fetchone()
        except: pass
        finally: conn.close()
        
    if not op: return "Error: Viaje no encontrado"

    tipo_srv = op[11] if len(op) > 11 and op[11] else ""
    es_retiro = "Retiro" in tipo_srv
    
    txt_exito = "✅ CONFIRMAR RETIRO" if es_retiro else "✅ CONFIRMAR ENTREGA"
    txt_falla = "❌ NO RETIRADO" if es_retiro else "❌ NO ENTREGADO"
    prov_txt = op[10] if op[10] else "Desconocido"

    if request.method == 'POST':
        estado_btn = request.form.get('estado')
        
        lat = request.form.get('lat', '')
        lng = request.form.get('lng', '')
        enlace_gps = f"https://maps.google.com/?q={lat},{lng}" if lat and lng else ""
        texto_gps_historial = f" | GPS: {enlace_gps}" if enlace_gps else ""
        
        rutas_fotos = []
        archivos = request.files.getlist('foto')
        for i, archivo in enumerate(archivos):
            if archivo and archivo.filename != '':
                # HORA CORREGIDA PARA NOMBRES DE ARCHIVO
                filename = f"foto_{id_op}_{i}_{int(get_now().timestamp())}.jpg"
                ruta_foto = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                archivo.save(ruta_foto)
                rutas_fotos.append(ruta_foto)
        
        tiene_foto = len(rutas_fotos) > 0
            
        recibe = request.form.get('recibe', '').strip()
        motivo = request.form.get('motivo', '').strip()
        fecha_repro = request.form.get('fecha_repro', '')
        
        if estado_btn == "ENTREGADO":
            if not recibe: 
                flash("❌ ERROR: Escribe quién recibió.", "error")
                return redirect(url_for('gestion', id_op=id_op))
            if "jetpaq" not in op[10].lower() and not tiene_foto:
                flash("📸 ERROR: Faltó la foto (Obligatoria).", "error")
                return redirect(url_for('gestion', id_op=id_op))
                
        if estado_btn in ["Pendiente", "Reprogramado"]:
            if not motivo:
                flash("❌ ERROR: Debes escribir un motivo.", "error")
                return redirect(url_for('gestion', id_op=id_op))

        estado_db = "EN REPARTO"
        detalle_historial = ""
        
        if estado_btn == "ENTREGADO":
            estado_db = "ENTREGADO"
            detalle_historial = f"Recibio: {recibe}"
            if tiene_foto: detalle_historial += f" [{len(rutas_fotos)} FOTO/S]"
            detalle_historial += texto_gps_historial 
            
        elif estado_btn == "Pendiente":
            estado_db = "EN REPARTO" 
            detalle_historial = f"Pendiente en calle. Motivo: {motivo}{texto_gps_historial}"
            
        elif estado_btn == "Reprogramado":
            estado_db = "EN DEPOSITO" 
            if fecha_repro:
                try:
                    f_str = datetime.strptime(fecha_repro, "%Y-%m-%d").strftime("%d/%m/%Y")
                    detalle_historial = f"Reprogramado para el {f_str}. Motivo: {motivo}{texto_gps_historial}"
                except:
                    detalle_historial = f"Reprogramado. Motivo: {motivo}{texto_gps_historial}"
            else:
                detalle_historial = f"Devuelto a depósito. Motivo: {motivo}{texto_gps_historial}"
        
        conn = get_db()
        if conn:
            try:
                # HORA CORREGIDA PARA INSERTAR EN DB
                now_db = get_now()
                if estado_btn == "Reprogramado":
                    if fecha_repro:
                        try:
                            f_dt = datetime.strptime(fecha_repro, "%Y-%m-%d")
                            conn.execute(text("UPDATE operaciones SET estado=:e, chofer_asignado=NULL, fecha_salida=:fs WHERE id=:i"), {"e": estado_db, "fs": f_dt, "i": id_op})
                        except:
                            conn.execute(text("UPDATE operaciones SET estado=:e, chofer_asignado=NULL WHERE id=:i"), {"e": estado_db, "i": id_op})
                    else:
                        conn.execute(text("UPDATE operaciones SET estado=:e, chofer_asignado=NULL WHERE id=:i"), {"e": estado_db, "i": id_op})
                else:
                    conn.execute(text("UPDATE operaciones SET estado=:e, fecha_entrega=:f WHERE id=:i"), {"e": estado_db, "f": now_db, "i": id_op})
                
                conn.execute(text("INSERT INTO historial_movimientos (operacion_id, usuario, accion, detalle, fecha_hora) VALUES (:o, :u, 'APP', :d, :f)"), {"o": id_op, "u": chofer, "d": detalle_historial, "f": now_db})
                conn.commit()
            except Exception as e: print("Error actualizando DB:", e)
            finally: conn.close()
            
        if estado_btn == "ENTREGADO" and tiene_foto:
            flash("✅ Confirmado. Enviando correo y guardando copias...", "success")
            enviar_email(recibe, op[0], rutas_fotos, op[10], link_mapa=enlace_gps)
        elif estado_btn == "ENTREGADO":
            flash("✅ Confirmado correctamente.", "success")
        elif estado_btn == "Pendiente":
            flash("⏱️ Queda en tu ruta para intentar más tarde.", "success")
        elif estado_btn == "Reprogramado":
            flash("🏠 Guía bajada de la ruta y devuelta a depósito.", "success")
            
        return redirect(url_for('lista_viajes'))

    mensajes_html = ""
    mensajes = session.pop('_flashes', [])
    for categoria, mensaje in mensajes:
        clase = "alert-success" if categoria == "success" else "alert-error"
        mensajes_html += f'<div class="alert {clase}">{mensaje}</div>'

    cobranza_html = ""
    if op[7] and op[8]:
        cobranza_html = f"<div style='background:#fff3cd; padding:15px; border-radius:8px; margin-bottom:20px; border-left: 5px solid #ffc107; color:#856404;'>💰 <b>COBRAR: $ {op[8]}</b></div>"
    
    intercambio_html = ""
    if op[9]:
        intercambio_html = f"<div style='background:#e2e3e5; padding:15px; border-radius:8px; margin-bottom:20px; border-left: 5px solid #6c757d; color:#383d41;'>📦 <b>OBS / INTERCAMBIO:</b><br>{op[9]}</div>"

    telefono_limpio = limpiar_telefono_wsp(op[4])
    mensaje_wa = urllib.parse.quote(f"Hola, soy el chofer de JetPaq. Estoy en camino con tu envío (Guía: {op[0]}).")
    link_wa = f"https://wa.me/{telefono_limpio}?text={mensaje_wa}" if telefono_limpio else "#"
    btn_wa_style = "opacity:0.5; pointer-events:none;" if not telefono_limpio else ""

    html = f"""
    <!DOCTYPE html>
    <html>
    {HTML_HEAD}
    <body>
        <div class="header">
            <h2>Gestión de Guía</h2>
        </div>
        <div class="container">
            {mensajes_html}
            <div class="card">
                {cobranza_html}
                {intercambio_html}
                <div style="color:#888; font-size:0.85rem; text-transform:uppercase; letter-spacing:1px; margin-bottom:5px; border-bottom:1px solid #eee; padding-bottom:5px;">
                    🏢 PROVEEDOR: <strong style="color:#1565C0;">{prov_txt}</strong>
                </div>
                <h2 style="margin:10px 0 5px 0; font-size:1.4rem;">{op[1]}</h2>
                <div style="font-size:1.1rem; margin-bottom:15px;">📍 {op[2]} <br> <small style="color:#666;">({op[3]})</small></div>
                <div style="display:grid; grid-template-columns: 1fr 1fr; gap:10px;">
                    <a href="tel:{op[4]}" class="btn btn-grey" style="margin:0; font-size:0.9rem;">📞 Llamar</a>
                    <a href="{link_wa}" class="btn btn-wa" style="margin:0; font-size:0.9rem; {btn_wa_style}" target="_blank">💬 WhatsApp</a>
                </div>
            </div>
            
            <form method="POST" enctype="multipart/form-data">
                
                <details id="acc_exito" class="accordion-card success-accordion" ontoggle="handleAccordion('exito')">
                    <summary>{txt_exito}</summary>
                    <div class="accordion-content">
                        <label>Quien Recibe:</label>
                        <input type="text" name="recibe" placeholder="Nombre y Apellido...">
                        
                        <label style="margin-top: 15px;">Comprobante/s:</label>
                        <div id="fotosList" style="margin-bottom: 10px;"></div>
                        <div id="fotosContainer"></div>
                        <button type="button" id="cameraBtn" class="camera-btn" onclick="agregarFoto()">
                            <span class="camera-icon">📷</span> <span id="btnFotoTexto">TOMAR FOTO</span>
                        </button>
                        
                        <input type="hidden" name="lat" id="lat_entrega">
                        <input type="hidden" name="lng" id="lng_entrega">

                        <button type="submit" name="estado" value="ENTREGADO" class="btn btn-green" style="margin-top:20px;">FINALIZAR</button>
                    </div>
                </details>
                
                <details id="acc_falla" class="accordion-card error-accordion" ontoggle="handleAccordion('falla')">
                    <summary>{txt_falla}</summary>
                    <div class="accordion-content">
                        <label>¿Qué vas a hacer?</label>
                        <select name="estado_select" id="estado_select" onchange="toggleReprogramar()">
                            <option value="Pendiente">Intentar luego en el día (Pendiente)</option>
                            <option value="Reprogramado">Devolver al depósito (Reprogramar)</option>
                        </select>
                        
                        <label>Motivo del problema:</label>
                        <input type="text" name="motivo" placeholder="Ej: No había nadie, mudado, etc.">
                        
                        <div id="div_reprogramar" style="display:none;">
                            <label>Fecha sugerida de visita (Opcional):</label>
                            <input type="date" name="fecha_repro">
                            <p style="font-size: 0.8rem; color: #666; margin-top: 5px;">Al devolver al depósito, la guía se quitará de tu ruta.</p>
                        </div>
                        
                        <input type="hidden" name="lat" id="lat_falla">
                        <input type="hidden" name="lng" id="lng_falla">

                        <button type="button" class="btn btn-outline" style="border:2px solid #D32F2F; color:#D32F2F; margin-top:20px;" onclick="enviarFallo()">GUARDAR ESTADO</button>
                        <input type="hidden" name="estado" id="hidden_estado" value="">
                        <button type="submit" id="submit_falla" style="display:none;"></button>
                    </div>
                </details>

            </form>
            
            <script>
                function enviarFallo() {{
                    document.getElementById('hidden_estado').value = document.getElementById('estado_select').value;
                    document.getElementById('submit_falla').click();
                }}
            </script>
            <br>
            <a href="/viajes" class="btn btn-outline" style="border:1px solid #ccc; color:#666;">← Volver a la lista</a>
            <br><br>
        </div>
    </body>
    </html>
    """
    return render_template_string(html)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)





























