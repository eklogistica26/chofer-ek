import flet as ft
from sqlalchemy import create_engine, text
from datetime import datetime
import os
import urllib.parse 

# --- CONFIGURACIÓN DB ---
DATABASE_URL = "postgresql://postgres.gwdypvvyjuqzvpbbzchk:Eklogisticasajetpaq@aws-0-us-west-2.pooler.supabase.com:6543/postgres"

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
    print("🚀 INICIANDO V30 (CODIGO UNIVERSAL)...")
    
    page.title = "Choferes"
    page.bgcolor = "white"
    page.theme_mode = ft.ThemeMode.LIGHT 
    page.scroll = "auto"
    
    state = {"id": None, "guia": "", "tiene_foto": False}

    # ---------------------------------------------------------
    # 1. CAMARA (COMPATIBLE CON VERSIONES VIEJAS)
    # ---------------------------------------------------------
    def on_foto_seleccionada(e):
        # Esta función sirve para cualquier versión
        if e.files:
            state["tiene_foto"] = True
            btn_foto.text = f"✅ FOTO LISTA"
            btn_foto.bgcolor = "green"
            btn_foto.update()
        else:
            print("Foto cancelada")

    # TRUCO: Creamos el FilePicker VACÍO (esto nunca falla)
    file_picker = ft.FilePicker()
    
    # Y le asignamos la función DESPUÉS (esto funciona en viejas y nuevas)
    file_picker.on_result = on_foto_seleccionada
    
    page.overlay.append(file_picker)

    # ---------------------------------------------------------
    # 2. FUNCIONES
    # ---------------------------------------------------------
    def abrir_mapa(domicilio, localidad):
        direccion_full = f"{domicilio}, {localidad}"
        query = urllib.parse.quote(direccion_full)
        url = f"https://www.google.com/maps/search/?api=1&query={query}"
        # Usamos el método simple que no falla
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

    # ---------------------------------------------------------
    # 3. PANTALLAS
    # ---------------------------------------------------------
    
    # INICIO
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

    # LISTA
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
                sql = text("SELECT id, guia_remito, destinatario, domicilio, localidad, bultos, estado FROM operaciones WHERE chofer_asignado = :c ORDER BY id ASC")
                rows = conn.execute(sql, {"c": chofer}).fetchall()
                
                if not rows:
                    lista_viajes.controls.append(ft.Text("❌ No hay viajes.", color="red"))
                
                for row in rows:
                    id_op, guia, dest, dom, loc, bultos, estado = row
                    
                    color_est = "grey"
                    if estado == "En Reparto": color_est = "blue"
                    if estado == "ENTREGADO": color_est = "green"
                    if estado == "Pendiente": color_est = "orange"

                    tarjeta = ft.Container(
                        bgcolor="white", padding=10, border=ft.border.all(1, "#dddddd"), border_radius=8,
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
                            ft.Container(height=5),
                            ft.ElevatedButton("GESTIONAR", bgcolor="blue", color="white", width=280, height=40, on_click=lambda _,x=id_op,g=guia: ir_a_gestion(x,g))
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
        page.add(ft.Column([ft.Text("MI RUTA", size=18, weight="bold", color="black"), dd_chofer, btn_buscar, ft.Divider(), lista_viajes]))

    # GESTION
    txt_recibe = ft.TextField(label="Quien recibe", text_size=14, border_color="grey", label_style=ft.TextStyle(color="black"))
    txt_motivo = ft.TextField(label="Motivo (Pendiente/Reprog)", text_size=14, border_color="grey", label_style=ft.TextStyle(color="black"))
    
    # Boton camara CON ASIGNACIÓN TARDÍA
    btn_foto = ft.ElevatedButton(
        "📷 FOTO (Cámara)", 
        bgcolor="grey", color="white", height=45
        # NO asignamos on_click aquí para evitar errores si FilePicker no está listo
    )

    def guardar(estado):
        id_op = state["id"]
        if not id_op: return
        if estado == "ENTREGADO" and not txt_recibe.value: 
            txt_recibe.error_text = "Requerido"; txt_recibe.update(); return
        if (estado == "Pendiente" or estado == "Reprogramado") and not txt_motivo.value:
            txt_motivo.error_text = "Requerido"; txt_motivo.update(); return

        det = f"Recibio: {txt_recibe.value}" if estado == "ENTREGADO" else f"Motivo: {txt_motivo.value}"
        if state["tiene_foto"]: det += " [CON FOTO]"
        
        conn = get_db_connection()
        if conn:
            try:
                conn.execute(text("UPDATE operaciones SET estado=:e, fecha_entrega=:f WHERE id=:i"), {"e": estado, "f": datetime.now(), "i": id_op})
                conn.execute(text("INSERT INTO historial_movimientos (operacion_id, usuario, accion, detalle, fecha_hora) VALUES (:o, :u, 'APP', :d, :f)"), {"o": id_op, "u": dd_chofer.value, "d": det, "f": datetime.now()})
                conn.commit()
                ir_a_principal(); cargar_ruta(None)
            except: pass
            finally: conn.close()

    def ir_a_gestion(id_op, guia):
        state["id"] = id_op; state["tiene_foto"] = False
        txt_recibe.value = ""; txt_motivo.value = ""
        
        btn_foto.text = "📷 FOTO (Cámara)"; btn_foto.bgcolor = "grey"
        # Asignamos la acción AHORA, de forma segura
        btn_foto.on_click = lambda _: file_picker.pick_files(allow_multiple=False)
        
        page.clean()
        page.add(ft.Column([
            ft.Text(f"Guia: {guia}", size=18, weight="bold", color="black"), ft.Divider(),
            ft.Text("ENTREGA EXITOSA:", weight="bold", color="black"), txt_recibe,
            ft.ElevatedButton("ENTREGADO ✅", bgcolor="green", color="white", width=300, height=45, on_click=lambda _: guardar("ENTREGADO")),
            ft.Divider(),
            ft.Text("NO ENTREGADO:", weight="bold", color="black"), txt_motivo, btn_foto, ft.Container(height=5),
            ft.Row([ft.ElevatedButton("PENDIENTE", bgcolor="orange", color="white", expand=True, on_click=lambda _: guardar("Pendiente")), ft.ElevatedButton("REPROGRAMAR", bgcolor="purple", color="white", expand=True, on_click=lambda _: guardar("Reprogramado"))]),
            ft.Container(height=20), ft.TextButton("VOLVER", on_click=lambda _: ir_a_principal())
        ]))

    page.add(vista_inicio)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    ft.app(target=main, view=ft.AppView.WEB_BROWSER, port=port, host="0.0.0.0")












