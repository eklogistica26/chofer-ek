import flet as ft
from sqlalchemy import create_engine, text
from datetime import datetime
import os
import urllib.parse
import smtplib
from email.message import EmailMessage

# --- CONFIGURACIÓN DB ---
DATABASE_URL = "postgresql://postgres.gwdypvvyjuqzvpbbzchk:Eklogisticasajetpaq@aws-0-us-west-2.pooler.supabase.com:6543/postgres"

# --- CREDENCIALES EMAIL ---
EMAIL_USER = os.environ.get("EMAIL_USER", "eklogistica19@gmail.com") 
EMAIL_PASS = os.environ.get("EMAIL_PASS", "") 

engine = None
try:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=3600)
except:
    pass

def get_db_connection():
    try:
        if engine: return engine.connect()
    except:
        return None
    return None

def main(page: ft.Page):
    print("🚀 INICIANDO V36 (INTENTO CÁMARA REAL)...")
    
    page.title = "Choferes EK"
    page.bgcolor = "white"
    page.theme_mode = ft.ThemeMode.LIGHT 
    page.scroll = "auto"
    
    state = {
        "id": None, 
        "guia": "", 
        "proveedor": "", 
        "tiene_foto": False,
        "ruta_foto": None
    }

    # ---------------------------------------------------------
    # 1. FUNCIÓN DE EMAIL (CON FOTO ADJUNTA)
    # ---------------------------------------------------------
    def enviar_reporte_email(destinatario_final, guia, ruta_imagen, proveedor_nombre):
        if not EMAIL_PASS:
            print("❌ Falta contraseña de email")
            return

        email_proveedor = None
        conn = get_db_connection()
        if conn:
            try:
                # Buscamos el mail del proveedor
                res = conn.execute(text("SELECT email_reportes FROM clientes_principales WHERE nombre = :n"), {"n": proveedor_nombre}).fetchone()
                if res and res[0]:
                    email_proveedor = res[0]
            except Exception as e:
                print(f"Error DB Email: {e}")
            finally:
                conn.close()

        if not email_proveedor:
            print(f"⚠️ Proveedor {proveedor_nombre} no tiene email cargado.")
            return

        # Armado del correo
        msg = EmailMessage()
        msg['Subject'] = f"ENTREGA REALIZADA - Guía: {guia}"
        msg['From'] = EMAIL_USER
        msg['To'] = email_proveedor
        
        cuerpo = f"""
        Hola,
        
        Se informa la entrega exitosa.
        
        📅 Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}
        📦 Guía: {guia}
        🚛 Proveedor: {proveedor_nombre}
        👤 Recibió: {destinatario_final}
        
        Se adjunta foto del remito.
        
        Atte. EK Logística
        """
        msg.set_content(cuerpo)

        # Adjuntar foto si existe
        if ruta_imagen:
            try:
                with open(ruta_imagen, 'rb') as f:
                    file_data = f.read()
                    file_name = f"remito_{guia}.jpg"
                    msg.add_attachment(file_data, maintype='image', subtype='jpeg', filename=file_name)
            except Exception as e:
                print(f"No se pudo adjuntar foto: {e}")

        # Enviar
        try:
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
                smtp.login(EMAIL_USER, EMAIL_PASS)
                smtp.send_message(msg)
            print(f"✅ Email enviado a {email_proveedor}")
        except Exception as e:
            print(f"❌ Error SMTP: {e}")

    # ---------------------------------------------------------
    # 2. CÁMARA (CONFIGURACIÓN SEGURA)
    # ---------------------------------------------------------
    def on_foto_seleccionada(e: ft.FilePickerResultEvent):
        if e.files:
            path = e.files[0].path
            state["tiene_foto"] = True
            state["ruta_foto"] = path
            
            btn_foto.text = "✅ FOTO CARGADA"
            btn_foto.bgcolor = "green"
            btn_foto.icon = ft.icons.CHECK
            btn_foto.update()
        else:
            print("Selección cancelada")

    # Creamos el FilePicker. 
    # SI ESTO FALLA, ES PORQUE RENDER NO ACTUALIZÓ LA LIBRERÍA FLET.
    file_picker = ft.FilePicker(on_result=on_foto_seleccionada)
    page.overlay.append(file_picker)

    # ---------------------------------------------------------
    # 3. INTERFAZ
    # ---------------------------------------------------------
    
    def abrir_mapa(domicilio, localidad):
        q = urllib.parse.quote(f"{domicilio}, {localidad}")
        page.launch_url(f"https://www.google.com/maps/search/?api=1&query={q}")

    def conectar(e):
        btn_inicio.text = "Cargando..."
        btn_inicio.disabled = True
        page.update()
        conn = get_db_connection()
        if conn:
            try:
                res = conn.execute(text("SELECT nombre FROM choferes ORDER BY nombre")).fetchall()
                dd_chofer.options = [ft.dropdown.Option(r[0]) for r in res]
                ir_a_principal()
            except:
                btn_inicio.text = "Error DB"
                btn_inicio.disabled = False
        else:
            btn_inicio.text = "Error Conexión"
            btn_inicio.disabled = False
        page.update()

    btn_inicio = ft.ElevatedButton("CONECTAR", on_click=conectar, bgcolor="blue", color="white", height=50)
    vista_inicio = ft.Column([ft.Text("🚛", size=50), ft.Text("BIENVENIDO", size=30, weight="bold", color="black"), ft.Container(height=20), btn_inicio], horizontal_alignment="center")

    # --- PANTALLA PRINCIPAL ---
    dd_chofer = ft.Dropdown(label="Tu nombre", bgcolor="#f0f2f5", label_style=ft.TextStyle(color="black"))
    lista_viajes = ft.Column(spacing=10)

    def cargar_ruta(e):
        chofer = dd_chofer.value
        if not chofer: return
        conn = get_db_connection()
        lista_viajes.controls.clear()
        if conn:
            try:
                # Traemos proveedor tambien
                sql = text("SELECT id, guia_remito, destinatario, domicilio, localidad, bultos, estado, proveedor FROM operaciones WHERE chofer_asignado = :c AND estado IN ('En Reparto', 'Pendiente') ORDER BY id ASC")
                rows = conn.execute(sql, {"c": chofer}).fetchall()
                if not rows: lista_viajes.controls.append(ft.Text("✅ Sin viajes pendientes.", color="green"))
                
                for row in rows:
                    id_op, guia, dest, dom, loc, bultos, est, prov = row
                    color_est = "blue" if est == "En Reparto" else "orange"
                    
                    card = ft.Container(
                        bgcolor="white", padding=10, border_radius=8, border=ft.border.all(1, "#ddd"),
                        content=ft.Column([
                            ft.Row([ft.Text(dest[:25], weight="bold", color="black"), ft.Container(content=ft.Text(est[:10], color="white", size=10), bgcolor=color_est, padding=3, border_radius=3)], alignment="spaceBetween"),
                            ft.Row([ft.Text("📍"), ft.Text(f"{dom}", size=12, color="#333", expand=True), ft.ElevatedButton("IR", on_click=lambda _,d=dom,l=loc: abrir_mapa(d,l))]),
                            ft.Text(f"Guía: {guia} | Bultos: {bultos}", size=12, color="black"),
                            ft.ElevatedButton("ENTREGAR / GESTIONAR", bgcolor="blue", color="white", width=280, on_click=lambda _,x=id_op,g=guia,p=prov: ir_a_gestion(x,g,p))
                        ])
                    )
                    lista_viajes.controls.append(card)
            except Exception as ex: lista_viajes.controls.append(ft.Text(f"Error: {ex}", color="red"))
            finally: conn.close()
        page.update()

    btn_buscar = ft.ElevatedButton("VER MIS VIAJES 🔍", on_click=cargar_ruta, bgcolor="green", color="white")

    def ir_a_principal():
        page.clean()
        page.add(ft.Column([ft.Text("MI RUTA", size=18, weight="bold", color="black"), dd_chofer, btn_buscar, ft.Divider(), lista_viajes]))

    # --- PANTALLA GESTION ---
    txt_recibe = ft.TextField(label="Quien recibe", border_color="grey", label_style=ft.TextStyle(color="black"))
    txt_motivo = ft.TextField(label="Motivo (No entregado)", border_color="grey", label_style=ft.TextStyle(color="black"))
    
    # BOTON CAMARA
    btn_foto = ft.ElevatedButton(
        "📷 TOMAR FOTO", 
        bgcolor="grey", color="white", height=45,
        on_click=lambda _: file_picker.pick_files(allow_multiple=False, file_type=ft.FilePickerFileType.IMAGE)
    )

    def guardar(estado):
        id_op = state["id"]
        if not id_op: return
        
        if estado == "ENTREGADO" and not txt_recibe.value:
            txt_recibe.error_text = "Requerido"; txt_recibe.update(); return
        if estado != "ENTREGADO" and not txt_motivo.value:
            txt_motivo.error_text = "Requerido"; txt_motivo.update(); return

        det = f"Recibio: {txt_recibe.value}" if estado == "ENTREGADO" else f"Motivo: {txt_motivo.value}"
        if state["tiene_foto"]: det += " [CON FOTO]"

        conn = get_db_connection()
        if conn:
            try:
                conn.execute(text("UPDATE operaciones SET estado=:e, fecha_entrega=:f WHERE id=:i"), {"e": estado, "f": datetime.now(), "i": id_op})
                conn.execute(text("INSERT INTO historial_movimientos (operacion_id, usuario, accion, detalle, fecha_hora) VALUES (:o, :u, 'APP', :d, :f)"), {"o": id_op, "u": dd_chofer.value, "d": det, "f": datetime.now()})
                conn.commit()
                
                # ENVIO DE CORREO AUTOMATICO
                if estado == "ENTREGADO" and state["tiene_foto"]:
                    page.snack_bar = ft.SnackBar(ft.Text(f"📤 Enviando correo a {state['proveedor']}..."), bgcolor="blue")
                    page.snack_bar.open = True; page.update()
                    enviar_reporte_email(txt_recibe.value, state["guia"], state["ruta_foto"], state["proveedor"])

                ir_a_principal(); cargar_ruta(None)
                page.snack_bar = ft.SnackBar(ft.Text("✅ Guardado"), bgcolor="green"); page.snack_bar.open = True
            except Exception as e:
                page.snack_bar = ft.SnackBar(ft.Text(f"Error: {e}"), bgcolor="red"); page.snack_bar.open = True
            finally: conn.close()
        page.update()

    def ir_a_gestion(id_op, guia, prov):
        state["id"] = id_op; state["guia"] = guia; state["proveedor"] = prov; state["tiene_foto"] = False; state["ruta_foto"] = None
        txt_recibe.value = ""; txt_motivo.value = ""
        btn_foto.text = "📷 TOMAR FOTO"; btn_foto.bgcolor = "grey"; btn_foto.icon = ft.icons.CAMERA_ALT
        
        page.clean()
        page.add(ft.Column([
            ft.Text(f"Guía: {guia}", size=20, weight="bold", color="black"),
            ft.Text(f"Cliente: {prov}", size=16, color="grey"),
            ft.Divider(),
            ft.Text("ENTREGA EXITOSA:", weight="bold", color="black"),
            txt_recibe, btn_foto, ft.Container(height=10),
            ft.ElevatedButton("CONFIRMAR ENTREGA ✅", bgcolor="green", color="white", width=300, height=50, on_click=lambda _: guardar("ENTREGADO")),
            ft.Divider(),
            ft.Text("NO ENTREGADO:", weight="bold", color="black"),
            txt_motivo,
            ft.Row([
                ft.ElevatedButton("PENDIENTE", bgcolor="orange", color="white", expand=True, on_click=lambda _: guardar("Pendiente")),
                ft.ElevatedButton("REPROGRAMAR", bgcolor="purple", color="white", expand=True, on_click=lambda _: guardar("Reprogramado"))
            ]),
            ft.Container(height=20),
            ft.TextButton("VOLVER", on_click=lambda _: ir_a_principal())
        ]))

    page.add(vista_inicio)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    ft.app(target=main, view=ft.AppView.WEB_BROWSER, port=port, host="0.0.0.0")















