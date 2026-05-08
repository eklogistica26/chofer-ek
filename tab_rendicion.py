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
        from database import ClientePrincipal
        # Buscar email del proveedor en la base
        prov_db = session.query(ClientePrincipal).filter(ClientePrincipal.nombre.ilike(f"%{proveedor}%")).first()
        if prov_db and prov_db.email_reportes:
            email_prov = prov_db.email_reportes
            
        if not email_prov:
            return f"⚠️ Correo NO enviado: No hay email configurado para {proveedor}."

        # 🔥 LA MAGIA: Cortamos los mails por coma y limpiamos espacios extra 🔥
        lista_destinatarios = [{"email": correo.strip()} for correo in email_prov.split(',') if correo.strip()]

        html_content = f"""
        <div style="font-family: Arial, sans-serif; color: #333;">
            <h2 style="color: #0d6efd;">Notificación de Rendición Logística</h2>
            <p>Estimado equipo de <b>{proveedor}</b>,</p>
            <p>Se adjuntan los comprobantes físicos (fotos) correspondientes a la siguiente operación:</p>
            <ul>
                <li><b>Guía / Remito:</b> {guia}</li>
                <li><b>Destinatario:</b> {destinatario}</li>
                <li><b>Fecha de Proceso:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}</li>
            </ul>
            <br>
            <p>Atentamente,<br><b>Sistema de Gestión E.K. Logística</b></p>
        </div>
        """

        adjuntos = []
        for ruta in rutas_fotos:
            if os.path.exists(ruta):
                with open(ruta, "rb") as f:
                    contenido_b64 = base64.b64encode(f.read()).decode('utf-8')
                    nombre_arch = os.path.basename(ruta)
                    adjuntos.append({
                        "name": nombre_arch,
                        "content": contenido_b64
                    })

        url = "https://api.brevo.com/v3/smtp/email"
        headers = {
            "accept": "application/json",
            "api-key": BREVO_API_KEY,
            "content-type": "application/json"
        }

        payload = {
            "sender": {"name": "E.K. Logística", "email": EMAIL_REMITENTE},
            "to": lista_destinatarios,  # <-- ACÁ INYECTAMOS LA LISTA MÚLTIPLE
            "subject": f"Rendición Comprobantes - Guía: {guia}",
            "htmlContent": html_content
        }
        
        if adjuntos:
            payload["attachment"] = adjuntos

        response = requests.post(url, headers=headers, json=payload)
        if response.status_code in [200, 201, 202]:
            return f"✅ Correo enviado a {len(lista_destinatarios)} destinatario(s)."
        else:
            return f"⚠️ Error Brevo: {response.text}"

    except Exception as e:
        return f"⚠️ Excepción al enviar correo: {str(e)}"

class PintorCeldasDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        bg_color = index.data(Qt.ItemDataRole.BackgroundRole)
        if bg_color: painter.fillRect(option.rect, bg_color)
        super().paint(painter, option, index)

class TabRendicion(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main = main_window
        self.setup_ui()
        
    def setup_ui(self):
        l = QVBoxLayout(self)
        
        # Ocultamos sub-pestañas para que sea una sola vista directa si no es Admin Total
        self.tabs_rend = QTabWidget()
        l.addWidget(self.tabs_rend)
        
        tab_pendientes = QWidget()
        layout_pend = QVBoxLayout(tab_pendientes)
        
        filtros = QFrame()
        hl = QHBoxLayout(filtros)
        
        self.resumen_fecha = QDateEdit(QDate.currentDate())
        self.resumen_fecha.setCalendarPopup(True)
        
        self.resumen_chofer = QComboBox()
        self.resumen_chofer.addItem("Todos")
        
        btn_b = QPushButton("Cargar Pendientes")
        btn_b.clicked.connect(self.cargar_rendicion)
        
        btn_pdf = QPushButton("Generar Planilla (PDF)")
        btn_pdf.setStyleSheet("background-color: #6c757d; color: white;")
        btn_pdf.clicked.connect(self.generar_pdf_rendicion)
        
        hl.addWidget(QLabel("Fecha de Reparto:"))
        hl.addWidget(self.resumen_fecha)
        hl.addWidget(QLabel("Chofer:"))
        hl.addWidget(self.resumen_chofer)
        hl.addWidget(btn_b)
        hl.addWidget(btn_pdf)
        hl.addStretch()
        layout_pend.addWidget(filtros)
        
        self.tabla_rendicion = QTableWidget()
        self.tabla_rendicion.setColumnCount(12)
        self.tabla_rendicion.setHorizontalHeaderLabels(["ID", "Sel.", "F. Salida", "Chofer", "Cliente", "Guía", "Destinatario", "Estado Actual", "Monto ($)", "Pago CR", "Notas Chofer", "Acciones Rendición"])
        self.tabla_rendicion.hideColumn(0)
        
        header = self.tabla_rendicion.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tabla_rendicion.setColumnWidth(1, 40)
        self.tabla_rendicion.setColumnWidth(2, 90)
        self.tabla_rendicion.setColumnWidth(3, 110)
        self.tabla_rendicion.setColumnWidth(4, 120)
        self.tabla_rendicion.setColumnWidth(5, 120)
        self.tabla_rendicion.setColumnWidth(6, 150)
        self.tabla_rendicion.setColumnWidth(7, 100)
        self.tabla_rendicion.setColumnWidth(8, 80)
        self.tabla_rendicion.setColumnWidth(9, 80)
        self.tabla_rendicion.setColumnWidth(10, 150)
        self.tabla_rendicion.setColumnWidth(11, 230)
        header.setStretchLastSection(True)
        
        self.tabla_rendicion.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla_rendicion.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        
        self.pintor = PintorCeldasDelegate(self.tabla_rendicion)
        self.tabla_rendicion.setItemDelegate(self.pintor)
        
        layout_pend.addWidget(self.tabla_rendicion)
        
        h_btn_masivos = QHBoxLayout()
        btn_sel = QPushButton("☑️ Seleccionar Todos")
        btn_sel.clicked.connect(self.seleccionar_todos_rend)
        
        btn_des = QPushButton("Deshacer y volver a En Deposito")
        btn_des.setStyleSheet("background-color: #6c757d; color: white;")
        btn_des.clicked.connect(self.deshacer_estado)
        
        btn_rep = QPushButton("Reprogramar Seleccionados (Nuevo Día)")
        btn_rep.setStyleSheet("background-color: #ffc107; color: black;")
        btn_rep.clicked.connect(self.reprogramar_masivo)
        
        # 🔥 BOTÓN NUEVO LOGÍSTICA INVERSA (NARANJA) 🔥
        btn_dev = QPushButton("🟠 Devolver a Origen (Log. Inversa)")
        btn_dev.setStyleSheet("background-color: #fd7e14; color: black; font-weight: bold;")
        btn_dev.clicked.connect(self.confirmar_devolucion)
        
        h_btn_masivos.addWidget(btn_sel)
        h_btn_masivos.addWidget(btn_des)
        h_btn_masivos.addWidget(btn_rep)
        h_btn_masivos.addWidget(btn_dev)
        layout_pend.addLayout(h_btn_masivos)
        
        self.tabs_rend.addTab(tab_pendientes, "Carga de Comprobantes y Rendición")

    def cargar_rendicion(self):
        f = self.resumen_fecha.date().toPyDate()
        c = self.resumen_chofer.currentText()
        try:
            self.tabla_rendicion.setRowCount(0)
            query = self.main.session.query(Operacion).filter(
                Operacion.sucursal == self.main.sucursal_actual,
                Operacion.estado.in_([Estados.EN_REPARTO, "EN REPARTO (TERCERIZADO)"])
            )
            
            if c != "Todos": query = query.filter(Operacion.chofer_asignado == c)
            
            # Unir historial para filtrar por la fecha en que el chofer lo escaneó/se le asignó
            query = query.join(Historial, Operacion.id == Historial.operacion_id).filter(
                Historial.accion.in_(["SALIDA A REPARTO", "SALIDA A TERCERIZADO"]),
                text("DATE(historial.fecha_hora) = :f").bindparams(f=f)
            ).order_by(Operacion.fecha_ingreso.asc())
            
            resultados = query.all()
            if not resultados:
                QMessageBox.information(self, "Aviso", f"No hay guías En Reparto pendientes de rendición para la fecha {f.strftime('%d/%m/%Y')} (Chofer: {c}).")
                return

            for row, op in enumerate(resultados):
                self.tabla_rendicion.insertRow(row)
                self.tabla_rendicion.setItem(row, 0, QTableWidgetItem(str(op.id)))
                
                chk = QTableWidgetItem()
                chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
                chk.setCheckState(Qt.CheckState.Unchecked)
                self.tabla_rendicion.setItem(row, 1, chk)
                
                self.tabla_rendicion.setItem(row, 2, QTableWidgetItem(op.fecha_ingreso.strftime("%d/%m/%Y") if op.fecha_ingreso else ""))
                self.tabla_rendicion.setItem(row, 3, QTableWidgetItem(op.chofer_asignado or "N/A"))
                self.tabla_rendicion.setItem(row, 4, QTableWidgetItem(op.proveedor or "N/A"))
                self.tabla_rendicion.setItem(row, 5, QTableWidgetItem(op.guia_remito or "N/A"))
                self.tabla_rendicion.setItem(row, 6, QTableWidgetItem(op.destinatario or "N/A"))
                self.tabla_rendicion.setItem(row, 7, QTableWidgetItem(op.estado))
                self.tabla_rendicion.setItem(row, 8, QTableWidgetItem(f"$ {op.monto_servicio:,.2f}" if op.monto_servicio else "$ 0.00"))
                self.tabla_rendicion.setItem(row, 9, QTableWidgetItem("N/A"))
                self.tabla_rendicion.setItem(row, 10, QTableWidgetItem(op.notas or ""))
                
                w_acc = QWidget()
                l_acc = QHBoxLayout(w_acc)
                l_acc.setContentsMargins(0, 0, 0, 0)
                
                btn_ok = QPushButton("✔️ Confirmar Entrega")
                btn_ok.setStyleSheet("background-color: #198754; color: white; font-weight: bold;")
                btn_ok.clicked.connect(lambda checked, id_op=op.id: self.abrir_dialogo_entrega(id_op))
                
                btn_fallo = QPushButton("❌ NO Entregado")
                btn_fallo.setStyleSheet("background-color: #dc3545; color: white;")
                btn_fallo.clicked.connect(lambda checked, id_op=op.id: self.reprogramar_falla(id_op))
                
                l_acc.addWidget(btn_ok)
                l_acc.addWidget(btn_fallo)
                self.tabla_rendicion.setCellWidget(row, 11, w_acc)
                
        except Exception as e:
            self.main.session.rollback()
            QMessageBox.critical(self, "Error", f"Error al cargar rendición: {str(e)}")

    def abrir_dialogo_entrega(self, id_op):
        try:
            op = self.main.session.query(Operacion).get(id_op)
            if not op: return
            
            dlg = ConfirmarEntregaDialog(op, self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                rutas_fotos = dlg.obtener_rutas_fotos()
                
                if op.proveedor and rutas_fotos:
                    res_mail = enviar_email_desktop(self.main.session, op.destinatario or "S/D", op.guia_remito or "S/D", rutas_fotos, op.proveedor)
                    self.main.toast.mostrar(res_mail)
                    
                op.estado = Estados.ENTREGADO
                op.fecha_entrega = datetime.now()
                self.main.log_movimiento(op, "ENTREGA CONFIRMADA", f"Rendido desde Oficina (Se enviaron {len(rutas_fotos)} fotos adjuntas).")
                self.main.session.commit()
                self.cargar_rendicion()
                if hasattr(self.main, 'cargar_monitor_global'): self.main.cargar_monitor_global()
                
        except Exception as e:
            self.main.session.rollback()

    def reprogramar_falla(self, id_op):
        try:
            op = self.main.session.query(Operacion).get(id_op)
            if not op: return
            dlg = ReprogramarAdminDialog(op, self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                op.estado = Estados.EN_DEPOSITO
                op.chofer_asignado = None
                self.main.log_movimiento(op, "REPROGRAMADO (ADMIN)", f"Marcado NO Entregado. Regresa a En Depósito.")
                self.main.session.commit()
                self.cargar_rendicion()
                if hasattr(self.main, 'cargar_monitor_global'): self.main.cargar_monitor_global()
        except Exception:
            self.main.session.rollback()

    def seleccionar_todos_rend(self):
        for r in range(self.tabla_rendicion.rowCount()):
            it = self.tabla_rendicion.item(r, 1)
            if it: it.setCheckState(Qt.CheckState.Checked)

    def generar_pdf_rendicion(self):
        try:
            f = self.resumen_fecha.date().toPyDate()
            c = self.resumen_chofer.currentText()
            ops = []
            for r in range(self.tabla_rendicion.rowCount()):
                id_op = int(self.tabla_rendicion.item(r, 0).text())
                op = self.main.session.query(Operacion).get(id_op)
                if op: ops.append(op)
            if not ops:
                QMessageBox.warning(self, "Aviso", "No hay datos para generar el PDF.")
                return
            
            descargas = os.path.join(os.path.expanduser('~'), 'Downloads')
            os.makedirs(descargas, exist_ok=True)
            ruta = os.path.join(descargas, f"Planilla_Rendicion_{c}_{f.strftime('%d%m%Y')}.pdf")
            
            crear_pdf_resumen_diario(ruta, ops, c, f.strftime('%d/%m/%Y'), self.main.usuario.username)
            os.startfile(ruta)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Fallo generar PDF: {e}")

    def reprogramar_masivo(self):
        ids = []
        for r in range(self.tabla_rendicion.rowCount()):
            if self.tabla_rendicion.item(r, 1).checkState() == Qt.CheckState.Checked: ids.append(int(self.tabla_rendicion.item(r, 0).text()))
        if not ids: 
            QMessageBox.warning(self, "Aviso", "Seleccione guías para reprogramar.")
            return
        
        reply = QMessageBox.question(self, "Confirmar Reprogramación", f"¿Reprogramar {len(ids)} guías seleccionadas y mandarlas a EN DEPOSITO con cobro de nueva visita?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                ops = self.main.session.query(Operacion).filter(Operacion.id.in_(ids)).all()
                for op in ops:
                    op.estado = Estados.EN_DEPOSITO
                    bultos_tot = op.bultos or 1
                    b_frio = getattr(op, 'bultos_frio', 0) or 0
                    precio_base = self.main.obtener_precio(op.localidad, bultos_tot - b_frio, b_frio, op.sucursal, op.proveedor, op.peso, bultos_tot)
                    nuevo_precio = (op.monto_servicio or 0.0) + precio_base
                    op.monto_servicio = nuevo_precio; op.chofer_asignado = None; self.main.log_movimiento(op, "REPROGRAMADO (ADMIN)", f"Nuevo Precio: {nuevo_precio}")
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
                self.main.tab_ingreso.cargar_ingresos_tabla()
        except Exception: self.main.session.rollback()

    def confirmar_devolucion(self):
        ids = []
        for r in range(self.tabla_rendicion.rowCount()):
            if self.tabla_rendicion.item(r, 1).checkState() == Qt.CheckState.Checked: 
                ids.append(int(self.tabla_rendicion.item(r, 0).text()))
        if not ids: 
            QMessageBox.warning(self, "Atención", "Seleccione guías para marcar como Devueltas a Origen.")
            return
        
        reply = QMessageBox.question(self, "Confirmar Devolución", f"¿Marcar {len(ids)} guías como DEVUELTO A ORIGEN?\n(Se facturarán igual que un entregado).", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes: return
        
        try:
            ops = self.main.session.query(Operacion).filter(Operacion.id.in_(ids)).all()
            for op in ops:
                op.estado = Estados.DEVUELTO_ORIGEN
                op.fecha_entrega = datetime.now()
                self.main.log_movimiento(op, "DEVOLUCION ORIGEN", "Logística Inversa - Retorno al Cliente")
            self.main.session.commit()
            QMessageBox.information(self, "Éxito", f"{len(ids)} guías marcadas como Devueltas.")
            self.cargar_rendicion()
            if hasattr(self.main, 'cargar_monitor_global'): self.main.cargar_monitor_global()
        except Exception as e: 
            self.main.session.rollback()
            QMessageBox.warning(self, "Error", f"Fallo al actualizar: {e}")