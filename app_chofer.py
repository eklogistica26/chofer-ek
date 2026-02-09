import flet as ft
from sqlalchemy import create_engine, text
from datetime import datetime
import logging
import urllib.parse
import os

# Configuración de logs
logging.basicConfig(level=logging.INFO)

# =============================================================================
# ☁️ CONFIGURACIÓN DE LA NUBE
# =============================================================================
DATABASE_URL = "postgresql://postgres.gwdypvvyjuqzvpbbzchk:Eklogisticasajetpaq@aws-0-us-west-2.pooler.supabase.com:6543/postgres"

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=3600)

def get_db_connection():
    try:
        return engine.connect()
    except Exception as e:
        print(f"❌ Error DB: {e}")
        return None

def main(page: ft.Page):
    print("🚀 Iniciando App Chofer (v6.0 - Fix Orden)...")
    page.title = "E.K. Choferes"
    page.theme_mode = "light"
    page.bgcolor = "#f0f2f5"
    page.padding = 10
    page.scroll = "adaptive"

    # Variables globales
    seleccion_actual = {"id": None, "guia": ""}

    # =========================================================================
    # 1. DEFINICIÓN DE ELEMENTOS UI (Primero creamos las cajas)
    # =========================================================================
    
    # Elementos de la pantalla de detalle
    lbl_guia_titulo = ft.Text("", size=20, weight="bold", color="blue")
    lbl_info_destinatario = ft.Text("", size=16, weight="bold")
    lbl_info_direccion = ft.Text("", size=14)
    lbl_info_bultos = ft.Text("", size=14)
    container_cobranza = ft.Container()
    txt_recibe = ft.TextField(label="Nombre / DNI de quien recibe ✍️", bgcolor="white")
    txt_motivo = ft.TextField(label="Motivo (Solo si es Pendiente) ⚠️", bgcolor="white")
    
    btn_foto = ft.ElevatedButton(
        "📷 TOMAR FOTO EVIDENCIA",
        icon="camera_alt",
        bgcolor="grey", color="white",
        width=300,
        on_click=lambda _: page.open(ft.SnackBar(ft.Text("📸 Cámara activada (Simulación)")))
    )

    # Elementos de la pantalla principal
    dd_chofer = ft.Dropdown(label="¿Quién eres?", bgcolor="white", width=300, options=[])
    columna_ruta = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True)
    lbl_sin_datos = ft.Text("No tienes entregas pendientes 🎉", visible=False, size=16, color="green")
    
    # Buscador
    txt_buscar = ft.TextField(label="Escanear/Escribir Guía", bgcolor="white")
    col_resultado_busqueda = ft.Column()

    # =========================================================================
    # 2. DEFINICIÓN DE FUNCIONES (¡AQUI ARRIBA PARA QUE NO FALLE!)
    # =========================================================================

    def abrir_mapa(domicilio, localidad):
        q = urllib.parse.quote(f"{domicilio}, {localidad}")
        page.launch_url(f"https://www.google.com/maps/search/?api=1&query={q}")

    def abrir_whatsapp(cel, guia, dest):
        if not cel or len(str(cel)) < 6: return
        num = ''.join(filter(str.isdigit, str(cel)))
        if not num.startswith("54"): num = "54" + num
        msg = urllib.parse.quote(f"Hola {dest}, envío de EK Logística (Guía: {guia}).")
        page.launch_url(f"https://wa.me/{num}?text={msg}")

    def abrir_pantalla_edicion(id_op, n_guia):
        seleccion_actual["id"] = id_op
        seleccion_actual["guia"] = n_guia
        conn = get_db_connection()
        if conn:
            try:
                res = conn.execute(text("SELECT destinatario, domicilio, localidad, bultos, es_contra_reembolso, monto_recaudacion, celular FROM operaciones WHERE id = :id"), {"id": id_op}).fetchone()
                if res:
                    d, dom, loc, b, cr, m, cel = res
                    lbl_guia_titulo.value = f"Guía: {n_guia}"
                    lbl_info_destinatario.value = f"👤 {d}"
                    lbl_info_direccion.value = f"🏠 {dom} ({loc})"
                    lbl_info_bultos.value = f"📦 {b} Bultos"
                    if cr: container_cobranza.content = ft.Container(content=ft.Text(f"💰 A COBRAR: $ {m}", color="white", weight="bold"), bgcolor="red", padding=5, border_radius=5)
                    else: container_cobranza.content = ft.Container(content=ft.Text("✅ PAGADO", color="white", weight="bold", size=12), bgcolor="green", padding=5, border_radius=5)
            except: pass
            finally: conn.close()
        txt_recibe.value = ""; txt_motivo.value = ""
        vista_principal.visible = False; vista_edicion.visible = True
        page.update()

    # --- LA FUNCION QUE DABA ERROR (MOVIDA AQUI ARRIBA) ---
    def buscar_manual(e):
        term = txt_buscar.value.strip()
        if not term: return
        conn = get_db_connection()
        col_resultado_busqueda.controls.clear()
        if conn:
            try:
                res = conn.execute(text("SELECT id, guia_remito, estado FROM operaciones WHERE guia_remito ILIKE :g"), {"g": f"%{term}%"}).fetchone()
                if res:
                    id_op, guia, est = res
                    # Creamos el botón de resultado aqui mismo
                    btn_gestion = ft.ElevatedButton(
                        f"GESTIONAR {guia}", 
                        bgcolor="blue", color="white", 
                        on_click=lambda _: abrir_pantalla_edicion(id_op, guia)
                    )
                    col_resultado_busqueda.controls.append(
                        ft.Container(
                            content=ft.Column([
                                ft.Text(f"Guía: {guia}", size=18, weight="bold"), 
                                ft.Text(f"Estado: {est}", color="blue"), 
                                btn_gestion
                            ]), 
                            bgcolor="white", padding=10, border_radius=10
                        )
                    )
                else:
                    col_resultado_busqueda.controls.append(ft.Text("No encontrada", color="red"))
            except Exception as ex:
                print(ex)
            finally:
                conn.close()
        col_resultado_busqueda.update()

    def cargar_hoja_de_ruta(e=None):
        if not dd_chofer.value: return
        columna_ruta.controls.clear(); columna_ruta.controls.append(ft.ProgressBar(width=100, color="blue")); columna_ruta.update()
        conn = get_db_connection(); columna_ruta.controls.clear()
        if conn:
            try:
                rows = conn.execute(text("SELECT id, guia_remito, destinatario, domicilio, localidad, bultos, es_contra_reembolso, monto_recaudacion, celular FROM operaciones WHERE estado = 'En Reparto' AND chofer_asignado = :chof ORDER BY id ASC"), {"chof": dd_chofer.value}).fetchall()
                if not rows: columna_ruta.controls.append(lbl_sin_datos); lbl_sin_datos.visible = True
                else:
                    lbl_sin_datos.visible = False
                    for r in rows:
                        id_op, guia, dest, dom, loc, b, cr, m, cel = r
                        info = ft.Container(content=ft.Text(f"💰 ${m}", color="white", weight="bold"), bgcolor="red", padding=5, border_radius=5) if cr else ft.Container(content=ft.Text("✅ OK", color="white", weight="bold"), bgcolor="green", padding=5, border_radius=5)
                        
                        btn_wa = ft.IconButton(ft.icons.MESSAGE, icon_color="green", icon_size=30, on_click=lambda _, c=cel, g=guia, d=dest: abrir_whatsapp(c, g, d))
                        if not cel or len(str(cel)) < 6: btn_wa.disabled = True; btn_wa.icon_color = "grey"
                        
                        card = ft.Card(content=ft.Container(padding=10, content=ft.Column([
                            ft.ListTile(leading=ft.Icon("local_shipping", color="blue"), title=ft.Text(dest, weight="bold"), subtitle=ft.Text(f"{dom}\n({loc})")),
                            ft.Row([ft.Text("Ir:"), ft.IconButton("map", icon_color="red", on_click=lambda _,d=dom,l=loc: abrir_mapa(d,l)), ft.VerticalDivider(width=10), ft.Text("Chat:"), btn_wa], alignment=ft.MainAxisAlignment.CENTER),
                            ft.Divider(), ft.Row([info, ft.Text(f"📦 {b}")], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            ft.ElevatedButton("GESTIONAR", bgcolor="#0d6efd", color="white", width=280, on_click=lambda _,x=id_op,g=guia: abrir_pantalla_edicion(x,g))
                        ])))
                        columna_ruta.controls.append(card)
            except Exception as ex: columna_ruta.controls.append(ft.Text(f"Error: {ex}", color="red"))
            finally: conn.close()
        columna_ruta.update()

    def procesar_accion(id_op, est, det, guia):
        conn = get_db_connection()
        if conn:
            try:
                conn.execute(text("UPDATE operaciones SET estado = :e, fecha_entrega = :fe WHERE id = :id"), {"e": est, "fe": datetime.now(), "id": id_op})
                conn.execute(text("INSERT INTO historial_movimientos (operacion_id, usuario, accion, detalle, fecha_hora) VALUES (:oid, :usr, 'APP CHOFER', :det, :fh)"), {"oid": id_op, "usr": dd_chofer.value, "det": det, "fh": datetime.now()})
                conn.commit()
                page.open(ft.SnackBar(ft.Text(f"Guía {guia} actualizada")))
                cargar_hoja_de_ruta()
            except Exception as ex: page.open(ft.SnackBar(ft.Text(f"Error: {ex}")))
            finally: conn.close()

    def volver_a_lista(e=None):
        vista_edicion.visible = False
        vista_principal.visible = True
        page.update()

    def click_accion_final(estado):
        id_op = seleccion_actual["id"]
        n_guia = seleccion_actual["guia"]
        if id_op:
            quien = txt_recibe.value.strip()
            motivo = txt_motivo.value.strip()
            detalle = estado
            if estado == "ENTREGADO":
                if not quien:
                    page.open(ft.SnackBar(ft.Text("⚠️ Falta quién recibe"), bgcolor="red"))
                    return
                detalle = f"Recibió: {quien}"
            elif estado == "Pendiente":
                if not motivo:
                    page.open(ft.SnackBar(ft.Text("⚠️ Falta el motivo"), bgcolor="red"))
                    return
                detalle = f"Motivo: {motivo}"
            procesar_accion(id_op, estado, detalle, n_guia)
            volver_a_lista()

    def cargar_choferes():
        conn = get_db_connection()
        if conn:
            try:
                res = conn.execute(text("SELECT nombre FROM choferes ORDER BY nombre ASC")).fetchall()
                dd_chofer.options = [ft.dropdown.Option(r[0]) for r in res]
                dd_chofer.update()
            finally: conn.close()

    # =========================================================================
    # 3. ARMADO DE PANTALLA (AL FINAL, CUANDO TODO EXISTE)
    # =========================================================================

    # Vista Edición
    vista_edicion = ft.Container(
        visible=False, bgcolor="#f0f2f5", padding=10,
        content=ft.Column([
            ft.Container(height=10),
            ft.Card(content=ft.Container(padding=15, content=ft.Column([
                ft.Row([ft.Icon("local_shipping", color="blue"), lbl_guia_titulo], alignment=ft.MainAxisAlignment.CENTER),
                ft.Divider(), lbl_info_destinatario, lbl_info_direccion,
                ft.Row([lbl_info_bultos, container_cobranza], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            ]))),
            ft.Container(height=10), ft.Text("Evidencia:", weight="bold"), btn_foto,
            ft.Container(height=5), txt_recibe, txt_motivo,
            ft.Container(height=20),
            ft.Row([
                ft.ElevatedButton("PENDIENTE ⚠️", bgcolor="orange", color="white", expand=True, height=50, on_click=lambda _: click_accion_final("Pendiente")),
                ft.ElevatedButton("ENTREGADO ✅", bgcolor="green", color="white", expand=True, height=50, on_click=lambda _: click_accion_final("ENTREGADO")),
            ]),
            ft.Container(height=20),
            ft.TextButton("CANCELAR / VOLVER", on_click=volver_a_lista, width=300)
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, scroll=ft.ScrollMode.AUTO)
    )

    # Eventos
    dd_chofer.on_change = cargar_hoja_de_ruta
    
    # Pestañas (AHORA SÍ FUNCIONA PORQUE buscar_manual YA SE LEYÓ ARRIBA)
    tab_ruta = ft.Container(content=columna_ruta, padding=5)
    tab_buscar = ft.Container(content=ft.Column([txt_buscar, ft.ElevatedButton("Buscar", on_click=buscar_manual), ft.Divider(), col_resultado_busqueda]), padding=20)
    
    tabs = ft.Tabs(
        selected_index=0,
        tabs=[
            ft.Tab("Mi Ruta", icon="list", content=tab_ruta),
            ft.Tab("Escáner", icon="qr_code", content=tab_buscar),
        ],
        expand=1
    )

    vista_principal = ft.Column([
        ft.Row([ft.Icon("local_shipping", color="blue", size=30), ft.Text("E.K. LOGISTICA", size=20, weight="bold")], alignment=ft.MainAxisAlignment.CENTER),
        ft.Container(content=dd_chofer, alignment=ft.alignment.center),
        tabs
    ], expand=True)

    page.add(ft.Column([vista_principal, vista_edicion], expand=True))
    cargar_choferes()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    ft.app(target=main, view=ft.AppView.WEB_BROWSER, port=port, host="0.0.0.0")
