import flet as ft
from sqlalchemy import create_engine, text
from datetime import datetime
import os
import logging

# Configuración de logs
logging.basicConfig(level=logging.INFO)

# =============================================================================
# ☁️ CONFIGURACIÓN DB
# =============================================================================
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
    print("🚀 INICIANDO V14 (FIX ALIGNMENT)...")
    
    page.title = "E.K. Choferes"
    page.bgcolor = "#f0f2f5"
    page.padding = 15
    page.scroll = "auto"
    
    # Variables de estado
    state = {"id": None, "guia": ""}

    # =========================================================================
    # 1. ELEMENTOS VISUALES
    # =========================================================================
    
    # PANTALLA DE INICIO
    btn_conectar = ft.ElevatedButton(
        "🚀 INICIAR SISTEMA", 
        bgcolor="#0d6efd", color="white", 
        width=250, height=50,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10))
    )
    lbl_mensaje_inicio = ft.Text("Presiona para conectar...", color="grey")
    
    columna_inicio = ft.Column(
        [
            ft.Icon("local_shipping", size=50, color="blue"),
            ft.Text("BIENVENIDO", size=20, weight="bold"),
            ft.Container(height=20),
            btn_conectar,
            ft.Container(height=10),
            lbl_mensaje_inicio
        ],
        horizontal_alignment="center", # Esto sí funciona (es texto simple)
        alignment=ft.MainAxisAlignment.CENTER
    )

    # --- CORRECCIÓN AQUÍ: Usamos Alignment(0,0) manual ---
    contenedor_inicio = ft.Container(
        content=columna_inicio,
        alignment=ft.Alignment(0, 0), # <--- ESTO ARREGLA EL ERROR
        expand=True
    )

    # PANTALLA PRINCIPAL
    dd_chofer = ft.Dropdown(label="👤 Tu nombre", bgcolor="white", width=300)
    columna_viajes = ft.Column(spacing=10)
    
    # PANTALLA GESTIÓN
    txt_recibe = ft.TextField(label="Quien recibe", bgcolor="white")
    txt_motivo = ft.TextField(label="Motivo (si falla)", bgcolor="white")
    
    # =========================================================================
    # 2. FUNCIONES
    # =========================================================================
    
    def mostrar_alerta(texto, color="red"):
        page.snack_bar = ft.SnackBar(ft.Text(texto), bgcolor=color)
        page.snack_bar.open = True
        page.update()

    def conectar_sistema(e):
        btn_conectar.disabled = True
        btn_conectar.text = "Conectando..."
        lbl_mensaje_inicio.value = "Despertando base de datos..."
        page.update()

        conn = get_db_connection()
        if conn:
            try:
                # Cargar choferes
                res = conn.execute(text("SELECT nombre FROM choferes ORDER BY nombre")).fetchall()
                dd_chofer.options = []
                for r in res:
                    dd_chofer.options.append(ft.dropdown.Option(r[0]))
                
                # Ir a pantalla principal
                ir_a_principal()
            except Exception as ex:
                lbl_mensaje_inicio.value = f"Error: {ex}"
                lbl_mensaje_inicio.color = "red"
                btn_conectar.disabled = False
                btn_conectar.text = "REINTENTAR"
            finally:
                conn.close()
        else:
            lbl_mensaje_inicio.value = "Error de conexión. Reintenta."
            lbl_mensaje_inicio.color = "red"
            btn_conectar.disabled = False
            btn_conectar.text = "REINTENTAR"
        page.update()

    def ir_a_principal():
        page.clean()
        # --- CORRECCIÓN AQUÍ TAMBIÉN ---
        page.add(
            ft.Column([
                ft.Row([ft.Icon("local_shipping", color="blue"), ft.Text("E.K. LOGISTICA", weight="bold", size=18)], alignment="center"),
                ft.Container(content=dd_chofer, alignment=ft.Alignment(0, 0)), # <--- FIX
                ft.Divider(),
                columna_viajes
            ])
        )

    def cargar_ruta(e):
        chofer = dd_chofer.value
        if not chofer: return
        
        columna_viajes.controls.clear()
        columna_viajes.controls.append(ft.Text("Cargando ruta...", color="blue"))
        page.update()
        
        conn = get_db_connection()
        columna_viajes.controls.clear()
        
        if conn:
            try:
                rows = conn.execute(text("SELECT id, guia_remito, destinatario, domicilio, localidad, bultos, es_contra_reembolso, monto_recaudacion FROM operaciones WHERE estado = 'En Reparto' AND chofer_asignado = :c"), {"c": chofer}).fetchall()
                
                if not rows:
                    columna_viajes.controls.append(ft.Text("🎉 Sin viajes pendientes", color="green", size=16))
                
                for row in rows:
                    id_op, guia, dest, dom, loc, bultos, es_cr, monto = row
                    pago = ft.Text(f"💰 COBRAR: ${monto}", color="red", weight="bold") if es_cr else ft.Text("✅ PAGADO", color="green", weight="bold")
                    
                    card = ft.Card(
                        content=ft.Container(
                            padding=15,
                            content=ft.Column([
                                ft.Text(dest, weight="bold", size=16),
                                ft.Text(f"{dom} ({loc})"),
                                ft.Divider(),
                                ft.Row([pago, ft.Text(f"📦 {bultos}")], alignment="spaceBetween"),
                                ft.Container(height=10),
                                ft.ElevatedButton("GESTIONAR", bgcolor="#0d6efd", color="white", on_click=lambda _,x=id_op,g=guia: ir_a_gestion(x,g))
                            ])
                        )
                    )
                    columna_viajes.controls.append(card)
            except:
                mostrar_alerta("Error al cargar ruta", "red")
            finally:
                conn.close()
        page.update()

    def ir_a_gestion(id_op, guia):
        state["id"] = id_op
        txt_recibe.value = ""; txt_motivo.value = ""
        
        page.clean()
        page.add(
            ft.Column([
                ft.Text(f"Gestionando: {guia}", size=18, weight="bold"),
                ft.Divider(),
                txt_recibe,
                txt_motivo,
                ft.Container(height=10),
                ft.Row([
                    ft.ElevatedButton("PENDIENTE", bgcolor="orange", color="white", expand=True, on_click=lambda _: guardar("Pendiente")),
                    ft.ElevatedButton("ENTREGADO", bgcolor="green", color="white", expand=True, on_click=lambda _: guardar("ENTREGADO"))
                ]),
                ft.Container(height=20),
                ft.TextButton("VOLVER", on_click=lambda _: ir_a_principal())
            ])
        )

    def guardar(estado):
        if not state["id"]: return
        if estado == "ENTREGADO" and not txt_recibe.value:
            mostrar_alerta("Falta quien recibe")
            return
        if estado == "Pendiente" and not txt_motivo.value:
            mostrar_alerta("Falta motivo")
            return
            
        det = f"Recibió: {txt_recibe.value}" if estado == "ENTREGADO" else f"Motivo: {txt_motivo.value}"
        
        conn = get_db_connection()
        if conn:
            try:
                conn.execute(text("UPDATE operaciones SET estado=:e, fecha_entrega=:f WHERE id=:i"), {"e": estado, "f": datetime.now(), "i": state["id"]})
                conn.execute(text("INSERT INTO historial_movimientos (operacion_id, usuario, accion, detalle, fecha_hora) VALUES (:o, :u, 'APP', :d, :f)"), {"o": state["id"], "u": dd_chofer.value, "d": det, "f": datetime.now()})
                conn.commit()
                mostrar_alerta("Guardado!")
                ir_a_principal()
                cargar_ruta(None) # Recargar
            except Exception as e:
                mostrar_alerta(f"Error: {e}")
            finally:
                conn.close()

    # =========================================================================
    # 3. INICIO
    # =========================================================================
    btn_conectar.on_click = conectar_sistema
    dd_chofer.on_change = cargar_ruta
    
    page.add(contenedor_inicio)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    ft.app(target=main, view=ft.AppView.WEB_BROWSER, port=port, host="0.0.0.0")





