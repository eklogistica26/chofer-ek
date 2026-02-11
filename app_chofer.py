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

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
if not os.path.exists(UPLOAD_FOLDER): os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def get_db():
    try: return create_engine(DATABASE_URL, pool_pre_ping=True).connect()
    except: return None

# --- EMAIL (TEXTO ACTUALIZADO) ---
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
    
    # HTML ACTUALIZADO CON LA FRASE PEDIDA
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

# --- ESTILOS CSS (BOTON CAMARA MEJORADO) ---
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
        
        .card { background: white; padding: 20px; margin-bottom: 15px; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        
        /* BOTONES */
        .btn { display: block; width: 100%; padding: 14px; border: none; border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer; text-align: center; text-decoration: none; box-sizing: border-box; margin-top: 10px; transition: all 0.2s; }
        .btn:active { transform: scale(0.98); opacity: 0.9; }
        .btn-blue { background: #2196F3; color: white; }
        .btn-green { background: #4CAF50; color: white; }
        .btn-red { background: #f44336; color: white; }
        .btn-orange { background: #ff9800; color: white; }
        .btn-purple { background: #9c27b0; color: white; }
        .btn-grey { background: #9e9e9e; color: white; }
        
        input, select { width: 100%; padding: 12px; margin-top: 8px; border: 1px solid #ddd; border-radius: 8px; font-size: 16px; background: #fff; box-sizing: border-box; }
        label { font-weight: 600; color: #555; margin-top: 15px; display: block; font-size: 0.9rem; }
        
        .tag { padding: 4px 8px; border-radius: 4px; font-size: 0.75rem; color: white; float: right; font-weight: bold; text-transform: uppercase; letter-spacing: 0.5px; }
        .tag-blue { background: #2196F3; } .tag-orange { background: #ff9800; }
        
        /* NUEVO BOTON DE CAMARA ESTILO APP */
        .camera-btn {
            background-color: #e3f2fd;
            color: #1565c0;
            border: 2px solid #2196F3;
            border-radius: 8px;
            padding: 12px;
            text-align: center;
            cursor: pointer;
            margin-top: 5px;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            font-weight: bold;
            transition: all 0.3s;
        }
        .camera-btn:active { background-color: #bbdefb; }
        .camera-icon { font-size: 1.5rem; }
        
        .alert { padding: 12px; margin-bottom: 15px; border-radius: 8px; font-weight: 500; text-align: center; font-size: 0.9rem; }
        .alert-success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .alert-error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
    </style>
    <script>
        function fileSelected(input) {
            var btn = document.getElementById('cameraLabel');
            if (input.files && input.files[0]) {
                btn.style.backgroundColor = '#4CAF50';
                btn.style.color = 'white';
                btn.style.borderColor = '#4CAF50';
                btn.innerHTML = '<span class="camera-icon">✅</span> Foto Cargada';
            }
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
        
    html = f"""
    <!DOCTYPE html>
    <html>
    {HTML_HEAD}
    <body>
        <div class="header"><h1>🚛 Choferes EK</h1></div>
        <div class="container">
            <div class="card" style="text-align: center; padding: 40px 20px;">
                <div style="font-size: 3rem; margin-bottom: 10px;">👋</div>
                <h2 style="margin-bottom: 20px; color: #333;">Iniciar Turno</h2>
                <form method="POST">
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
        cards_html = "<div class='card' style='text-align:center; color:#666; padding: 40px;'><h3>✅ ¡Todo Listo!</h3><p>No tienes entregas pendientes por ahora.</p></div>"
    else:
        for v in viajes:
            color = "tag-blue" if v[6] == "En Reparto" else "tag-orange"
            q = f"{v[3]}, {v[4]}"
            mapa_url = f"https://www.google.com/maps/search/?api=1&query={q}"
            
            cards_html += f"""
            <div class="card">
                <div style="margin-bottom: 10px; overflow: hidden;">
                    <span class="tag {color}">{v[6]}</span>
                    <h3 style="margin: 0; font-size: 1.1rem;">{v[2]}</h3>
                </div>
                <div style="color: #555; font-size: 0.95rem; margin-bottom: 12px; display: flex; align-items: start; gap: 5px;">
                    <span>📍</span> <span>{v[3]} <br> <small style="color:#888;">{v[4]}</small></span>
                </div>
                <div style="background: #f5f5f5; padding: 10px; border-radius: 6px; font-size: 0.85rem; color: #444; margin-bottom: 15px; border-left: 4px solid #ddd;">
                    📦 Guía: <b>{v[1]}</b> &nbsp;|&nbsp; Bultos: {v[5]}
                </div>
                <div style="display:flex; gap:10px;">
                    <a href="{mapa_url}" target="_blank" class="btn btn-grey" style="flex:1; margin-top:0;">🗺️ Mapa</a>
                    <a href="/gestion/{v[0]}" class="btn btn-blue" style="flex:2; margin-top:0;">Gestionar</a>
                </div>
            </div>
            """
            
    html = f"""
    <!DOCTYPE html>
    <html>
    {HTML_HEAD}
    <body>
        <div class="header" style="display:flex; justify-content:space-between; align-items:center;">
            <div style="font-weight:bold;">🚛 {chofer}</div>
            <a href="/" style="color:white; font-size:0.8rem; text-decoration:none; background:rgba(255,255,255,0.2); padding: 4px 10px; border-radius: 20px;">Salir</a>
        </div>
        <div class="container">
            {mensajes_html}
            {cards_html}
            <br>
            <a href="/viajes" class="btn btn-green" style="margin-bottom: 30px;">🔄 ACTUALIZAR LISTA</a>
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
            except Exception as e:
                flash(f"Error Base de Datos: {e}", "error")
                return redirect(url_for('gestion', id_op=id_op))
            finally: conn.close()
            
        if estado == "ENTREGADO" and tiene_foto:
            flash("✅ ¡Excelente! Enviando correo...", "success")
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
                    <div style="background:#f5f5f5; padding:10px; border-radius:8px; text-align:center;">
                        <div style="font-size:0.7rem; color:#888;">GUÍA</div>
                        <div style="font-weight:bold;">{op[0]}</div>
                    </div>
                </div>
            </div>
            
            <form method="POST" enctype="multipart/form-data">
                <div class="card" style="border-top: 5px solid #4CAF50;">
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
                
                <div class="card" style="border-top: 5px solid #f44336;">
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
            <a href="/viajes" class="btn btn-grey" style="background:transparent; color:#666; border:1px solid #ccc;">← Volver a la lista</a>
            <br><br>
        </div>
    </body>
    </html>
    """
    return render_template_string(html)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)























