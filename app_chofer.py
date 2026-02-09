import flet as ft
from sqlalchemy import create_engine, text
from datetime import datetime
import os

# Configuración básica de base de datos
DATABASE_URL = "postgresql://postgres.gwdypvvyjuqzvpbbzchk:Eklogisticasajetpaq@aws-0-us-west-2.pooler.supabase.com:6543/postgres"

# Intentamos conectar, si falla no rompe la app al inicio
try:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=3600)
except:
    engine = None

def get_db_connection():
    try:
        if engine: return engine.connect()
    except:
        return None
    return None

def main(page: ft.Page):
    print("🚀 INICIANDO VERSION 10 (SI LEES ESTO, ACTUALIZO)")
    
    # Configuración super básica para evitar errores
    page.title = "Choferes"
    page.bgcolor = "white"
    page.scroll = "auto" # 'adaptive' a veces falla
    
    # Variables
    state = {"id": None, "guia": ""}
    
    # --- ELEMENTOS VISUALES ---
    lbl_titulo = ft.Text("MI RUTA", size=20, weight="bold", color="blue")
    
    # Dropdown de Chofer
    dd_chofer = ft.Dropdown(label="Selecciona tu nombre", width=300)

    # Contenedor de la lista de viajes
    columna_viajes = ft.Column()

    # Mensajes de error/exito (Metodo Clasico compatible con todo)
    def mostrar_mensaje(texto, color="green"):
        page.snack_bar = ft.SnackBar(ft.Text(texto), bgcolor=color)
        page.snack_bar.open = True
        page.update()

    # --- PANTALLA DE EDICION (Crear elementos al vuelo) ---
    txt_recibe = ft.TextField(label="Quien recibe")
    txt_motivo = ft.TextField(label="Motivo (si falla)")
    
    contenedor_principal = ft.Column()

    def volver_atras(e):
        mostrar_pantalla_principal()

    def guardar_accion(estado):
        if not state["id"]: return
        
        # Validaciones
        if estado == "ENTREGADO" and not txt_recibe.value:
            mostrar_mensaje("Falta quien recibe", "red")
            return
        if estado == "Pendiente" and not txt_motivo.value:
            mostrar_mensaje("Falta motivo", "red")
            return

        detalle = f"Recibio: {txt_recibe.value}" if estado == "ENTREGADO" else f"Motivo: {txt_motivo.value}"
        
        conn = get_db_connection()
        if conn:
            try:
                # Actualizar estado
                conn.execute(text("UPDATE operaciones SET estado = :e, fecha_entrega = :fe WHERE id = :id"), 
                             {"e": estado, "fe": datetime.now(), "id": state["id"]})
                # Guardar historial
                conn.execute(text("INSERT INTO historial_movimientos (operacion_id, usuario, accion, detalle, fecha_hora) VALUES (:oid, :usr, 'APP', :det, :fh)"), 
                             {"oid": state["id"], "usr": dd_chofer.value, "det": detalle, "fh": datetime.now()})
                conn.commit()
                mostrar_mensaje("Guardado correctamente")
            except Exception as ex:
                mostrar_mensaje(f"Error: {ex}", "red")
            finally:
                conn.close()
        
        mostrar_pantalla_principal()

    def mostrar_pantalla_edicion(id_op, guia, destinatario):
        state["id"] = id_op
        state["guia"] = guia
        
        txt_recibe.value = ""
        txt_motivo.value = ""
        
        # Limpiamos la pantalla y ponemos el formulario
        contenedor_principal.controls.clear()
        contenedor_principal.controls.append(ft.Text(f"Gestionando: {guia}", size=20, weight="bold"))
        contenedor_principal.controls.append(ft.Text(f"Cliente: {destinatario}", size=16))
        contenedor_principal.controls.append(ft.Divider())
        contenedor_principal.controls.append(txt_recibe)
        contenedor_principal.controls.append(txt_motivo)
        contenedor_principal.controls.append(ft.Divider())
        
        # Botones simples
        btn_entregado = ft.ElevatedButton("ENTREGADO", bgcolor="green", color="white", on_click=lambda _: guardar_accion("ENTREGADO"))
        btn_pendiente = ft.ElevatedButton("PENDIENTE", bgcolor="orange", color="white", on_click=lambda _: guardar_accion("Pendiente"))
        btn_volver = ft.ElevatedButton("VOLVER", on_click=volver_atras)
        
        contenedor_principal.controls.append(btn_entregado)
        contenedor_principal.controls.append(btn_pendiente)
        contenedor_principal.controls.append(ft.Container(height=20))
        contenedor_principal.controls.append(btn_volver)
        
        page.update()

    def cargar_ruta(e=None):
        chofer = dd_chofer.value
        if not chofer: return
        
        columna_viajes.controls.clear()
        conn = get_db_connection()
        if conn:
            try:
                sql = text("SELECT id, guia_remito, destinatario, domicilio, localidad, bultos FROM operaciones WHERE estado = 'En Reparto' AND chofer_asignado = :chof")
                rows = conn.execute(sql, {"chof": chofer}).fetchall()
                
                if not rows:
                    columna_viajes.controls.append(ft.Text("Nada por aqui..."))
                
                for row in rows:
                    id_op, guia, dest, dom, loc, bultos = row
                    # Tarjeta simple
                    card = ft.Container(
                        padding=10, 
                        bgcolor="#e0e0e0", # Gris clarito
                        border_radius=10,
                        content=ft.Column([
                            ft.Text(dest, weight="bold"),
                            ft.Text(f"{dom} ({loc})"),
                            ft.Text(f"Guia: {guia}"),
                            ft.ElevatedButton("GESTIONAR", on_click=lambda _,x=id_op,g=guia,d=dest: mostrar_pantalla_edicion(x,g,d))
                        ])
                    )
                    columna_viajes.controls.append(card)
                    columna_viajes.controls.append(ft.Container(height=5)) # Espacio
            except Exception as ex:
                columna_viajes.controls.append(ft.Text(f"Error SQL: {ex}", color="red"))
            finally:
                conn.close()
        page.update()

    def mostrar_pantalla_principal():
        contenedor_principal.controls.clear()
        contenedor_principal.controls.append(ft.Row([ft.Icon("local_shipping"), lbl_titulo], alignment="center"))
        contenedor_principal.controls.append(dd_chofer)
        contenedor_principal.controls.append(ft.Divider())
        contenedor_principal.controls.append(columna_viajes)
        page.update()
        cargar_ruta() # Recargar datos

    # Cargar choferes al inicio
    def iniciar_app():
        conn = get_db_connection()
        if conn:
            try:
                res = conn.execute(text("SELECT nombre FROM choferes ORDER BY nombre")).fetchall()
                for r in res:
                    dd_chofer.options.append(ft.dropdown.Option(r[0]))
            except:
                pass
            finally:
                conn.close()
        mostrar_pantalla_principal()

    # Asignar evento al dropdown
    dd_chofer.on_change = cargar_ruta
    
    # Agregar contenedor maestro
    page.add(contenedor_principal)
    iniciar_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    ft.app(target=main, view=ft.AppView.WEB_BROWSER, port=port, host="0.0.0.0")


