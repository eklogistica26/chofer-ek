import flet as ft
from sqlalchemy import create_engine, text
from datetime import datetime
import os
import urllib.parse
import smtplib
from email.message import EmailMessage
import mimetypes

# --- CONFIGURACIÓN DB ---
DATABASE_URL = "postgresql://postgres.gwdypvvyjuqzvpbbzchk:Eklogisticasajetpaq@aws-0-us-west-2.pooler.supabase.com:6543/postgres"

# --- CREDENCIALES EMAIL (Las toma de Render) ---
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
    print("🚀 INICIANDO V33 (FIX CAMARA + EMAIL)...")
    
    page.title = "Choferes EK"
    page.bgcolor = "white"
    page.theme_mode = ft.ThemeMode.LIGHT 
    page.scroll = "auto"
    
    # Estado global de la app
    state = {
        "id": None, 
        "guia": "", 
        "proveedor": "", 
        "tiene_foto": False,
        "ruta_foto": None
    }

    # ---------------------------------------------------------
    # 1. FUNCIÓN DE EMAIL (EL ROBOT POSTAL) 📧
    # ---------------------------------------------------------
    def enviar_reporte_email(destinatario_final, guia, ruta_imagen, proveedor_nombre):
        if not EMAIL_PASS:
            print("❌ No hay contraseña de email configurada.")
            return

        # 1. Buscamos el email del proveedor en la base de datos
        email_proveedor = None
        conn = get_db_connection()
        if conn:
            try:
                # Busca el email en la tabla que creamos en escritorio
                res = conn.execute(text("SELECT email_reportes FROM clientes_principales WHERE nombre = :n"), {"n": proveedor_nombre}).fetchone()
                if res and res[0]:
                    email_proveedor = res[0]
            except Exception as e:
                print(f"Error buscando email proveedor: {e}")
            finally:
                conn.close()

        if not email_proveedor:
            print(f"⚠️ El proveedor {proveedor_nombre} no tiene email configurado. No se envía correo.")
            return

        # 2. Armamos el correo
        msg = EmailMessage()
        msg['Subject'] = f"ENTREGA REALIZADA - Guía: {guia}"
        msg['From'] = EMAIL_USER
        msg['To'] = email_proveedor
        
        cuerpo = f"""
        Hola,
        
        Se informa la entrega exitosa de la carga.
        
        📅 Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}
        📦 Guía/Remito: {guia}
        🚛 Proveedor: {proveedor_nombre}
        👤 Recibió: {destinatario_final}
        
        Adjuntamos la foto del remito conformado.
        
        Atte.
        Equipo EK Logística
        """
        msg.set_content(cuerpo)

        # 3. Adjuntamos la foto
        if ruta_imagen and os.path.exists(ruta_imagen):
            with open(ruta_imagen, 'rb') as f:
                file_data = f.read()
                file_name = f"remito_{guia}.jpg"
                msg.add_attachment(file_data, maintype='image', subtype='jpeg', filename=file_name)

        # 4. Enviamos
        try:
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
                smtp.login(EMAIL_USER, EMAIL_PASS)
                smtp.send_message(msg)
            print(f"✅ Correo enviado exitosamente a {email_proveedor}")
        except Exception as e:
            print(f"❌ Error enviando correo: {e}")

    # ---------------------------------------------------------
    # 2. CÁMARA REAL (FILEPICKER) 📷
    # ---------------------------------------------------------
    
    # CORRECCIÓN AQUÍ: Quitamos ": ft.FilePickerResultEvent" para que no falle nunca más
    def on_foto_seleccionada(e):
        if e.files:
            file_path = e.files[0].path
            state["tiene_foto"] = True
            state["ruta_foto"] = file_path 
            
            btn_foto.text = "✅ FOTO LISTA"
            btn_foto.bgcolor = "green"
            btn_foto.update()
        else:
            print("Foto cancelada")

    file_picker = ft.FilePicker(on_result=on_foto_seleccionada)
    page.overlay.append(file_picker)

    # ---------------------------------------------------------
    # 3. FUNCIONES DE PANTALLA
    # ---------------------------------------------------------
    def abrir_mapa(domicilio, localidad):
        direccion_full = f"{domicilio}, {localidad}"
        query = urllib.parse.quote(direccion_full)
        url = f"https://www.google.com/maps/search/?api=1&query={query}"
        page.launch_url(url)

    def conectar(e):
        btn_inicio.text = "Cargando..."
        btn_inicio.disabled = True
        page.update()
        
        conn = get_db_connection()
        if conn:
            try:
                res = conn.execute(text("SELECT nombre FROM choferes ORDER BY nombre")).fetchall()
                dd_chofer.options = []
                for r in res:
                    dd_chofer.options.append(ft.dropdown.Option(r[0]))
                
                ir_a_principal()
            except Exception as ex:
                btn_inicio.text = f"Error: {ex}"
                btn_inicio.disabled = False
        else:
            btn_inicio.text = "Error de Conexión DB"
            btn_inicio.disabled = False
        page.update()

    btn_inicio = ft.ElevatedButton("CONECTAR", on_click=conectar, bgcolor="blue", color="white", height=50)
    
    vista_inicio = ft.Column(
        [
            ft.Text("🚛", size=50),
            ft.Text("BIENVENIDO", size=30, color="black", weight="bold"),
            ft.Container(height=20),
            btn_inicio
        ],
        horizontal_alignment="center" 
    )

    # ---------------------------------------------------------
    # PANTALLA LISTA
    # ---------------------------------------------------------
    dd_chofer = ft.Dropdown(label="Selecciona tu nombre", bgcolor="#f0f2f5", label_style=ft.TextStyle(color="black"))
    lista_viajes = ft.Column(spacing=5)

    def cargar_ruta(e):
        chofer = dd_chofer.value
        if not chofer: return
        
        lista_viajes.controls.clear()
        lista_viajes.controls.append(ft.Text(f"🔎 Buscando para: {chofer}...", color="blue"))
        page.update()
        
        conn = get_db_connection()
        lista_viajes.controls.clear()
        
        if conn:
            try:
                sql = text("""
                    SELECT id, guia_remito, destinatario, domicilio, localidad, bultos, estado, proveedor 
                    FROM operaciones 
                    WHERE chofer_asignado = :c AND estado IN ('En Reparto', 'Pendiente')
                    ORDER BY id ASC
                """)
                rows = conn.execute(sql, {"c": chofer}).fetchall()
                
                if not rows:
                    lista_viajes.controls.append(ft.Text("✅ No tienes viajes pendientes.", color="green"))
                
                for row in rows:
                    id_op, guia, dest, dom, loc, bultos, estado, prov = row
                    
                    color_est = "blue" if estado == "En Reparto" else "orange"

                    tarjeta = ft.Container(
                        bgcolor="white",
                        padding=10, 
                        border=ft.border.all(1, "#dddddd"),
                        border_radius=8,
                        content=ft.Column([
                            ft.Row([
                                ft.Text(dest[:25], weight="bold", size=14, color="black"),
                                ft.Container(content=ft.Text(estado[:10], color="white", size=10), bgcolor=color_est, padding=3, border_radius=3)
                            ], alignment="spaceBetween"),
                            
                            ft.Row([
                                ft.Text("📍", size=20),
                                ft.Text(f"{dom}", size=12, color="#333333", expand=True),
                                ft.ElevatedButton("🗺️ IR", bgcolor="#e3f2fd", color="blue", on_click=lambda _,d=dom,l=loc: abrir_mapa(d,l))
                            ]),
                            
                            ft.Text(f"Guía: {guia} | Bultos: {bultos}", size=11, color="black"),
                            ft.Text(f"Cliente: {prov}", size=11, color="grey", weight="bold"),
                            
                            ft.Container(height=5),
                            ft.ElevatedButton(
                                "GESTIONAR ENTREGA", 
                                bgcolor="blue", color="white", 
                                height=40,
                                width=280,
                                on_click=lambda _,x=id_op,g=guia,p=prov: ir_a_gestion(x,g,p)
                            )
                        ], spacing=5)
                    )
                    lista_viajes.controls.append(tarjeta)
            except Exception as ex:
                lista_viajes.controls.append(ft.Text(f"Error: {ex}", color="red"))
            finally:
                conn.close()
        
        page.update()

    btn_buscar = ft.ElevatedButton("VER MIS VIAJES 🔍", on_click=cargar_ruta, bgcolor="green", color="white", width=200)

    def ir_a_principal():
        page.clean()
        page.add(
            ft.Column([
                ft.Text("MI RUTA", size=18, weight="bold", color="black"),
                dd_chofer,
                btn_buscar, 
                ft.Divider(),
                lista_viajes
            ])
        )

    # ---------------------------------------------------------
    # PANTALLA GESTION
    # ---------------------------------------------------------
    txt_recibe = ft.TextField(label="Quien recibe", text_size=14, border_color="grey", label_style=ft.TextStyle(color="black"))
    txt_motivo = ft.TextField(label="Motivo (Pendiente/Reprog)", text_size=14, border_color="grey", label_style=ft.TextStyle(color="black"))
    
    # Boton camara que llama al file_picker
    btn_foto = ft.ElevatedButton(
        "📷 FOTO REMITO", 
        bgcolor="grey", color="white", height=45,
        on_click=lambda _: file_picker.pick_files(allow_multiple=False, file_type=ft.FilePickerFileType.IMAGE)
    )

    def guardar(estado_final):
        id_op = state["id"]
        if not id_op: return
        
        # Validaciones
        if estado_final == "ENTREGADO" and not txt_recibe.value: 
            txt_recibe.error_text = "Requerido"
            txt_recibe.update()
            return
        
        if (estado_final == "Pendiente" or estado_final == "Reprogramado") and not txt_motivo.value:
            txt_motivo.error_text = "Escribe el motivo"
            txt_motivo.update()
            return

        det = ""
        if estado_final == "ENTREGADO":
            det = f"Recibio: {txt_recibe.value}"
        else:
            det = f"Motivo: {txt_motivo.value}"
            
        if state["tiene_foto"]:
            det += " [CON FOTO]"
        
        # 1. ACTUALIZAR BASE DE DATOS
        conn = get_db_connection()
        if conn:
            try:
                conn.execute(text("UPDATE operaciones SET estado=:e, fecha_entrega=:f WHERE id=:i"), {"e": estado_final, "f": datetime.now(), "i": id_op})
                conn.execute(text("INSERT INTO historial_movimientos (operacion_id, usuario, accion, detalle, fecha_hora) VALUES (:o, :u, 'APP', :d, :f)"), {"o": id_op, "u": dd_chofer.value, "d": det, "f": datetime.now()})
                conn.commit()
                
                # 2. ENVIAR EMAIL (Solo si es Entregado y tiene foto)
                if estado_final == "ENTREGADO" and state["tiene_foto"] and state["ruta_foto"]:
                    # Mostramos un aviso visual
                    page.snack_bar = ft.SnackBar(ft.Text(f"📧 Enviando remito a {state['proveedor']}..."), bgcolor="blue")
                    page.snack_bar.open = True
                    page.update()
                    
                    # Llamamos a la funcion de envio
                    enviar_reporte_email(txt_recibe.value, state["guia"], state["ruta_foto"], state["proveedor"])

                ir_a_principal()
                cargar_ruta(None)
                
                page.snack_bar = ft.SnackBar(ft.Text("✅ Guardado correctamente"), bgcolor="green")
                page.snack_bar.open = True
                page.update()

            except Exception as ex:
                page.add(ft.Text(f"Error al guardar: {ex}", color="red"))
            finally:
                conn.close()

    def ir_a_gestion(id_op, guia, proveedor):
        state["id"] = id_op
        state["guia"] = guia
        state["proveedor"] = proveedor
        state["tiene_foto"] = False
        state["ruta_foto"] = None
        
        txt_recibe.value = ""
        txt_motivo.value = ""
        txt_recibe.error_text = None
        txt_motivo.error_text = None
        
        btn_foto.text = "📷 FOTO REMITO"
        btn_foto.bgcolor = "grey"
        
        page.clean()
        page.add(
            ft.Column([
                ft.Text(f"Guia: {guia}", size=18, weight="bold", color="black"),
                ft.Text(f"Cliente: {proveedor}", size=14, color="grey"),
                ft.Divider(),
                
                ft.Text("ENTREGA EXITOSA:", weight="bold", color="black"),
                txt_recibe,
                btn_foto, # Boton de camara real
                ft.Container(height=10),
                ft.ElevatedButton("CONFIRMAR ENTREGA Y ENVIAR 📧", bgcolor="green", color="white", width=300, height=50, on_click=lambda _: guardar("ENTREGADO")),
                
                ft.Divider(),
                
                ft.Text("NO ENTREGADO:", weight="bold", color="black"),
                txt_motivo,
                ft.Container(height=5),
                
                ft.Row([
                    ft.ElevatedButton("PENDIENTE", bgcolor="orange", color="white", expand=True, height=45, on_click=lambda _: guardar("Pendiente")),
                    ft.ElevatedButton("REPROGRAMAR", bgcolor="purple", color="white", expand=True, height=45, on_click=lambda _: guardar("Reprogramado"))
                ]),
                
                ft.Container(height=20),
                ft.TextButton("VOLVER ATRAS", on_click=lambda _: ir_a_principal())
            ])
        )

    try:
        page.add(vista_inicio)
    except Exception as ex:
        page.add(ft.Text(f"Error inicio: {ex}", color="red"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    ft.app(target=main, view=ft.AppView.WEB_BROWSER, port=port, host="0.0.0.0")














