import flet as ft
from sqlalchemy import create_engine, text
from datetime import datetime
import os

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
    print("🚀 INICIANDO V18 (CON BOTON MANUAL)...")
    
    page.title = "Choferes"
    page.bgcolor = "white"
    page.scroll = "auto"
    
    state = {"id": None, "guia": ""}

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
                # Cargamos choferes
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
            ft.Text("BIENVENIDO", size=30, color="black"),
            ft.Container(height=20),
            btn_inicio
        ]
    )

    # ---------------------------------------------------------
    # PANTALLA 2: LISTA (Con Botón "VER VIAJES")
    # ---------------------------------------------------------
    dd_chofer = ft.Dropdown(label="Selecciona tu nombre", bgcolor="#f0f2f5")
    lista_viajes = ft.Column()

    def cargar_ruta(e):
        chofer = dd_chofer.value
        if not chofer:
            lista_viajes.controls.clear()
            lista_viajes.controls.append(ft.Text("⚠️ Primero selecciona un nombre", color="red"))
            page.update()
            return
        
        # Feedback visual
        lista_viajes.controls.clear()
        lista_viajes.controls.append(ft.Text(f"🔎 Buscando guías para: {chofer}...", color="blue"))
        page.update()
        
        conn = get_db_connection()
        lista_viajes.controls.clear() # Limpiamos el mensaje de busqueda
        
        if conn:
            try:
                # TRAEMOS TODO (Sin filtro de estado para ver si existen)
                sql = text("""
                    SELECT id, guia_remito, destinatario, domicilio, localidad, bultos, estado 
                    FROM operaciones 
                    WHERE chofer_asignado = :c 
                    ORDER BY id ASC
                """)
                rows = conn.execute(sql, {"c": chofer}).fetchall()
                
                if not rows:
                    lista_viajes.controls.append(ft.Text("❌ No encontré guías asignadas a este nombre.", color="red", size=16))
                
                for row in rows:
                    id_op, guia, dest, dom, loc, bultos, estado = row
                    
                    texto_estado = f"Estado: {estado}"
                    color_estado = "grey"
                    if estado == "En Reparto": color_estado = "blue"
                    if estado == "ENTREGADO": color_estado = "green"

                    tarjeta = ft.Container(
                        bgcolor="#eeeeee",
                        padding=10,
                        border_radius=5,
                        content=ft.Column([
                            ft.Text(dest, weight="bold", size=16),
                            ft.Text(texto_estado, color=color_estado, weight="bold"),
                            ft.Text(f"{dom} ({loc})"),
                            ft.Text(f"Guía: {guia}"),
                            ft.ElevatedButton("GESTIONAR", bgcolor="blue", color="white", on_click=lambda _,x=id_op,g=guia: ir_a_gestion(x,g))
                        ])
                    )
                    lista_viajes.controls.append(tarjeta)
                    lista_viajes.controls.append(ft.Container(height=10))
            except Exception as ex:
                lista_viajes.controls.append(ft.Text(f"Error: {ex}"))
            finally:
                conn.close()
        else:
            lista_viajes.controls.append(ft.Text("Error de conexión"))
        
        page.update()

    # BOTON MANUAL PARA BUSCAR
    btn_buscar = ft.ElevatedButton("VER MIS VIAJES 🔍", on_click=cargar_ruta, bgcolor="green", color="white", width=200)

    def ir_a_principal():
        page.clean()
        page.add(
            ft.Column([
                ft.Text("MI RUTA", size=20, weight="bold"),
                dd_chofer,
                ft.Container(height=10),
                btn_buscar, # <--- AQUI ESTA EL BOTON QUE FALTABA
                ft.Divider(),
                lista_viajes
            ])
        )

    # ---------------------------------------------------------
    # PANTALLA 3: GESTION
    # ---------------------------------------------------------
    txt_recibe = ft.TextField(label="Quien recibe")
    txt_motivo = ft.TextField(label="Motivo (si falla)")

    def guardar(estado):
        id_op = state["id"]
        if not id_op: return
        
        det = f"Recibio: {txt_recibe.value}" if estado == "ENTREGADO" else f"Motivo: {txt_motivo.value}"
        
        conn = get_db_connection()
        if conn:
            try:
                conn.execute(text("UPDATE operaciones SET estado=:e, fecha_entrega=:f WHERE id=:i"), {"e": estado, "f": datetime.now(), "i": id_op})
                conn.execute(text("INSERT INTO historial_movimientos (operacion_id, usuario, accion, detalle, fecha_hora) VALUES (:o, :u, 'APP', :d, :f)"), {"o": id_op, "u": dd_chofer.value, "d": det, "f": datetime.now()})
                conn.commit()
                ir_a_principal()
                # Forzamos click en buscar para refrescar
                cargar_ruta(None)
            except:
                pass
            finally:
                conn.close()

    def ir_a_gestion(id_op, guia):
        state["id"] = id_op
        txt_recibe.value = ""
        txt_motivo.value = ""
        
        page.clean()
        page.add(
            ft.Column([
                ft.Text(f"Guia: {guia}", size=20, weight="bold"),
                ft.Text("Datos de Entrega:"),
                txt_recibe,
                ft.Text("Si falla:"),
                txt_motivo,
                ft.Container(height=20),
                ft.Row([
                    ft.ElevatedButton("PENDIENTE", bgcolor="orange", color="white", on_click=lambda _: guardar("Pendiente")),
                    ft.ElevatedButton("ENTREGADO", bgcolor="green", color="white", on_click=lambda _: guardar("ENTREGADO"))
                ]),
                ft.Container(height=20),
                ft.ElevatedButton("VOLVER", on_click=lambda _: ir_a_principal())
            ])
        )

    # ---------------------------------------------------------
    # INICIO
    # ---------------------------------------------------------
    page.add(vista_inicio)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    ft.app(target=main, view=ft.AppView.WEB_BROWSER, port=port, host="0.0.0.0")








