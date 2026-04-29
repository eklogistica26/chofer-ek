import sys
import os
import re
import math
import traceback
import urllib.parse
from manual_ayuda import ManualAyudaDialog
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
from sqlalchemy import text, extract, desc, func

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
        
        global TabIngreso, TabRendicion, TabFacturacion, TabConfiguracion, TabFlota
        from tab_ingreso import TabIngreso
        from tab_rendicion import TabRendicion
        from tab_facturacion import TabFacturacion
        from vista_configuracion import TabConfiguracion
        from tab_flota import TabFlota
        
        global ToastNotification, ConfirmarEntregaDialog, ReprogramarAdminDialog, HistorialHojasRutaDialog, EditarOperacionDialog, CambiarFechaDialog, TrackingDialog
        from dialogos import ToastNotification, ConfirmarEntregaDialog, ReprogramarAdminDialog, HistorialHojasRutaDialog, EditarOperacionDialog, CambiarFechaDialog
        
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
                self.actualizar_combos_dinamicos()
                self.tab_ingreso.configurar_autocompletado_global()
            elif "Ruta" in nombre_tab: self.cargar_ruta()
            elif "Rendición" in nombre_tab: self.tab_rendicion.cargar_rendicion()
            elif "Estadísticas" in nombre_tab: self.cargar_estadisticas()
            elif "Flota" in nombre_tab: self.tab_flota.cargar_vehiculos()
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
        
        self.combo_sucursal = QComboBox(); self.combo_sucursal.addItems(["Mendoza", "San Juan"]); self.combo_sucursal.setCurrentText(self.sucursal_actual); self.combo_sucursal.setMinimumWidth(250)
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
        self.tab_flota = TabFlota(self)
        
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
        
        if getattr(self.usuario, 'ver_flota', True): 
            self.tabs.addTab(self.tab_flota, "🚚 Flota / Mantenimiento")
        
        if self.usuario.ver_configuracion: self.tabs.addTab(self.tab_config, "⚙️ Configuración")
        
        self.setup_monitor(); self.setup_ruta(); self.setStatusBar(QStatusBar())

    def mostrar_ayuda_inteligente(self):
        indice_actual = self.tabs.currentIndex()
        dlg = ManualAyudaDialog(indice_pestana_actual=indice_actual, parent=self)
        dlg.exec()
    
    def abrir_tracking(self): 
        d = TrackingDialog(self.session, getattr(self, 'usuario', None)); d.exec()
    
    def cambiar_sucursal(self, suc):
        self.sucursal_actual = suc
        self.lbl_sucursal_grande.setText(f"📍 SUCURSAL {suc.upper()}")
        if hasattr(self.tab_ingreso, 'btn_dhl'): self.tab_ingreso.btn_dhl.setVisible(suc == "San Juan")
        QApplication.processEvents() 
        try:
            self.actualizar_combos_dinamicos()
            if hasattr(self, 'tab_ingreso'): self.tab_ingreso.in_guia.clear()
            QApplication.processEvents()
            self.al_cambiar_pestana(self.tabs.currentIndex())
        except Exception as e: self.session.rollback()
        self.combo_sucursal.blockSignals(True); self.combo_sucursal.setCurrentText(suc); self.combo_sucursal.blockSignals(False)

    def actualizar_combos_dinamicos(self):
        try:
            zs = self.session.query(Tarifa.localidad).filter(Tarifa.sucursal == self.sucursal_actual).distinct().all()
            chs = self.session.query(Chofer.nombre).filter(Chofer.sucursal == self.sucursal_actual).all()
            nombres_choferes = [c[0] for c in chs]
            clis = self.session.query(ClienteRetiro).filter(ClienteRetiro.sucursal == self.sucursal_actual).order_by(ClienteRetiro.nombre).all()
            chs_todos = self.session.query(Chofer.nombre).all()
            clientes_db = self.session.query(ClientePrincipal).order_by(ClientePrincipal.nombre.asc()).all()
            self.lista_proveedores = [c.nombre for c in clientes_db] if clientes_db else ["Andreani", "DHL", "Directo", "JetPaq", "MercadoLibre", "Otro"]
            
            if hasattr(self, 'tab_ingreso'):
                self.tab_ingreso.in_loc_combo.clear(); self.tab_ingreso.in_loc_combo.addItems(sorted([z[0] for z in zs]))
                self.tab_ingreso.in_cliente_retiro.clear(); self.tab_ingreso.in_cliente_retiro.addItem("--- Buscar Cliente ---")
                for c in clis: self.tab_ingreso.in_cliente_retiro.addItem(f"{c.id} - {c.nombre}", c.id)
                self.tab_ingreso.in_prov.clear(); self.tab_ingreso.in_prov.addItems(self.lista_proveedores)

            if hasattr(self, 'combo_masivo_chofer'): self.combo_masivo_chofer.clear(); self.combo_masivo_chofer.addItems(nombres_choferes)
            if hasattr(self, 'mon_chofer_combo'): self.mon_chofer_combo.clear(); self.mon_chofer_combo.addItem("Todos"); self.mon_chofer_combo.addItems(nombres_choferes)
            if hasattr(self, 'tab_rendicion'): self.tab_rendicion.resumen_chofer.clear(); self.tab_rendicion.resumen_chofer.addItems(nombres_choferes)
            if hasattr(self, 'rep_chofer'): 
                self.rep_chofer.clear(); self.rep_chofer.addItem("Todos"); self.rep_chofer.addItems(sorted(list(set([c[0] for c in chs_todos]))))
                self.rep_cliente.clear(); self.rep_cliente.addItem("Todos"); self.rep_cliente.addItems(self.lista_proveedores)
            if hasattr(self, 'tab_cierre'):
                self.tab_cierre.cierre_prov.clear(); self.tab_cierre.cierre_prov.addItem("Todos"); self.tab_cierre.cierre_prov.addItems([p for p in self.lista_proveedores if p.lower() != "jetpaq"])
        except Exception: self.session.rollback()
            
    def obtener_precio(self, loc, cant_comun, cant_frio, suc_forzada=None, proveedor="", peso=0.0, bultos_totales=1):
        suc = suc_forzada if suc_forzada else self.sucursal_actual
        proveedor_str = proveedor or ""
        try:
            if "DHL" in proveedor_str.upper():
                p_val = float(peso) if peso else 0.0
                
                # 🔥 REGLA ANTI-CERO: Si pesa 0 Kg, el costo es $0 automático 🔥
                if p_val <= 0.0:
                    return 0.0
                    
                t = self.session.query(TarifaDHL).filter(TarifaDHL.sucursal.ilike(suc)).first()
                if not t: return 0.0
                
                b_tot = int(bultos_totales) if bultos_totales else 1
                if b_tot <= 0: b_tot = 1
                
                if p_val <= b_tot * 2: base = b_tot * (t.t2 or 0.0)
                elif p_val <= b_tot * 5: base = b_tot * (t.t5 or 0.0)
                elif p_val <= b_tot * 10: base = b_tot * (t.t10 or 0.0)
                elif p_val <= b_tot * 20: base = b_tot * (t.t20 or 0.0)
                else: base = b_tot * (t.t30 or 0.0)
                
                excedente_kg = max(0.0, p_val - (b_tot * 30))
                costo_exc = excedente_kg * (t.excedente or 0.0)
                return base + costo_exc
            else:
                loc_limpia = loc.strip()
                # ... ACÁ ABAJO DEJÁS INTACTO TU CÓDIGO ORIGINAL ...
                t = self.session.query(Tarifa).filter(Tarifa.localidad.ilike(loc_limpia), Tarifa.sucursal == suc).first()
                if not t: return 0.0
                if cant_comun > 0 and cant_frio > 0:
                    bultos_tot = cant_comun + cant_frio
                    multiplicador = math.ceil(bultos_tot / 3)
                    return multiplicador * t.precio_base_refrig
                else:
                    costo_comun = math.ceil(cant_comun / 3) * t.precio_base_comun if cant_comun > 0 else 0
                    costo_frio = math.ceil(cant_frio / 3) * t.precio_base_refrig if cant_frio > 0 else 0
                    return costo_comun + costo_frio
        except Exception: self.session.rollback(); return 0.0

    def eliminar_fila(self, tabla, Modelo):
        r = tabla.currentRow(); 
        if r < 0: QMessageBox.warning(self, "Atención", "Seleccione la fila que desea eliminar."); return
        id_item = tabla.item(r, 0)
        if not id_item: return
        texto_confirm = "este elemento"
        if tabla.columnCount() > 2:
            item_desc = tabla.item(r, 2)
            if item_desc: texto_confirm = item_desc.text()
        box = QMessageBox(self); box.setWindowTitle("Confirmar Eliminación"); box.setText(f"¿Seguro que desea eliminar: {texto_confirm}?"); box.setIcon(QMessageBox.Icon.Question)
        btn_si = box.addButton("Sí, Eliminar", QMessageBox.ButtonRole.YesRole); btn_no = box.addButton("Cancelar", QMessageBox.ButtonRole.NoRole); box.exec()
        if box.clickedButton() != btn_si: return
        try: 
            id_obj = int(id_item.text()); self.session.delete(self.session.query(Modelo).get(id_obj)); self.session.commit(); tabla.removeRow(r)
            self.actualizar_combos_dinamicos(); self.statusBar().showMessage("🗑️ Eliminado correctamente", 3000)
        except Exception as e: self.session.rollback(); QMessageBox.critical(self, "Error", f"No se pudo eliminar: {e}")

    def abrir_edicion(self, tabla):
        r = tabla.currentRow(); id_op = None
        if r >= 0: id_op = int(tabla.item(r, 0).text())
        else:
            for i in range(tabla.rowCount()):
                if tabla.item(i, 1).checkState() == Qt.CheckState.Checked: id_op = int(tabla.item(i, 0).text()); break
        if not id_op: QMessageBox.warning(self, "Error", "Seleccione una fila para editar."); return
        try:
            op = self.session.query(Operacion).get(id_op)
            if op:
                dlg = EditarOperacionDialog(op, self.session, self)
                if dlg.exec() == QDialog.DialogCode.Accepted:
                    if tabla == self.tabla_ruta: self.cargar_ruta()
                    elif hasattr(self, 'tab_rendicion') and tabla == self.tab_rendicion.tabla_rendicion: self.tab_rendicion.cargar_rendicion()
                    elif hasattr(self, 'tab_ingreso') and tabla == self.tab_ingreso.tabla_ingresos: self.tab_ingreso.cargar_movimientos_dia()
                    self.cargar_monitor_global()
        except Exception: self.session.rollback()

    def setup_monitor(self):
        layout = QVBoxLayout(self.tab_monitor)
        self.tabs_internas_monitor = QTabWidget()
        tab_tabla = QWidget(); layout_tabla = QVBoxLayout(tab_tabla); top_bar = QHBoxLayout()
        
        filtros_layout = QFormLayout()
        self.mon_date = QDateEdit(QDate.currentDate()); self.mon_date.setCalendarPopup(True); self.mon_date.dateChanged.connect(self.cargar_monitor_global)
        
        self.mon_chofer_combo = QComboBox()
        self.mon_chofer_combo.setMinimumWidth(200)
        self.mon_chofer_combo.addItem("Todos")
        self.mon_chofer_combo.currentTextChanged.connect(self.cargar_monitor_global)
        
        btn_refresh = QPushButton("🔄 Actualizar Ahora")
        btn_refresh.setStyleSheet("background-color: #1565c0; color: white; font-weight: bold; padding: 4px 12px; border-radius: 4px;")
        btn_refresh.clicked.connect(lambda: {self.cargar_monitor_global(), self.cargar_novedades()})
        
        # Agrupamos el combo y el botón en una misma línea horizontal
        h_chofer_btn = QHBoxLayout()
        h_chofer_btn.setContentsMargins(0, 0, 0, 0)
        h_chofer_btn.addWidget(self.mon_chofer_combo)
        h_chofer_btn.addWidget(btn_refresh)
        
        filtros_layout.addRow("Fecha:", self.mon_date)
        filtros_layout.addRow("Chofer:", h_chofer_btn) # Acá inyectamos la línea combinada
        
        self.lbl_mini_dash = QLabel("Cargando métricas...")
        self.lbl_mini_dash.setStyleSheet("""
            background-color: #f8f9fa; 
            border: 1px solid #ced4da; 
            border-radius: 6px; 
            padding: 10px; 
            font-size: 13px;
        """)
        self.lbl_mini_dash.setWordWrap(True)
        self.lbl_mini_dash.setMinimumWidth(750) # 🔥 ENSANCHADO AL MÁXIMO 🔥

        top_bar.addLayout(filtros_layout)
        top_bar.addStretch() 
        top_bar.addWidget(self.lbl_mini_dash)
        
        self.tabla_monitor = QTableWidget(); self.tabla_monitor.setColumnCount(8); 
        self.tabla_monitor.setHorizontalHeaderLabels(["Estado", "Guía", "Cliente", "Destinatario", "Domicilio / Novedad", "Zona", "Bultos", "Chofer"])
        self.pintor = PintorCeldasDelegate(self.tabla_monitor); self.tabla_monitor.setItemDelegate(self.pintor)
        
        header = self.tabla_monitor.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tabla_monitor.setColumnWidth(0, 130)  
        self.tabla_monitor.setColumnWidth(1, 140)  
        self.tabla_monitor.setColumnWidth(2, 180)  
        self.tabla_monitor.setColumnWidth(3, 250)  
        self.tabla_monitor.setColumnWidth(4, 350)  
        self.tabla_monitor.setColumnWidth(5, 150)  
        self.tabla_monitor.setColumnWidth(6, 80)   
        header.setStretchLastSection(True)         
        
        self.tabla_monitor.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.tabla_monitor.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        legend = QHBoxLayout()
        def create_filter_btn(texto, filtro_val, color_bg):
            btn = QPushButton(texto); btn.setStyleSheet(f"background-color: {color_bg} !important; color: #000000 !important; font-weight: bold !important; border-radius: 4px !important; padding: 8px 12px !important; border: 1px solid #ccc !important;")
            btn.clicked.connect(lambda: self.aplicar_filtro_monitor(filtro_val)); return btn
        legend.addWidget(create_filter_btn("🔵 EN DEPOSITO", "EN DEPOSITO", "#e3f2fd")); legend.addWidget(create_filter_btn("🟡 EN REPARTO", Estados.EN_REPARTO, "#fff3cd")); legend.addWidget(create_filter_btn("🟣 REPROGRAMADO", "REPROGRAMADO", "#e2d9f3")); legend.addWidget(create_filter_btn("🟢 ENTREGADO", Estados.ENTREGADO, "#d4edda")); legend.addWidget(create_filter_btn("⚪ VER TODOS", None, "#ffffff")); legend.addStretch()
        layout_tabla.addLayout(top_bar); layout_tabla.addWidget(self.tabla_monitor); layout_tabla.addLayout(legend)
        tab_novedades = QWidget(); layout_novedades = QVBoxLayout(tab_novedades)
        btn_ref_nov = QPushButton("🔄 Actualizar Novedades"); btn_ref_nov.clicked.connect(self.cargar_novedades)
        self.lista_novedades = QListWidget(); self.lista_novedades.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection); self.lista_novedades.setStyleSheet("font-size: 14px; padding: 10px;")
        layout_novedades.addWidget(btn_ref_nov); layout_novedades.addWidget(self.lista_novedades)
        self.tabs_internas_monitor.addTab(tab_tabla, "📋 Listado de Guías"); self.tabs_internas_monitor.addTab(tab_novedades, "🔔 Últimas Novedades y Auditoría"); layout.addWidget(self.tabs_internas_monitor)
    def aplicar_filtro_monitor(self, filtro):
        self.filtro_monitor = filtro; self.cargar_monitor_global()

    def cargar_novedades(self):
        try:
            self.lista_novedades.clear()
            sql = text("SELECT h.fecha_hora, h.detalle, o.guia_remito, h.usuario, h.accion FROM historial_movimientos h JOIN operaciones o ON h.operacion_id = o.id WHERE o.sucursal = :s ORDER BY h.fecha_hora DESC LIMIT 100")
            logs = self.session.execute(sql, {"s": self.sucursal_actual}).fetchall()
            for log in logs:
                hora = log[0].strftime("%d/%m %H:%M:%S") if log[0] else ""
                guia = log[2] or "S/G"; detalle = log[1] or ""; usuario = log[3]; accion = log[4] or ""
                texto = f"{hora} | {guia} | {usuario} | {accion}: {detalle}"
                item = QListWidgetItem() 
                if "Reprogramado" in detalle or "Motivo" in detalle or "No Entregado" in detalle or "REPROGRAMADO" in accion: 
                    item.setBackground(QColor("#f8d7da")); item.setForeground(QColor("#721c24")); item.setFont(QFont("Arial", 10, QFont.Weight.Bold)); item.setText(f"⚠️ {texto}")
                elif "Recibio" in detalle or "ENTREGA" in accion or "ENTREGADO" in accion: 
                    item.setBackground(QColor("#d4edda")); item.setForeground(QColor("#155724")); item.setText(f"✅ {texto}")
                elif "REPARTO" in accion or "TERCERIZADO" in accion:
                    item.setBackground(QColor("#fff3cd")); item.setForeground(QColor("#856404")); item.setText(f"🚚 {texto}")
                elif "INGRESO" in accion:
                    item.setBackground(QColor("#e2e3e5")); item.setForeground(QColor("#383d41")); item.setText(f"📥 {texto}")
                else: item.setText(f"ℹ️ {texto}")
                self.lista_novedades.addItem(item)
        except Exception: self.session.rollback()

    def cargar_monitor_global(self):
        try:
            self.tabla_monitor.blockSignals(True); self.tabla_monitor.setUpdatesEnabled(False); self.tabla_monitor.setRowCount(0); QApplication.processEvents()
            fecha_sel = self.mon_date.date().toPyDate(); chofer_sel = self.mon_chofer_combo.currentText()
            query = self.session.query(Operacion).filter(
                (Operacion.fecha_ingreso == fecha_sel) | 
                (text("DATE(fecha_salida) = :f").bindparams(f=fecha_sel)) |
                (text("DATE(fecha_entrega) = :f").bindparams(f=fecha_sel)) |
                (Operacion.id.in_(self.session.query(Historial.operacion_id).filter(text("DATE(fecha_hora) = :f").bindparams(f=fecha_sel))))
            ).filter(Operacion.sucursal == self.sucursal_actual)
            
            if chofer_sel != "Todos": query = query.filter(Operacion.chofer_asignado == chofer_sel)
            ops = query.order_by(Operacion.id.desc()).all()
            if not ops: self.tabla_monitor.setUpdatesEnabled(True); self.tabla_monitor.blockSignals(False); return
            all_op_ids = [op.id for op in ops]; estados_deposito = ["EN DEPOSITO", "EN DEPÓSITO"]
            op_ids_deposito = [op.id for op in ops if (op.estado or "").upper() in estados_deposito]
            reprogramados_set = set()
            if op_ids_deposito:
                hist_records = self.session.query(Historial.operacion_id).filter(Historial.operacion_id.in_(op_ids_deposito), Historial.accion.ilike('%REPROGRAMADO%')).all()
                reprogramados_set = {r[0] for r in hist_records}
            gps_dict = {}
            if all_op_ids:
                gps_records = self.session.query(Historial.operacion_id, Historial.detalle).filter(Historial.operacion_id.in_(all_op_ids), Historial.detalle.like('%| GPS:%')).order_by(Historial.id.asc()).all()
                for op_id, detalle in gps_records: gps_dict[op_id] = detalle 
                    
            # Variables para el Mini-Dashboard
            c_estados = {}
            c_tipos = {"Entregas": 0, "Retiros": 0, "Fletes": 0}
            c_choferes = {}
                    
            for r, op in enumerate(ops):
                estado_visual = op.estado; bg_color = QColor("#ffffff"); txt_color_main = QColor("#000000") 
                if op.estado == Estados.ENTREGADO: bg_color = QColor("#d4edda"); txt_color_estado = QColor("#155724")
                elif op.estado == Estados.EN_REPARTO: bg_color = QColor("#fff3cd"); txt_color_estado = QColor("#856404")
                elif op.estado == Estados.DEVUELTO_ORIGEN: bg_color = QColor("#ffe8d6"); txt_color_estado = QColor("#fd7e14")
                elif (op.estado or "").upper() in estados_deposito:
                    if op.id in reprogramados_set: bg_color = QColor("#e2d9f3"); txt_color_estado = QColor("#4b0082"); estado_visual = "REPROGRAMADO"
                    else: bg_color = QColor("#e3f2fd"); txt_color_estado = QColor("#0c5460"); estado_visual = "EN DEPOSITO"
                
                if self.filtro_monitor:
                    if self.filtro_monitor == "REPROGRAMADO" and estado_visual != "REPROGRAMADO": continue
                    elif self.filtro_monitor == "EN DEPOSITO" and estado_visual != "EN DEPOSITO": continue
                    elif self.filtro_monitor not in ["REPROGRAMADO", "EN DEPOSITO"] and op.estado != self.filtro_monitor: continue
                
                # Sumatorias para el Mini-Dashboard
                c_estados[estado_visual] = c_estados.get(estado_visual, 0) + 1
                
                t_serv = op.tipo_servicio or ""
                if "Retiro" in t_serv: c_tipos["Retiros"] += 1
                elif "Flete" in t_serv: c_tipos["Fletes"] += 1
                else: c_tipos["Entregas"] += 1
                
                chof = op.chofer_asignado or "Sin Asignar"
                c_choferes[chof] = c_choferes.get(chof, 0) + 1

                row_idx = self.tabla_monitor.rowCount(); self.tabla_monitor.insertRow(row_idx)
                guia_texto = op.guia_remito or "-"
                if op.tipo_servicio and "Retiro" in op.tipo_servicio: guia_texto = f"🔄 {guia_texto}"
                elif op.tipo_servicio and "Flete" in op.tipo_servicio: guia_texto = f"⏱️ {guia_texto}"
                
                self.tabla_monitor.setItem(row_idx, 0, QTableWidgetItem(estado_visual)); self.tabla_monitor.setItem(row_idx, 1, QTableWidgetItem(guia_texto)); self.tabla_monitor.setItem(row_idx, 2, QTableWidgetItem(op.proveedor)); self.tabla_monitor.setItem(row_idx, 3, QTableWidgetItem(op.destinatario))
                extra = ""
                if op.es_contra_reembolso and op.monto_recaudacion: extra += f"Cobrar ${op.monto_recaudacion} "
                if op.info_intercambio: extra += op.info_intercambio
                domicilio_full = op.domicilio
                if extra: domicilio_full += f" | Obs: {extra}"
                detalle_gps = gps_dict.get(op.id)
                if detalle_gps:
                    try:
                        link = detalle_gps.split("| GPS:")[1].strip()
                        dom_html = f'<div style="background-color:transparent;">{domicilio_full} <a href="{link}" style="color:#d32f2f; text-decoration:none; font-weight:bold; font-size:13px;">[📍 MAPA]</a></div>'
                        lbl = QLabel(dom_html); lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft); lbl.setOpenExternalLinks(True); lbl.setStyleSheet("background-color: transparent; padding-left: 5px;") 
                        self.tabla_monitor.setCellWidget(row_idx, 4, lbl); self.tabla_monitor.setItem(row_idx, 4, QTableWidgetItem("")) 
                    except: self.tabla_monitor.setItem(row_idx, 4, QTableWidgetItem(domicilio_full))
                else: self.tabla_monitor.setItem(row_idx, 4, QTableWidgetItem(domicilio_full))
                self.tabla_monitor.setItem(row_idx, 5, QTableWidgetItem(op.localidad)); self.tabla_monitor.setItem(row_idx, 6, QTableWidgetItem(str(op.bultos))); self.tabla_monitor.setItem(row_idx, 7, QTableWidgetItem(op.chofer_asignado or "-"))
                brush_bg = QBrush(bg_color)
                for col_idx in range(8):
                    it = self.tabla_monitor.item(row_idx, col_idx)
                    if it:
                        it.setBackground(brush_bg)
                        if col_idx == 0: font = QFont(); font.setBold(True); it.setFont(font); it.setForeground(txt_color_estado)
                        else: it.setForeground(txt_color_main)
            # 🔥 CONSTRUIR Y ACTUALIZAR EL MINI-DASHBOARD 🔥
            # Formateamos como listas verticales con viñetas
            txt_est = "<br>".join([f"&nbsp;&nbsp;• {k}: <b>{v}</b>" for k, v in sorted(c_estados.items(), key=lambda x: x[1], reverse=True)])
            
            txt_tipos = f"&nbsp;&nbsp;• Entregas: <b>{c_tipos['Entregas']}</b><br>&nbsp;&nbsp;• Retiros: <b>{c_tipos['Retiros']}</b>"
            if c_tipos['Fletes'] > 0: txt_tipos += f"<br>&nbsp;&nbsp;• Fletes: <b>{c_tipos['Fletes']}</b>"
            
            txt_chof = "<br>".join([f"&nbsp;&nbsp;• {k}: <b>{v}</b>" for k, v in sorted(c_choferes.items(), key=lambda x: x[1], reverse=True)])
            
            if not ops:
                dash_html = "<span style='color: #6c757d;'>No hay guías para la fecha seleccionada.</span>"
            else:
                dash_html = f"""
                <div style='color: #333; font-family: sans-serif; font-size: 13px; line-height: 1.6;'>
                    <table width='100%' style='margin: 0; padding: 0;'>
                        <tr>
                            <td width='33%' valign='top'>
                                <b>ESTADOS</b><br>{txt_est}
                            </td>
                            <td width='33%' valign='top' style='border-left: 1px solid #ccc; padding-left: 15px;'>
                                <b>TIPOS DE SERVICIO</b><br>{txt_tipos}
                            </td>
                            <td width='33%' valign='top' style='border-left: 1px solid #ccc; padding-left: 15px;'>
                                <b>TOP CHOFERES</b><br>{txt_chof}
                            </td>
                        </tr>
                    </table>
                </div>
                """
            
            if hasattr(self, 'lbl_mini_dash'):
                self.lbl_mini_dash.setText(dash_html)

            self.tabla_monitor.setUpdatesEnabled(True); self.tabla_monitor.blockSignals(False)
        except Exception: 
            self.session.rollback()
            self.tabla_monitor.setUpdatesEnabled(True); self.tabla_monitor.blockSignals(False)
    def setup_ruta(self):
        l = QVBoxLayout(self.tab_ruta); top_row1 = QHBoxLayout(); top_row2 = QHBoxLayout()
        
        self.combo_masivo_chofer = QComboBox()
        self.combo_masivo_chofer.setMinimumWidth(250)
        
        self.txt_filtro_ruta = QLineEdit(); self.txt_filtro_ruta.setPlaceholderText("🔎 Filtrar por Guía, Cliente, Destino..."); self.txt_filtro_ruta.textChanged.connect(self.filtrar_tabla_ruta)
        btn_aplicar_masivo = QPushButton("ASIGNAR GUÍAS"); btn_aplicar_masivo.clicked.connect(self.asignar_chofer_masivo)
        btn_mark = QPushButton("☑️ Seleccionar Todo"); btn_mark.clicked.connect(lambda: self.toggle_seleccion_todo(self.tabla_ruta))
        btn_tercerizado = QPushButton("🚚 TERCERIZADOS"); btn_tercerizado.clicked.connect(self.generar_pdf_terc)
        
        btn_reimprimir = QPushButton("🖨️ REIMPRIMIR RUTA DE HOY")
        btn_reimprimir.setStyleSheet("background-color: #6f42c1 !important; color: white !important;")
        btn_reimprimir.clicked.connect(self.reimprimir_ruta_completa)
        
        btn_reprog = QPushButton("📅 CAMBIAR FECHA"); btn_reprog.clicked.connect(self.cambiar_fecha_ruta)
        btn_historial = QPushButton("📜 HISTORIAL"); btn_historial.clicked.connect(self.abrir_historial_hojas)
        btn_editar = QPushButton("✏️ EDITAR"); btn_editar.clicked.connect(lambda: self.abrir_edicion(self.tabla_ruta))
        btn_ref = QPushButton("🔄 Actualizar"); btn_ref.clicked.connect(self.cargar_ruta)
        
        top_row1.addWidget(QLabel("Seleccionar Chofer:")); top_row1.addWidget(self.combo_masivo_chofer); top_row1.addWidget(btn_aplicar_masivo); top_row1.addWidget(btn_mark); top_row1.addWidget(btn_tercerizado); top_row1.addWidget(btn_reimprimir); top_row1.addStretch()
        top_row2.addWidget(self.txt_filtro_ruta); top_row2.addWidget(btn_reprog); top_row2.addWidget(btn_editar); top_row2.addWidget(btn_historial); top_row2.addWidget(btn_ref)
        
        self.tabla_ruta = QTableWidget(); self.tabla_ruta.setColumnCount(10); self.tabla_ruta.setHorizontalHeaderLabels(["ID", "Sel.", "Guía", "Proveedor", "Destinatario", "Domicilio", "Localidad", "Bultos/Hs", "Cobro / Obs", "Estado"]); self.tabla_ruta.hideColumn(0); 
        
        header_ruta = self.tabla_ruta.horizontalHeader()
        header_ruta.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tabla_ruta.setColumnWidth(1, 40)   
        self.tabla_ruta.setColumnWidth(2, 140)  
        self.tabla_ruta.setColumnWidth(3, 180)  
        self.tabla_ruta.setColumnWidth(4, 250)  
        self.tabla_ruta.setColumnWidth(5, 350)  
        self.tabla_ruta.setColumnWidth(6, 150)  
        self.tabla_ruta.setColumnWidth(7, 90)   
        self.tabla_ruta.setColumnWidth(8, 150)  
        header_ruta.setStretchLastSection(True) 
        
        self.tabla_ruta.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.tabla_ruta.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        l.addLayout(top_row1); l.addLayout(top_row2); l.addWidget(self.tabla_ruta)
    
    def filtrar_tabla_ruta(self, texto):
        texto = texto.lower()
        for r in range(self.tabla_ruta.rowCount()):
            mostrar = False
            for c in [2, 3, 4, 5, 6, 9]: 
                item = self.tabla_ruta.item(r, c)
                if item and texto in item.text().lower(): mostrar = True; break
            self.tabla_ruta.setRowHidden(r, not mostrar)

    def abrir_historial_hojas(self): d = HistorialHojasRutaDialog(self.session, self.sucursal_actual, self); d.exec()

    def cargar_ruta(self):
        try:
            seleccionados = set(); 
            for r in range(self.tabla_ruta.rowCount()):
                if self.tabla_ruta.item(r, 1).checkState() == Qt.CheckState.Checked: seleccionados.add(self.tabla_ruta.item(r, 0).text())
            self.tabla_ruta.blockSignals(True); self.tabla_ruta.setRowCount(0); 
            estados_deposito = [Estados.EN_DEPOSITO, 'EN DEPOSITO', 'En Depósito', 'En Deposito', 'EN DEPÓSITO']
            
            ops = self.session.query(Operacion).filter(
                Operacion.estado.in_(estados_deposito), 
                Operacion.sucursal == self.sucursal_actual,
                text("DATE(COALESCE(fecha_salida, fecha_ingreso)) <= CURRENT_DATE")
            ).order_by(Operacion.domicilio.asc()).all()
            
            op_ids = [op.id for op in ops]; last_hists = {}
            if op_ids:
                h_records = self.session.query(Historial).filter(Historial.operacion_id.in_(op_ids)).order_by(Historial.id.asc()).all()
                for h in h_records: last_hists[h.operacion_id] = h
            tiene_cobro_general = False
            for row, op in enumerate(ops):
                self.tabla_ruta.insertRow(row); self.tabla_ruta.setItem(row, 0, QTableWidgetItem(str(op.id)))
                chk = QTableWidgetItem(); chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
                if str(op.id) in seleccionados: chk.setCheckState(Qt.CheckState.Checked)
                else: chk.setCheckState(Qt.CheckState.Unchecked)
                self.tabla_ruta.setItem(row, 1, chk)
                
                guia_texto = op.guia_remito or "-"
                if op.tipo_servicio and "Retiro" in op.tipo_servicio: guia_texto = f"🔄 [RETIRO] {guia_texto}"
                elif op.tipo_servicio and "Flete" in op.tipo_servicio: guia_texto = f"⏱️ {guia_texto}"
                
                self.tabla_ruta.setItem(row, 2, QTableWidgetItem(guia_texto)); self.tabla_ruta.setItem(row, 3, QTableWidgetItem(op.proveedor)); self.tabla_ruta.setItem(row, 4, QTableWidgetItem(op.destinatario)); self.tabla_ruta.setItem(row, 5, QTableWidgetItem(op.domicilio)); self.tabla_ruta.setItem(row, 6, QTableWidgetItem(op.localidad))
                det_b = str(op.bultos); 
                if op.bultos_frio and op.bultos_frio > 0 and op.bultos_frio < op.bultos: det_b += f" ({op.bultos-op.bultos_frio}C/{op.bultos_frio}R)"
                elif op.bultos_frio == op.bultos: det_b += " (R)"
                self.tabla_ruta.setItem(row, 7, QTableWidgetItem(det_b))
                estado_visual = op.estado; hist = last_hists.get(op.id); es_reprogramado = False
                if hist:
                    if 'Reprogramado' in (hist.detalle or "") or 'REPROGRAMADO' in (hist.accion or ""):
                        es_reprogramado = True; match = re.search(r'(\d{2}/\d{2}/\d{4})', hist.detalle or "")
                        if match: estado_visual = f"REPROG. ({match.group(1)[:5]})" 
                        else: estado_visual = "REPROGRAMADO"
                it_estado = QTableWidgetItem(estado_visual)
                if es_reprogramado: it_estado.setForeground(QColor("#9c27b0")); it_estado.setFont(QFont("Arial", 9, QFont.Weight.Bold))
                self.tabla_ruta.setItem(row, 9, it_estado)
                extra_txt = ""
                if op.es_contra_reembolso and op.monto_recaudacion and op.monto_recaudacion > 0: extra_txt += f"COBRAR ${op.monto_recaudacion} "
                if op.info_intercambio: extra_txt += f"| {op.info_intercambio}" if extra_txt else f"{op.info_intercambio}"
                if es_reprogramado and hist and hist.detalle:
                    motivo_limpio = hist.detalle.split("Motivo:")[-1].strip() if "Motivo:" in hist.detalle else "Sin motivo"
                    if "| GPS:" in motivo_limpio: motivo_limpio = motivo_limpio.split("| GPS:")[0].strip()
                    extra_txt += f" | Obs: {motivo_limpio}" if extra_txt else f"Obs: {motivo_limpio}"
                if extra_txt.strip(): tiene_cobro_general = True
                it_extra = QTableWidgetItem(extra_txt.strip()); 
                if op.es_contra_reembolso: it_extra.setForeground(QColor("red"))
                self.tabla_ruta.setItem(row, 8, it_extra)
            if tiene_cobro_general: self.tabla_ruta.showColumn(8)
            else: self.tabla_ruta.hideColumn(8)
        except Exception: self.session.rollback()
        finally: self.tabla_ruta.blockSignals(False)

    def cambiar_fecha_ruta(self):
        ids = []
        for r in range(self.tabla_ruta.rowCount()):
            if self.tabla_ruta.item(r, 1).checkState() == Qt.CheckState.Checked: 
                ids.append(int(self.tabla_ruta.item(r, 0).text()))
        if not ids: 
            QMessageBox.warning(self, "Atención", "Seleccione al menos un envío para cambiar la fecha.")
            return
        try:
            titulo_dlg = f"{len(ids)} guías seleccionadas" if len(ids) > 1 else (self.session.query(Operacion).get(ids[0]).guia_remito or f"ID {ids[0]}")
            dlg = CambiarFechaDialog(titulo_dlg, self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                detalle = f"Reprogramado para el {dlg.fecha_str}. Motivo: {dlg.motivo}"; nueva_fecha = datetime.combine(dlg.in_fecha.date().toPyDate(), datetime.min.time())
                ops = self.session.query(Operacion).filter(Operacion.id.in_(ids)).all()
                for op in ops: op.fecha_salida = nueva_fecha; self.log_movimiento(op, "REPROGRAMADO (OFICINA)", detalle)
                self.session.commit(); self.toast.mostrar(f"✅ {len(ids)} guía(s) reprogramada(s)"); self.cargar_ruta()
                if hasattr(self, 'tab_ingreso'): self.tab_ingreso.cargar_movimientos_dia()
                self.cargar_monitor_global()
        except Exception: self.session.rollback()

    def asignar_chofer_masivo(self):
        chofer = self.combo_masivo_chofer.currentText()
        if not chofer: return
        ids = []
        for r in range(self.tabla_ruta.rowCount()):
            if self.tabla_ruta.item(r, 1).checkState() == Qt.CheckState.Checked: ids.append(int(self.tabla_ruta.item(r, 0).text()))
        if not ids: QMessageBox.warning(self, "Atención", "Seleccione al menos un envío."); return
        box = QMessageBox(self); box.setWindowTitle("Confirmar Asignación"); box.setText(f"¿Está seguro de asignar {len(ids)} guías al chofer {chofer}?"); box.setIcon(QMessageBox.Icon.Question); btn_si = box.addButton("Sí, Asignar", QMessageBox.ButtonRole.YesRole); btn_no = box.addButton("Cancelar", QMessageBox.ButtonRole.NoRole); box.exec()
        if box.clickedButton() != btn_si: return 
        try:
            ops = self.session.query(Operacion).filter(Operacion.id.in_(ids)).all(); now = datetime.now()
            for op in ops: op.chofer_asignado = chofer; op.estado = Estados.EN_REPARTO; op.fecha_salida = now; self.log_movimiento(op, "SALIDA A REPARTO", f"Asignado a {chofer}")
            self.session.commit()
            try:
                res_cel = self.session.execute(text("SELECT celular FROM choferes WHERE nombre = :n"), {"n": chofer}).fetchone()
                if res_cel and res_cel[0]:
                    cel_chofer = "".join(filter(str.isdigit, str(res_cel[0])))
                    if cel_chofer:
                        msg_wsp = QMessageBox(self); msg_wsp.setWindowTitle("Aviso por WhatsApp"); msg_wsp.setText(f"✅ Guías asignadas a {chofer}.\n¿Deseas avisarle por WhatsApp?"); msg_wsp.setIcon(QMessageBox.Icon.Question); btn_wsp_si = msg_wsp.addButton("Sí, avisar", QMessageBox.ButtonRole.YesRole); btn_wsp_no = msg_wsp.addButton("No", QMessageBox.ButtonRole.NoRole); msg_wsp.exec()
                        if msg_wsp.clickedButton() == btn_wsp_si:
                            if not cel_chofer.startswith("54"): cel_chofer = "549" + cel_chofer
                            mensaje = f"🚨 Hola {chofer}, te acabo de agregar {len(ids)} envío(s) a tu ruta. ¡Por favor revisá la App para ver los detalles!"
                            url = f"https://web.whatsapp.com/send?phone={cel_chofer}&text={urllib.parse.quote(mensaje)}"
                            QDesktopServices.openUrl(QUrl(url))
            except Exception: pass
            box2 = QMessageBox(self); box2.setWindowTitle("Imprimir Hoja de Ruta"); box2.setText("¿Desea generar el PDF de Hoja de Ruta ahora?"); box2.setIcon(QMessageBox.Icon.Question); btn_si2 = box2.addButton("Sí, Imprimir", QMessageBox.ButtonRole.YesRole); btn_no2 = box2.addButton("No", QMessageBox.ButtonRole.NoRole); box2.exec()
            if box2.clickedButton() == btn_si2: self.generar_pdf_ruta(ids_forzados=ids)
            self.cargar_ruta(); self.cargar_monitor_global()
        except Exception: self.session.rollback()
        
    def toggle_seleccion_todo(self, tabla):
        rows = tabla.rowCount(); 
        if rows == 0: return
        estado = Qt.CheckState.Checked if tabla.item(0, 1).checkState() == Qt.CheckState.Unchecked else Qt.CheckState.Unchecked
        for r in range(rows): tabla.item(r, 1).setCheckState(estado)
        
    def reimprimir_ruta_completa(self):
        chofer_filtro = self.combo_masivo_chofer.currentText()
        if not chofer_filtro: 
            QMessageBox.warning(self, "Atención", "Seleccione un chofer de la lista.")
            return
        try:
            ops = self.session.query(Operacion).filter(
                Operacion.chofer_asignado == chofer_filtro,
                text("DATE(fecha_salida) = CURRENT_DATE")
            ).all()
            if not ops:
                QMessageBox.warning(self, "Sin viajes", f"El chofer {chofer_filtro} no tiene ninguna guía asignada en el día de hoy.")
                return
            descargas_dir = os.path.join(os.path.expanduser('~'), 'Downloads')
            if not os.path.exists(descargas_dir): os.makedirs(descargas_dir, exist_ok=True)
            ruta_pdf = os.path.join(descargas_dir, f"Ruta_COMPLETA_{chofer_filtro}_{datetime.now().strftime('%d-%m-%Y_%H%M')}.pdf")
            crear_pdf_ruta(ruta_pdf, ops, self.sucursal_actual, chofer_filtro, self.usuario.username, datetime.now().strftime('%d/%m/%Y %H:%M'))
            try: os.startfile(ruta_pdf)
            except: pass
            self.toast.mostrar(f"✅ Hoja de ruta completa generada ({len(ops)} guías)")
        except Exception as e:
            self.session.rollback()
            QMessageBox.critical(self, "Error", f"Ocurrió un error: {e}")

    def generar_pdf_ruta(self, ids_forzados=None, nombre_sufijo=""):
        chofer_filtro = self.combo_masivo_chofer.currentText()
        try:
            if ids_forzados: 
                op_test = self.session.query(Operacion).get(ids_forzados[0])
                if op_test: chofer_filtro = op_test.chofer_asignado
            if not chofer_filtro: QMessageBox.warning(self, "Error", "Seleccione un chofer."); return
            ids = []
            if ids_forzados: ids = ids_forzados
            else:
                for r in range(self.tabla_ruta.rowCount()):
                    if self.tabla_ruta.item(r, 1).checkState() == Qt.CheckState.Checked: ids.append(int(self.tabla_ruta.item(r, 0).text()))
                if not ids: return
                ops_upd = self.session.query(Operacion).filter(Operacion.id.in_(ids)).all()
                for op in ops_upd: op.chofer_asignado = chofer_filtro; op.estado = Estados.EN_REPARTO; op.fecha_salida = datetime.now(); self.log_movimiento(op, "SALIDA A REPARTO", f"Asignado a {chofer_filtro}")
                self.session.commit(); self.cargar_ruta()
            
            ops = self.session.query(Operacion).filter(Operacion.id.in_(ids)).all()
            
            descargas_dir = os.path.join(os.path.expanduser('~'), 'Downloads')
            if not os.path.exists(descargas_dir): os.makedirs(descargas_dir, exist_ok=True)
            ruta_pdf = os.path.join(descargas_dir, f"Ruta_{chofer_filtro}_{datetime.now().strftime('%d-%m')}{nombre_sufijo}.pdf")
            
            crear_pdf_ruta(ruta_pdf, ops, self.sucursal_actual, chofer_filtro, self.usuario.username, datetime.now().strftime('%d/%m/%Y %H:%M'))
            try: os.startfile(ruta_pdf)
            except: pass
        except Exception: self.session.rollback()

    def generar_pdf_terc(self):
        transporte, ok = QInputDialog.getText(self, "Transporte Tercerizado", "Nombre del Transporte / Empresa:")
        if not ok or not transporte: return
        ids = []
        for r in range(self.tabla_ruta.rowCount()):
            if self.tabla_ruta.item(r, 1).checkState() == Qt.CheckState.Checked: ids.append(int(self.tabla_ruta.item(r, 0).text()))
        if not ids: return
        try:
            ops = self.session.query(Operacion).filter(Operacion.id.in_(ids)).all()
            for op in ops:
                op.chofer_asignado = f"TERCERIZADO: {transporte}"
                if op.estado != Estados.EN_REPARTO: self.log_movimiento(op, "SALIDA A TERCERIZADO", f"Entregado a {transporte}")
                op.estado = Estados.EN_REPARTO; op.fecha_salida = datetime.now() 
            self.session.commit(); self.cargar_ruta()
            
            descargas_dir = os.path.join(os.path.expanduser('~'), 'Downloads')
            if not os.path.exists(descargas_dir): os.makedirs(descargas_dir, exist_ok=True)
            ruta_pdf = os.path.join(descargas_dir, f"Remito_{transporte}_{datetime.now().strftime('%d-%m')}.pdf")
            
            crear_pdf_tercerizados(ruta_pdf, ops, self.sucursal_actual, transporte, self.usuario.username, datetime.now().strftime('%d/%m/%Y %H:%M'))
            try: os.startfile(ruta_pdf)
            except: pass
        except Exception: self.session.rollback()

    def setup_reportes(self):
        layout = QVBoxLayout(self.tab_reportes); filtros = QGroupBox("Filtros"); flayout = QHBoxLayout()
        self.rep_fecha_desde = QDateEdit(QDate.currentDate().addDays(-30)); self.rep_fecha_hasta = QDateEdit(QDate.currentDate()); self.rep_fecha_desde.setCalendarPopup(True); self.rep_fecha_hasta.setCalendarPopup(True)
        
        self.rep_sucursal = QComboBox(); self.rep_sucursal.addItems(["Todas", "Mendoza", "San Juan"])
        self.rep_sucursal.setMinimumWidth(100) 
        
        self.rep_chofer = QComboBox()
        self.rep_chofer.setMinimumWidth(200) 
        self.rep_chofer.addItem("Todos")
        
        self.rep_cliente = QComboBox(); self.rep_cliente.addItem("Todos"); self.rep_cliente.addItems(self.lista_proveedores)
        
        self.rep_estado = QComboBox(); self.rep_estado.addItem("Todos"); self.rep_estado.addItems(Estados.LISTA_TODOS)
        
        # 🔥 NUEVO FILTRO DE TIPO 🔥
        self.rep_tipo = QComboBox()
        self.rep_tipo.addItems(["Todos", "Entrega", "Retiro", "Flete", "Cargo Extra"])
        
        self.rep_facturado = QComboBox(); self.rep_facturado.addItems(["Todos", "Facturado", "NO Facturado"]) 
        
        btn_buscar = QPushButton("🔍 Generar"); btn_buscar.clicked.connect(self.generar_reporte_avanzado)
        btn_excel = QPushButton("Excel"); btn_excel.setStyleSheet("background-color: #28a745 !important; color: white !important;"); btn_excel.clicked.connect(self.exportar_reporte_excel)
        btn_pdf_rep = QPushButton("PDF"); btn_pdf_rep.setStyleSheet("background-color: #dc3545 !important; color: white !important;"); btn_pdf_rep.clicked.connect(self.generar_pdf_rep)
        
        flayout.addWidget(QLabel("Desde:")); flayout.addWidget(self.rep_fecha_desde); flayout.addWidget(QLabel("Hasta:")); flayout.addWidget(self.rep_fecha_hasta); flayout.addWidget(QLabel("Suc:")); flayout.addWidget(self.rep_sucursal)
        flayout.addWidget(QLabel("Cliente:")); flayout.addWidget(self.rep_cliente); flayout.addWidget(QLabel("Chof:")); flayout.addWidget(self.rep_chofer); flayout.addWidget(QLabel("Est:")); flayout.addWidget(self.rep_estado)
        flayout.addWidget(QLabel("Tipo:")); flayout.addWidget(self.rep_tipo) # Agregado a la vista
        flayout.addWidget(QLabel("Fac:")); flayout.addWidget(self.rep_facturado)
        flayout.addWidget(btn_buscar); flayout.addWidget(btn_excel); flayout.addWidget(btn_pdf_rep); filtros.setLayout(flayout)
        
        self.tabla_reportes = QTableWidget(); self.tabla_reportes.setAlternatingRowColors(True); self.tabla_reportes.setColumnCount(11); 
        self.tabla_reportes.setHorizontalHeaderLabels(["Fecha", "Suc", "Cliente", "Guía", "Chofer", "Destinatario", "Zona", "Estado", "Fac?", "Bultos", "Precio"]); 
        
        header_rep = self.tabla_reportes.horizontalHeader(); 
        header_rep.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tabla_reportes.setColumnWidth(0, 90); self.tabla_reportes.setColumnWidth(1, 100); self.tabla_reportes.setColumnWidth(2, 140)
        self.tabla_reportes.setColumnWidth(3, 140); self.tabla_reportes.setColumnWidth(4, 140); self.tabla_reportes.setColumnWidth(5, 250)
        self.tabla_reportes.setColumnWidth(6, 140); self.tabla_reportes.setColumnWidth(7, 150); self.tabla_reportes.setColumnWidth(8, 70); self.tabla_reportes.setColumnWidth(9, 70)
        header_rep.setStretchLastSection(True)
        
        self.tabla_reportes.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.tabla_reportes.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        
        self.panel_resumen = QTextBrowser()
        self.panel_resumen.setOpenExternalLinks(False)
        self.panel_resumen.setMinimumHeight(250)
        self.panel_resumen.setMaximumHeight(350)
        self.panel_resumen.setStyleSheet("background-color: #f4f6f9; border: 1px solid #ced4da; border-radius: 8px;")
        
        html_inicial = "<div style='padding: 20px; font-size: 16px; color: #6c757d; text-align: center;'>Seleccione los filtros arriba y presione <b>Generar</b> para visualizar el Dashboard Gerencial.</div>"
        self.panel_resumen.setHtml(html_inicial)
        
        layout.addWidget(filtros); layout.addWidget(self.tabla_reportes); layout.addWidget(self.panel_resumen)
        
    def construir_query_reportes(self):
        f_desde = self.rep_fecha_desde.date().toPyDate(); f_hasta = self.rep_fecha_hasta.date().toPyDate()
        
        # 🔥 EL ARREGLO MÁGICO: Prioriza la fecha en que se ENTREGÓ la guía 🔥
        fecha_ref = func.coalesce(Operacion.fecha_entrega, Operacion.fecha_ingreso)
        query = self.session.query(Operacion).filter(func.date(fecha_ref) >= f_desde, func.date(fecha_ref) <= f_hasta)
        
        if self.rep_sucursal.currentText() != "Todas": query = query.filter(Operacion.sucursal == self.rep_sucursal.currentText())
        if self.rep_chofer.currentText() != "Todos": query = query.filter(Operacion.chofer_asignado == self.rep_chofer.currentText())
        
        # 🔥 ILIKE ignora si está en mayúscula o minúscula 🔥
        if self.rep_cliente.currentText() != "Todos": query = query.filter(Operacion.proveedor.ilike(self.rep_cliente.currentText()))
        
        if self.rep_estado.currentText() != "Todos": query = query.filter(Operacion.estado == self.rep_estado.currentText())
        
        tipo_sel = self.rep_tipo.currentText()
        if tipo_sel != "Todos":
            if tipo_sel == "Entrega": query = query.filter(Operacion.tipo_servicio.ilike('%Entrega%'))
            elif tipo_sel == "Retiro": query = query.filter(Operacion.tipo_servicio.ilike('%Retiro%'))
            elif tipo_sel == "Flete": query = query.filter(Operacion.tipo_servicio.ilike('%Flete%'))
            elif tipo_sel == "Cargo Extra": query = query.filter(Operacion.tipo_servicio.ilike('%Cargo%'))
            
        if self.rep_facturado.currentText() == "Facturado": query = query.filter(Operacion.facturado == True)
        elif self.rep_facturado.currentText() == "NO Facturado": query = query.filter(Operacion.facturado == False)
        
        return query.order_by(Operacion.fecha_ingreso.desc()).all()
        
    def generar_reporte_avanzado(self):
        try:
            resultados = self.construir_query_reportes()
            self.tabla_reportes.setRowCount(0)
            total_dinero = 0
            total_guias = len(resultados)
            
            # 🔥 DICCIONARIOS PARA EL DESGLOSE GERENCIAL 🔥
            desglose_est = {}
            c_cli = {}
            c_chof_general = {}
            
            for row, op in enumerate(resultados):
                # REGLA DE NEGOCIO: JETPAQ NO SUMA DINERO
                es_jetpaq = bool(op.proveedor and op.proveedor.lower() == 'jetpaq')
                precio_mostrar = 0.0 if es_jetpaq else (op.monto_servicio or 0.0)

                self.tabla_reportes.insertRow(row)
                
                # 🔥 BLINDAJE ANTI-CRASH PARA VALORES NULOS 🔥
                f_ing = op.fecha_ingreso.strftime("%d/%m/%Y") if op.fecha_ingreso else "-"
                
                self.tabla_reportes.setItem(row, 0, QTableWidgetItem(f_ing))
                self.tabla_reportes.setItem(row, 1, QTableWidgetItem(op.sucursal or "-"))
                self.tabla_reportes.setItem(row, 2, QTableWidgetItem(op.proveedor or "-"))
                self.tabla_reportes.setItem(row, 3, QTableWidgetItem(op.guia_remito or "-"))
                self.tabla_reportes.setItem(row, 4, QTableWidgetItem(op.chofer_asignado or "-"))
                self.tabla_reportes.setItem(row, 5, QTableWidgetItem(op.destinatario or "-"))
                self.tabla_reportes.setItem(row, 6, QTableWidgetItem(op.localidad or "-"))
                self.tabla_reportes.setItem(row, 7, QTableWidgetItem(op.estado or "-"))
                
                item_fac = QTableWidgetItem("SI" if op.facturado else "NO")
                if op.facturado: 
                    item_fac.setForeground(QColor("green"))
                    item_fac.setFont(QFont("Arial", 9, QFont.Weight.Bold))
                self.tabla_reportes.setItem(row, 8, item_fac)
                self.tabla_reportes.setItem(row, 9, QTableWidgetItem(str(op.bultos or 1)))
                
                if es_jetpaq:
                    item_precio = QTableWidgetItem("Uso Interno ($0)")
                    item_precio.setForeground(QColor("gray"))
                else:
                    item_precio = QTableWidgetItem(f"$ {precio_mostrar:,.2f}")
                self.tabla_reportes.setItem(row, 10, item_precio)
                
                # Sumatoria financiera (JetPaq suma 0)
                total_dinero += precio_mostrar
                
                # Extracción de datos para el desglose
                est = op.estado or "S/D"
                suc = op.sucursal or "S/D"
                chof = op.chofer_asignado or "Sin Chofer"
                cli = op.proveedor or "S/D"
                
                # Armado del árbol de Estados -> Sucursal -> Chofer
                if est not in desglose_est:
                    desglose_est[est] = {'tot': 0, 'MZA': 0, 'SJ': 0, 'choferes': {}}
                
                desglose_est[est]['tot'] += 1
                if suc == 'Mendoza': desglose_est[est]['MZA'] += 1
                elif suc == 'San Juan': desglose_est[est]['SJ'] += 1
                
                if chof not in desglose_est[est]['choferes']:
                    desglose_est[est]['choferes'][chof] = 0
                desglose_est[est]['choferes'][chof] += 1

                # Totales generales de Clientes y Choferes
                c_cli[cli] = c_cli.get(cli, 0) + 1
                c_chof_general[chof] = c_chof_general.get(chof, 0) + 1

            # 🔥 CONSTRUCCIÓN DEL DASHBOARD HTML CORPORATIVO 🔥
            html = "<div style='font-family: Arial, sans-serif; color: #333; padding: 5px;'>"
            
            # Fila Superior: Métricas Principales
            html += f"""
            <table width='100%' style='border-bottom: 2px solid #0d6efd; padding-bottom: 10px; margin-bottom: 15px;'>
                <tr>
                    <td width='50%'><span style='font-size: 22px; color: #0d6efd;'><b>📦 Volumen Total: {total_guias} Guías</b></span></td>
                    <td width='50%' align='right'><span style='font-size: 22px; color: #198754;'><b>💵 Facturación: $ {total_dinero:,.2f}</b></span></td>
                </tr>
            </table>
            """
            
            html += "<table width='100%' cellpadding='8'><tr>"
            
            # Columna Izquierda: Desglose Profundo por Estados (Formato Vertical Limpio)
            html += "<td width='60%' valign='top' style='background-color: #ffffff; border: 1px solid #dee2e6; border-radius: 6px; padding: 15px;'>"
            html += "<h3 style='color: #495057; margin-top: 0; border-bottom: 1px solid #eee; padding-bottom: 5px;'>📈 Desglose Operativo por Estado</h3>"
            
            if not desglose_est:
                html += "<span style='color: #6c757d;'>No hay datos operativos en este rango.</span>"
            
            for estado, data in sorted(desglose_est.items(), key=lambda x: x[1]['tot'], reverse=True):
                html += f"<div style='margin-bottom: 15px; padding-bottom: 15px; border-bottom: 1px dashed #e9ecef;'>"
                
                # Título del Estado
                html += f"<div style='font-size: 15px; font-weight: bold; color: #212529; margin-bottom: 8px;'>{estado} ({data['tot']})</div>"
                
                # Lista de Sucursales
                html += f"<div style='font-size: 13px; color: #495057; font-weight: bold; margin-bottom: 4px;'>SUCURSALES:</div>"
                if data['MZA'] > 0: 
                    html += f"<div style='font-size: 13px; color: #495057; margin-left: 15px; margin-bottom: 2px;'>• Mendoza: {data['MZA']}</div>"
                if data['SJ'] > 0: 
                    html += f"<div style='font-size: 13px; color: #495057; margin-left: 15px; margin-bottom: 8px;'>• San Juan: {data['SJ']}</div>"
                
                # Lista de Choferes
                html += f"<div style='font-size: 13px; color: #495057; font-weight: bold; margin-bottom: 4px;'>CHOFERES:</div>"
                for c, cant in sorted(data['choferes'].items(), key=lambda x: x[1], reverse=True):
                    html += f"<div style='font-size: 13px; color: #495057; margin-left: 15px; margin-bottom: 2px;'>• {c}: {cant}</div>"
                
                html += "</div>"
                
            html += "</td><td width='2%'></td>"
            
            # Columna Derecha: Clientes y Choferes
            html += "<td width='38%' valign='top'>"
            
            # Panel Clientes
            html += "<div style='background-color: #ffffff; border: 1px solid #dee2e6; border-radius: 6px; padding: 15px; margin-bottom: 15px;'>"
            html += "<h4 style='color: #495057; margin-top: 0; border-bottom: 1px solid #eee; padding-bottom: 5px;'>🏢 Volumen por Cliente</h4>"
            for cli, cant in sorted(c_cli.items(), key=lambda x: x[1], reverse=True)[:8]:
                html += f"<div style='font-size: 14px; margin-bottom: 6px;'>• <b>{cli}</b>: {cant} guías</div>"
            html += "</div>"
            
            # Panel Choferes
            html += "<div style='background-color: #ffffff; border: 1px solid #dee2e6; border-radius: 6px; padding: 15px;'>"
            html += "<h4 style='color: #495057; margin-top: 0; border-bottom: 1px solid #eee; padding-bottom: 5px;'>🚛 Distribución por Chofer</h4>"
            for chof, cant in sorted(c_chof_general.items(), key=lambda x: x[1], reverse=True)[:8]:
                html += f"<div style='font-size: 14px; margin-bottom: 6px;'>• <b>{chof}</b>: {cant} guías</div>"
            html += "</div>"
            
            html += "</td></tr></table></div>"
            
            self.panel_resumen.setHtml(html)
            
        except Exception as e: 
            self.session.rollback()
            # ESTE CARTEL TE VA A SALVAR LA VIDA SI VUELVE A FALLAR
            QMessageBox.critical(self, "Error en Reporte", f"Ocurrió un error al generar el reporte:\n\n{str(e)}")
        
    def generar_pdf_rep(self):
        try:
            resultados = self.construir_query_reportes()
            
            descargas_dir = os.path.join(os.path.expanduser('~'), 'Downloads')
            if not os.path.exists(descargas_dir): os.makedirs(descargas_dir, exist_ok=True)
            ruta_pdf = os.path.join(descargas_dir, f"Reporte_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self.sucursal_actual}.pdf")
            
            total_dinero = sum([op.monto_servicio for op in resultados])
            
            filtro_info = f"Desde: {self.rep_fecha_desde.text()} Hasta: {self.rep_fecha_hasta.text()}"
            if self.rep_sucursal.currentText() != "Todas": filtro_info += f" | SUC: {self.rep_sucursal.currentText()}"
            if self.rep_cliente.currentText() != "Todos": filtro_info += f" | CLI: {self.rep_cliente.currentText()}"
            if self.rep_chofer.currentText() != "Todos": filtro_info += f" | CHOF: {self.rep_chofer.currentText()}"
            if self.rep_estado.currentText() != "Todos": filtro_info += f" | ESTADO: {self.rep_estado.currentText()}"
            if self.rep_facturado.currentText() != "Todos": filtro_info += f" | FAC: {self.rep_facturado.currentText()}"
            
            crear_pdf_reporte(ruta_pdf, resultados, self.sucursal_actual, self.usuario.username, datetime.now().strftime('%d/%m/%Y %H:%M'), filtro_info, total_dinero)
            try: os.startfile(ruta_pdf)
            except: pass
        except Exception: self.session.rollback()
        
    def exportar_reporte_excel(self):
        try:
            import pandas as pd
            resultados = self.construir_query_reportes(); data = []
            for op in resultados: 
                guia_val = op.guia_remito
                
                # 🔥 FIX PARA EXCEL: CONVERTIR A NÚMERO SI SON SOLO DÍGITOS 🔥
                if guia_val and str(guia_val).strip().isdigit():
                    guia_val = int(str(guia_val).strip())
                    
                data.append({"Fecha": op.fecha_ingreso, "Sucursal": op.sucursal, "Cliente": op.proveedor, "Guia": guia_val, "Destinatario": op.destinatario, "Estado": op.estado, "Facturado": "SI" if op.facturado else "NO", "Monto": op.monto_servicio})
            df = pd.DataFrame(data)
            
            descargas_dir = os.path.join(os.path.expanduser('~'), 'Downloads')
            if not os.path.exists(descargas_dir): os.makedirs(descargas_dir, exist_ok=True)
            ruta_excel = os.path.join(descargas_dir, f"Reporte_Gestion_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
            
            df.to_excel(ruta_excel, index=False)
            try: os.startfile(ruta_excel)
            except: pass
        except Exception: self.session.rollback()

    def setup_crm(self):
        layout = QVBoxLayout(self.tab_crm); lbl_info = QLabel("📲 <b>Contacto con Clientes Recientes</b>"); layout.addWidget(lbl_info)
        top_bar = QHBoxLayout(); btn_refresh = QPushButton("🔄 Cargar Entregas Recientes"); btn_refresh.clicked.connect(self.cargar_crm)
        top_bar.addWidget(btn_refresh); top_bar.addStretch(); layout.addLayout(top_bar)
        
        self.tabla_crm = QTableWidget(); self.tabla_crm.setColumnCount(5); self.tabla_crm.setHorizontalHeaderLabels(["Fecha Entrega", "Guía", "Cliente (Destinatario)", "Celular", "Acción"])
        self.tabla_crm.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tabla_crm.setColumnWidth(0, 150)
        self.tabla_crm.setColumnWidth(1, 150)
        self.tabla_crm.setColumnWidth(2, 250)
        self.tabla_crm.setColumnWidth(3, 150)
        self.tabla_crm.horizontalHeader().setStretchLastSection(True)
        self.tabla_crm.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); self.tabla_crm.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); layout.addWidget(self.tabla_crm)
        
    def cargar_crm(self):
        self.tabla_crm.setRowCount(0)
        try:
            ops = self.session.query(Operacion).filter(Operacion.estado == Estados.ENTREGADO, Operacion.celular != "", Operacion.celular != None, Operacion.sucursal == self.sucursal_actual).order_by(Operacion.fecha_salida.desc()).limit(100).all()
            for r, op in enumerate(ops):
                self.tabla_crm.insertRow(r); f_str = op.fecha_salida.strftime("%d/%m/%Y") if op.fecha_salida else op.fecha_ingreso.strftime("%d/%m/%Y")
                self.tabla_crm.setItem(r, 0, QTableWidgetItem(f_str)); self.tabla_crm.setItem(r, 1, QTableWidgetItem(op.guia_remito or "-")); self.tabla_crm.setItem(r, 2, QTableWidgetItem(op.destinatario)); self.tabla_crm.setItem(r, 3, QTableWidgetItem(op.celular))
                btn_wsp = QPushButton("💬 Enviar WhatsApp"); btn_wsp.clicked.connect(lambda checked, num=op.celular, nom=op.destinatario: self.enviar_whatsapp(num, nom)); self.tabla_crm.setCellWidget(r, 4, btn_wsp)
        except Exception: self.session.rollback()

    def enviar_whatsapp(self, numero, nombre):
        num_limpio = "".join(c for c in numero if c.isdigit())
        if not num_limpio: QMessageBox.warning(self, "Error", "El número no es válido."); return
        if not num_limpio.startswith("54"): num_limpio = "549" + num_limpio
        mensaje = f"Hola {nombre}, somos de EK Logística. Hemos entregado tu envío recientemente y nos encantaría saber qué te pareció el servicio. ¡Gracias por elegirnos!"
        url = f"https://web.whatsapp.com/send?phone={num_limpio}&text={mensaje}"; QDesktopServices.openUrl(QUrl(url))

    def setup_estadisticas(self):
        layout = QVBoxLayout(self.tab_stats)
        top_bar = QHBoxLayout()
        
        self.meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        self.combo_mes_stats = QComboBox()
        self.combo_mes_stats.addItems(self.meses)
        self.combo_mes_stats.setCurrentIndex(datetime.now().month - 1)
        self.combo_mes_stats.setMinimumWidth(150)
        
        self.combo_anio_stats = QComboBox()
        anio_actual = datetime.now().year
        self.combo_anio_stats.addItems([str(anio_actual - 1), str(anio_actual), str(anio_actual + 1)])
        self.combo_anio_stats.setCurrentText(str(anio_actual))
        
        btn_refresh = QPushButton("📊 Filtrar y Comparar con Mes Anterior")
        btn_refresh.setStyleSheet("background-color: #0d6efd; color: white; font-weight: bold; padding: 6px 15px;")
        btn_refresh.clicked.connect(self.cargar_estadisticas)
        
        top_bar.addWidget(QLabel("<b>Mes a Analizar:</b>"))
        top_bar.addWidget(self.combo_mes_stats)
        top_bar.addWidget(QLabel("<b>Año:</b>"))
        top_bar.addWidget(self.combo_anio_stats)
        top_bar.addWidget(btn_refresh)
        top_bar.addStretch()
        
        self.vista_stats = QTextBrowser()
        self.vista_stats.setOpenExternalLinks(False)
        
        layout.addLayout(top_bar)
        layout.addWidget(self.vista_stats)

    def cargar_estadisticas(self):
        try:
            mes_sel = self.combo_mes_stats.currentIndex() + 1
            anio_sel = int(self.combo_anio_stats.currentText())
            
            if mes_sel == 1: mes_ant = 12; anio_ant = anio_sel - 1
            else: mes_ant = mes_sel - 1; anio_ant = anio_sel
            
            def obtener_datos(m, y):
                tot = self.session.execute(text("SELECT COUNT(*) FROM operaciones WHERE EXTRACT(MONTH FROM fecha_ingreso) = :m AND EXTRACT(YEAR FROM fecha_ingreso) = :y AND sucursal = :s"), {"m": m, "y": y, "s": self.sucursal_actual}).scalar() or 0
                ent = self.session.execute(text("SELECT COUNT(*) FROM operaciones WHERE EXTRACT(MONTH FROM fecha_ingreso) = :m AND EXTRACT(YEAR FROM fecha_ingreso) = :y AND sucursal = :s AND estado = 'ENTREGADO'"), {"m": m, "y": y, "s": self.sucursal_actual}).scalar() or 0
                fac = self.session.execute(text("SELECT SUM(monto_servicio) FROM operaciones WHERE EXTRACT(MONTH FROM fecha_ingreso) = :m AND EXTRACT(YEAR FROM fecha_ingreso) = :y AND sucursal = :s AND facturado = true"), {"m": m, "y": y, "s": self.sucursal_actual}).scalar() or 0.0
                return tot, ent, fac

            t_sel, e_sel, f_sel = obtener_datos(mes_sel, anio_sel)
            t_ant, e_ant, f_ant = obtener_datos(mes_ant, anio_ant)
            
            def calc_var(actual, anterior):
                if anterior == 0: return "<span style='color:#198754;'>+100% ⬆</span>" if actual > 0 else "-"
                pct = ((actual - anterior) / anterior) * 100
                if pct > 0: return f"<span style='color:#198754;'>+{pct:.1f}% ⬆</span>"
                elif pct < 0: return f"<span style='color:#dc3545;'>{pct:.1f}% ⬇</span>"
                return "<span style='color:#6c757d;'>0% =</span>"

            res_prov = self.session.execute(text("SELECT proveedor, COUNT(*) FROM operaciones WHERE EXTRACT(MONTH FROM fecha_ingreso) = :m AND EXTRACT(YEAR FROM fecha_ingreso) = :y AND sucursal = :s GROUP BY proveedor ORDER BY COUNT(*) DESC"), {"m": mes_sel, "y": anio_sel, "s": self.sucursal_actual}).fetchall()
            
            # 🔥 CÁLCULO DE HORAS DE CHOFER EN CALLE 🔥
            sql_horas = text("""
                SELECT chofer_asignado, DATE(fecha_salida), MIN(fecha_salida), MAX(COALESCE(fecha_entrega, fecha_salida))
                FROM operaciones
                WHERE EXTRACT(MONTH FROM fecha_salida) = :m AND EXTRACT(YEAR FROM fecha_salida) = :y
                AND sucursal = :s AND chofer_asignado IS NOT NULL AND chofer_asignado NOT LIKE '%TERCERIZADO%'
                GROUP BY chofer_asignado, DATE(fecha_salida)
            """)
            res_horas = self.session.execute(sql_horas, {"m": mes_sel, "y": anio_sel, "s": self.sucursal_actual}).fetchall()
            
            horas_por_chofer = {}; dias_por_chofer = {}
            for r in res_horas:
                chof = r[0]; inicio = r[2]; fin = r[3]
                if inicio and fin and fin > inicio:
                    diff_horas = (fin - inicio).total_seconds() / 3600.0
                    if diff_horas > 14: diff_horas = 14 # Filtro para evitar errores si dejaron App abierta
                    if chof not in horas_por_chofer: 
                        horas_por_chofer[chof] = 0.0; dias_por_chofer[chof] = 0
                    horas_por_chofer[chof] += diff_horas
                    dias_por_chofer[chof] += 1
            
            lista_chof = []
            for chof in horas_por_chofer:
                promedio = horas_por_chofer[chof] / dias_por_chofer[chof]
                lista_chof.append((chof, promedio, dias_por_chofer[chof]))
            lista_chof.sort(key=lambda x: x[1], reverse=True)

            nombre_mes_ant = self.meses[mes_ant - 1]
            
            html = f"<html><body style='font-family: Arial; padding: 20px;'><h1 style='color: #1565C0; border-bottom: 2px solid #1565C0; padding-bottom: 10px;'>📊 RENDIMIENTO MENSUAL - {self.combo_mes_stats.currentText().upper()} {anio_sel}</h1>"
            
            html += f"<table width='100%' style='text-align:center; font-size:16px; margin-bottom: 30px;'><tr>"
            html += f"<td style='background:#f8f9fa; padding:20px; border-radius:12px; border: 1px solid #dee2e6; width: 33%; color: black;'><b>Total Guías (Mes)</b><br><span style='font-size:32px; color:#0d6efd;'><b>{t_sel}</b></span><br><small>vs {nombre_mes_ant}: {calc_var(t_sel, t_ant)}</small></td><td width='2%'></td>"
            html += f"<td style='background:#f8f9fa; padding:20px; border-radius:12px; border: 1px solid #dee2e6; width: 33%; color: black;'><b>Entregas Exitosas</b><br><span style='font-size:32px; color:#198754;'><b>{e_sel}</b></span><br><small>vs {nombre_mes_ant}: {calc_var(e_sel, e_ant)}</small></td><td width='2%'></td>"
            html += f"<td style='background:#f8f9fa; padding:20px; border-radius:12px; border: 1px solid #dee2e6; width: 33%; color: black;'><b>Facturado Confirmado</b><br><span style='font-size:32px; color:#6f42c1;'><b>$ {f_sel:,.0f}</b></span><br><small>vs {nombre_mes_ant}: {calc_var(f_sel, f_ant)}</small></td>"
            html += f"</tr></table><hr style='border:1px solid #ddd;'><br>"
            
            html += f"<table width='100%'><tr><td width='48%' valign='top' style='padding:20px; border-radius:10px; border:1px solid #ccc; background:#ffffff;'><h2 style='margin-top:0; color:#444;'>📦 Volúmen por Cliente ({self.combo_mes_stats.currentText()})</h2><ul style='list-style-type: none; padding-left: 0;'>"
            for p in res_prov: html += f"<li style='font-size: 16px; margin-bottom: 12px; padding-bottom:5px; border-bottom:1px dashed #eee;'>📌 <b>{p[0]}</b>: <span style='float:right; color:#1565C0; font-weight:bold;'>{p[1]} envíos</span></li>"
            
            html += "</ul></td><td width='4%'></td><td width='48%' valign='top' style='padding:20px; border-radius:10px; border:1px solid #ccc; background:#ffffff;'><h2 style='margin-top:0; color:#444;'>⏱️ Rendimiento Choferes (Promedio en Calle)</h2><ul style='list-style-type: none; padding-left: 0;'>"
            
            if not lista_chof:
                html += "<li style='color:#777; font-style:italic;'>No hay suficientes datos de rutas en este mes.</li>"
            else:
                for idx, c in enumerate(lista_chof): 
                    med = "🏃" if c[1] > 6 else ("🚶" if c[1] > 3 else "☕")
                    html += f"<li style='font-size: 16px; margin-bottom: 12px; padding-bottom:5px; border-bottom:1px dashed #eee;'>{med} <b>{c[0]}</b> <small>({c[2]} rutas)</small>: <span style='float:right; color:#d32f2f; font-weight:bold;'>{c[1]:.1f} Hs / día</span></li>"
            
            html += "</ul><p style='font-size:12px; color:#888; margin-top:20px;'>* El tiempo en calle se calcula desde que la guía sale del depósito (En Reparto) hasta el horario exacto de la última entrega del día registrada en la App.</p></td></tr></table></body></html>"
            
            self.vista_stats.setHtml(html)
        except Exception as e: 
            self.session.rollback()
            print(f"Error en estadisticas: {e}")

class DBWakeUpThread(QThread):
    finished_signal = pyqtSignal()
    def run(self):
        try: 
            from database import get_session
            engine, session = get_session()
            session.execute(text("SELECT 1"))
            session.close()
        except: pass
        self.finished_signal.emit()

class PantallaCargaMinimalista(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("QDialog { background: transparent; border: none; }")
        self.setFixedSize(400, 300) 
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.contenedor = QWidget(); self.contenedor.setFixedSize(300, 200); self.contenedor.setStyleSheet("background: rgba(255, 255, 255, 240); border-radius: 15px;")
        lay_cont = QVBoxLayout(self.contenedor); lay_cont.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_logo = QLabel()
        base_dir = os.path.dirname(os.path.abspath(__file__))
        logo_path = os.path.join(base_dir, "eklogo.png")
        pixmap = QPixmap(logo_path)
        if not pixmap.isNull(): self.lbl_logo.setPixmap(pixmap.scaled(120, 120, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else: self.lbl_logo.setText("📦 E.K."); self.lbl_logo.setStyleSheet("font-size: 40px; color: #1565c0; font-weight: bold;")
        self.lbl_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.lbl_texto = QLabel("Entrando a plataforma espere...")
        
        self.lbl_texto.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay_cont.addWidget(self.lbl_logo); lay_cont.addWidget(self.lbl_texto)
        shadow = QGraphicsDropShadowEffect(); shadow.setBlurRadius(20); shadow.setColor(QColor(0, 0, 0, 80)); shadow.setOffset(0, 0)
        self.contenedor.setGraphicsEffect(shadow); layout.addWidget(self.contenedor)
        self.anim_latido = QVariantAnimation(self); self.anim_latido.setDuration(1000); self.anim_latido.setStartValue(1.0); self.anim_latido.setKeyValueAt(0.5, 0.4); self.anim_latido.setEndValue(1.0); self.anim_latido.valueChanged.connect(self.actualizar_opacidad_texto)
        self.timer_repeticion = QTimer(self); self.timer_repeticion.timeout.connect(self.anim_latido.start); self.timer_repeticion.start(1000); self.anim_latido.start()

    def actualizar_opacidad_texto(self, value):
        self.lbl_texto.setStyleSheet(f"font-size: 15px; font-weight: bold; color: rgba(51, 51, 51, {int(255*value)}); margin-top: 10px;")

class TrackingDialog(QDialog):
    def __init__(self, session, usuario=None):
        super().__init__()
        self.session = session
        self.usuario = usuario
        self.setWindowTitle("🔍 Rastreo de Guía y Auditoría Total")
        
        # 🔥 FIX WINDOWS 11: PERMITIR MAXIMIZAR Y MINIMIZAR 🔥
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowMinMaxButtonsHint | Qt.WindowType.WindowCloseButtonHint)
        self.resize(900, 650)
        self.setStyleSheet("background-color: white;")
        
        layout = QVBoxLayout(self)
        h = QHBoxLayout()
        self.in_buscar = QLineEdit()
        self.in_buscar.setPlaceholderText("Ingrese N° de Guía o Remito...")
        self.in_buscar.returnPressed.connect(self.buscar_tracking)
        
        btn_bus = QPushButton("RASTREAR")
        btn_bus.setStyleSheet("background-color: #0d6efd; color: white; font-weight: bold; padding: 6px 15px;")
        btn_bus.clicked.connect(self.buscar_tracking)
        
        btn_reset = QPushButton("⚠️ RESETEAR A DEPÓSITO")
        btn_reset.setStyleSheet("background-color: #dc3545; color: white; font-weight: bold; padding: 6px 15px;")
        btn_reset.clicked.connect(self.resetear_guia)
        
        if not self.usuario or not getattr(self.usuario, 'es_admin_total', False):
            btn_reset.hide()
            
        h.addWidget(self.in_buscar)
        h.addWidget(btn_bus)
        h.addWidget(btn_reset)
        
        self.lbl_info = QLabel("Ingrese una guía para ver el estado.")
        self.lbl_info.setStyleSheet("font-size: 14px; color: #333; padding: 12px; border: 1px solid #ccc; background: #f8f9fa; border-radius: 5px;")
        self.lbl_info.setWordWrap(True)
        
        # 🔥 NUEVO SISTEMA DE PESTAÑAS (TRACKING VS AUDITORÍA) 🔥
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("QTabBar::tab { padding: 8px 15px; font-weight: bold; }")
        
        # --- TAB 1: TRACKING CLIENTE ---
        self.tab_cliente = QWidget()
        lay_cli = QVBoxLayout(self.tab_cliente)
        self.tabla_cli = QTableWidget()
        self.tabla_cli.setColumnCount(4)
        self.tabla_cli.setHorizontalHeaderLabels(["Fecha/Hora", "Usuario", "Movimiento Físico", "Detalle"])
        self.tabla_cli.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tabla_cli.setColumnWidth(0, 130); self.tabla_cli.setColumnWidth(1, 100); self.tabla_cli.setColumnWidth(2, 160)
        self.tabla_cli.horizontalHeader().setStretchLastSection(True)
        lay_cli.addWidget(self.tabla_cli)
        
        # --- TAB 2: AUDITORÍA INTERNA ---
        self.tab_auditoria = QWidget()
        lay_aud = QVBoxLayout(self.tab_auditoria)
        self.tabla_aud = QTableWidget()
        self.tabla_aud.setColumnCount(4)
        self.tabla_aud.setHorizontalHeaderLabels(["Fecha/Hora", "Operador (Audit)", "Acción de Sistema", "Detalle Técnico"])
        self.tabla_aud.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tabla_aud.setColumnWidth(0, 130); self.tabla_aud.setColumnWidth(1, 120); self.tabla_aud.setColumnWidth(2, 180)
        self.tabla_aud.horizontalHeader().setStretchLastSection(True)
        self.tabla_aud.setStyleSheet("background-color: #fdfdfd; gridline-color: #e0e0e0;")
        lay_aud.addWidget(self.tabla_aud)
        
        self.tabs.addTab(self.tab_cliente, "📍 Tracking Operativo")
        self.tabs.addTab(self.tab_auditoria, "🛡️ Auditoría de Sistema")
        
        layout.addLayout(h)
        layout.addWidget(self.lbl_info)
        layout.addWidget(self.tabs)
        
    def resetear_guia(self):
        guia = self.in_buscar.text().strip()
        if not guia: return
        op = self.session.query(Operacion).filter(Operacion.guia_remito == guia).first()
        if not op: op = self.session.query(Operacion).filter(Operacion.guia_remito.ilike(f"%{guia}%")).first()
        if not op: return
        
        reply = QMessageBox.question(self, "⚠️ ALERTA DE SEGURIDAD EXTREMA", 
            f"¿Está seguro de devolver la guía '{op.guia_remito}' a EN DEPOSITO?\n\n"
            "Esto borrará de forma permanente TODO su historial de la calle, perderá a su chofer y se le borrará la marca de entregado, facturado y controlado.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.session.execute(text("DELETE FROM historial_movimientos WHERE operacion_id = :id"), {"id": op.id})
                op.estado = Estados.EN_DEPOSITO
                op.chofer_asignado = None; op.fecha_salida = None; op.fecha_entrega = None
                op.facturado = False; op.controlada = False
                self.session.commit()
                QMessageBox.information(self, "Éxito", "Guía reseteada exitosamente.")
                self.buscar_tracking() 
            except Exception as e:
                self.session.rollback()
                QMessageBox.critical(self, "Error", f"Fallo al resetear: {str(e)}")
    
    def buscar_tracking(self):
        guia = self.in_buscar.text().strip()
        if not guia: return
        op = self.session.query(Operacion).filter(Operacion.guia_remito == guia).first()
        if not op: op = self.session.query(Operacion).filter(Operacion.guia_remito.ilike(f"%{guia}%")).first()
        if not op: 
            self.lbl_info.setText("❌ GUÍA NO ENCONTRADA")
            self.lbl_info.setStyleSheet("font-size: 16px; color: red; font-weight: bold; padding: 10px; border: 1px solid red;")
            self.tabla_cli.setRowCount(0); self.tabla_aud.setRowCount(0)
            return
            
        self.lbl_info.setStyleSheet("font-size: 14px; color: #333; padding: 12px; border: 1px solid #ccc; background: #f8f9fa; border-radius: 5px;")
            
        color_estado = "blue"; bg_color = "#e7f1ff"
        if op.estado == Estados.ENTREGADO: color_estado = "#198754"; bg_color = "#d1e7dd"
        elif op.estado == Estados.EN_REPARTO: color_estado = "#856404"; bg_color = "#fff3cd"
        elif op.estado == Estados.DEVUELTO_ORIGEN: color_estado = "#fd7e14"; bg_color = "#ffe8d6"
        
        if op.proveedor and op.proveedor.lower() == "jetpaq":
            fac_str = "USO INTERNO"; color_fac = "gray"
        else:
            fac_str = "SÍ" if op.facturado else "NO PAGA"; color_fac = "green" if op.facturado else "red"
            
        # 🔥 NUEVO: ESTADO DE CONTROL Y PROVEEDOR 🔥
        ctrl_str = "✔️ SÍ (Auditada)" if getattr(op, 'controlada', False) else "❌ NO"
        color_ctrl = "green" if getattr(op, 'controlada', False) else "red"
            
        movs = self.session.query(Historial).filter(Historial.operacion_id == op.id).order_by(Historial.fecha_hora.desc()).all()
        
        entregado_info = ""
        if op.estado == Estados.ENTREGADO:
            for m in movs:
                if m.detalle and "Recibio:" in m.detalle:
                    recibe = m.detalle.split("Recibio:")[1].split("[")[0].split("|")[0].strip()
                    fecha_ent = m.fecha_hora.strftime("%d/%m/%Y a las %H:%M hs")
                    entregado_info = f"<br><b>ENTREGADO A:</b> <span style='color:#198754;'>{recibe}</span> <b>EL:</b> {fecha_ent}"
                    break
                    
        bultos_tot = op.bultos or 1
        bultos_fr = getattr(op, 'bultos_frio', 0) or 0
        bultos_com = bultos_tot - bultos_fr
        tipo_c = op.tipo_carga or "COMÚN"
        
        texto_bultos = f"{bultos_tot} Tot ({bultos_com}C, {bultos_fr}R)" if bultos_fr > 0 else f"{bultos_tot} (Comunes)"
        if "Flete" in (op.tipo_servicio or ""): texto_bultos = f"{bultos_tot} Horas (FLETE)"
        
        info_txt = f"""
        <div style='background-color: {bg_color}; padding: 8px;'>
            <table width='100%'>
                <tr>
                    <td width='50%'>
                        <b>GUÍA / REMITO:</b> <span style='font-size:16px;'>{op.guia_remito}</span><br>
                        <b>ESTADO ACTUAL:</b> <span style='color:{color_estado}; font-size: 16px; font-weight: bold;'>{op.estado.upper()}</span> {entregado_info}<br>
                        <b>PROVEEDOR:</b> <span style='color:#0d6efd; font-weight:bold;'>{op.proveedor}</span><br>
                        <b>FACTURADO:</b> <span style='color:{color_fac}; font-weight: bold;'>{fac_str}</span> | <b>CONTROLADA:</b> <span style='color:{color_ctrl}; font-weight: bold;'>{ctrl_str}</span>
                    </td>
                    <td width='50%'>
                        <b>DESTINATARIO:</b> {op.destinatario} ({op.localidad})<br>
                        <b>CHOFER:</b> {op.chofer_asignado or 'Sin Asignar'}<br>
                        <b>📦 BULTOS:</b> <span style='color:#d32f2f; font-weight:bold;'>{texto_bultos}</span><br>
                        <b>PESO:</b> {op.peso or 0} Kg
                    </td>
                </tr>
            </table>
        </div>
        """
        self.lbl_info.setText(info_txt)
        
        self.tabla_cli.setRowCount(0)
        self.tabla_aud.setRowCount(0)
        
        # Filtramos qué va a qué tabla
        row_cli = 0; row_aud = 0
        for m in movs: 
            accion = m.accion.upper()
            es_auditoria_pura = "CONTROL" in accion or "EDICIÓN" in accion or "FACTURACIÓN" in accion
            
            # Llenar Auditoría (Acá va TODO)
            self.tabla_aud.insertRow(row_aud)
            self.tabla_aud.setItem(row_aud, 0, QTableWidgetItem(m.fecha_hora.strftime("%d/%m/%y %H:%M:%S")))
            self.tabla_aud.setItem(row_aud, 1, QTableWidgetItem(m.usuario))
            it_acc = QTableWidgetItem(m.accion)
            if es_auditoria_pura: it_acc.setForeground(QColor("purple")); it_acc.setFont(QFont("Arial", 9, QFont.Weight.Bold))
            self.tabla_aud.setItem(row_aud, 2, it_acc)
            self.tabla_aud.setItem(row_aud, 3, QTableWidgetItem(m.detalle or ""))
            row_aud += 1
            
            # Llenar Tracking Físico (Omitimos cosas de facturación/edición)
            if not es_auditoria_pura:
                self.tabla_cli.insertRow(row_cli)
                self.tabla_cli.setItem(row_cli, 0, QTableWidgetItem(m.fecha_hora.strftime("%d/%m/%Y %H:%M")))
                self.tabla_cli.setItem(row_cli, 1, QTableWidgetItem(m.usuario))
                self.tabla_cli.setItem(row_cli, 2, QTableWidgetItem(m.accion))
                
                det_str = m.detalle or ""
                if "| GPS:" in det_str:
                    try:
                        base_txt = det_str.split("| GPS:")[0].strip()
                        link = det_str.split("| GPS:")[1].strip()
                        lbl = QLabel(f'{base_txt} <a href="{link}" style="color:#d32f2f; text-decoration:none; font-weight:bold;">📍 VER MAPA</a>')
                        lbl.setOpenExternalLinks(True)
                        self.tabla_cli.setCellWidget(row_cli, 3, lbl)
                    except: self.tabla_cli.setItem(row_cli, 3, QTableWidgetItem(det_str))
                else:
                    self.tabla_cli.setItem(row_cli, 3, QTableWidgetItem(det_str))
                row_cli += 1

if __name__ == "__main__":
    app = QApplication(sys.argv)
    apply_stylesheet(app, theme='light_blue.xml') 
    estilo_actual = app.styleSheet()
    estilo_tablas_blancas = """
    QTableWidget { background-color: #ffffff !important; gridline-color: #d0d0d0 !important; }
    QTableWidget::item { background-color: transparent !important; color: #000000 !important; border-bottom: 1px solid #e0e0e0 !important; }
    QTableWidget::item:selected { background-color: #bbdefb !important; color: #000000 !important; }
    QHeaderView::section { background-color: #f8f9fa !important; color: #333333 !important; font-weight: bold !important; border: 1px solid #dee2e6 !important; }
    """
    app.setStyleSheet(estilo_actual + estilo_tablas_blancas)
    
    login = LoginWindow()
    if login.exec() == QDialog.DialogCode.Accepted:
        splash = PantallaCargaMinimalista()
        screen = app.primaryScreen().geometry()
        splash.move(int((screen.width() - splash.width()) / 2), int((screen.height() - splash.height()) / 2))
        splash.show()
        QApplication.processEvents()
        
        def terminar_arranque():
            try:
                global ventana
                ventana = PlataformaLogistica(login.usuario_logueado)
                ventana.cambiar_sucursal(ventana.sucursal_actual)
                splash.close()
                ventana.showMaximized() 
            except Exception as e:
                splash.close()
                msg = QMessageBox(); msg.setIcon(QMessageBox.Icon.Critical); msg.setWindowTitle("Error Fatal"); msg.setText("Error al cargar los módulos."); msg.setDetailedText(traceback.format_exc()); msg.exec()
                sys.exit(1)
                
        wake_thread = DBWakeUpThread()
        wake_thread.finished_signal.connect(terminar_arranque)
        wake_thread.start()
        sys.exit(app.exec())