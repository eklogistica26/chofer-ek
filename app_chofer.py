import flet as ft
from sqlalchemy import create_engine, text
from datetime import datetime
import os
import logging

# Configuración de logs para ver qué pasa en la consola de Render
logging.basicConfig(level=logging.INFO)

# =============================================================================
# ☁️ CONFIGURACIÓN DE BASE DE DATOS
# =============================================================================
DATABASE_URL = "postgresql://postgres.gwdypvvyjuqzvpbbzchk:Eklogisticasajetpaq@aws-0-us-west-2.pooler.supabase.com:6543/postgres"

# Creamos el motor de base de datos fuera del main
try:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=3600)
except Exception as e:
    print(f"❌ Error creando motor DB: {e}")
    engine = None

def get_db_connection():
    """Intenta obtener una conexión. Retorna None si falla."""
    try:
        if engine:
            return engine.connect()
    except Exception as e:
        print(f"❌ Error conectando: {e}")
        return None
    return None

def main(page: ft.Page):
    print("🚀 INICIANDO APP CHOFER V11...")
    
    # 1. Configuración básica de la página
    page.title = "E.K. Choferes"
    page.bgcolor = "#f0f2f5"
    page.padding = 15
    page.scroll = "auto"
    
    # 2. Variables de estado (Memoria de la App)
    state = {
        "id_operacion": None,
        "guia_actual": ""
    }

    # =========================================================================
    # 3. PANTALLA DE CARGA (Para evitar pantalla gris)
    # =========================================================================
    lbl_estado = ft.Text("🔄 Conectando con el sistema...", color="blue", size=18, weight="bold")
    page.add(ft.Column([
        ft.Container(height=50),
        ft.ProgressRing(),
        ft.Container(height=20),
        lbl_estado
    ], horizontal_alignment="center"))
    page.update()

    # =========================================================================
    # 4. ELEMENTOS DE LA INTERFAZ (Se crean pero no se muestran aún)
    # =========================================================================
    
    # --- PANTALLA PRINCIPAL ---
    dd_chofer = ft.Dropdown(label="👤 Selecciona tu nombre", bgcolor="white", width=300)
    columna_viajes = ft.Column(spacing=10) # Aquí irán las tarjetas de viaje
    
    # --- PANTALLA DE GESTIÓN (Detalle) ---
    txt_recibe = ft.TextField(label="Nombre / DNI de quien recibe ✍️", bgcolor="white")
    txt_motivo = ft.TextField(label="Motivo (Solo si es Pendiente) ⚠️", bgcolor="white")
    
    lbl_titulo_gestion = ft.Text("", size=20, weight="bold")
    lbl_info_cliente = ft.Text("", size=16)

    # =========================================================================
    # 5. FUNCIONES LÓGICAS
    # =========================================================================

    def mostrar_mensaje(texto, color="green"):
        page.snack_bar = ft.SnackBar(ft.Text(texto), bgcolor=color)
        page.snack_bar.open = True
        page.update()

    def guardar_accion(estado):
        id_op = state["id_operacion"]
        if not id_op: return

        # Validaciones simples
        if estado == "ENTREGADO" and not txt_recibe.value:
            mostrar_mensaje("⚠️ Falta: ¿Quién recibe?", "red")
            return
        if estado == "Pendiente" and not txt_motivo.value:
            mostrar_mensaje("⚠️ Falta: Motivo", "red")
            return

        detalle = f"Recibió: {txt_recibe.value}" if estado == "ENTREGADO" else f"Motivo: {txt_motivo.value}"
        
        conn = get_db_connection()
        if conn:
            try:
                # 1. Actualizar estado en la tabla 'operaciones'
                conn.execute(text("UPDATE operaciones SET estado = :e, fecha_entrega = :fe WHERE id = :id"), 
                             {"e": estado, "fe": datetime.now(), "id": id_op})
                
                # 2. Guardar en el historial
                conn.execute(text("INSERT INTO historial_movimientos (operacion_id, usuario, accion, detalle, fecha_hora) VALUES (:oid, :usr, 'APP CHOFER', :det, :fh)"), 
                             {"oid": id_op, "usr": dd_chofer.value, "det": detalle, "fh": datetime.now()})
                
                conn.commit()
                mostrar_mensaje(f"✅ Guía {state['guia_actual']} guardada como {estado}")
                ir_a_pantalla_principal() # Volver a la lista
            except Exception as e:
                mostrar_mensaje(f"❌ Error al guardar: {e}", "red")
            finally:
                conn.close()
        else:
            mostrar_mensaje("❌ Sin conexión a base de datos", "red")

    def cargar_ruta(e=None):
        chofer = dd_chofer.value
        if not chofer: return
        
        columna_viajes.controls.clear()
        # Ponemos un cargando chiquito
        columna_viajes.controls.append(ft.Text("Cargando ruta...", color="blue"))
        page.update()

        conn = get_db_connection()
        columna_viajes.controls.clear() # Limpiar mensaje de carga
        
        if conn:
            try:
                # Buscamos solo lo que está 'En Reparto' para ese chofer
                sql = text("SELECT id, guia_remito, destinatario, domicilio, localidad, bultos, es_contra_reembolso, monto_recaudacion FROM operaciones WHERE estado = 'En Reparto' AND chofer_asignado = :chof ORDER BY id ASC")
                rows = conn.execute(sql, {"chof": chofer}).fetchall()
                
                if not rows:
                    columna_viajes.controls.append(ft.Container(
                        padding=20, 
                        content=ft.Text("🎉 No tienes entregas pendientes", color="green", size=16, weight="bold")
                    ))
                
                for row in rows:
                    id_op, guia, dest, dom, loc, bultos, es_cr, monto = row
                    
                    # Indicador visual de Cobro
                    if es_cr:
                        info_pago = ft.Text(f"💰 A COBRAR: ${monto}", color="red", weight="bold")
                    else:
                        info_pago = ft.Text("✅ PAGADO", color="green", weight="bold")

                    # Tarjeta de Viaje
                    card = ft.Card(
                        content=ft.Container(
                            padding=15,
                            content=ft.Column([
                                ft.ListTile(
                                    leading=ft.Icon("local_shipping", color="blue"),
                                    title=ft.Text(dest, weight="bold"),
                                    subtitle=ft.Text(f"{dom}\n({loc})")
                                ),
                                ft.Divider(),
                                ft.Row([info_pago, ft.Text(f"📦 {bultos} Bultos")], alignment="spaceBetween"),
                                ft.Container(height=10),
                                ft.ElevatedButton(
                                    "GESTIONAR ENTREGA", 
                                    bgcolor="#0d6efd", color="white", 
                                    width=280,
                                    on_click=lambda _, x=id_op, g=guia, d=dest: ir_a_pantalla_gestion(x, g, d)
                                )
                            ])
                        )
                    )
                    columna_viajes.controls.append(card)

            except Exception as ex:
                columna_viajes.controls.append(ft.Text(f"Error SQL: {ex}", color="red"))
            finally:
                conn.close()
        else:
            columna_viajes.controls.append(ft.Text("Error de conexión con DB", color="red"))
            
        page.update()

    # --- NAVEGACIÓN ---
    def ir_a_pantalla_gestion(id_op, guia, dest):
        state["id_operacion"] = id_op
        state["guia_actual"] = guia
        
        # Limpiamos campos
        txt_recibe.value = ""
        txt_motivo.value = ""
        lbl_titulo_gestion.value = f"Gestionando: {guia}"
        lbl_info_cliente.value = f"Cliente: {dest}"

        # Armamos la vista de gestión
        page.clean()
        page.add(
            ft.Column([
                ft.Container(height=10),
                ft.Text("GESTIÓN DE ENTREGA", size=18, color="grey"),
                lbl_titulo_gestion,
                lbl_info_cliente,
                ft.Divider(),
                ft.Text("Datos de Entrega:", weight="bold"),
                txt_recibe,
                ft.Text("Si no se entrega:", weight="bold"),
                txt_motivo,
                ft.Divider(),
                ft.Row([
                    ft.ElevatedButton("PENDIENTE ⚠️", bgcolor="orange", color="white", expand=True, height=50, on_click=lambda _: guardar_accion("Pendiente")),
                    ft.ElevatedButton("ENTREGADO ✅", bgcolor="green", color="white", expand=True, height=50, on_click=lambda _: guardar_accion("ENTREGADO")),
                ]),
                ft.Container(height=20),
                ft.TextButton("🔙 VOLVER A MI RUTA", on_click=lambda _: ir_a_pantalla_principal())
            ])
        )

    def ir_a_pantalla_principal():
        page.clean()
        page.add(
            ft.Column([
                ft.Row([ft.Icon("local_shipping", color="blue"), ft.Text("E.K. LOGÍSTICA", size=20, weight="bold")], alignment="center"),
                ft.Container(content=dd_chofer, alignment=ft.alignment.center),
                ft.Divider(),
                columna_viajes
            ])
        )
        cargar_ruta() # Recargar datos al volver

    # =========================================================================
    # 6. INICIO (BOOTSTRAP)
    # =========================================================================
    
    # Asignar evento al cambiar chofer
    dd_chofer.on_change = cargar_ruta

    # Intentar cargar lista de choferes
    conn = get_db_connection()
    if conn:
        try:
            lbl_estado.value = "✅ Conectado! Cargando choferes..."
            page.update()
            
            res = conn.execute(text("SELECT nombre FROM choferes ORDER BY nombre")).fetchall()
            for r in res:
                dd_chofer.options.append(ft.dropdown.Option(r[0]))
            
            # Si todo salió bien, mostramos la App real
            ir_a_pantalla_principal()
            
        except Exception as e:
            page.clean()
            page.add(ft.Text(f"❌ Error cargando datos: {e}", color="red", size=20))
        finally:
            conn.close()
    else:
        page.clean()
        page.add(ft.Text("❌ No se pudo conectar a la Base de Datos.\nVerifica tu internet o la clave de Supabase.", color="red", size=20))

if __name__ == "__main__":
    # IMPORTANTE: Puerto dinámico para Render
    port = int(os.environ.get("PORT", 8000))
    ft.app(target=main, view=ft.AppView.WEB_BROWSER, port=port, host="0.0.0.0")



