import sys
import os
import re
import math
import traceback
import urllib.parse
from datetime import datetime

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QComboBox, 
                             QPushButton, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QMessageBox, QDateEdit, QGroupBox, 
                             QFormLayout, QFileDialog, QTabWidget, QFrame, 
                             QSpinBox, QDoubleSpinBox, QRadioButton, QButtonGroup, 
                             QListWidget, QListWidgetItem, QAbstractItemView, QStatusBar, QDialog, QInputDialog,
                             QTextBrowser, QGraphicsDropShadowEffect, QStyledItemDelegate)
from PyQt6.QtCore import Qt, QDate, QTimer, QUrl, QPropertyAnimation, QEasingCurve, QPoint, QRect, QSize, QVariantAnimation, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QDesktopServices, QPainter, QRadialGradient, QLinearGradient, QPen, QPolygon, QBrush, QPixmap

from qt_material import apply_stylesheet
from sqlalchemy import text, extract, desc

from database import get_session, Usuario

print(">>> Iniciando Plataforma Ultra Rápida con Hilos de Carga...")

def detector_temprano(exc_type, exc_value, exc_traceback):
    err_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    try:
        with open("error_log.txt", "w", encoding="utf-8") as f: f.write("❌ ERROR:\n" + err_msg)
    except: pass

sys.excepthook = detector_temprano

class PintorCeldasDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        bg_color = index.data(Qt.ItemDataRole.BackgroundRole)
        if bg_color: painter.fillRect(option.rect, bg_color)
        super().paint(painter, option, index)

class LoginWindow(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Acceso Cloud - E.K. Logística")
        self.setGeometry(550, 300, 400, 280)
        layout = QVBoxLayout()
        lbl_tit = QLabel("INICIAR SESIÓN")
        lbl_tit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_tit.setStyleSheet("font-size: 22px; font-weight: bold; margin-bottom: 20px;")
        
        self.in_user = QLineEdit(); self.in_user.setPlaceholderText("Usuario")
        self.in_pass = QLineEdit(); self.in_pass.setPlaceholderText("Contraseña"); self.in_pass.setEchoMode(QLineEdit.EchoMode.Password)
        
        btn_login = QPushButton("INGRESAR")
        btn_login.clicked.connect(self.verificar_login)
        btn_login.setMinimumHeight(45) 
        
        for w in [lbl_tit, self.in_user, self.in_pass, btn_login]: layout.addWidget(w)
        layout.addStretch(); self.setLayout(layout)

    def verificar_login(self):
        u = self.in_user.text().strip().lower(); p = self.in_pass.text().strip()
        self.sender().setEnabled(False)
        self.setWindowTitle("Validando credenciales... Espere un momento"); QApplication.processEvents() 
        try:
            engine, self.session = get_session() 
            user_db = self.session.query(Usuario).filter(Usuario.username == u, Usuario.password == p).first()
            if user_db: 
                self.usuario_logueado = user_db; self.accept()
            else: 
                QMessageBox.warning(self, "Error", "Usuario o contraseña incorrectos.")
                self.setWindowTitle("Acceso Cloud - E.K. Logística")
                self.sender().setEnabled(True)
        except Exception as e: 
            QMessageBox.critical(self, "Error", f"Error de conexión: {e}")
            self.setWindowTitle("Acceso Cloud - E.K. Logística")
            self.sender().setEnabled(True)

class PlataformaLogistica(QMainWindow):
    def __init__(self, usuario_db):
        super().__init__()
        self.usuario = usuario_db; self.sucursal_actual = usuario_db.sucursal_asignada
        self.setWindowTitle(f"E.K. LOGISTICA (NUBE) - Usuario: {self.usuario.username.upper()}")
        self.setWindowState(Qt.WindowState.WindowMaximized) 
        
        global Operacion, Historial, Tarifa, Chofer, ClienteRetiro, ClientePrincipal, DestinoFrecuente, Estados, Urgencia, TarifaDHL, HistorialTarifas, ReciboPago
        from database import Operacion, Historial, Tarifa, Chofer, ClienteRetiro, ClientePrincipal, DestinoFrecuente, Estados, Urgencia, TarifaDHL, HistorialTarifas, ReciboPago
        
        global TabIngreso, TabRendicion, TabFacturacion, TabConfiguracion
        from tab_ingreso import TabIngreso
        from tab_rendicion import TabRendicion
        from tab_facturacion import TabFacturacion
        from vista_configuracion import TabConfiguracion
        
        global ToastNotification, ConfirmarEntregaDialog, ReprogramarAdminDialog, HistorialHojasRutaDialog, EditarOperacionDialog, CambiarFechaDialog, TrackingDialog
        from dialogos import ToastNotification, ConfirmarEntregaDialog, ReprogramarAdminDialog, HistorialHojasRutaDialog, EditarOperacionDialog, CambiarFechaDialog, TrackingDialog
        
        global crear_pdf_ruta, crear_pdf_tercerizados, crear_pdf_reporte
        from utilidades import crear_pdf_ruta, crear_pdf_tercerizados, crear_pdf_reporte

        _, self.session = get_session()
        
        self.lista_proveedores = []; self.toast = ToastNotification(self); self.filtro_monitor = None
        self.init_ui()
        self.tabs.currentChanged.connect(self.al_cambiar_pestana)
        self.timer = QTimer(); self.timer.timeout.connect(self.actualizar_tablas_automatico); self.timer.start(15000) 

    def safe_rollback(self):
        try: self.session.rollback()
        except: pass

    def al_cambiar_pestana(self, index):
        nombre_tab = self.tabs.tabText(index)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            if "MONITOR" in nombre_tab: 
                self.cargar_monitor_global(); self.cargar_novedades()
            elif "INGRESO" in nombre_tab: 
                self.tab_ingreso.cargar_movimientos_dia()
            elif "Ruta" in nombre_tab: self.cargar_ruta()
            elif "Rendición" in nombre_tab: self.tab_rendicion.cargar_rendicion()
            elif "Estadísticas" in nombre_tab: self.cargar_estadisticas()
            elif "CRM" in nombre_tab: self.cargar_crm()
        finally:
            QApplication.restoreOverrideCursor()

    def actualizar_tablas_automatico(self):
        try: self.session.execute(text("SELECT 1")).fetchall()
        except Exception: self.safe_rollback()
        if self.isActiveWindow():
            idx = self.tabs.currentIndex()
            if idx == 0: self.cargar_monitor_global(); self.cargar_novedades()
            elif idx == 1: self.tab_ingreso.cargar_movimientos_dia() 

    def log_movimiento(self, operacion, accion, detalle=""):
        try: self.session.add(Historial(operacion_id=operacion.id, usuario=self.usuario.username, accion=accion, detalle=detalle))
        except Exception: pass

    def init_ui(self):
        w = QWidget(); self.setCentralWidget(w); main_l = QVBoxLayout(w)
        top = QFrame(); l_top = QHBoxLayout(top)
        
        self.combo_sucursal = QComboBox(); self.combo_sucursal.addItems(["Mendoza", "San Juan"]); self.combo_sucursal.setCurrentText(self.sucursal_actual); self.combo_sucursal.setMinimumWidth(150)
        if not self.usuario.es_admin_total: self.combo_sucursal.setEnabled(False)
        self.combo_sucursal.currentTextChanged.connect(self.cambiar_sucursal)
        
        self.lbl_sucursal_grande = QLabel(self.sucursal_actual.upper()); self.lbl_sucursal_grande.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_sucursal_grande.setStyleSheet("font-size: 28px; font-weight: bold; color: #1565c0;")
        
        btn_tracking = QPushButton("🔍 TRACKING"); btn_tracking.clicked.connect(self.abrir_tracking)
        btn_ayuda = QPushButton("❓ AYUDA (Manual)"); btn_ayuda.setStyleSheet("background-color: #ff9800 !important; color: white !important; font-weight: bold !important;"); btn_ayuda.clicked.connect(self.mostrar_ayuda_inteligente)
        
        l_top.addWidget(QLabel("🏢 SUCURSAL:")); l_top.addWidget(self.combo_sucursal); l_top.addStretch(); l_top.addWidget(self.lbl_sucursal_grande); l_top.addStretch(); l_top.addWidget(btn_tracking); l_top.addWidget(btn_ayuda); l_top.addWidget(QLabel("  ")); l_top.addWidget(QLabel(f"👤 {self.usuario.username}")); main_l.addWidget(top)
        
        self.tabs = QTabWidget()
        css_pestanas = """
        QTabBar::tab { padding: 10px 15px !important; background-color: #e0e0e0 !important; color: #333333 !important; font-weight: bold !important; border: 1px solid #b0bec5 !important; }
        QTabBar::tab:selected { background-color: #1565c0 !important; color: white !important; }
        QTabBar::tab:hover:!selected { background-color: #bbdefb !important; }
        QPushButton { background-color: #1565c0 !important; color: #ffffff !important; font-weight: bold !important; border-radius: 4px !important; padding: 8px 15px !important; border: none !important; }
        QPushButton:hover { background-color: #1e88e5 !important; }
        QTableWidget QPushButton { padding: 4px 8px !important; font-size: 11px !important; border-radius: 2px !important; }
        """
        self.tabs.setStyleSheet(css_pestanas); main_l.addWidget(self.tabs)
        
        self.tab_monitor = QWidget(); self.tab_ruta = QWidget(); self.tab_reportes = QWidget(); self.tab_crm = QWidget(); self.tab_stats = QWidget(); 
        self.tab_ingreso = TabIngreso(self); self.tab_rendicion = TabRendicion(self); self.tab_cierre = TabFacturacion(self); self.tab_config = TabConfiguracion(self) 
        
        if getattr(self.usuario, 'ver_monitor', True): self.tabs.addTab(self.tab_monitor, "📊 MONITOR GLOBAL")
        if getattr(self.usuario, 'ver_ingreso', True): self.tabs.addTab(self.tab_ingreso, "1. INGRESO")
        if getattr(self.usuario, 'ver_ruta', True): self.tabs.addTab(self.tab_ruta, "2. Hoja de Ruta")
        
        if self.usuario.ver_rendicion: self.tabs.addTab(self.tab_rendicion, "3. Rendición")
        if self.usuario.ver_reportes: self.tabs.addTab(self.tab_reportes, "4. Reportes"); self.setup_reportes()
        
        if self.usuario.ver_facturacion: 
            self.tabs.addTab(self.tab_cierre, "5. Facturación")
            if hasattr(self.tab_cierre, 'tabla_cierre'): self.tab_cierre.tabla_cierre.setItemDelegate(PintorCeldasDelegate(self.tab_cierre.tabla_cierre))
                
        if self.usuario.ver_crm: self.tabs.addTab(self.tab_crm, "💬 CRM / Contacto"); self.setup_crm()
        if self.usuario.ver_estadisticas: self.tabs.addTab(self.tab_stats, "📈 Estadísticas"); self.setup_estadisticas()
        if self.usuario.ver_configuracion: self.tabs.addTab(self.tab_config, "⚙️ Configuración")
        
        self.setup_monitor(); self.setup_ruta(); self.setStatusBar(QStatusBar())
        
    def mostrar_ayuda_inteligente(self):
        d = QDialog(self)
        d.setWindowTitle("📖 Manual de Usuario")
        d.setGeometry(300, 150, 850, 600)
        btn = QPushButton("ENTENDIDO / CERRAR")
        btn.clicked.connect(d.accept)
        l = QVBoxLayout(d); l.addWidget(btn); d.exec()
def setup_monitor(self):
        layout = QVBoxLayout(self.tab_monitor)
        self.tabs_internas_monitor = QTabWidget()
        tab_tabla = QWidget(); layout_tabla = QVBoxLayout(tab_tabla); top_bar = QHBoxLayout()
        self.mon_date = QDateEdit(QDate.currentDate()); self.mon_date.setCalendarPopup(True); self.mon_date.dateChanged.connect(self.cargar_monitor_global)
        self.mon_chofer_combo = QComboBox(); self.mon_chofer_combo.addItem("Todos"); self.mon_chofer_combo.currentTextChanged.connect(self.cargar_monitor_global)
        btn_refresh = QPushButton("🔄 Actualizar Ahora"); btn_refresh.clicked.connect(lambda: {self.cargar_monitor_global(), self.cargar_novedades()})
        top_bar.addWidget(QLabel("Fecha:")); top_bar.addWidget(self.mon_date); top_bar.addWidget(QLabel("Chofer:")); top_bar.addWidget(self.mon_chofer_combo); top_bar.addWidget(btn_refresh); top_bar.addStretch()
        
        self.tabla_monitor = QTableWidget(); self.tabla_monitor.setColumnCount(8); 
        self.tabla_monitor.setHorizontalHeaderLabels(["Estado", "Guía", "Cliente", "Destinatario", "Domicilio / Novedad", "Zona", "Bultos", "Chofer"])
        self.pintor = PintorCeldasDelegate(self.tabla_monitor); self.tabla_monitor.setItemDelegate(self.pintor)
        
        header = self.tabla_monitor.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tabla_monitor.setColumnWidth(0, 130); self.tabla_monitor.setColumnWidth(1, 140); self.tabla_monitor.setColumnWidth(2, 180)
        self.tabla_monitor.setColumnWidth(3, 250); self.tabla_monitor.setColumnWidth(4, 350); self.tabla_monitor.setColumnWidth(5, 150)
        self.tabla_monitor.setColumnWidth(6, 80); header.setStretchLastSection(True)
        
        self.tabla_monitor.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.tabla_monitor.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        legend = QHBoxLayout()
        def create_filter_btn(texto, filtro_val, color_bg):
            btn = QPushButton(texto); btn.setStyleSheet(f"background-color: {color_bg} !important; color: #000000 !important; font-weight: bold !important; border: 1px solid #ccc !important;")
            btn.clicked.connect(lambda: self.aplicar_filtro_monitor(filtro_val)); return btn
        legend.addWidget(create_filter_btn("🔵 DEPOSITO", "EN DEPOSITO", "#e3f2fd")); legend.addWidget(create_filter_btn("🟡 REPARTO", Estados.EN_REPARTO, "#fff3cd"))
        legend.addWidget(create_filter_btn("🟣 REPROG.", "REPROGRAMADO", "#e2d9f3")); legend.addWidget(create_filter_btn("🟢 ENTREGADO", Estados.ENTREGADO, "#d4edda"))
        legend.addWidget(create_filter_btn("⚪ TODOS", None, "#ffffff")); legend.addStretch()
        layout_tabla.addLayout(top_bar); layout_tabla.addWidget(self.tabla_monitor); layout_tabla.addLayout(legend)
        
        tab_novedades = QWidget(); layout_novedades = QVBoxLayout(tab_novedades)
        btn_ref_nov = QPushButton("🔄 Actualizar Novedades"); btn_ref_nov.clicked.connect(self.cargar_novedades)
        self.lista_novedades = QListWidget(); self.lista_novedades.setStyleSheet("font-size: 14px; padding: 10px;")
        layout_novedades.addWidget(btn_ref_nov); layout_novedades.addWidget(self.lista_novedades)
        self.tabs_internas_monitor.addTab(tab_tabla, "📋 Listado de Guías"); self.tabs_internas_monitor.addTab(tab_novedades, "🔔 Novedades"); layout.addWidget(self.tabs_internas_monitor)

    def aplicar_filtro_monitor(self, filtro):
        self.filtro_monitor = filtro; self.cargar_monitor_global()

    def cargar_novedades(self):
        try:
            self.lista_novedades.clear()
            sql = text("SELECT h.fecha_hora, h.detalle, o.guia_remito, h.usuario, h.accion FROM historial_movimientos h JOIN operaciones o ON h.operacion_id = o.id WHERE o.sucursal = :s ORDER BY h.fecha_hora DESC LIMIT 100")
            logs = self.session.execute(sql, {"s": self.sucursal_actual}).fetchall()
            for log in logs:
                hora = log[0].strftime("%d/%m %H:%M") if log[0] else ""; guia = log[2] or "S/G"
                item = QListWidgetItem(f"{hora} | {guia} | {log[3]} | {log[4]}: {log[1]}")
                if "REPROGRAMADO" in str(log[4]): item.setBackground(QColor("#f8d7da"))
                elif "ENTREGA" in str(log[4]): item.setBackground(QColor("#d4edda"))
                self.lista_novedades.addItem(item)
        except Exception: self.session.rollback()

    def cargar_monitor_global(self):
        try:
            self.tabla_monitor.setRowCount(0); fecha_sel = self.mon_date.date().toPyDate()
            query = self.session.query(Operacion).filter(Operacion.sucursal == self.sucursal_actual)
            if self.mon_chofer_combo.currentText() != "Todos": query = query.filter(Operacion.chofer_asignado == self.mon_chofer_combo.currentText())
            ops = query.order_by(Operacion.id.desc()).limit(200).all()
            for r, op in enumerate(ops):
                self.tabla_monitor.insertRow(r)
                self.tabla_monitor.setItem(r, 0, QTableWidgetItem(op.estado))
                self.tabla_monitor.setItem(r, 1, QTableWidgetItem(op.guia_remito))
                self.tabla_monitor.setItem(r, 2, QTableWidgetItem(op.proveedor))
                self.tabla_monitor.setItem(r, 3, QTableWidgetItem(op.destinatario))
                self.tabla_monitor.setItem(r, 4, QTableWidgetItem(op.domicilio))
                self.tabla_monitor.setItem(r, 5, QTableWidgetItem(op.localidad))
                self.tabla_monitor.setItem(r, 6, QTableWidgetItem(str(op.bultos)))
                self.tabla_monitor.setItem(r, 7, QTableWidgetItem(op.chofer_asignado or "-"))
        except Exception: self.session.rollback()

    def setup_ruta(self):
        l = QVBoxLayout(self.tab_ruta); top_row1 = QHBoxLayout(); top_row2 = QHBoxLayout()
        self.combo_masivo_chofer = QComboBox(); self.combo_masivo_chofer.setMinimumWidth(150)
        self.txt_filtro_ruta = QLineEdit(); self.txt_filtro_ruta.setPlaceholderText("🔎 Filtrar..."); self.txt_filtro_ruta.textChanged.connect(self.filtrar_tabla_ruta)
        btn_aplicar_masivo = QPushButton("ASIGNAR GUÍAS"); btn_aplicar_masivo.clicked.connect(self.asignar_chofer_masivo)
        btn_mark = QPushButton("☑️ Todo"); btn_mark.clicked.connect(lambda: self.toggle_seleccion_todo(self.tabla_ruta))
        btn_reimprimir = QPushButton("🖨️ REIMPRIMIR RUTA"); btn_reimprimir.setStyleSheet("background-color: #6f42c1 !important; color: white !important;"); btn_reimprimir.clicked.connect(self.reimprimir_ruta_completa)
        btn_ref = QPushButton("🔄 Actualizar"); btn_ref.clicked.connect(self.cargar_ruta)
        top_row1.addWidget(QLabel("Chofer:")); top_row1.addWidget(self.combo_masivo_chofer); top_row1.addWidget(btn_aplicar_masivo); top_row1.addWidget(btn_mark); top_row1.addWidget(btn_reimprimir); top_row1.addStretch()
        top_row2.addWidget(self.txt_filtro_ruta); top_row2.addWidget(btn_ref)
        self.tabla_ruta = QTableWidget(); self.tabla_ruta.setColumnCount(10); self.tabla_ruta.setHorizontalHeaderLabels(["ID", "Sel.", "Guía", "Proveedor", "Destinatario", "Domicilio", "Localidad", "Bultos", "Cobro", "Estado"]); self.tabla_ruta.hideColumn(0)
        self.tabla_ruta.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); l.addLayout(top_row1); l.addLayout(top_row2); l.addWidget(self.tabla_ruta)
def filtrar_tabla_ruta(self, texto):
        texto = texto.lower()
        for r in range(self.tabla_ruta.rowCount()):
            mostrar = False
            for c in [2, 3, 4, 5, 6, 9]: 
                item = self.tabla_ruta.item(r, c)
                if item and texto in item.text().lower(): mostrar = True; break
            self.tabla_ruta.setRowHidden(r, not mostrar)

    def abrir_historial_hojas(self): 
        d = HistorialHojasRutaDialog(self.session, self.sucursal_actual, self)
        d.exec()

    def cargar_ruta(self):
        try:
            self.tabla_ruta.setRowCount(0)
            estados_deposito = [Estados.EN_DEPOSITO, 'EN DEPOSITO']
            ops = self.session.query(Operacion).filter(
                Operacion.estado.in_(estados_deposito), 
                Operacion.sucursal == self.sucursal_actual
            ).order_by(Operacion.domicilio.asc()).all()
            
            for row, op in enumerate(ops):
                self.tabla_ruta.insertRow(row)
                self.tabla_ruta.setItem(row, 0, QTableWidgetItem(str(op.id)))
                chk = QTableWidgetItem()
                chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
                chk.setCheckState(Qt.CheckState.Unchecked)
                self.tabla_ruta.setItem(row, 1, chk)
                self.tabla_ruta.setItem(row, 2, QTableWidgetItem(op.guia_remito or "-"))
                self.tabla_ruta.setItem(row, 3, QTableWidgetItem(op.proveedor))
                self.tabla_ruta.setItem(row, 4, QTableWidgetItem(op.destinatario))
                self.tabla_ruta.setItem(row, 5, QTableWidgetItem(op.domicilio))
                self.tabla_ruta.setItem(row, 6, QTableWidgetItem(op.localidad))
                self.tabla_ruta.setItem(row, 7, QTableWidgetItem(str(op.bultos)))
                self.tabla_ruta.setItem(row, 9, QTableWidgetItem(op.estado))
        except Exception: self.session.rollback()

    def cambiar_fecha_ruta(self):
        ids = []
        for r in range(self.tabla_ruta.rowCount()):
            if self.tabla_ruta.item(r, 1).checkState() == Qt.CheckState.Checked: 
                ids.append(int(self.tabla_ruta.item(r, 0).text()))
        if not ids: return
        dlg = CambiarFechaDialog("Reprogramar Selección", self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            nueva_fecha = datetime.combine(dlg.in_fecha.date().toPyDate(), datetime.min.time())
            ops = self.session.query(Operacion).filter(Operacion.id.in_(ids)).all()
            for op in ops: op.fecha_salida = nueva_fecha
            self.session.commit()
            self.cargar_ruta()

    def asignar_chofer_masivo(self):
        chofer = self.combo_masivo_chofer.currentText()
        if not chofer: return
        ids = []
        for r in range(self.tabla_ruta.rowCount()):
            if self.tabla_ruta.item(r, 1).checkState() == Qt.CheckState.Checked: 
                ids.append(int(self.tabla_ruta.item(r, 0).text()))
        if not ids: return
        try:
            ops = self.session.query(Operacion).filter(Operacion.id.in_(ids)).all()
            for op in ops:
                op.chofer_asignado = chofer
                op.estado = Estados.EN_REPARTO
                op.fecha_salida = datetime.now()
            self.session.commit()
            self.cargar_ruta()
        except Exception: self.session.rollback()

    def toggle_seleccion_todo(self, tabla):
        rows = tabla.rowCount()
        if rows == 0: return
        nuevo_estado = Qt.CheckState.Checked if tabla.item(0, 1).checkState() == Qt.CheckState.Unchecked else Qt.CheckState.Unchecked
        for r in range(rows): tabla.item(r, 1).setCheckState(nuevo_estado)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    apply_stylesheet(app, theme='light_blue.xml') 
    
    login = LoginWindow()
    if login.exec() == QDialog.DialogCode.Accepted:
        splash = PantallaCargaMinimalista()
        splash.show()
        QApplication.processEvents()
        
        def terminar_arranque():
            try:
                global ventana
                ventana = PlataformaLogistica(login.usuario_logueado)
                ventana.cambiar_sucursal(ventana.sucursal_actual)
                splash.close()
                ventana.showMaximized() 
            except Exception:
                splash.close()
                traceback.print_exc()
                sys.exit(1)
                
        wake_thread = DBWakeUpThread()
        wake_thread.finished_signal.connect(terminar_arranque)
        wake_thread.start()
        sys.exit(app.exec())