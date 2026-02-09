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
    print("🚀 INICIANDO V16 (MODO DETECTIVE)...")
    
    page.title = "E.K. Choferes"
    page.bgcolor = "white"
    page.scroll = "auto"
    
    state = {"id": None, "guia": ""}

    # ---------------------------------------------------------
    # PANTALLA 1: CONEXIÓN
    # ---------------------------------------------------------
    def conectar(e):
        btn_inicio.text = "⏳ Buscando choferes..."
        btn_inicio.disabled = True
        page.update()
        
        conn = get_db_connection()
        if conn:
            try:
                # Cargamos TODOS los choferes
                res = conn.execute(text("SELECT nombre FROM choferes ORDER BY nombre")).fetchall()
                dd_chofer.options = []
                for r in res:
                    dd_chofer.options.append(ft.dropdown.Option(r[0]))
                
                # Si cargó bien, vamos a la principal
                ir_a_principal()
            except Exception as ex:
                btn_inicio.text = f"❌ Error SQL: {ex}"
                btn_inicio.disabled = False
            finally:
                conn.close()
        else:
            btn_inicio.text = "❌ Error Conexión DB"
            btn_inicio.disabled = False
        page.update()

    btn_inicio = ft.ElevatedButton("CONECTAR SISTEMA", on_click=conectar, bgcolor="blue", color="white", height=50)
    
    vista_inicio = ft.Column(
        [
            ft.Icon("local_shipping", size=60, color="blue"),
            ft.Text("BIENVENIDO", size=24, weight="bold"),
            ft.Container(height=20),
            btn_inicio
        ],
        horizontal_alignment="center",
    )

    # ---------------------------------------------------------
    # PANTALLA 2: LISTA (El problema estaba aquí)
    # ---------------------------------------------------------
    dd_chofer = ft.Dropdown(label="Selecciona Chofer", width=300, bgcolor="#f0f2f5")
    lista_viajes = ft.Column(spacing=10)
    lbl_debug = ft.Text("", color="red") # Para ver mensajes de error

    def cargar_ruta(e):
        chofer = dd_chofer.value
        if not chofer: return
        
        # 1. Limpiamos y mostramos mensaje de carga
        lista_viajes.controls.clear()
        lbl_debug.value = f"🔎 Buscando guías de: {chofer}..."
        page.update()
        
        conn = get_db_connection()
        
        if conn:
            try:
                # 🛑 QUITE EL FILTRO 'En Reparto' PARA VER TODO 🛑
                # Así veremos si las guías existen pero tienen otro estado
                sql = text("""
                    SELECT id, guia_remito, destinatario, domicilio, localidad, bultos, estado 
                    FROM operaciones 
                    WHERE chofer_asignado = :c 
                    ORDER BY id ASC
                """)
                rows = conn.execute(sql, {"c": chofer}).fetchall()
                
                lbl_debug.value = f"Resultados encontrados: {len(rows)}"
                
                if not rows:
                    lista_viajes.controls.append(ft.Container(
                        padding=20, bgcolor="#ffebee",
                        content=ft.Text("❌ No encontré NINGUNA guía asignada a este nombre exacta.", color="red")
                    ))
                
                for row in rows:
                    id_op, guia, dest, dom, loc, bultos, estado = row
                    
                    # Coloreamos según estado para entender qué pasa
                    color_estado = "grey"
                    if estado == "En Reparto": color_estado = "blue"
                    elif estado == "Entregado" or estado == "ENTREGADO": color_estado = "green"
                    elif estado == "Pendiente": color_estado = "orange"
                    
                    # Tarjeta simple y robusta
                    tarjeta = ft.Container(
                        bgcolor="white",
                        padding=15,
                        border=ft.border.all(1, "grey"),
                        border_radius=10,
                        content=ft.Column([
                            ft.Row([
                                ft.Text(dest, weight="bold", size=16),
                                ft.Container(content=ft.Text(estado, color="white", size=10), bgcolor=color_estado, padding=5, border_radius=5)
                            ], alignment="spaceBetween"),
                            ft.Text(f"📍 {dom} ({loc})"),
                            ft.Text(f"📦 Guía: {guia} | Bultos: {bultos}"),
                            ft.Container(height=5),
                            ft.ElevatedButton("GESTIONAR", bgcolor="blue", color="white", on_click=lambda _,x=id_op,g=guia: ir_a_gestion(x,g))
                        ])
                    )
                    lista_viajes.controls.append(tarjeta)

            except Exception as ex:
                lbl_debug.value = f"❌ Error al traer datos: {ex}"
            finally:
                conn.close()
        else:
            lbl_debug.value = "❌ Se perdió la conexión al buscar."
        
        page.update()

    dd_chofer.on_change = cargar_ruta

    def ir_a_principal():
        page.clean()
        page.add(
            ft.Column([
                ft.Text("MI RUTA (MODO DEBUG)", size=20, weight="bold", color="red"),
                dd_chofer,
                lbl_debug, # Aquí veremos qué pasa
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
                # Forzamos recarga simulando el evento
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
                ft.Text(f"Gestionando: {guia}", size=18, weight="bold"),
                ft.Divider(),
                txt_recibe,
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






