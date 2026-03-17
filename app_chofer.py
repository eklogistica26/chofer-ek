from flask import Flask, request, render_template_string, redirect, url_for, session, flash
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

# --- CONFIGURACIÓN DE SEGURIDAD (LEE DE RENDER O .ENV) ---
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

# --- MAIL AHORA SOPORTA MÚLTIPLES FOTOS APILADAS ---
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
    
    # ADJUNTAR TODAS LAS FOTOS
    adjuntos = []
    if rutas_fotos:
        for i, ruta in enumerate(rutas_fotos):
            if os.path.exists(ruta):
                try:
                    with open(ruta, "rb") as f:
                        content = base64.b64encode(f.read()).decode('utf-8')
                        nombre_adjunto = f"remito_{guia}.jpg" if len(rutas_fotos) == 1 else f"remito_{guia}_parte{i+1}.jpg"
                        adjuntos.append({"content": content, "name": nombre_adjunto})
                except: pass

    url = "https://api.brevo.com/v3/smtp/email"
    fecha_hora = datetime.now().strftime('%d/%m/%Y %H:%M')
    
    texto_gps = f"<li><b>Ubicación (GPS):</b> <a href='{link_mapa}'>Ver en Google Maps</a></li>" if link_mapa else ""

    html_content = f"""
    <html><body>
    <h3>Hola,</h3>
    <p>Se informa la entrega exitosa. <b>Adjuntamos la foto del remito/guía conformado.</b></p>
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
        input[type="text"], input[type="number"], input[type="date"], select { width: 100%; padding: 12px; margin-top: 8px; border: 1px solid #ddd; border-radius: 8px; font-size: 16px; background: #fff; box-sizing: border-box; }
        label { font-weight: 600; color: #444; margin-top: 15px; display: block; font-size: 0.9rem; }
        .tag { padding: 4px 8px; border-radius: 4px; font-size: 0.75rem; color: white; float: right; font-weight: bold; text-transform: uppercase; letter-spacing: 0.5px; }
        .tag-blue { background: #1976D2; } .tag-purple { background: #7B1FA2; } .tag-orange { background: #F57C00; }
        .camera-btn { background-color: #E3F2FD; color: #1565C0; border: 2px solid #1976D2; border-radius: 8px; padding: 12px; text-align: center; cursor: pointer; margin-top: 10px; width: 100%; display: block; font-weight: bold; }
        .alert { padding: 12px; margin-bottom: 15px; border-radius: 8px; font-weight: 500; text-align: center; font-size: 0.9rem; }
        .alert-success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .alert-error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        .bottom-nav { position: fixed; bottom: 0; left: 0; width: 100%; background: white; border-top: 1px solid #eee; display: flex; justify-content: space-around; padding: 12px 0; z-index: 99; box-shadow: 0 -2px 5px rgba(0,0,0,0.05); }
        .nav-item { text-decoration: none; color: #777; text-align: center; font-size: 0.75rem; font-weight: 500; }
        .nav-icon { font-size: 1.4rem; display: block; margin-bottom: 3px; }
        .truck-icon { width: 80px; height: 80px; margin-bottom: 10px; fill: #1976D2; }
    </style>
</head>
"""

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        chofer_nombre = request.form.get('chofer')
        chofer_dni = request.form.get('dni')
        
        conn = get_db()
        if conn:
            try:
                res = conn.execute(text("SELECT dni FROM choferes WHERE nombre = :n"), {"n": chofer_nombre}).fetchone()
                db_dni = str(res[0]).strip() if res and res[0] else ""
                
                if db_dni == str(chofer_dni).strip():
                    session.permanent = True  
                    session['chofer'] = chofer_nombre
                    return redirect(url_for('lista_viajes'))
                else:
                    flash("❌ DNI incorrecto para este chofer.", "error")
            except Exception as e:
                print("Error validando DNI:", e)
                flash("❌ Error de conexión con el servidor.", "error")
            finally:
                conn.close()
        
        return redirect(url_for('index'))
    
    conn = get_db()
    choferes_data = []
    if conn:
        try:
            res = conn.execute(text("SELECT nombre, sucursal FROM choferes ORDER BY sucursal, nombre")).fetchall()
            choferes_data = [{"nombre": r[0], "sucursal": str(r[1])} for r in res]
        except: pass
        finally: conn.close()
        
    choferes_json = json.dumps(choferes_data)
        
    mensajes_html = ""
    mensajes = session.pop('_flashes', [])
    for categoria, mensaje in mensajes:
        clase = "alert-success" if categoria == "success" else "alert-error"
        mensajes_html += f'<div class="alert {clase}">{mensaje}</div>'
        
    svg_truck = """<svg class="truck-icon" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M20,8h-3V4H3C2.45,4,2,4.45,2,5v11h2c0,1.66,1.34,3,3,3s3-1.34,3-3h6c0,1.66,1.34,3,3,3s3-1.34,3-3h2v-5L20,8z M6,13.5 c-0.83,0-1.5-0.67-1.5-1.5s0.67-1.5,1.5-1.5s1.5,0.67,1.5,1.5S6.83,13.5,6,13.5z M19,17c-0.55,0-1-0.45-1-1s0.45-1,1-1s1,0.45,1,1 S19.55,17,19,17z M18,11V8.5h1.75L21,11H18z"/></svg>"""
        
    html = f"""
    <!DOCTYPE html>
    <html>
    {HTML_HEAD}
    <body style="background:white;">
        <script>
            var choferes = {choferes_json};
            function filtrarChoferes() {{
                var suc = document.getElementById('sucursal_select').value;
                var selectChofer = document.getElementById('chofer_select');
                selectChofer.innerHTML = '<option value="">Selecciona tu nombre...</option>';
                if (!suc) return;
                for (var i = 0; i < choferes.length; i++) {{
                    if (choferes[i].sucursal === suc) {{
                        var opt = document.createElement('option');
                        opt.value = choferes[i].nombre;
                        opt.innerHTML = choferes[i].nombre;
                        selectChofer.appendChild(opt);
                    }}
                }}
            }}
        </script>
        <div class="container" style="display:flex; flex-direction:column; justify-content:center; height:90vh;">
            <div style="text-align: center;">
                {svg_truck}
                <h1 style="color: #1565C0; margin-bottom: 5px;">JetPaq Logística</h1>
                <p style="color: #777; margin-top: 0;">Portal de Choferes</p>
                <br>
                {mensajes_html}
                <form method="POST" style="background: #f9f9f9; padding: 30px; border-radius: 15px; border: 1px solid #eee;">
                    
                    <label style="text-align: left;">1. Sucursal:</label>
                    <select id="sucursal_select" required style="margin-bottom: 15px; padding: 15px;" onchange="filtrarChoferes()">
                        <option value="">Selecciona tu base...</option>
                        <option value="Mendoza">Mendoza</option>
                        <option value="San Juan">San Juan</option>
                    </select>

                    <label style="text-align: left;">2. Conductor:</label>
                    <select name="chofer" id="chofer_select" required style="margin-bottom: 15px; padding: 15px;">
                        <option value="">Primero elige la sucursal...</option>
                    </select>
                    
                    <label style="text-align: left;">3. DNI (Contraseña):</label>
                    <input type="number" inputmode="numeric" pattern="[0-9]*" name="dni" placeholder="Ingresa tu DNI..." required style="margin-bottom: 25px; padding: 15px; letter-spacing: 2px; -webkit-text-security: disc;">
                    
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
            lbl_tipo = "🔄 RETIRO" if es_retiro else "🚚 ENTREGA"
            color_tipo = "tag-purple" if es_retiro else "tag-blue"
            q = f"{v[3]}, {v[4]}"
            mapa_url = f"https://www.google.com/maps/search/?api=1&query={q}"
            
            cards_html += f"""
            <div class="card">
                <div style="margin-bottom: 10px; overflow: hidden;">
                    <span class="tag {color_tipo}">{lbl_tipo}</span>
                    <h3 style="margin: 0; font-size: 1.1rem; color:#333;">{v[2]}</h3>
                </div>
                <div style="color: #555; font-size: 0.95rem; margin-bottom: 12px;">
                    📍 {v[3]} <small>({v[4]})</small>
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

@app.route('/historial')
def historial():
    chofer = session.get('chofer')
    if not chofer: return redirect(url_for('index'))
    
    conn = get_db()
    movimientos = []
    if conn:
        try:
            sql = text("SELECT detalle, fecha_hora, accion FROM historial_movimientos WHERE usuario = :u AND fecha_hora::date = CURRENT_DATE ORDER BY fecha_hora DESC")
            movimientos = conn.execute(sql, {"u": chofer}).fetchall()
        except: pass
        finally: conn.close()
    
    filas_html = ""
    if not movimientos:
        filas_html = "<div style='text-align:center; padding:20px; color:#888;'>No hay movimientos hoy.</div>"
    else:
        for m in movimientos:
            hora = m[1].strftime('%H:%M')
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
    
    lbl_exito = "✅ Retirado Exitosamente" if es_retiro else "✅ Entregado Exitosamente"
    lbl_pend = "⏱️ No Retirado (Intentar luego)" if es_retiro else "⏱️ No Entregado (Intentar luego)"
    lbl_repr = "🏠 No Retirado (Devolver)" if es_retiro else "🏠 No Entregado (Devolver a depósito)"

    if request.method == 'POST':
        estado_btn = request.form.get('estado_select')
        
        lat = request.form.get('lat', '')
        lng = request.form.get('lng', '')
        enlace_gps = f"https://maps.google.com/?q={lat},{lng}" if lat and lng else ""
        texto_gps_historial = f" | GPS: {enlace_gps}" if enlace_gps else ""
        
        # PROCESAR MÚLTIPLES FOTOS DINÁMICAS
        rutas_fotos = []
        tiene_foto = False
        archivos = request.files.getlist('fotos')
        for i, archivo in enumerate(archivos):
            if archivo and archivo.filename != '':
                filename = f"foto_{id_op}_{i}_{int(datetime.now().timestamp())}.jpg"
                ruta = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                archivo.save(ruta)
                rutas_fotos.append(ruta)
                tiene_foto = True
            
        recibe = request.form.get('recibe', '').strip()
        motivo = request.form.get('motivo', '').strip()
        fecha_repro = request.form.get('fecha_repro', '')
        
        if estado_btn == "ENTREGADO":
            if not recibe: 
                flash("❌ ERROR: Escribe quién recibió.", "error")
                return redirect(url_for('gestion', id_op=id_op))
            
            # 🔥 ACÁ ESTÁ LA REGLA DE JETPAQ INTACTA 🔥
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
            if tiene_foto: detalle_historial += f" [CON {len(rutas_fotos)} FOTO/S]"
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
                    conn.execute(text("UPDATE operaciones SET estado=:e, fecha_entrega=:f WHERE id=:i"), {"e": estado_db, "f": datetime.now(), "i": id_op})
                
                conn.execute(text("INSERT INTO historial_movimientos (operacion_id, usuario, accion, detalle, fecha_hora) VALUES (:o, :u, 'APP', :d, :f)"), {"o": id_op, "u": chofer, "d": detalle_historial, "f": datetime.now()})
                conn.commit()
            except Exception as e: print("Error actualizando DB:", e)
            finally: conn.close()
            
        if estado_btn == "ENTREGADO" and tiene_foto:
            flash(f"✅ Confirmado. Enviando {len(rutas_fotos)} foto/s y correo...", "success")
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
                <div style="color:#888; font-size:0.8rem; text-transform:uppercase; letter-spacing:1px; margin-bottom:5px;">Destinatario</div>
                <h2 style="margin:0 0 5px 0; font-size:1.4rem;">{op[1]}</h2>
                <div style="font-size:1.1rem; margin-bottom:15px;">📍 {op[2]} <br> <small style="color:#666;">({op[3]})</small></div>
                <div style="display:grid; grid-template-columns: 1fr 1fr; gap:10px;">
                    <a href="tel:{op[4]}" class="btn btn-grey" style="margin:0; font-size:0.9rem;">📞 Llamar</a>
                    <a href="{link_wa}" class="btn btn-wa" style="margin:0; font-size:0.9rem; {btn_wa_style}" target="_blank">💬 WhatsApp</a>
                </div>
            </div>
            
            <form method="POST" enctype="multipart/form-data" id="gestionForm">
                <div class="card" style="border-top: 5px solid #1565C0;">
                    
                    <label style="margin-top:0; font-size: 1.1rem;">¿Qué deseas hacer con la guía?</label>
                    <select name="estado_select" id="estado_select" onchange="cambiarEstado()" style="width: 100%; padding: 12px; margin-top: 8px; border: 2px solid #1565c0; border-radius: 8px; font-size: 16px; font-weight: bold; color: #1565c0; background: #f0f7ff;">
                        <option value="">-- Seleccionar Estado --</option>
                        <option value="ENTREGADO">{lbl_exito}</option>
                        <option value="Pendiente">{lbl_pend}</option>
                        <option value="Reprogramado">{lbl_repr}</option>
                    </select>

                    <div id="panel_entregado" style="display:none; margin-top: 15px; padding-top: 15px; border-top: 1px solid #ddd;">
                        <label>Quien Recibe:</label>
                        <input type="text" name="recibe" placeholder="Nombre y Apellido...">
                        
                        <label style="margin-top:20px;">Fotos del Comprobante / Domicilio:</label>
                        <div id="contenedor_fotos"></div>
                        <button type="button" onclick="agregarFoto()" class="camera-btn">➕ AGREGAR OTRA FOTO</button>
                    </div>
                    
                    <div id="panel_falla" style="display:none; margin-top: 15px; padding-top: 15px; border-top: 1px solid #ddd;">
                        <label>Motivo del problema:</label>
                        <input type="text" name="motivo" placeholder="Ej: No había nadie, dirección incorrecta...">
                        
                        <div id="div_reprogramar" style="display:none;">
                            <label>Fecha sugerida de visita (Opcional):</label>
                            <input type="date" name="fecha_repro">
                            <p style="font-size: 0.8rem; color: #666; margin-top: 5px;">Al devolver al depósito, la guía saldrá de tu ruta hoy.</p>
                        </div>
                    </div>
                    
                    <input type="hidden" name="lat" id="lat_gps">
                    <input type="hidden" name="lng" id="lng_gps">

                    <button type="button" id="btn_guardar" class="btn btn-blue" style="display:none; margin-top:20px;" onclick="validarYEnviar()">GUARDAR GESTIÓN</button>
                </div>
            </form>
            
            <br>
            <a href="/viajes" class="btn btn-outline" style="border:1px solid #ccc; color:#666;">← Volver a la lista</a>
            <br><br>
        </div>

        <script>
            let fotoCount = 0;
            
            function agregarFoto() {{
                fotoCount++;
                var container = document.getElementById("contenedor_fotos");
                var div = document.createElement("div");
                div.style.marginBottom = "10px";
                div.innerHTML = '<input type="file" name="fotos" accept="image/*" capture="environment" style="padding: 10px; border: 2px dashed #1976D2; background: #e3f2fd; width: 100%; border-radius: 8px;">';
                container.appendChild(div);
            }}

            function cambiarEstado() {{
                var estado = document.getElementById("estado_select").value;
                var p_ent = document.getElementById("panel_entregado");
                var p_falla = document.getElementById("panel_falla");
                var d_repro = document.getElementById("div_reprogramar");
                var btn = document.getElementById("btn_guardar");

                p_ent.style.display = "none";
                p_falla.style.display = "none";
                d_repro.style.display = "none";
                btn.style.display = "none";

                if (estado === "ENTREGADO") {{
                    p_ent.style.display = "block";
                    btn.style.display = "block";
                    btn.className = "btn btn-green";
                    btn.innerHTML = "CONFIRMAR ENTREGA";
                    if(fotoCount === 0) agregarFoto(); // Auto-agrega la primera foto
                }} else if (estado === "Pendiente") {{
                    p_falla.style.display = "block";
                    btn.style.display = "block";
                    btn.className = "btn btn-orange";
                    btn.innerHTML = "GUARDAR COMO PENDIENTE";
                }} else if (estado === "Reprogramado") {{
                    p_falla.style.display = "block";
                    d_repro.style.display = "block";
                    btn.style.display = "block";
                    btn.className = "btn btn-purple";
                    btn.innerHTML = "DEVOLVER A DEPÓSITO";
                }}
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