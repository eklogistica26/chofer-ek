from flask import Flask, request, render_template_string, redirect, url_for, session, flash
from sqlalchemy import create_engine, text
from datetime import datetime
import os
import base64
import requests
import urllib.parse
import re

app = Flask(__name__)
app.secret_key = "secreto_super_seguro_choferes_ek"

# --- CONFIGURACIÓN ---
DATABASE_URL = "postgresql://postgres.gwdypvvyjuqzvpbbzchk:Eklogisticasajetpaq@aws-0-us-west-2.pooler.supabase.com:6543/postgres"
BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "") 
EMAIL_REMITENTE = "eklogistica19@gmail.com" 

# !!! IMPORTANTE: PON TU NUMERO AQUI SIN ESPACIOS NI GUIONES !!!
# Ej: 2615555555 (El codigo agrega el 549 solo)
NUMERO_BASE_RAW = "2613672674" 

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
if not os.path.exists(UPLOAD_FOLDER): os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def get_db():
    try: return create_engine(DATABASE_URL, pool_pre_ping=True).connect()
    except: return None

# --- UTILIDADES ---
def limpiar_telefono_wsp(telefono):
    """Deja solo los números y asegura formato internacional 549..."""
    if not telefono: return ""
    nums = "".join(filter(str.isdigit, str(telefono)))
    
    # Si parece un numero local sin codigo de pais (10 digitos), le agregamos 549
    if len(nums) == 10:
        return "549" + nums
    # Si tiene 13 digitos (549...) lo dejamos asi
    return nums

# Preparamos el numero de la base una sola vez
NUMERO_BASE_FINAL = limpiar_telefono_wsp(NUMERO_BASE_RAW)

# --- EMAIL ---
def enviar_email(destinatario, guia, ruta_foto, proveedor):
    if not BREVO_API_KEY: return
    conn = get_db()
    email_prov = None
    if conn:
        try:
            res = conn.execute(text("SELECT email_reportes FROM clientes_principales WHERE nombre = :n"), {"n": proveedor}).fetchone()
            if res: email_prov = res[0]
        except: pass
        finally: conn.close()
    
    if not email_prov: return

    adjuntos = []
    if ruta_foto and os.path.exists(ruta_foto):
        try:
            with open(ruta_foto, "rb") as f:
                content = base64.b64encode(f.read()).decode('utf-8')
                adjuntos.append({"content": content, "name": f"remito_{guia}.jpg"})
        except: pass

    url = "https://api.brevo.com/v3/smtp/email"
    fecha_hora = datetime.now().strftime('%d/%m/%Y %H:%M')
    html_content = f"""
    <html><body>
    <h3>Hola,</h3>
    <p>Se informa la entrega exitosa. <b>Adjuntamos la foto del remito/guía conformado.</b></p>
    <ul>
        <li><b>Fecha:</b> {fecha_hora}</li>
        <li><b>Guía:</b> {guia}</li>
        <li><b>Proveedor:</b> {proveedor}</li>
        <li><b>Recibió:</b> {destinatario}</li>
    </ul>
    <p>Atte.<br><b>Equipo JetPaq / EK</b></p>
    </body></html>
    """
    
    payload = {
        "sender": {"name": "Logistica JetPaq", "email": EMAIL_REMITENTE},
        "to": [{"email": email_prov}],
        "subject": f"ENTREGA REALIZADA - Guía: {guia}",
        "htmlContent": html_content
    }
    if adjuntos: payload["attachment"] = adjuntos
    headers = {"accept": "application/json", "api-key": BREVO_API_KEY, "content-type": "application/json"}
    try: requests.post(url, json=payload, headers=headers)
    except: pass

# --- ESTILOS CSS ---
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
        
        /* BOTONES */
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
        .tag-blue { background: #1976D2; } .tag-orange { background: #F57C00; }
        
        .camera-btn { background-color: #E3F2FD; color: #1565C0; border: 2px solid #1976D2; border-radius: 8px; padding: 12px; text-align: center; cursor: pointer; margin-top: 5px; display: flex; align-items: center; justify-content: center; gap: 10px; font-weight: bold; }
        
        .alert { padding: 12px; margin-bottom: 15px; border-radius: 8px; font-weight: 500; text-align: center; font-size: 0.9rem; }
        .alert-success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .alert-error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }

        /* NAV INFERIOR */
        .bottom-nav { position: fixed; bottom: 0; left: 0; width: 100%; background: white; border-top: 1px solid #eee; display: flex; justify-content: space-around; padding: 12px 0; z-index: 99; box-shadow: 0 -2px 5px rgba(0,0,0,0.05); }
        .nav-item { text-decoration: none; color: #777; text-align: center; font-size: 0.75rem; font-weight: 500; }
        .nav-icon { font-size: 1.4rem; display: block; margin-bottom: 3px; }
        
        /* SVG ICON */
        .truck-icon { width: 80px; height: 80px; margin-bottom: 10px; fill: #1976D2; }
    </style>
    <script>
        function fileSelected(input) {
            var btn = document.getElementById('cameraLabel');
            if (input.files && input.files[0]) {
                btn.style.backgroundColor = '#43A047';
                btn.style.color = 'white';
                btn.style.borderColor = '#43A047';
                btn.innerHTML = '✅ Foto Lista';
            }
        }
    </script>
</head>
"""

# --- RUTAS ---

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
        
    # LOGO CAMION SVG (Profesional)
    svg_truck = """
    <svg class="truck-icon" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <path d="M20,8h-3V4H3C2.45,4,2,4.45,2,5v11h2c0,1.66,1.34,3,3,3s3-1.34,3-3h6c0,1.66,1.34,3,3,3s3-1.34,3-3h2v-5L20,8z M6,13.5 c-0.83,0-1.5-0.67-1.5-1.5s0.67-1.5,1.5-1.5s1.5,0.67,1.5,1.5S6.83,13.5,6,13.5z M19,17c-0.55,0-1-0.45-1-1s0.45-1,1-1s1,0.45,1,1 S19.55,17,19,17z M18,11V8.5h1.75L21,11H18z"/>
    </svg>
    """
        
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
            sql = text("SELECT id, guia_remito, destinatario, domicilio, localidad, bultos, estado, proveedor FROM operaciones WHERE chofer_asignado = :c AND estado IN ('En Reparto', 'Pendiente') ORDER BY id ASC")
            viajes = conn.execute(sql, {"c": chofer}).fetchall()
        except: pass
        finally: conn.close()
        
    cards_html = ""
    if not viajes:
        cards_html = """
        <div class='card' style='text-align:center; padding: 40px; border: 2px dashed #ddd;'>
            <div style="font-size: 2rem;">🎉</div>
            <h3>¡Todo Entregado!</h3>
            <p style="color:#666;">No tienes viajes pendientes.</p>
        </div>
        """
    else:
        for v in viajes:
            color = "tag-blue" if v[6] == "En Reparto" else "tag-orange"
            q = f"{v[3]}, {v[4]}"
            mapa_url = f"https://www.google.com/maps/search/?api=1&query={q}"
            
            cards_html += f"""
            <div class="card">
                <div style="margin-bottom: 10px; overflow: hidden;">
                    <span class="tag {color}">{v[6]}</span>
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
            sql = text("""
                SELECT detalle, fecha_hora, accion 
                FROM historial_movimientos 
                WHERE usuario = :u AND fecha_hora::date = CURRENT_DATE 
                ORDER BY fecha_hora DESC
            """)
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
            if "No Entregado" in m[0] or "Motivo" in m[0]: color = "#D32F2F"
            elif "Pendiente" in m[0]: color = "#F57C00"
            
            filas_html += f"""
            <div style="background:white; padding:15px; border-radius:8px; margin-bottom:10px; border-left: 5px solid {color}; box-shadow: 0 1px 2px rgba(0,0,0,0.1);">
                <div style="display:flex; justify-content:space-between;">
                    <span style="font-weight:bold; color:#333;">{hora} hs</span>
                    <span style="font-size:0.8rem; color:#888;">{m[2]}</span>
                </div>
                <div style="margin-top:5px; color:#555; font-size:0.9rem;">{m[0]}</div>
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
            sql = text("SELECT guia_remito, destinatario, domicilio, localidad, celular, tipo_urgencia, tipo_carga, es_contra_reembolso, monto_recaudacion, info_intercambio, proveedor FROM operaciones WHERE id = :i")
            op = conn.execute(sql, {"i": id_op}).fetchone()
        except: pass
        finally: conn.close()
        
    if not op: return "Error: Viaje no encontrado"

    if request.method == 'POST':
        estado = request.form.get('estado')
        
        ruta_foto = None
        tiene_foto = False
        archivo = request.files.get('foto')
        if archivo and archivo.filename != '':
            filename = f"foto_{id_op}_{int(datetime.now().timestamp())}.jpg"
            ruta_foto = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            archivo.save(ruta_foto)
            tiene_foto = True
            
        recibe = request.form.get('recibe', '')
        motivo = request.form.get('motivo', '')
        
        if estado == "ENTREGADO":
            if not recibe: 
                flash("❌ ERROR: Escribe quién recibió.", "error")
                return redirect(url_for('gestion', id_op=id_op))
            if "jetpaq" not in op[10].lower() and not tiene_foto:
                flash("📸 ERROR: Faltó la foto (Obligatoria).", "error")
                return redirect(url_for('gestion', id_op=id_op))

        detalle = f"Recibio: {recibe}" if estado == "ENTREGADO" else f"Motivo: {motivo}"
        if tiene_foto: detalle += " [CON FOTO]"
        
        conn = get_db()
        if conn:
            try:
                conn.execute(text("UPDATE operaciones SET estado=:e, fecha_entrega=:f WHERE id=:i"), {"e": estado, "f": datetime.now(), "i": id_op})
                conn.execute(text("INSERT INTO historial_movimientos (operacion_id, usuario, accion, detalle, fecha_hora) VALUES (:o, :u, 'APP', :d, :f)"), {"o": id_op, "u": chofer, "d": detalle, "f": datetime.now()})
                conn.commit()
            except: pass
            finally: conn.close()
            
        if estado == "ENTREGADO" and tiene_foto:
            flash("✅ Entregado. Enviando correo con foto...", "success")
            enviar_email(recibe, op[0], ruta_foto, op[10])
        elif estado == "ENTREGADO":
            flash("✅ Entregado correctamente.", "success")
        else:
            flash(f"⚠️ Guardado como: {estado}", "success")
            
        return redirect(url_for('lista_viajes'))

    mensajes_html = ""
    mensajes = session.pop('_flashes', [])
    for categoria, mensaje in mensajes:
        clase = "alert-success" if categoria == "success" else "alert-error"
        mensajes_html += f'<div class="alert {clase}">{mensaje}</div>'

    cobranza_html = ""
    if op[7]:
        cobranza_html = f"<div style='background:#fff3cd; padding:15px; border-radius:8px; margin-bottom:20px; border-left: 5px solid #ffc107; color:#856404;'>💰 <b>COBRAR: $ {op[8]}</b><br><small>{op[9]}</small></div>"

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
            <h2>Gestión de Entrega</h2>
        </div>
        <div class="container">
            {mensajes_html}
            
            <div class="card">
                {cobranza_html}
                <div style="color:#888; font-size:0.8rem; text-transform:uppercase; letter-spacing:1px; margin-bottom:5px;">Destinatario</div>
                <h2 style="margin:0 0 5px 0; font-size:1.4rem;">{op[1]}</h2>
                <div style="font-size:1.1rem; margin-bottom:15px;">📍 {op[2]} <br> <small style="color:#666;">({op[3]})</small></div>
                
                <div style="display:grid; grid-template-columns: 1fr 1fr; gap:10px;">
                    <a href="tel:{op[4]}" class="btn btn-grey" style="margin:0; font-size:0.9rem;">📞 Llamar</a>
                    <a href="{link_wa}" class="btn btn-wa" style="margin:0; font-size:0.9rem; {btn_wa_style}" target="_blank">💬 WhatsApp</a>
                </div>
            </div>
            
            <form method="POST" enctype="multipart/form-data">
                <div class="card" style="border-top: 5px solid #43A047;">
                    <h3 style="margin-top:0; color:#2E7D32;">✅ Confirmar Entrega</h3>
                    
                    <label>Quien Recibe:</label>
                    <input type="text" name="recibe" placeholder="Nombre y Apellido...">
                    
                    <label>Comprobante:</label>
                    <label for="fileInput" id="cameraLabel" class="camera-btn">
                        <span class="camera-icon">📷</span> SUBIR FOTO
                    </label>
                    <input type="file" id="fileInput" name="foto" accept="image/*" capture="environment" style="display:none;" onchange="fileSelected(this)">
                    
                    <button type="submit" name="estado" value="ENTREGADO" class="btn btn-green" style="margin-top:20px;">CONFIRMAR FINALIZADO</button>
                </div>
                
                <div class="card" style="border-top: 5px solid #D32F2F;">
                    <h3 style="margin-top:0; color:#c62828;">❌ No Entregado</h3>
                    <label>Motivo:</label>
                    <input type="text" name="motivo" placeholder="Ej: Dirección incorrecta">
                    
                    <div style="display:flex; gap:10px;">
                        <button type="submit" name="estado" value="Pendiente" class="btn btn-orange" style="flex:1;">PENDIENTE</button>
                        <button type="submit" name="estado" value="Reprogramado" class="btn btn-purple" style="flex:1;">REPROGRAMAR</button>
                    </div>
                </div>
            </form>
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
























