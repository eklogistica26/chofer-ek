import os
import requests
import base64
import io
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                             QComboBox, QPushButton, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QMessageBox, QDateEdit, QTabWidget, QAbstractItemView, QStyledItemDelegate, QFileDialog)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QColor, QFont
from sqlalchemy import text

from database import Operacion, Historial, Estados
from utilidades import crear_pdf_resumen_diario
from dialogos import ConfirmarEntregaDialog, ReprogramarAdminDialog

# --- FUNCIÓN DE CORREOS PARA LA RENDICIÓN ---
def enviar_email_desktop(session, destinatario, guia, rutas_fotos, proveedor):
    try:
        from dotenv import load_dotenv
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        load_dotenv(os.path.join(BASE_DIR, '.env'))
    except:
        pass

    BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
    if not BREVO_API_KEY: 
        return "⚠️ Correo NO enviado: Falta configurar BREVO_API_KEY en el archivo .env de tu PC."
        
    EMAIL_REMITENTE = "eklogistica19@gmail.com"
    email_prov = None
    try:
        res = session.execute(text("SELECT email_reportes FROM clientes_principales WHERE UPPER(TRIM(nombre)) = UPPER(TRIM(:n))"), {"n": proveedor}).fetchone()
        if res: email_prov = res[0]
    except: pass
    
    destinatarios_lista = []
    if email_prov:
        correos_limpios = str(email_prov).replace(',', ' ').replace(';', ' ')
        for c in correos_limpios.split():
            if "@" in c: destinatarios_lista.append({"email": c.strip()})
    
    if not destinatarios_lista:
        destinatarios_lista = [{"email": EMAIL_REMITENTE}]
        
    adjuntos = []
    if rutas_fotos:
        for i, ruta in enumerate(rutas_fotos):
            if os.path.exists(ruta):
                try:
                    try:
                        from PIL import Image
                        img = Image.open(ruta)
                        if img.mode in ("RGBA", "P"): img = img.convert("RGB")
                        
                        img.thumbnail((1600, 1600)) 
                        buffer = io.BytesIO()
                        img.save(buffer, format="JPEG", quality=85, optimize=True)
                        b64_content = base64.b64encode(buffer.getvalue()).decode('utf-8')
                    except Exception as e:
                        print("Fallo compresión PIL, enviando original:", e)
                        with open(ruta, "rb") as f:
                            b64_content = base64.b64encode(f.read()).decode('utf-8')
                            
                    nombre_adjunto = f"remito_{guia}.jpg" if len(rutas_fotos) == 1 else f"remito_{guia}_parte{i+1}.jpg"
                    adjuntos.append({"content": b64_content, "name": nombre_adjunto})
                except Exception as e: 
                    pass
    
    url = "https://api.brevo.com/v3/smtp/email"
    fecha_hora = datetime.now().strftime('%d/%m/%Y %H:%M')
    
    html_content = f"""
    <html><body>
    <h3>Hola,</h3>
    <p>Se informa la entrega exitosa. <b>Adjuntamos la foto del remito/guía conformado.</b></p>
    <ul>
        <li><b>Fecha:</b> {fecha_hora}</li>
        <li><b>Guía:</b> {guia}</li>
        <li><b>Proveedor:</b> {proveedor}</li>
        <li><b>Recibió:</b> {destinatario}</li>
    </ul>
    <p>Atte.<br><b>Equipo JetPaq / EK Logística</b></p>
    </body></html>
    """
    
    payload = {
        "sender": {"name": "Logistica JetPaq", "email": EMAIL_REMITENTE},
        "subject": f"ENTREGA REALIZADA - Guía: {guia}",
        "htmlContent": html_content,
        "to": destinatarios_lista,
        "bcc": [{"email": EMAIL_REMITENTE, "name": "Archivo EK Logistica"}]
    }
    if len(destinatarios_lista) == 1 and destinatarios_lista[0]["email"] == EMAIL_REMITENTE:
        if "bcc" in payload: del payload["bcc"]
    if adjuntos: payload["attachment"] = adjuntos
    
    headers = {"accept": "application/json", "api-key": BREVO_API_KEY, "content-type": "application/json"}
    
    try: 
        r = requests.post(url, json=payload, headers=headers)
        if r.status_code in [200, 201, 202]:
            return "📧 Correo enviado exitosamente con la foto adjunta."
        else:
            if "attachment" in payload:
                del payload["attachment"]
                payload["htmlContent"] = html_content.replace(
                    "<b>Adjuntamos la foto del remito/guía conformado.</b>",
                    "<b style='color:#D32F2F;'>⚠️ La foto se guardó en nuestro sistema, pero era demasiado pesada para adjuntarse en este correo.</b>"
                )
                r2 = requests.post(url, json=payload, headers=headers)
                if r2.status_code in [200, 201, 202]:
                    return "📧 Correo enviado (Sin foto porque excedía el peso de la PC)."
                else:
                    payload["to"] = [{"email": EMAIL_REMITENTE}]
                    if "bcc" in payload: del payload["bcc"]
                    requests.post(url, json=payload, headers=headers)
                    return f"⚠️ Fallo al enviar al cliente. Error de servidor: {r2.status_code}"
            return f"⚠️ Fallo en servidor de correo. Error: {r.status_code}"
    except Exception as e: 
        return f"⚠️ Error de conexión a internet al enviar correo: {str(e)}"

# --- DELEGADO DE PINTURA ---
class PintorCeldasDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        bg_color = index.data(Qt.ItemDataRole.BackgroundRole)
        if bg_color:
            painter.fillRect(option.rect, bg_color)
        super().paint(painter, option, index)

ESTILO_TABLAS_BLANCAS = """
QTableWidget { background-color: #ffffff !important; }
QTableWidget::item { background-color: transparent !important; color: #000000 !important; border-bottom: 1px solid #f0f0f0 !important; }
QTableWidget::item:selected { background-color: #bbdefb !important; color: #000000 !important; }
"""

# --- PESTAÑA PRINCIPAL DE RENDICIÓN ---
class TabRendicion(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main = main_window
        self.setup_ui()

    def setup_ui(self):
        l = QVBoxLayout(self)
        self.tabs_rendicion = QTabWidget()
        l.addWidget(self.tabs_rendicion)
        
        tab_reparto = QWidget(); lay_reparto = QVBoxLayout(tab_reparto)
        top = QHBoxLayout()
        btn_mark = QPushButton("☑️ Todo"); btn_mark.clicked.connect(lambda: self.main.toggle_seleccion_todo(self.tabla_rendicion)); 
        btn_confirmar = QPushButton("✅ CONFIRMAR ENTREGAS"); btn_confirmar.clicked.connect(self.confirmar_entrega_rendicion)
        btn_pendiente = QPushButton("📅 REPROGRAMAR"); btn_pendiente.clicked.connect(self.marcar_pendiente_masivo); 
        btn_ref = QPushButton("🔄 Actualizar"); btn_ref.clicked.connect(self.cargar_rendicion)
        
        top.addWidget(QLabel("<b>GUIAS EN REPARTO:</b>")); top.addStretch(); top.addWidget(btn_mark); top.addWidget(btn_confirmar); top.addWidget(btn_pendiente); top.addWidget(btn_ref)
        admin_bar = QHBoxLayout(); 
        btn_deshacer = QPushButton("↩️ DESHACER (Admin)"); btn_deshacer.clicked.connect(self.deshacer_estado)
        if not getattr(self.main.usuario, 'es_admin_total', False): btn_deshacer.hide()
        admin_bar.addWidget(btn_deshacer); admin_bar.addStretch()
        self.txt_filtro_rendir = QLineEdit(); self.txt_filtro_rendir.setPlaceholderText("🔎 Filtrar por Chofer, Guía..."); self.txt_filtro_rendir.textChanged.connect(self.filtrar_tabla_rendicion)
        top.insertWidget(2, self.txt_filtro_rendir)
        
        self.tabla_rendicion = QTableWidget(); self.tabla_rendicion.setColumnCount(10); 
        self.tabla_rendicion.setHorizontalHeaderLabels(["ID", "Sel.", "Chofer", "Guía / Remito", "Destinatario", "Domicilio", "Localidad", "Bultos/Hs", "Estado", "Fecha Ingreso"]); self.tabla_rendicion.hideColumn(0); 
        self.tabla_rendicion.setStyleSheet(ESTILO_TABLAS_BLANCAS)
        self.pintor_rend = PintorCeldasDelegate(self.tabla_rendicion)
        self.tabla_rendicion.setItemDelegate(self.pintor_rend)

        header_rend = self.tabla_rendicion.horizontalHeader()
        header_rend.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tabla_rendicion.setColumnWidth(1, 60)
        self.tabla_rendicion.setColumnWidth(2, 160)
        self.tabla_rendicion.setColumnWidth(3, 140)
        self.tabla_rendicion.setColumnWidth(4, 250)
        self.tabla_rendicion.setColumnWidth(5, 350)
        self.tabla_rendicion.setColumnWidth(6, 160)
        self.tabla_rendicion.setColumnWidth(7, 100)
        self.tabla_rendicion.setColumnWidth(8, 180)
        self.tabla_rendicion.setColumnWidth(9, 100)
        header_rend.setStretchLastSection(True)
        
        self.tabla_rendicion.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.tabla_rendicion.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        lay_reparto.addLayout(top); lay_reparto.addWidget(self.tabla_rendicion); lay_reparto.addLayout(admin_bar)
        self.tabs_rendicion.addTab(tab_reparto, "1. Gestión de Rendición")
        
        tab_res = QWidget(); lay_res = QVBoxLayout(tab_res)
        top_res = QHBoxLayout()
        self.resumen_chofer = QComboBox()
        self.resumen_fecha = QDateEdit(QDate.currentDate()); self.resumen_fecha.setCalendarPopup(True)
        btn_buscar_res = QPushButton("🔍 Buscar Resumen"); btn_buscar_res.clicked.connect(self.cargar_resumen_chofer_vista)
        
        btn_pdf_res = QPushButton("Imprimir PDF")
        btn_pdf_res.setStyleSheet("background-color: #dc3545 !important; color: white !important;")
        btn_pdf_res.clicked.connect(self.imprimir_resumen_chofer)
        
        top_res.addWidget(QLabel("Seleccionar Chofer:")); top_res.addWidget(self.resumen_chofer); top_res.addWidget(QLabel("Fecha:")); top_res.addWidget(self.resumen_fecha); top_res.addWidget(btn_buscar_res); top_res.addStretch(); top_res.addWidget(btn_pdf_res)
        self.lbl_res_exitos = QLabel("✅ ENTREGAS / RETIROS EXITOSOS (0)"); self.lbl_res_exitos.setStyleSheet("font-size: 14px; font-weight: bold; color: #2e7d32; margin-top: 10px;")
        
        self.tabla_res_exitos = QTableWidget(); self.tabla_res_exitos.setColumnCount(3); self.tabla_res_exitos.setHorizontalHeaderLabels(["Guía", "Destinatario", "Domicilio"])
        
        self.tabla_res_exitos.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tabla_res_exitos.setColumnWidth(0, 150)
        self.tabla_res_exitos.setColumnWidth(1, 250)
        self.tabla_res_exitos.horizontalHeader().setStretchLastSection(True)
        self.tabla_res_exitos.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        
        self.lbl_res_fallos = QLabel("⚠️ NO ENTREGADOS / PENDIENTES (0)"); self.lbl_res_fallos.setStyleSheet("font-size: 14px; font-weight: bold; color: #c62828; margin-top: 10px;")
        
        self.tabla_res_fallos = QTableWidget(); self.tabla_res_fallos.setColumnCount(3); self.tabla_res_fallos.setHorizontalHeaderLabels(["Guía", "Destinatario", "Motivo del Chofer"])
        
        self.tabla_res_fallos.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tabla_res_fallos.setColumnWidth(0, 150)
        self.tabla_res_fallos.setColumnWidth(1, 250)
        self.tabla_res_fallos.horizontalHeader().setStretchLastSection(True)
        self.tabla_res_fallos.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        
        self.tabla_res_exitos.setStyleSheet(ESTILO_TABLAS_BLANCAS)
        self.tabla_res_fallos.setStyleSheet(ESTILO_TABLAS_BLANCAS)

        lay_res.addLayout(top_res); lay_res.addWidget(self.lbl_res_exitos); lay_res.addWidget(self.tabla_res_exitos); lay_res.addWidget(self.lbl_res_fallos); lay_res.addWidget(self.tabla_res_fallos)
        self.tabs_rendicion.addTab(tab_res, "2. Resumen Diario por Chofer")

    def cargar_resumen_chofer_vista(self):
        chofer = self.resumen_chofer.currentText(); fecha = self.resumen_fecha.date().toPyDate()
        if not chofer or chofer == "Todos": return
        try:
            sql_entregados = text("SELECT DISTINCT o.id, o.guia_remito, o.destinatario, o.domicilio, o.tipo_servicio FROM operaciones o JOIN historial_movimientos h ON o.id = h.operacion_id WHERE o.chofer_asignado = :c AND o.estado = 'ENTREGADO' AND DATE(h.fecha_hora) = :f AND (h.accion LIKE '%ENTREGA%' OR h.accion = 'APP')")
            entregados = self.main.session.execute(sql_entregados, {"c": chofer, "f": fecha}).fetchall()
            
            sql_no_ent = text("""
                SELECT o.guia_remito, o.destinatario, h.detalle, o.tipo_servicio 
                FROM historial_movimientos h 
                JOIN operaciones o ON h.operacion_id = o.id 
                WHERE DATE(h.fecha_hora) = :f 
                  AND ((h.usuario = :c AND h.detalle LIKE 'Motivo:%') 
                       OR (h.usuario = :c AND h.detalle LIKE 'Pendiente%') 
                       OR (o.chofer_asignado = :c AND h.accion LIKE '%REPROGRAMADO%'))
                UNION
                SELECT guia_remito, destinatario, 'EN CALLE (Aún no gestionado)', tipo_servicio 
                FROM operaciones 
                WHERE chofer_asignado = :c AND estado = 'EN REPARTO'
            """)
            no_entregados = self.main.session.execute(sql_no_ent, {"c": chofer, "f": fecha}).fetchall()
            
            self.datos_resumen_exitos = entregados; self.datos_resumen_fallos = no_entregados
            self.tabla_res_exitos.setRowCount(0)
            
            for r, row_data in enumerate(entregados):
                self.tabla_res_exitos.insertRow(r)
                guia_str = row_data[1] or "-"
                if row_data[4] and "Retiro" in row_data[4]:
                    guia_str = f"🔄 [RETIRO] {guia_str}"
                elif row_data[4] and "Flete" in row_data[4]:
                    guia_str = f"⏱️ {guia_str}"
                
                self.tabla_res_exitos.setItem(r, 0, QTableWidgetItem(guia_str))
                self.tabla_res_exitos.setItem(r, 1, QTableWidgetItem(row_data[2]))
                self.tabla_res_exitos.setItem(r, 2, QTableWidgetItem(row_data[3]))
                
            self.lbl_res_exitos.setText(f"✅ ENTREGAS / RETIROS EXITOSOS ({len(entregados)})")
            
            self.tabla_res_fallos.setRowCount(0)
            for r, row_data in enumerate(no_entregados):
                self.tabla_res_fallos.insertRow(r)
                guia_str = row_data[0] or "-"
                if row_data[3] and "Retiro" in row_data[3]:
                    guia_str = f"🔄 [RETIRO] {guia_str}"
                elif row_data[3] and "Flete" in row_data[3]:
                    guia_str = f"⏱️ {guia_str}"
                    
                self.tabla_res_fallos.setItem(r, 0, QTableWidgetItem(guia_str))
                self.tabla_res_fallos.setItem(r, 1, QTableWidgetItem(row_data[1]))
                self.tabla_res_fallos.setItem(r, 2, QTableWidgetItem(row_data[2]))
                
            self.lbl_res_fallos.setText(f"⚠️ NO ENTREGADOS / PENDIENTES ({len(no_entregados)})")
        except Exception as e: self.main.session.rollback(); QMessageBox.critical(self, "Error", str(e))

    def imprimir_resumen_chofer(self):
        if not hasattr(self, 'datos_resumen_exitos'): QMessageBox.warning(self, "Atención", "Busque primero."); return
        chofer = self.resumen_chofer.currentText(); fecha_str = self.resumen_fecha.date().toPyDate().strftime("%d/%m/%Y"); fecha_file = self.resumen_fecha.date().toPyDate().strftime("%Y-%m-%d")
        if not self.datos_resumen_exitos and not self.datos_resumen_fallos: QMessageBox.warning(self, "Sin datos", "No hay actividad."); return
        
        descargas_dir = os.path.join(os.path.expanduser('~'), 'Downloads')
        if not os.path.exists(descargas_dir): os.makedirs(descargas_dir, exist_ok=True)
        ruta_pdf = os.path.join(descargas_dir, f"Resumen_{chofer}_{fecha_file}.pdf")
        
        crear_pdf_resumen_diario(ruta_pdf, chofer, fecha_str, self.datos_resumen_exitos, self.datos_resumen_fallos, self.main.sucursal_actual, self.main.usuario.username)
        try: os.startfile(ruta_pdf)
        except: pass

    def filtrar_tabla_rendicion(self, texto):
        texto = texto.lower()
        for r in range(self.tabla_rendicion.rowCount()):
            mostrar = False
            for c in [2, 3, 4, 5, 6]:
                if self.tabla_rendicion.item(r, c) and texto in self.tabla_rendicion.item(r, c).text().lower(): mostrar = True; break
            self.tabla_rendicion.setRowHidden(r, not mostrar)

    def cargar_rendicion(self):
        try:
            self.tabla_rendicion.blockSignals(True); self.tabla_rendicion.setRowCount(0); estados = [Estados.EN_REPARTO]
            ops = self.main.session.query(Operacion).filter(Operacion.estado.in_(estados), Operacion.sucursal == self.main.sucursal_actual).order_by(Operacion.chofer_asignado.asc()).all()
            for row, op in enumerate(ops):
                if row % 10 == 0: QApplication.processEvents() 
                self.tabla_rendicion.insertRow(row); self.tabla_rendicion.setItem(row, 0, QTableWidgetItem(str(op.id)))
                chk = QTableWidgetItem(); chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled); chk.setCheckState(Qt.CheckState.Unchecked); self.tabla_rendicion.setItem(row, 1, chk)
                guia_texto = op.guia_remito or "-"
                if op.tipo_servicio and "Retiro" in op.tipo_servicio: guia_texto = f"🔄 [RETIRO] {guia_texto}"
                elif op.tipo_servicio and "Flete" in op.tipo_servicio: guia_texto = f"⏱️ {op.guia_remito}"
                
                self.tabla_rendicion.setItem(row, 2, QTableWidgetItem(op.chofer_asignado or "SIN ASIGNAR")); self.tabla_rendicion.setItem(row, 3, QTableWidgetItem(guia_texto)); self.tabla_rendicion.setItem(row, 4, QTableWidgetItem(op.destinatario)); self.tabla_rendicion.setItem(row, 5, QTableWidgetItem(op.domicilio)); self.tabla_rendicion.setItem(row, 6, QTableWidgetItem(op.localidad)); self.tabla_rendicion.setItem(row, 7, QTableWidgetItem(str(op.bultos)))
                estado_calle = op.estado
                h_pend = self.main.session.query(Historial).filter(Historial.operacion_id == op.id, Historial.accion == 'APP').order_by(Historial.id.desc()).first()
                if h_pend and "Pendiente" in h_pend.detalle: estado_calle = "EN CALLE (Pendiente)"
                it_est = QTableWidgetItem(estado_calle)
                if "Pendiente" in estado_calle: it_est.setForeground(QColor("#f57f17"))
                self.tabla_rendicion.setItem(row, 8, it_est); 
                
                fecha_creacion_str = op.fecha_ingreso.strftime("%d/%m/%Y") if op.fecha_ingreso else "-"
                self.tabla_rendicion.setItem(row, 9, QTableWidgetItem(fecha_creacion_str)) 
                
        except Exception: self.main.session.rollback()
        finally: self.tabla_rendicion.blockSignals(False)
        
    def confirmar_entrega_rendicion(self):
        ids = []
        for r in range(self.tabla_rendicion.rowCount()):
            if self.tabla_rendicion.item(r, 1).checkState() == Qt.CheckState.Checked: ids.append(int(self.tabla_rendicion.item(r, 0).text()))
        if not ids: QMessageBox.warning(self, "Atención", "Seleccione guías para confirmar su entrega."); return
        
        dlg = ConfirmarEntregaDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted: return
        
        try:
            ops = self.main.session.query(Operacion).filter(Operacion.id.in_(ids)).all()
            count = 0
            mensajes_mail = []
            
            for op in ops:
                if op.estado == Estados.ENTREGADO: continue 
                op.estado = Estados.ENTREGADO
                op.fecha_entrega = datetime.combine(dlg.fecha_final, datetime.now().time())
                detalle = f"Recibió: {dlg.recibe_final}"
                
                if hasattr(dlg, 'rutas_fotos') and dlg.rutas_fotos:
                    detalle += f" [CON {len(dlg.rutas_fotos)} FOTO/S CARGADAS POR PC]"
                    
                    res_mail = enviar_email_desktop(self.main.session, dlg.recibe_final, op.guia_remito, dlg.rutas_fotos, op.proveedor)
                    if res_mail:
                        mensajes_mail.append(f"Guía {op.guia_remito}: {res_mail}")
                
                self.main.log_movimiento(op, "ENTREGA CONFIRMADA (ADMIN)", detalle)
                count += 1
                
            self.main.session.commit()
            
            msg_final = f"{count} guía(s) entregada(s) correctamente en el sistema."
            if mensajes_mail:
                msg_final += "\n\n📋 Estado de Correos:\n" + "\n".join(list(set(mensajes_mail)))
                
            QMessageBox.information(self, "Resultado de la Gestión", msg_final)
            
            self.cargar_rendicion()
            if hasattr(self.main, 'cargar_monitor_global'): self.main.cargar_monitor_global()
        except Exception as e: 
            self.main.session.rollback()
            QMessageBox.warning(self, "Error de Sistema", f"Ocurrió un error al procesar: {e}")

    def marcar_pendiente_masivo(self):
        ids = []
        for r in range(self.tabla_rendicion.rowCount()):
            if self.tabla_rendicion.item(r, 1).checkState() == Qt.CheckState.Checked: ids.append(int(self.tabla_rendicion.item(r, 0).text()))
        if not ids: return
        try:
            op_ref = self.main.session.query(Operacion).get(ids[0]); precio_actual = op_ref.monto_servicio if op_ref else 0.0
            last_mov = self.main.session.query(Historial).filter(Historial.operacion_id == ids[0]).order_by(Historial.id.desc()).first()
            dlg = ReprogramarAdminDialog(precio_actual, last_mov.detalle if last_mov else "Sin motivo", self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                nuevo_precio = dlg.precio_final; ops = self.main.session.query(Operacion).filter(Operacion.id.in_(ids)).all()
                for op in ops: op.estado = Estados.EN_DEPOSITO; op.monto_servicio = nuevo_precio; op.chofer_asignado = None; self.main.log_movimiento(op, "REPROGRAMADO (ADMIN)", f"Nuevo Precio: {nuevo_precio}")
                self.main.session.commit(); self.cargar_rendicion()
                if hasattr(self.main, 'cargar_monitor_global'): self.main.cargar_monitor_global()
        except Exception: self.main.session.rollback()
        
    def deshacer_estado(self):
        ids = []
        for r in range(self.tabla_rendicion.rowCount()):
            if self.tabla_rendicion.item(r, 1).checkState() == Qt.CheckState.Checked: ids.append(int(self.tabla_rendicion.item(r, 0).text()))
        if not ids: return
        try:
            ops = self.main.session.query(Operacion).filter(Operacion.id.in_(ids)).all()
            for op in ops:
                op.estado = Estados.EN_DEPOSITO
                op.chofer_asignado = None
                self.main.log_movimiento(op, "DESHACER (ADMIN)", f"Restaurado a En Deposito")
            
            self.main.session.commit()
            self.cargar_rendicion()
            
            if hasattr(self.main, 'cargar_monitor_global'): 
                self.main.cargar_monitor_global()
                
            if hasattr(self.main, 'tab_ingreso'):
                self.main.tab_ingreso.cargar_movimientos_dia()
            if hasattr(self.main, 'cargar_ruta'):
                self.main.cargar_ruta()
                
        except Exception: 
            self.main.session.rollback()