from flask import Flask, request, render_template_string, redirect, url_for, session, flash
from sqlalchemy import create_engine, text
from datetime import datetime
import os
import base64
import requests

app = Flask(__name__)
app.secret_key = "secreto_super_seguro_choferes_ek"

# --- CONFIGURACIÓN DB Y EMAIL ---
DATABASE_URL = "postgresql://postgres.gwdypvvyjuqzvpbbzchk:Eklogisticasajetpaq@aws-0-us-west-2.pooler.supabase.com:6543/postgres"
BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "") 
EMAIL_REMITENTE = "eklogistica19@gmail.com" 

# Configurar carpeta de subida
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- DB CONNECTION ---
def get_db():
    try:
        engine = create_engine(DATABASE_URL, pool_pre_ping=True)
        return engine.connect()
    except:
        return None

# --- EMAIL (DISEÑO "CANCHERO" RECUPERADO) ---
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

    # Preparar adjunto
    adjuntos = []
    if ruta_foto and os.path.exists(ruta_foto):
        try:
            with open(ruta_foto, "rb") as f:
                content = base64.b64encode(f.read()).decode('utf-8')
                adjuntos.append({"content": content, "name": f"remito_{guia}.jpg"})
        except: pass

    url = "https://api.brevo.com/v3/smtp/email"
    
    # HTML FORMATO FLET (RECUPERADO)
    fecha_hora = datetime.now().strftime('%d/%m/%Y %H:%M')
    html_content = f"""
    <html><body>
    <h3>Hola,</h3>
    <p>Se informa la entrega exitosa.</p>
    <ul>
        <li><b>Fecha:</b> {fecha_hora}</li>
        <li><b>Guía:</b> {guia}</li>
        <li><b>Proveedor:</b> {proveedor}</li>
        <li><b>Recibió:</b> {destinatario}</li>
    </ul>
    <p>Atte.<br><b>Equipo EK Logística</b></p>
    </body></html>
    """
    
    payload = {
        "sender": {"name": "Logistica EK", "email": EMAIL_REMITENTE},
        "to": [{"email": email_prov}],
        "subject": f"ENTREGA REALIZADA - Guía: {guia}",
        "htmlContent": html_content
    }
    if adjuntos: payload["attachment"] = adjuntos
    headers = {"accept": "application/json", "api-key": BREVO_API_KEY, "content-type": "application/json"}
    try: requests.post(url, json=payload, headers=headers)
    except: pass

# --- ESTILOS CSS (DISEÑO MÓVIL OPTIMIZADO) ---
# Agregamos viewport meta tag para que se vea bien en celular
HTML_HEAD = """
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Choferes EK</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #f0f2f5; margin: 0; padding: 0; font-size: 16px; }
        .header { background: #2196F3; color: white; padding: 15px; text-align: center; position: sticky; top: 0; z-index: 100; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .header h2 { margin: 0; font-size: 1.2rem; }
        .container { padding: 15px; max-width: 600px; margin: 0 auto; }
        
        /* TARJETAS */
        .card { background: white; padding: 20px; margin-bottom: 15px; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        
        /* BOTONES GRANDES */
        .btn { display: block; width: 100%; padding: 15px; border: none; border-radius: 8px; font-size: 16px; font-weight: bold; cursor: pointer; text-align: center; text-decoration: none; box-sizing: border-box; margin-top: 10px; transition: opacity 0.2s; }
        .btn:active { opacity: 0.8; }
        .btn-blue { background: #2196F3; color: white; }
        .btn-green { background: #4CAF50; color: white; }
        .btn-red { background: #f44336; color: white; }
        .btn-orange { background: #ff9800; color: white; }
        .btn-purple { background: #9c27b0; color: white; }
        .btn-grey { background: #757575; color: white; }
        
        /* INPUTS MEJORADOS */
        input, select { width: 100%; padding: 12px; margin-top: 8px; border: 1px solid #ccc; border-radius: 8px; font-size: 16px; box-sizing: border-box; background: #fff; }
        label { font-weight: 600; color: #444; margin-top: 15px; display: block; }
        
        /* ETIQUETAS */
        .tag { padding: 4px 8px; border-radius: 4px; font-size: 0.85rem; color: white; float: right; font-weight: bold; }
        .tag-blue { background: #2196F3; } .tag-orange { background: #ff9800; }
        
        /* AREA DE CARGA DE FOTO */
        .file-upload { border: 2px dashed #bbb; padding: 30px; text-align: center; margin-top: 10px; border-radius: 8px; background: #fafafa; cursor: pointer; }
        
        /* MENSAJES DE ALERTA */
        .alert { padding: 15px; margin-bottom: 15px; border-radius: 8px; font-weight: bold; text-align: center; animation: fadeIn 0.5s; }
        .alert-success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .alert-error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        
        @keyframes fadeIn { from { opacity: 0; transform: translateY(-10px); } to { opacity: 1; transform: translateY(0); } }
    </style>
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
        
    html = f"""
    <!DOCTYPE html>
    <html>
    {HTML_HEAD}
    <body>
        <div class="header"><h1>🚛 Choferes EK</h1></div>
        <div class="container">
            <div class="card" style="text-align: center;">
                <h2 style="margin-bottom: 20px;">Iniciar Turno</h2>
                <form method="POST">
                    <label style="text-align: left;">Selecciona tu nombre:</label>
                    <select name="chofer" required style="margin-bottom: 20px;">
                        <option value="">-- Seleccionar --</option>
                        {"".join([f'<option value="{c}">{c}</option>' for c in choferes])}
                    </select>
                    <button type="submit" class="btn btn-blue">CONECTAR</button>
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
    
    # MENSAJES FLASH (ALERTA DE ÉXITO)
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
        cards_html = "<div class='card' style='text-align:center; color:green;'>✅ <b>¡Todo entregado!</b><br>No tienes viajes pendientes.</div>"
    else:
        for v in viajes:
            color = "tag-blue" if v[6] == "En Reparto" else "tag-orange"
            q = f"{v[3]}, {v[4]}"
            mapa_url = f"https://www.google.com/maps/search/?api=1&query={q}"
            
            cards_html += f"""
            <div class="card">
                <span class="tag {color}">{v[6]}</span>
                <h3 style="margin: 0 0 10px 0;">{v[2]}</h3>
                <div style="color: #666; font-size: 0.9rem; margin-bottom: 10px;">
                    📍 {v[3]} <br> ({v[4]})
                </div>
                <div style="background: #f9f9f9; padding: 8px; border-radius: 5px; font-size: 0.9rem; margin-bottom: 15px;">
                    📦 Guía: <b>{v[1]}</b> | Bultos: {v[5]}
                </div>
                <div style="display:flex; gap:10px;">
                    <a href="{mapa_url}" target="_blank" class="btn btn-grey" style="flex:1;">🗺️ MAPA</a>
                    <a href="/gestion/{v[0]}" class="btn btn-blue" style="flex:2;">GESTIONAR</a>
                </div>
            </div>
            """
            
    html = f"""
    <!DOCTYPE html>
    <html>
    {HTML_HEAD}
    <body>
        <div class="header">
            <h2>Hola, {chofer}</h2>
            <a href="/" style="color:white; font-size:0.8rem; text-decoration:underline;">(Salir)</a>
        </div>
        <div class="container">
            {mensajes_html}
            {cards_html}
            <br>
            <a href="/viajes" class="btn btn-green">🔄 ACTUALIZAR LISTA</a>
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
        
        # PROCESAR SUBIDA DE FOTO
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
        
        # Validaciones
        if estado == "ENTREGADO":
            if not recibe: 
                flash("❌ ERROR: Debes indicar quién recibe.", "error")
                return redirect(url_for('gestion', id_op=id_op))
            # JetPaq rule
            if "jetpaq" not in op[10].lower() and not tiene_foto:
                flash("⚠️ ERROR: FOTO OBLIGATORIA (Salvo JetPaq).", "error")
                return redirect(url_for('gestion', id_op=id_op))

        detalle = f"Recibio: {recibe}" if estado == "ENTREGADO" else f"Motivo: {motivo}"
        if tiene_foto: detalle += " [CON FOTO]"
        
        # GUARDAR DB
        conn = get_db()
        if conn:
            try:
                conn.execute(text("UPDATE operaciones SET estado=:e, fecha_entrega=:f WHERE id=:i"), {"e": estado, "f": datetime.now(), "i": id_op})
                conn.execute(text("INSERT INTO historial_movimientos (operacion_id, usuario, accion, detalle, fecha_hora) VALUES (:o, :u, 'APP', :d, :f)"), {"o": id_op, "u": chofer, "d": detalle, "f": datetime.now()})
                conn.commit()
            except Exception as e:
                flash(f"Error Base de Datos: {e}", "error")
                return redirect(url_for('gestion', id_op=id_op))
            finally: conn.close()
            
        # ENVIAR EMAIL
        if estado == "ENTREGADO" and tiene_foto:
            flash("✅ Entregado. Enviando correo con foto...", "success")
            enviar_email(recibe, op[0], ruta_foto, op[10])
        elif estado == "ENTREGADO":
            flash("✅ Entregado correctamente.", "success")
        else:
            flash(f"⚠️ Marcado como: {estado}", "success")
            
        return redirect(url_for('lista_viajes'))

    # MENSAJES FLASH
    mensajes_html = ""
    mensajes = session.pop('_flashes', [])
    for categoria, mensaje in mensajes:
        clase = "alert-success" if categoria == "success" else "alert-error"
        mensajes_html += f'<div class="alert {clase}">{mensaje}</div>'

    # INFO COBRANZA
    cobranza_html = ""
    if op[7]: # es_contra_reembolso
        cobranza_html = f"<div style='background:#ffebee; padding:15px; border-radius:8px; margin-bottom:20px; border:2px solid #f44336; color:#d32f2f;'>💰 <b>COBRAR: $ {op[8]}</b><br><small>{op[9]}</small></div>"

    html = f"""
    <!DOCTYPE html>
    <html>
    {HTML_HEAD}
    <body>
        <div class="header">
            <h2>Gestión: {op[0]}</h2>
        </div>
        <div class="container">
            {mensajes_html}
            
            <div class="card">
                {cobranza_html}
                <h2 style="margin-top:0;">👤 {op[1]}</h2>
                <p>📍 <a href="https://www.google.com/maps/search/?api=1&query={op[2]}, {op[3]}" target="_blank" style="color:#2196F3; font-weight:bold; text-decoration:none;">{op[2]} ({op[3]})</a></p>
                <p>📞 <a href="tel:{op[4]}" style="color:#2196F3; font-weight:bold; text-decoration:none;">{op[4]}</a></p>
                <hr style="border:0; border-top:1px solid #eee; margin:15px 0;">
                <p>⚡ Urgencia: <b>{op[5]}</b></p> 
                <p>📦 Carga: <b>{op[6]}</b></p>
            </div>
            
            <form method="POST" enctype="multipart/form-data">
                <div class="card">
                    <h3 style="color:#4CAF50;">✅ Entrega Exitosa</h3>
                    <label>Quién recibe:</label>
                    <input type="text" name="recibe" placeholder="Nombre y Apellido">
                    
                    <label>📷 FOTO (Remito/Lugar):</label>
                    <div class="file-upload" onclick="document.getElementById('fileInput').click();">
                        <span style="font-size:2rem;">📸</span><br>
                        Tocar para abrir cámara o galería
                    </div>
                    <input type="file" id="fileInput" name="foto" accept="image/*" capture="environment" style="display:none;" onchange="alert('✅ Foto seleccionada: ' + this.files[0].name)">
                    
                    <button type="submit" name="estado" value="ENTREGADO" class="btn btn-green">CONFIRMAR ENTREGA</button>
                </div>
                
                <div class="card">
                    <h3 style="color:#f44336;">❌ No Entregado</h3>
                    <label>Motivo:</label>
                    <input type="text" name="motivo" placeholder="Ej: No estaba, Dir. incorrecta">
                    <div style="display:flex; gap:10px;">
                        <button type="submit" name="estado" value="Pendiente" class="btn btn-orange" style="flex:1;">PENDIENTE</button>
                        <button type="submit" name="estado" value="Reprogramado" class="btn btn-purple" style="flex:1;">REPROGRAMAR</button>
                    </div>
                </div>
            </form>
            <br>
            <a href="/viajes" class="btn btn-grey">VOLVER A LA LISTA</a>
        </div>
    </body>
    </html>
    """
    return render_template_string(html)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)






















