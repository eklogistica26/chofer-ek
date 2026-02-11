from flask import Flask, request, render_template_string, redirect, url_for, session
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

    # Preparar adjunto
    adjuntos = []
    if ruta_foto and os.path.exists(ruta_foto):
        try:
            with open(ruta_foto, "rb") as f:
                content = base64.b64encode(f.read()).decode('utf-8')
                adjuntos.append({"content": content, "name": f"remito_{guia}.jpg"})
        except: pass

    url = "https://api.brevo.com/v3/smtp/email"
    payload = {
        "sender": {"name": "Logistica EK", "email": EMAIL_REMITENTE},
        "to": [{"email": email_prov}],
        "subject": f"ENTREGA REALIZADA - Guía: {guia}",
        "htmlContent": f"<html><body><h3>Entrega Exitosa</h3><p>Guía: {guia}<br>Recibió: {destinatario}</p></body></html>"
    }
    if adjuntos: payload["attachment"] = adjuntos
    headers = {"accept": "application/json", "api-key": BREVO_API_KEY, "content-type": "application/json"}
    try: requests.post(url, json=payload, headers=headers)
    except: pass

# --- ESTILOS CSS (Diseño bonito tipo App) ---
CSS = """
<style>
    body { font-family: sans-serif; background: #f4f4f4; margin: 0; padding: 0; }
    .header { background: #2196F3; color: white; padding: 20px; text-align: center; }
    .container { padding: 15px; max-width: 600px; margin: 0 auto; }
    .card { background: white; padding: 15px; margin-bottom: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
    .btn { display: block; width: 100%; padding: 12px; border: none; border-radius: 5px; font-size: 16px; cursor: pointer; text-align: center; text-decoration: none; box-sizing: border-box; margin-top: 10px; }
    .btn-blue { background: #2196F3; color: white; }
    .btn-green { background: #4CAF50; color: white; }
    .btn-red { background: #f44336; color: white; }
    .btn-grey { background: #757575; color: white; }
    input, select { width: 100%; padding: 10px; margin-top: 5px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
    label { font-weight: bold; color: #333; margin-top: 10px; display: block; }
    .tag { padding: 4px 8px; border-radius: 4px; font-size: 12px; color: white; float: right; }
    .tag-blue { background: #2196F3; } .tag-orange { background: #ff9800; }
    .file-upload { border: 2px dashed #ddd; padding: 20px; text-align: center; margin-top: 10px; border-radius: 5px; }
</style>
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
    {CSS}
    <div class="header"><h1>🚛 Choferes EK</h1></div>
    <div class="container">
        <div class="card">
            <h3>Bienvenido</h3>
            <form method="POST">
                <label>Selecciona tu nombre:</label>
                <select name="chofer" required>
                    <option value="">-- Seleccionar --</option>
                    {"".join([f'<option value="{c}">{c}</option>' for c in choferes])}
                </select>
                <button type="submit" class="btn btn-blue">CONECTAR</button>
            </form>
        </div>
    </div>
    """
    return render_template_string(html)

@app.route('/viajes')
def lista_viajes():
    chofer = session.get('chofer')
    if not chofer: return redirect(url_for('index'))
    
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
        cards_html = "<div class='card' style='text-align:center; color:green;'>✅ Sin viajes pendientes</div>"
    else:
        for v in viajes:
            color = "tag-blue" if v[6] == "En Reparto" else "tag-orange"
            # MAPA LINK
            q = f"{v[3]}, {v[4]}"
            mapa_url = f"https://www.google.com/maps/search/?api=1&query={q}"
            
            cards_html += f"""
            <div class="card">
                <span class="tag {color}">{v[6]}</span>
                <h3>{v[2]}</h3>
                <p>📍 {v[3]} ({v[4]})</p>
                <p>📦 Guía: <b>{v[1]}</b> | Bultos: {v[5]}</p>
                <div style="display:flex; gap:5px;">
                    <a href="{mapa_url}" target="_blank" class="btn btn-grey" style="flex:1;">🗺️ MAPA</a>
                    <a href="/gestion/{v[0]}" class="btn btn-blue" style="flex:2;">GESTIONAR</a>
                </div>
            </div>
            """
            
    html = f"""
    {CSS}
    <div class="header">
        <h2>Hola, {chofer}</h2>
        <a href="/" style="color:white; font-size:12px;">(Cambiar)</a>
    </div>
    <div class="container">
        {cards_html}
        <br>
        <a href="/viajes" class="btn btn-green">🔄 ACTUALIZAR</a>
    </div>
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
            if not recibe: return "ERROR: Falta quien recibe"
            # JetPaq rule
            if "jetpaq" not in op[10].lower() and not tiene_foto:
                return "ERROR: FOTO OBLIGATORIA (Salvo JetPaq) - Vuelve atrás e intentalo."

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
                return f"Error DB: {e}"
            finally: conn.close()
            
        # ENVIAR EMAIL
        if estado == "ENTREGADO" and tiene_foto:
            enviar_email(recibe, op[0], ruta_foto, op[10])
            
        return redirect(url_for('lista_viajes'))

    # RENDERIZAR FORMULARIO
    cobranza_html = ""
    if op[7]: # es_contra_reembolso
        cobranza_html = f"<div style='background:#ffebee; padding:10px; border-radius:5px; margin-bottom:10px; border:1px solid red;'>💰 <b>COBRAR: $ {op[8]}</b><br>📝 {op[9]}</div>"

    html = f"""
    {CSS}
    <div class="header"><h2>Gestionar Guía: {op[0]}</h2></div>
    <div class="container">
        <div class="card">
            {cobranza_html}
            <h3>👤 {op[1]}</h3>
            <p>📍 {op[2]} ({op[3]})</p>
            <p>📞 {op[4]}</p>
            <hr>
            <p>⚡ {op[5]} | 📦 {op[6]}</p>
        </div>
        
        <form method="POST" enctype="multipart/form-data">
            <div class="card">
                <h3>✅ Entrega Exitosa</h3>
                <label>Quién recibe:</label>
                <input type="text" name="recibe">
                
                <label>📷 FOTO (Remito/Lugar):</label>
                <input type="file" name="foto" accept="image/*" capture="environment" class="file-upload">
                
                <button type="submit" name="estado" value="ENTREGADO" class="btn btn-green">CONFIRMAR ENTREGA</button>
            </div>
            
            <div class="card">
                <h3>❌ No Entregado</h3>
                <label>Motivo:</label>
                <input type="text" name="motivo">
                <div style="display:flex; gap:5px;">
                    <button type="submit" name="estado" value="Pendiente" class="btn btn-orange" style="flex:1; background:orange;">PENDIENTE</button>
                    <button type="submit" name="estado" value="Reprogramado" class="btn btn-purple" style="flex:1; background:purple; color:white;">REPROGRAMAR</button>
                </div>
            </div>
        </form>
        <a href="/viajes" class="btn btn-grey">VOLVER</a>
    </div>
    """
    return render_template_string(html)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)





















