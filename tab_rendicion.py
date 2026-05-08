import os
import requests
import base64
import io
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                             QComboBox, QPushButton, QTableWidget, QTableWidgetItem, QFrame,
                             QHeaderView, QMessageBox, QDateEdit, QTabWidget, QAbstractItemView, QStyledItemDelegate, QFileDialog)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QColor, QFont
from sqlalchemy import text

from database import Operacion, Historial, Estados
from utilidades import crear_pdf_resumen_diario
from dialogos import ConfirmarEntregaDialog, ReprogramarAdminDialog

# --- FUNCIÓN DE CORREOS PARA LA RENDICIÓN (Soporta múltiples mails) ---
def enviar_email_desktop(session, destinatario, guia, rutas_fotos, proveedor):
    try:
        from dotenv import load_dotenv
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        load_dotenv(os.path.join(BASE_DIR, '.env'))
    except: pass

    BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
    if not BREVO_API_KEY: return "⚠️ Correo NO enviado: Falta configurar BREVO_API_KEY."
        
    EMAIL_REMITENTE = "eklogistica19@gmail.com"
    email_prov = None
    
    try:
        from database import ClientePrincipal
        prov_db = session.query(ClientePrincipal).filter(ClientePrincipal.nombre.ilike(f"%{proveedor}%")).first()
        if prov_db and prov_db.email_reportes: email_prov = prov_db.email_reportes
            
        if not email_prov: return f"⚠️ Correo NO enviado: No hay email configurado para {proveedor}."

        # 🔥 CORTAMOS LOS MAILS POR COMA PARA EL ENVÍO MÚLTIPLE 🔥
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
            <br><p>Atentamente,<br><b>Sistema de Gestión E.K. Logística</b></p>
        </div>
        """
        adjuntos = []
        for ruta in rutas_fotos:
            if os.path.exists(ruta):
                with open(ruta, "rb") as f:
                    contenido_b64 = base64.b64encode(f.read()).decode('utf-8')
                    adjuntos.append({"name": os.path.basename(ruta), "content": contenido_b64})

        url = "https://api.brevo.com/v3/smtp/email"
        headers = {"accept": "application/json", "api-key": BREVO_API_KEY, "content-type": "application/json"}
        payload = {"sender": {"name": "E.K. Logística", "email": EMAIL_REMITENTE}, "to": lista_destinatarios, "subject": f"Rendición Comprobantes - Guía: {guia}", "htmlContent": html_content}
        if adjuntos: payload["attachment"] = adjuntos

        response = requests.post(url, headers=headers, json=payload)
        if response.status_code in [200, 201, 202]: return f"✅ Correo enviado a {len(lista_destinatarios)} destinatario(s)."
        else: return f"⚠️ Error Brevo: {response.text}"
    except Exception as e: return f"⚠️ Excepción al enviar correo: {str(e)}"

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
        l = QVBoxLayout(self); self.tabs_rend = QTabWidget(); l.addWidget(self.tabs_rend)
        
        # --- TAB 1: RENDICIÓN DE GUÍAS ---
        tab_pendientes = QWidget(); layout_pend = QVBoxLayout(tab_pendientes)
        filtros = QFrame(); hl = QHBoxLayout(filtros)
        
        self.resumen_fecha = QDateEdit(QDate.currentDate()); self.resumen_fecha.setCalendarPopup(True)
        self.resumen_chofer = QComboBox(); self.resumen_chofer.addItem("Todos")
        btn_b = QPushButton("🔄 Cargar Pendientes"); btn_b.clicked.connect(lambda: self.cargar_rendicion(manual=True))
        btn_pdf = QPushButton("📑 Planilla PDF"); btn_pdf.clicked.connect(self.generar_pdf_rendicion)
        
        # 🔥 BOTONES ACCIÓN MASIVA (AHORA ARRIBA PARA NO QUITAR ESPACIO) 🔥
        btn_sel = QPushButton("☑️ Todos"); btn_sel.setFixedWidth(70); btn_sel.clicked.connect(self.seleccionar_todos_rend)
        btn_des = QPushButton("⏪ Deshacer"); btn_des.setStyleSheet("background-color: #6c757d; color: white;"); btn_des.clicked.connect(self.deshacer_estado)
        btn_rep = QPushButton("📅 Reprogramar"); btn_rep.setStyleSheet("background-color: #ffc107; color: black;"); btn_rep.clicked.connect(self.reprogramar_masivo)
        btn_dev = QPushButton("🟠 Devolver"); btn_dev.setStyleSheet("background-color: #fd7e14; color: black; font-weight: bold;"); btn_dev.clicked.connect(self.confirmar_devolucion)
        
        hl.addWidget(QLabel("Fecha:")); hl.addWidget(self.resumen_fecha); hl.addWidget(QLabel("Chofer:")); hl.addWidget(self.resumen_chofer)
        hl.addWidget(btn_b); hl.addWidget(btn_pdf); hl.addSpacing(15); hl.addWidget(btn_sel); hl.addWidget(btn_des); hl.addWidget(btn_rep); hl.addWidget(btn_dev); hl.addStretch()
        layout_pend.addWidget(filtros)
        
        self.tabla_rendicion = QTableWidget(); self.tabla_rendicion.setColumnCount(12); self.tabla_rendicion.setHorizontalHeaderLabels(["ID", "Sel.", "F. Salida", "Chofer", "Cliente", "Guía", "Destinatario", "Estado Actual", "Monto ($)", "Pago CR", "Notas Chofer", "Acciones Rendición"]); self.tabla_rendicion.hideColumn(0)
        header = self.tabla_rendicion.horizontalHeader(); header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive); self.tabla_rendicion.setColumnWidth(1, 40); self.tabla_rendicion.setColumnWidth(11, 230); header.setStretchLastSection(True)
        self.tabla_rendicion.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.tabla_rendicion.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla_rendicion.setItemDelegate(PintorCeldasDelegate(self.tabla_rendicion))
        layout_pend.addWidget(self.tabla_rendicion)
        self.tabs_rend.addTab(tab_pendientes, "Rendición de Guías")

        # --- TAB 2: RENDICIÓN DIARIA ---
        tab_diaria = QWidget(); layout_diaria = QVBoxLayout(tab_diaria); f_diaria = QFrame(); hl_d = QHBoxLayout(f_diaria)
        self.d_fecha = QDateEdit(QDate.currentDate()); self.d_fecha.setCalendarPopup(True)
        btn_cargar_d = QPushButton("Ver Rendiciones del Día"); btn_cargar_d.clicked.connect(self.cargar_resumen_diario)
        hl_d.addWidget(QLabel("Seleccionar Fecha:")); hl_d.addWidget(self.d_fecha); hl_d.addWidget(btn_cargar_d); hl_d.addStretch()
        layout_diaria.addWidget(f_diaria)
        self.tabla_diaria = QTableWidget(); self.tabla_diaria.setColumnCount(8); self.tabla_diaria.setHorizontalHeaderLabels(["ID", "Chofer", "Guía", "Proveedor", "Destinatario", "Estado", "Monto ($)", "Pago CR"]); self.tabla_diaria.hideColumn(0)
        self.tabla_diaria.horizontalHeader().setStretchLastSection(True); self.tabla_diaria.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.tabla_diaria.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout_diaria.addWidget(self.tabla_diaria)
        self.tabs_rend.addTab(tab_diaria, "Rendición Diaria")

    def cargar_rendicion(self, manual=False):
        f = self.resumen_fecha.date().toPyDate(); c = self.resumen_chofer.currentText()
        try:
            self.tabla_rendicion.setRowCount(0)
            query = self.main.session.query(Operacion).filter(Operacion.sucursal == self.main.sucursal_actual, Operacion.estado.in_([Estados.EN_REPARTO, "EN REPARTO (TERCERIZADO)"]))
            if c != "Todos": query = query.filter(Operacion.chofer_asignado == c)
            query = query.join(Historial, Operacion.id == Historial.operacion_id).filter(Historial.accion.in_(["SALIDA A REPARTO", "SALIDA A TERCERIZADO"]), text("DATE(historial.fecha_hora) = :f").bindparams(f=f)).order_by(Operacion.fecha_ingreso.asc())
            res = query.all()
            if not res:
                # 🔥 SOLO MUESTRA EL CARTEL SI FUE CLIC MANUAL 🔥
                if manual: QMessageBox.information(self, "Aviso", f"No hay guías pendientes para la fecha seleccionada.")
                return
            for row, op in enumerate(res):
                self.tabla_rendicion.insertRow(row); self.tabla_rendicion.setItem(row, 0, QTableWidgetItem(str(op.id)))
                chk = QTableWidgetItem(); chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled); chk.setCheckState(Qt.CheckState.Unchecked); self.tabla_rendicion.setItem(row, 1, chk)
                self.tabla_rendicion.setItem(row, 2, QTableWidgetItem(op.fecha_ingreso.strftime("%d/%m/%Y") if op.fecha_ingreso else "")); self.tabla_rendicion.setItem(row, 3, QTableWidgetItem(op.chofer_asignado or "N/A")); self.tabla_rendicion.setItem(row, 4, QTableWidgetItem(op.proveedor or "N/A")); self.tabla_rendicion.setItem(row, 5, QTableWidgetItem(op.guia_remito or "N/A")); self.tabla_rendicion.setItem(row, 6, QTableWidgetItem(op.destinatario or "N/A")); self.tabla_rendicion.setItem(row, 7, QTableWidgetItem(op.estado)); self.tabla_rendicion.setItem(row, 8, QTableWidgetItem(f"$ {op.monto_servicio:,.2f}")); self.tabla_rendicion.setItem(row, 9, QTableWidgetItem("N/A")); self.tabla_rendicion.setItem(row, 10, QTableWidgetItem(op.notes or ""))
                w_acc = QWidget(); l_acc = QHBoxLayout(w_acc); l_acc.setContentsMargins(0, 0, 0, 0)
                btn_ok = QPushButton("✔️"); btn_ok.setStyleSheet("background-color: #198754; color: white; font-weight: bold;"); btn_ok.clicked.connect(lambda checked, id_o=op.id: self.abrir_dialogo_entrega(id_o))
                btn_fallo = QPushButton("❌"); btn_fallo.setStyleSheet("background-color: #dc3545; color: white;"); btn_fallo.clicked.connect(lambda checked, id_o=op.id: self.reprogramar_falla(id_o))
                l_acc.addWidget(btn_ok); l_acc.addWidget(btn_fallo); self.tabla_rendicion.setCellWidget(row, 11, w_acc)
        except Exception as e: self.main.session.rollback(); QMessageBox.critical(self, "Error", str(e))

    def abrir_dialogo_entrega(self, id_op):
        try:
            op = self.main.session.query(Operacion).get(id_op)
            if not op: return
            dlg = ConfirmarEntregaDialog(op, self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                rutas = dlg.obtener_rutas_fotos()
                if op.proveedor and rutas:
                    res_m = enviar_email_desktop(self.main.session, op.destinatario or "S/D", op.guia_remito or "S/D", rutas, op.proveedor)
                    self.main.toast.mostrar(res_m)
                op.estado = Estados.ENTREGADO; op.fecha_entrega = datetime.now()
                self.main.log_movimiento(op, "ENTREGA CONFIRMADA", f"Rendido desde Oficina.")
                self.main.session.commit(); self.cargar_rendicion()
                if hasattr(self.main, 'cargar_monitor_global'): self.main.cargar_monitor_global()
        except Exception: self.main.session.rollback()

    def reprogramar_falla(self, id_op):
        try:
            op = self.main.session.query(Operacion).get(id_op)
            if not op: return
            dlg = ReprogramarAdminDialog(op, self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                op.estado = Estados.EN_DEPOSITO; op.chofer_asignado = None
                self.main.log_movimiento(op, "REPROGRAMADO (ADMIN)", "Regresa a En Depósito.")
                self.main.session.commit(); self.cargar_rendicion()
                if hasattr(self.main, 'cargar_monitor_global'): self.main.cargar_monitor_global()
        except Exception: self.main.session.rollback()

    def seleccionar_todos_rend(self):
        btn = self.sender()
        marcar = Qt.CheckState.Checked if btn.text() == "☑️ Todos" else Qt.CheckState.Unchecked
        btn.setText("⬜ Ninguno" if btn.text() == "☑️ Todos" else "☑️ Todos")
        for r in range(self.tabla_rendicion.rowCount()):
            it = self.tabla_rendicion.item(r, 1)
            if it: it.setCheckState(marcar)

    def cargar_resumen_diario(self):
        f = self.d_fecha.date().toPyDate()
        try:
            self.tabla_diaria.setRowCount(0)
            ops = self.main.session.query(Operacion).filter(Operacion.sucursal == self.main.sucursal_actual, text("DATE(operaciones.fecha_entrega) = :f").bindparams(f=f)).all()
            for r, op in enumerate(ops):
                self.tabla_diaria.insertRow(r); self.tabla_diaria.setItem(r,0,QTableWidgetItem(str(op.id))); self.tabla_diaria.setItem(r,1,QTableWidgetItem(op.chofer_asignado or "-")); self.tabla_diaria.setItem(r,2,QTableWidgetItem(op.guia_remito or "-")); self.tabla_diaria.setItem(r,3,QTableWidgetItem(op.proveedor or "-")); self.tabla_diaria.setItem(r,4,QTableWidgetItem(op.destinatario or "-")); self.tabla_diaria.setItem(r,5,QTableWidgetItem(op.estado)); self.tabla_diaria.setItem(r,6,QTableWidgetItem(f"$ {op.monto_servicio:,.2f}")); self.tabla_diaria.setItem(r,7,QTableWidgetItem("-"))
        except Exception: self.main.session.rollback()

    def generar_pdf_rendicion(self):
        f = self.resumen_fecha.date().toPyDate(); c = self.resumen_chofer.currentText(); ops = []
        for r in range(self.tabla_rendicion.rowCount()):
            op = self.main.session.query(Operacion).get(int(self.tabla_rendicion.item(r,0).text()))
            if op: ops.append(op)
        if not ops: return
        ruta = os.path.join(os.path.expanduser('~'), 'Downloads', f"Rendicion_{c}_{f.strftime('%d%m%Y')}.pdf")
        crear_pdf_resumen_diario(ruta, ops, c, f.strftime('%d/%m/%Y'), self.main.usuario.username)
        os.startfile(ruta)

    def reprogramar_masivo(self):
        ids = [int(self.tabla_rendicion.item(r,0).text()) for r in range(self.tabla_rendicion.rowCount()) if self.tabla_rendicion.item(r,1).checkState() == Qt.CheckState.Checked]
        if not ids: return
        if QMessageBox.question(self, "Conf", f"¿Reprogramar {len(ids)} guías?") == QMessageBox.StandardButton.Yes:
            try:
                for op in self.main.session.query(Operacion).filter(Operacion.id.in_(ids)).all():
                    op.estado = Estados.EN_DEPOSITO; op.chofer_asignado = None
                self.main.session.commit(); self.cargar_rendicion()
            except Exception: self.main.session.rollback()

    def deshacer_estado(self):
        ids = [int(self.tabla_rendicion.item(r,0).text()) for r in range(self.tabla_rendicion.rowCount()) if self.tabla_rendicion.item(r,1).checkState() == Qt.CheckState.Checked]
        if not ids: return
        try:
            for op in self.main.session.query(Operacion).filter(Operacion.id.in_(ids)).all():
                op.estado = Estados.EN_DEPOSITO; op.chofer_asignado = None
            self.main.session.commit(); self.cargar_rendicion()
        except Exception: self.main.session.rollback()

    def confirmar_devolucion(self):
        ids = [int(self.tabla_rendicion.item(r,0).text()) for r in range(self.tabla_rendicion.rowCount()) if self.tabla_rendicion.item(r,1).checkState() == Qt.CheckState.Checked]
        if not ids: return
        if QMessageBox.question(self, "Conf", "¿Marcar como DEVOLUCION?") == QMessageBox.StandardButton.Yes:
            try:
                for op in self.main.session.query(Operacion).filter(Operacion.id.in_(ids)).all():
                    op.estado = Estados.DEVUELTO_ORIGEN; op.fecha_entrega = datetime.now()
                self.main.session.commit(); self.cargar_rendicion()
            except Exception: self.main.session.rollback()