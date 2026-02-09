import flet as ft
from sqlalchemy import create_engine, text
from datetime import datetime
import os
import urllib.parse # Para que el link del mapa funcione bien

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
    print("🚀 INICIANDO V19 (DISEÑO PULIDO + MAPA)...")
    
    # CONFIGURACIÓN VISUAL PARA QUE SE LEA BIEN
    page.title = "Choferes"
    page.bgcolor = "white"
    page.theme_mode = ft.ThemeMode.LIGHT # Fuerza modo claro
    page.scroll = "auto"
    
    # ESTADO
    state = {"id": None, "guia": "", "tiene_foto": False}

    # ---------------------------------------------------------
    # FUNCIONES UTILES
    # ---------------------------------------------------------
    def abrir_mapa(domicilio, localidad):
        # Preparamos la dirección para Google Maps
        direccion_full = f"{domicilio}, {localidad}"
        query = urllib.parse.quote(direccion_full)
        url = f"https://www.google.com/maps/search/?api=1&query={query}"
        page.launch_url(url)

    # ---------------------------------------------------------
    # PANTALLA 1: INICIO (Conectar)
    # ---------------------------------------------------------
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
            finally:
                conn.close()
        else:
            btn_inicio.text = "Error de Conexión DB"
        page.update()

    btn_inicio = ft.ElevatedButton("CONECTAR", on_click=conectar, bgcolor="blue", color="white")
    
    vista_inicio = ft.Column(
        [
            ft.Text("BIENVENIDO", size=30, color="black", weight="bold"),
            ft.Text("Sistema de Choferes", size=16, color="black"),
            ft.Container(height=20),
            btn_inicio
        ],
        horizontal_alignment="center" 
    )

    # ---------------------------------------------------------
    # PANTALLA 2: LISTA (Compacta y con Mapa)
    # ---------------------------------------------------------
    dd_chofer = ft.Dropdown(label="Selecciona tu nombre", bgcolor="#f0f2f5", label_style=ft.TextStyle(color="black"))
    lista_viajes = ft.Column(spacing=5) # Menos espacio entre tarjetas

    def cargar_ruta(e):
        chofer = dd_chofer.value
        if not chofer:
            lista_viajes.controls.clear()
            page.update()
            return
        
        lista_viajes.controls.clear()
        lista_viajes.controls.append(ft.Text(f"🔎 Buscando para: {chofer}...", color="blue"))
        page.update()
        
        conn = get_db_connection()
        lista_viajes.controls.clear()
        
        if conn:
            try:
                # Traemos todo
                sql = text("""
                    SELECT id, guia_remito, destinatario, domicilio, localidad, bultos, estado 
                    FROM operaciones 
                    WHERE chofer_asignado = :c 
                    ORDER BY id ASC
                """)
                rows = conn.execute(sql, {"c": chofer}).fetchall()
                
                if not rows:
                    lista_viajes.controls.append(ft.Text("❌ No hay viajes asignados.", color="red"))
                
                for row in rows:
                    id_op, guia, dest, dom, loc, bultos, estado = row
                    
                    # Colores de estado
                    color_est = "grey"
                    if estado == "En Reparto": color_est = "blue"
                    if estado == "ENTREGADO": color_est = "green"
                    if estado == "Reprogramado": color_est = "purple"
                    if estado == "Pendiente": color_est = "orange"

                    # TARJETA COMPACTA
                    tarjeta = ft.Container(
                        bgcolor="white",
                        padding=10, # Menos relleno
                        border=ft.border.all(1, "#dddddd"), # Borde finito
                        border_radius=8,
                        content=ft.Column([
                            # Fila 1: Nombre y Estado
                            ft.Row([
                                ft.Text(dest[:20], weight="bold", size=14, color="black"), # Nombre cortado si es largo
                                ft.Container(content=ft.Text(estado[:10], color="white", size=10), bgcolor=color_est, padding=3, border_radius=3)
                            ], alignment="spaceBetween"),
                            
                            # Fila 2: Dirección y Botón Mapa
                            ft.Row([
                                ft.Icon(ft.icons.LOCATION_ON, size=16, color="red"),
                                ft.Text(f"{dom}", size=12, color="#333333", expand=True),
                                ft.IconButton(
                                    icon=ft.icons.MAP, 
                                    icon_color="blue", 
                                    icon_size=20, 
                                    tooltip="Abrir Mapa",
                                    on_click=lambda _,d=dom,l=loc: abrir_mapa(d,l)
                                )
                            ]),
                            
                            # Fila 3: Datos extra
                            ft.Text(f"Guía: {guia} | Bultos: {bultos}", size=11, color="black"),
                            
                            # Botón Gestionar
                            ft.Container(height=5),
                            ft.ElevatedButton(
                                "GESTIONAR", 
                                bgcolor="blue", color="white", 
                                height=35, # Boton mas fino
                                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=5)),
                                on_click=lambda _,x=id_op,g=guia: ir_a_gestion(x,g)
                            )
                        ], spacing=2) # Todo mas juntito
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
    # PANTALLA 3: GESTION (Con Reprogramar y Foto)
    # ---------------------------------------------------------
    txt_recibe = ft.TextField(label="Quien recibe", text_size=14, border_color="grey", label_style=ft.TextStyle(color="black"))
    txt_motivo = ft.TextField(label="Motivo (Pendiente/Reprog)", text_size=14, border_color="grey", label_style=ft.TextStyle(color="black"))
    btn_foto = ft.ElevatedButton("📷 FOTO (Opcional)", icon="camera_alt", bgcolor="grey", color="white")

    def tomar_foto(e):
        state["tiene_foto"] = True
        btn_foto.text = "✅ FOTO ADJUNTADA"
        btn_foto.bgcolor = "green"
        btn_foto.update()

    def guardar(estado):
        id_op = state["id"]
        if not id_op: return
        
        # Validaciones
        if estado == "ENTREGADO" and not txt_recibe.value: 
            txt_recibe.error_text = "Requerido"
            txt_recibe.update()
            return
        
        # Motivo requerido para Pendiente O Reprogramado
        if (estado == "Pendiente" or estado == "Reprogramado") and not txt_motivo.value:
            txt_motivo.error_text = "Escribe el motivo"
            txt_motivo.update()
            return

        # Preparamos el detalle
        det = ""
        if estado == "ENTREGADO":
            det = f"Recibio: {txt_recibe.value}"
        else:
            det = f"Motivo: {txt_motivo.value}"
            
        if state["tiene_foto"]:
            det += " [CON FOTO]"
        
        conn = get_db_connection()
        if conn:
            try:
                conn.execute(text("UPDATE operaciones SET estado=:e, fecha_entrega=:f WHERE id=:i"), {"e": estado, "f": datetime.now(), "i": id_op})
                conn.execute(text("INSERT INTO historial_movimientos (operacion_id, usuario, accion, detalle, fecha_hora) VALUES (:o, :u, 'APP', :d, :f)"), {"o": id_op, "u": dd_chofer.value, "d": det, "f": datetime.now()})
                conn.commit()
                ir_a_principal()
                cargar_ruta(None)
            except:
                pass
            finally:
                conn.close()

    def ir_a_gestion(id_op, guia):
        state["id"] = id_op
        state["tiene_foto"] = False # Reset foto
        
        # Reset campos visuales
        txt_recibe.value = ""
        txt_motivo.value = ""
        txt_recibe.error_text = None
        txt_motivo.error_text = None
        btn_foto.text = "📷 FOTO (Opcional)"
        btn_foto.bgcolor = "grey"
        btn_foto.on_click = tomar_foto # Asignamos la funcion
        
        page.clean()
        page.add(
            ft.Column([
                ft.Text(f"Guia: {guia}", size=18, weight="bold", color="black"),
                ft.Divider(),
                
                ft.Text("ENTREGA EXITOSA:", weight="bold", color="black"),
                txt_recibe,
                ft.ElevatedButton("ENTREGADO ✅", bgcolor="green", color="white", width=300, height=45, on_click=lambda _: guardar("ENTREGADO")),
                
                ft.Divider(),
                
                ft.Text("NO ENTREGADO:", weight="bold", color="black"),
                txt_motivo,
                btn_foto, # Boton de foto
                ft.Container(height=5),
                
                ft.Row([
                    ft.ElevatedButton("PENDIENTE", bgcolor="orange", color="white", expand=True, on_click=lambda _: guardar("Pendiente")),
                    ft.ElevatedButton("REPROGRAMAR", bgcolor="purple", color="white", expand=True, on_click=lambda _: guardar("Reprogramado"))
                ]),
                
                ft.Container(height=20),
                ft.TextButton("VOLVER ATRAS", on_click=lambda _: ir_a_principal())
            ])
        )

    # ---------------------------------------------------------
    # INICIO
    # ---------------------------------------------------------
    page.add(vista_inicio)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    ft.app(target=main, view=ft.AppView.WEB_BROWSER, port=port, host="0.0.0.0")









