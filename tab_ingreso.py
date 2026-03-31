import os
from datetime import datetime, date
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                             QComboBox, QPushButton, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QMessageBox, QDateEdit, QGroupBox, 
                             QFormLayout, QSpinBox, QDoubleSpinBox, QRadioButton, 
                             QButtonGroup, QFileDialog, QCheckBox, QStyledItemDelegate, QScrollArea, QCompleter, QAbstractItemView, QDialog)
from PyQt6.QtCore import Qt, QDate, QTimer
from PyQt6.QtGui import QColor, QFont, QBrush
from sqlalchemy import text

from database import Operacion, Historial, Estados, Urgencia, DestinoFrecuente, ClienteRetiro
from utilidades import parsear_txt_dhl_logic, crear_pdf_retiro
from dialogos import PreviewImportacionDialog

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

ESTILO_GRUPO = """
QGroupBox {
    font-weight: bold !important;
    border: 2px solid #78909c !important; 
    border-radius: 8px !important;
    padding-top: 25px !important; 
    margin-top: 5px !important;
}
QGroupBox::title {
    subcontrol-origin: margin !important;
    subcontrol-position: top left !important;
    top: 5px !important;
    left: 15px !important;
    color: #0d47a1 !important; 
    background: transparent !important;
}
"""

class TabIngreso(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main = main_window
        self.mapa_destinos_global = {}
        self.setup_ui()

    def setup_ui(self):
        l = QHBoxLayout(self)
        self.scroll_izq = QScrollArea()
        self.scroll_izq.setWidgetResizable(True)
        self.scroll_izq.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_izq.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")
        
        self.widget_izq = QWidget()
        col_izq = QVBoxLayout(self.widget_izq)
        col_izq.setContentsMargins(0, 0, 10, 0)
        
        p_datos = QGroupBox("Datos Principales")
        p_datos.setStyleSheet(ESTILO_GRUPO)
        fl = QFormLayout()
        
        self.in_serv = QComboBox()
        self.in_serv.addItems(["Entrega (Reparto)", "Retiro (Solicitud Cliente)", "Flete Especial (Por Hora/Viaje)"])
        self.in_serv.currentTextChanged.connect(self.actualizar_interfaz_retiro)
        
        self.in_fecha = QDateEdit(QDate.currentDate())
        self.in_fecha.setCalendarPopup(True)
        self.in_fecha.setEnabled(getattr(self.main.usuario, 'es_admin_total', False))
        self.in_fecha.dateChanged.connect(self.cargar_movimientos_dia)
        
        self.lbl_guia = QLabel("Guía / Remito:"); self.in_guia = QLineEdit()
        self.lbl_cli_ret = QLabel("Buscar Cliente:"); self.in_cliente_retiro = QComboBox(); self.in_cliente_retiro.setEditable(True); self.in_cliente_retiro.completer().setFilterMode(Qt.MatchFlag.MatchContains); self.in_cliente_retiro.currentIndexChanged.connect(self.cargar_datos_cliente); self.lbl_cli_ret.hide(); self.in_cliente_retiro.hide()
        
        self.in_prov = QComboBox(); self.in_prov.addItems(self.main.lista_proveedores); self.in_prov.setEditable(True)
        self.in_prov.currentTextChanged.connect(self.cargar_destinos_frecuentes_combo)
        self.in_prov.currentTextChanged.connect(self.actualizar_interfaz_peso)
        
        dest_layout = QHBoxLayout()
        self.in_destinos_frecuentes = QComboBox()
        self.in_destinos_frecuentes.addItem("--- Destinos Guardados ---")
        self.in_destinos_frecuentes.setEnabled(False)
        self.in_destinos_frecuentes.setEditable(True)
        self.in_destinos_frecuentes.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.in_destinos_frecuentes.setMinimumContentsLength(25)
        self.in_destinos_frecuentes.completer().setFilterMode(Qt.MatchFlag.MatchContains)
        self.in_destinos_frecuentes.currentIndexChanged.connect(self.llenar_datos_destino)
        
        self.in_codigo_rapido = QLineEdit(); self.in_codigo_rapido.setPlaceholderText("Buscar ID..."); self.in_codigo_rapido.setFixedWidth(80); self.in_codigo_rapido.returnPressed.connect(self.buscar_destino_por_codigo)
        dest_layout.addWidget(self.in_destinos_frecuentes); dest_layout.addWidget(self.in_codigo_rapido)
        
        self.in_dest = QLineEdit(); self.in_cel = QLineEdit(); self.in_cel.setPlaceholderText("Ej: 261-155..."); self.in_dom = QLineEdit(); self.in_loc_combo = QComboBox()
        
        fl.addRow("Tipo:", self.in_serv)
        fl.addRow(self.lbl_cli_ret, self.in_cliente_retiro)
        fl.addRow("Fecha:", self.in_fecha)
        fl.addRow(self.lbl_guia, self.in_guia)
        fl.addRow("Proveedor:", self.in_prov)
        fl.addRow("📍 Destinos Fijos:", dest_layout)
        fl.addRow("Destinatario:", self.in_dest)
        fl.addRow("Celular:", self.in_cel)
        fl.addRow("Domicilio:", self.in_dom)
        fl.addRow("Zona:", self.in_loc_combo)
        p_datos.setLayout(fl)
        
        gb_tipo = QGroupBox("Configuración de Carga")
        gb_tipo.setStyleSheet(ESTILO_GRUPO)
        ly_tipo_principal = QVBoxLayout()
        
        self.widget_carga_normal = QWidget()
        ly_normal = QVBoxLayout(self.widget_carga_normal)
        ly_normal.setContentsMargins(0,0,0,0)
        
        self.radio_comun = QRadioButton("📦 COMÚN"); self.radio_frio = QRadioButton("❄️ REFRIGERADO"); self.radio_comb = QRadioButton("🔄 COMBINADO"); self.bg_tipo = QButtonGroup(); self.bg_tipo.addButton(self.radio_comun); self.bg_tipo.addButton(self.radio_frio); self.bg_tipo.addButton(self.radio_comb); self.radio_comun.setChecked(True)
        ly_radios = QHBoxLayout(); ly_radios.addWidget(self.radio_comun); ly_radios.addWidget(self.radio_frio); ly_radios.addWidget(self.radio_comb)
        
        self.widget_simple = QWidget(); ly_simple = QHBoxLayout(self.widget_simple); ly_simple.setContentsMargins(0,0,0,0)
        self.lbl_bultos_simple = QLabel("Bultos:")
        self.in_bultos_simple = QSpinBox(); self.in_bultos_simple.setRange(1, 999); self.in_bultos_simple.setValue(1)
        self.lbl_peso = QLabel("Peso:")
        self.in_peso_manual = QDoubleSpinBox(); self.in_peso_manual.setRange(0, 9999); self.in_peso_manual.setSuffix(" Kg")
        ly_simple.addWidget(self.lbl_bultos_simple); ly_simple.addWidget(self.in_bultos_simple)
        ly_simple.addWidget(self.lbl_peso); ly_simple.addWidget(self.in_peso_manual)
        
        self.widget_comb = QWidget(); ly_comb = QFormLayout(self.widget_comb); ly_comb.setContentsMargins(0,0,0,0); self.in_cant_comun = QSpinBox(); self.in_cant_comun.setRange(1, 999); self.in_cant_comun.setPrefix("📦 "); self.in_cant_frio = QSpinBox(); self.in_cant_frio.setRange(1, 999); self.in_cant_frio.setPrefix("❄️ "); ly_comb.addRow("Cant. Común:", self.in_cant_comun); ly_comb.addRow("Cant. Refrigerado:", self.in_cant_frio); self.widget_comb.hide()
        
        self.chk_contingencia = QCheckBox("❄️ Aplicar Contingencia de Frío")
        self.chk_contingencia.setStyleSheet("color: #0d47a1; font-weight: bold;")
        self.in_monto_contingencia = QDoubleSpinBox()
        self.in_monto_contingencia.setRange(0, 100000)
        self.in_monto_contingencia.setPrefix("$ ")
        self.in_monto_contingencia.setValue(1500.0)
        self.in_monto_contingencia.hide()
        self.chk_contingencia.toggled.connect(self.in_monto_contingencia.setVisible)
        self.chk_contingencia.hide() 
        
        lay_cont = QHBoxLayout()
        lay_cont.addWidget(self.chk_contingencia)
        lay_cont.addWidget(self.in_monto_contingencia)
        lay_cont.addStretch()
        
        ly_normal.addLayout(ly_radios)
        ly_normal.addWidget(self.widget_simple)
        ly_normal.addWidget(self.widget_comb)
        ly_normal.addLayout(lay_cont)
        
        self.widget_carga_flete = QWidget()
        ly_flete = QVBoxLayout(self.widget_carga_flete)
        ly_flete.setContentsMargins(0,0,0,0)
        
        h_flete_radios = QHBoxLayout()
        self.radio_ida = QRadioButton("➡ Solo Ida (1 Viaje)")
        self.radio_ida_vuelta = QRadioButton("🔁 Ida y Vuelta (2 Viajes)")
        self.radio_ida.setChecked(True)
        self.radio_ida.setStyleSheet("font-weight: bold; color: #198754;")
        self.radio_ida_vuelta.setStyleSheet("font-weight: bold; color: #0d6efd;")
        self.bg_flete = QButtonGroup()
        self.bg_flete.addButton(self.radio_ida)
        self.bg_flete.addButton(self.radio_ida_vuelta)
        h_flete_radios.addWidget(self.radio_ida)
        h_flete_radios.addWidget(self.radio_ida_vuelta)
        
        h_flete_precio = QHBoxLayout()
        self.lbl_precio_flete = QLabel("Precio Final Pactado:")
        self.lbl_precio_flete.setStyleSheet("color: #d32f2f; font-weight: bold; font-size: 14px;")
        self.in_precio_flete = QDoubleSpinBox()
        self.in_precio_flete.setRange(0, 10000000)
        self.in_precio_flete.setPrefix("$ ")
        self.in_precio_flete.setStyleSheet("font-size: 14px; font-weight: bold;")
        h_flete_precio.addWidget(self.lbl_precio_flete)
        h_flete_precio.addWidget(self.in_precio_flete)
        h_flete_precio.addStretch()
        
        ly_flete.addLayout(h_flete_radios)
        ly_flete.addLayout(h_flete_precio)
        self.widget_carga_flete.hide()
        
        self.bg_tipo.buttonClicked.connect(self.cambiar_interfaz_tipo)
        ly_tipo_principal.addWidget(self.widget_carga_normal)
        ly_tipo_principal.addWidget(self.widget_carga_flete)
        gb_tipo.setLayout(ly_tipo_principal)
        
        self.group_cr = QGroupBox("Contra Reembolso / Intercambio")
        self.group_cr.setStyleSheet(ESTILO_GRUPO)
        lay_main_cr = QVBoxLayout(self.group_cr)
        lay_main_cr.setContentsMargins(15, 5, 15, 10) 
        
        self.chk_cr = QCheckBox("Activar Cobro / Intercambio (Opcional)")
        self.chk_cr.setStyleSheet("color: #d32f2f; font-weight: bold;")
        lay_main_cr.addWidget(self.chk_cr)
        
        self.wid_cr = QWidget()
        lay_cr = QFormLayout(self.wid_cr)
        lay_cr.setContentsMargins(0,0,0,0)
        self.in_monto_recaudar = QDoubleSpinBox(); self.in_monto_recaudar.setRange(0, 1e7); self.in_monto_recaudar.setPrefix("$ ")
        self.in_info_intercambio = QLineEdit()
        lay_cr.addRow("Cobrar:", self.in_monto_recaudar); lay_cr.addRow("Detalle:", self.in_info_intercambio)
        lay_main_cr.addWidget(self.wid_cr)
        self.wid_cr.hide() 
        self.chk_cr.toggled.connect(self.wid_cr.setVisible)
        
        col_izq.addWidget(p_datos)
        col_izq.addWidget(gb_tipo)
        col_izq.addWidget(self.group_cr)
        col_izq.addStretch() 
        self.scroll_izq.setWidget(self.widget_izq)
        
        btn_add = QPushButton("GUARDAR EN DEPOSITO")
        btn_add.setMinimumHeight(55) 
        btn_add.setStyleSheet("font-size: 16px; font-weight: bold;")
        btn_add.clicked.connect(self.guardar_ingreso)
        
        self.btn_dhl = QPushButton("📥 IMPORTAR TXT DHL")
        self.btn_dhl.setMinimumHeight(45)
        self.btn_dhl.clicked.connect(self.importar_txt_dhl)
        if self.main.sucursal_actual != "San Juan": self.btn_dhl.hide()
        
        # 🔥 SOLUCIÓN AL CORTE EN PANTALLAS CHICAS 🔥
        panel_izquierdo = QWidget()
        panel_izquierdo.setMinimumWidth(420) # Obliga a que siempre tenga un tamaño legible
        panel_izquierdo.setMaximumWidth(480) # Evita que se estire demasiado en monitores gigantes
        layout_izquierdo = QVBoxLayout(panel_izquierdo)
        layout_izquierdo.setContentsMargins(0, 0, 5, 0)
        layout_izquierdo.addWidget(self.scroll_izq) 
        layout_izquierdo.addWidget(btn_add)         
        layout_izquierdo.addWidget(self.btn_dhl)    
        
        col_der = QVBoxLayout(); h_header_ingreso = QHBoxLayout(); h_header_ingreso.addWidget(QLabel("<b>EN DEPOSITO:</b>"))
        btn_ref_ingreso = QPushButton("🔄 Actualizar")
        btn_ref_ingreso.clicked.connect(self.cargar_movimientos_dia)
        h_header_ingreso.addWidget(btn_ref_ingreso); h_header_ingreso.addStretch()
        
        self.tabla_ingresos = QTableWidget(); self.tabla_ingresos.setColumnCount(8); 
        self.tabla_ingresos.setHorizontalHeaderLabels(["ID", "Serv", "Guía", "Proveedor", "Destino", "Domicilio", "Zona", "Bultos/Hs"]); self.tabla_ingresos.hideColumn(0); 
        self.tabla_ingresos.setStyleSheet(ESTILO_TABLAS_BLANCAS)
        self.pintor_ingreso = PintorCeldasDelegate(self.tabla_ingresos)
        self.tabla_ingresos.setItemDelegate(self.pintor_ingreso)

        header_ing = self.tabla_ingresos.horizontalHeader()
        header_ing.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tabla_ingresos.setColumnWidth(1, 140)
        self.tabla_ingresos.setColumnWidth(2, 140)
        self.tabla_ingresos.setColumnWidth(3, 160)
        self.tabla_ingresos.setColumnWidth(4, 250)
        self.tabla_ingresos.setColumnWidth(5, 350)
        self.tabla_ingresos.setColumnWidth(6, 160)
        self.tabla_ingresos.setColumnWidth(7, 90)
        header_ing.setStretchLastSection(True)
        
        self.tabla_ingresos.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.tabla_ingresos.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        lay_botones_tabla = QHBoxLayout(); btn_del = QPushButton("🗑️ ELIMINAR"); btn_del.clicked.connect(lambda: self.main.eliminar_fila(self.tabla_ingresos, Operacion)); btn_edit_ingreso = QPushButton("✏️ EDITAR"); btn_edit_ingreso.clicked.connect(lambda: self.main.abrir_edicion(self.tabla_ingresos)); lay_botones_tabla.addWidget(btn_edit_ingreso); lay_botones_tabla.addWidget(btn_del); col_der.addLayout(h_header_ingreso); col_der.addWidget(self.tabla_ingresos); col_der.addLayout(lay_botones_tabla)
        
        # 🔥 LE SACAMOS EL PORCENTAJE (30/70) Y LO DEJAMOS AUTOMÁTICO 🔥
        l.addWidget(panel_izquierdo) 
        l.addLayout(col_der, 1) # La tabla absorbe todo el espacio sobrante
        
        self.configurar_autocompletado_global()
        self.actualizar_interfaz_peso()

    def configurar_autocompletado_global(self):
        try:
            destinos = self.main.session.query(DestinoFrecuente).filter(DestinoFrecuente.sucursal == self.main.sucursal_actual).all()
            nombres_completos = []
            self.mapa_destinos_global.clear()
            for i, d in enumerate(destinos):
                if i % 100 == 0: QApplication.processEvents() 
                texto_completer = f"{d.destinatario.upper()} - {d.domicilio.upper()} [{d.proveedor.upper()}]"
                if texto_completer not in nombres_completos:
                    nombres_completos.append(texto_completer)
                    self.mapa_destinos_global[texto_completer] = d
            if hasattr(self, 'in_dest') and isinstance(self.in_dest, QLineEdit):
                completer = QCompleter(nombres_completos)
                completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
                completer.setFilterMode(Qt.MatchFlag.MatchContains)
                vista_lista = completer.popup()
                vista_lista.setMinimumWidth(600)
                vista_lista.setStyleSheet("QListView { background-color: #ffffff; border: 1px solid #999; font-size: 14px; outline: none; } QListView::item { padding: 10px; border-bottom: 1px solid #ddd; } QListView::item:selected { background-color: #bbdefb; color: black; border-bottom: 1px solid #90caf9; }")
                self.in_dest.setCompleter(completer)
                completer.activated.connect(self.autollenar_desde_completer_global)
        except Exception: self.main.session.rollback()

    def autollenar_desde_completer_global(self, texto):
        try:
            if texto in self.mapa_destinos_global:
                destino_db = self.mapa_destinos_global[texto]
                self.in_prov.blockSignals(True) 
                self.in_prov.setCurrentText(destino_db.proveedor.upper())
                self.in_prov.blockSignals(False)
                self.cargar_destinos_frecuentes_combo(destino_db.proveedor)
                self.actualizar_interfaz_peso()
                self.in_dest.blockSignals(True)
                self.in_dest.setText(destino_db.destinatario.upper())
                self.in_dest.blockSignals(False)
                self.in_dom.setText(destino_db.domicilio.upper())
                self.in_cel.setText(destino_db.celular or "")
                self.in_loc_combo.setCurrentText(destino_db.localidad.upper())
                estilo_flash = "background-color: #d1e7dd; color: #0f5132; font-weight: bold; border: 2px solid #198754; border-radius: 4px;"
                self.in_dest.setStyleSheet(estilo_flash); self.in_dom.setStyleSheet(estilo_flash); self.in_loc_combo.setStyleSheet(estilo_flash); self.in_prov.setStyleSheet(estilo_flash)
                QTimer.singleShot(1500, self.restaurar_estilo_inputs)
        except Exception: self.main.session.rollback()

    def actualizar_interfaz_peso(self):
        prov = self.in_prov.currentText().upper()
        if "DHL" in prov: self.lbl_peso.show(); self.in_peso_manual.show()
        else: self.lbl_peso.hide(); self.in_peso_manual.hide(); self.in_peso_manual.setValue(0.0)

    def cambiar_interfaz_tipo(self):
        if self.radio_comb.isChecked(): self.widget_simple.hide(); self.widget_comb.show(); self.chk_contingencia.show()
        else: 
            self.widget_simple.show(); self.widget_comb.hide()
            if self.radio_frio.isChecked(): self.chk_contingencia.show()
            else: self.chk_contingencia.hide(); self.chk_contingencia.setChecked(False)

    def actualizar_interfaz_retiro(self, texto):
        is_flete = texto.startswith("Flete"); is_retiro = texto.startswith("Retiro")
        if is_retiro: self.lbl_guia.hide(); self.in_guia.hide(); self.lbl_cli_ret.show(); self.in_cliente_retiro.show(); self.in_guia.clear()
        elif is_flete: self.lbl_guia.hide(); self.in_guia.hide(); self.lbl_cli_ret.hide(); self.in_cliente_retiro.hide(); self.in_guia.clear()
        else: self.lbl_guia.show(); self.in_guia.show(); self.lbl_cli_ret.hide(); self.in_cliente_retiro.hide()
        if is_flete: self.widget_carga_normal.hide(); self.widget_carga_flete.show(); self.group_cr.hide(); self.chk_cr.setChecked(False) 
        else: self.widget_carga_normal.show(); self.widget_carga_flete.hide(); self.group_cr.show()

    def cargar_datos_cliente(self):
        try:
            idx = self.in_cliente_retiro.currentIndex()
            if idx <= 0: return
            id_cli = self.in_cliente_retiro.itemData(idx); c = self.main.session.query(ClienteRetiro).get(id_cli)
            if c: self.in_dest.setText(c.nombre.upper()); self.in_dom.setText(c.domicilio.upper()); self.in_cel.setText(c.celular); self.in_loc_combo.setCurrentText(c.localidad.upper())
        except Exception: self.main.session.rollback()

    def cargar_destinos_frecuentes_combo(self, proveedor_texto):
        try:
            self.in_destinos_frecuentes.clear(); self.in_destinos_frecuentes.addItem("--- Destinos Guardados ---")
            destinos = self.main.session.query(DestinoFrecuente).filter(DestinoFrecuente.proveedor == proveedor_texto, DestinoFrecuente.sucursal == self.main.sucursal_actual).order_by(DestinoFrecuente.destinatario).all()
            if destinos:
                self.in_destinos_frecuentes.setEnabled(True)
                for d in destinos: 
                    self.in_destinos_frecuentes.addItem(f"{d.id} - {d.destinatario.upper()}", d.id)
            else: self.in_destinos_frecuentes.setEnabled(False); self.in_destinos_frecuentes.addItem("(Sin destinos guardados)")
        except Exception: self.main.session.rollback()

    def buscar_destino_por_codigo(self):
        codigo = self.in_codigo_rapido.text().strip(); prov = self.in_prov.currentText()
        if not codigo or not prov or prov == "JetPaq": return
        try:
            id_buscado = int(codigo); destino = self.main.session.query(DestinoFrecuente).get(id_buscado)
            if destino:
                if destino.proveedor != prov or destino.sucursal != self.main.sucursal_actual: QMessageBox.warning(self, "Conflicto", f"El ID pertenece a otra sucursal o proveedor."); return
                index = self.in_destinos_frecuentes.findData(destino.id)
                if index >= 0: self.in_destinos_frecuentes.setCurrentIndex(index)
                self.llenar_campos_con_objeto(destino); self.in_codigo_rapido.clear()
            else: QMessageBox.warning(self, "No encontrado", "No existe el ID")
        except ValueError: pass
        except Exception: self.main.session.rollback()

    def llenar_datos_destino(self, index):
        try:
            if index <= 0: return 
            id_destino = self.in_destinos_frecuentes.itemData(index); destino_db = self.main.session.query(DestinoFrecuente).get(id_destino)
            if destino_db: self.llenar_campos_con_objeto(destino_db)
        except Exception: self.main.session.rollback()

    def llenar_campos_con_objeto(self, destino_db):
        self.in_dest.setText(destino_db.destinatario.upper()); self.in_dom.setText(destino_db.domicilio.upper()); self.in_cel.setText(destino_db.celular or ""); self.in_loc_combo.setCurrentText(destino_db.localidad.upper())
        estilo_flash = "background-color: #d1e7dd; color: #0f5132; font-weight: bold; border: 2px solid #198754; border-radius: 4px;"
        self.in_dest.setStyleSheet(estilo_flash); self.in_dom.setStyleSheet(estilo_flash); self.in_loc_combo.setStyleSheet(estilo_flash); self.in_prov.setStyleSheet(estilo_flash)
        QTimer.singleShot(800, self.restaurar_estilo_inputs)

    def restaurar_estilo_inputs(self): 
        self.in_dest.setStyleSheet(""); self.in_dom.setStyleSheet(""); self.in_loc_combo.setStyleSheet(""); self.in_prov.setStyleSheet("")

    def guardar_ingreso(self):
        if not self.in_guia.text().strip() and "Entrega" in self.in_serv.currentText(): QMessageBox.warning(self, "Falta Dato", "Debe ingresar el N° de Guía/Remito."); return
        if not self.in_dest.text().strip(): QMessageBox.warning(self, "Falta Dato", "Falta el Destinatario."); return
        if not self.in_dom.text().strip(): QMessageBox.warning(self, "Falta Dato", "Falta el Domicilio."); return
        if not self.in_loc_combo.currentText(): QMessageBox.warning(self, "Falta Dato", "Seleccione una Zona."); return
        try:
            servicio = self.in_serv.currentText()
            loc = self.in_loc_combo.currentText().strip().upper()
            peso_manual = self.in_peso_manual.value()
            prov = self.in_prov.currentText().strip().upper()
            guia_final = self.in_guia.text().strip().upper()
            if prov and prov != "JETPAQ" and guia_final and "Flete" not in servicio:
                existe = self.main.session.query(Operacion).filter(Operacion.guia_remito == guia_final, Operacion.proveedor == prov).first()
                if existe: QMessageBox.warning(self, "Guía Duplicada", f"⚠️ ¡ALTO!\n\nEl remito/guía '{guia_final}' ya fue ingresado previamente para el cliente '{prov}'."); return
            if "Flete" in servicio:
                c_comun = 0; c_frio = 0; bultos_total = 2 if self.radio_ida_vuelta.isChecked() else 1; tipo_carga_txt = "FLETE (IDA Y VUELTA)" if bultos_total == 2 else "FLETE (SOLO IDA)"; precio = self.in_precio_flete.value(); tiene_cr = False; monto_cr = 0.0; info_cr = ""
            else:
                if self.radio_comb.isChecked(): c_comun = self.in_cant_comun.value(); c_frio = self.in_cant_frio.value(); bultos_total = c_comun + c_frio; tipo_carga_txt = "COMBINADO"
                else:
                    bultos_total = self.in_bultos_simple.value()
                    if self.radio_frio.isChecked(): c_frio = bultos_total; c_comun = 0; tipo_carga_txt = "REFRIGERADO"
                    else: c_frio = 0; c_comun = bultos_total; tipo_carga_txt = "COMUN"
                if bultos_total == 0: QMessageBox.warning(self, "Error", "Debe ingresar al menos 1 bulto."); return
                precio = self.main.obtener_precio(loc, c_comun, c_frio, proveedor=prov, peso=peso_manual, bultos_totales=bultos_total)
                if self.chk_contingencia.isChecked(): precio += self.in_monto_contingencia.value(); tipo_carga_txt += " (+Contingencia)"
                tiene_cr = self.chk_cr.isChecked(); monto_cr = self.in_monto_recaudar.value() if tiene_cr else 0.0; info_cr = self.in_info_intercambio.text().strip().upper() if tiene_cr else ""
            if ("Retiro" in servicio or "Flete" in servicio) and not guia_final: 
                now = datetime.now(); c_year = now.strftime('%Y'); c_month = now.strftime('%m'); prefijo = "RETIRO" if "Retiro" in servicio else "FLETE"; ops_auto = self.main.session.query(Operacion.guia_remito).filter(Operacion.guia_remito.like(f"{prefijo} {c_year}-%")).all(); max_seq = 0
                for r_op in ops_auto:
                    if r_op[0]:
                        try: seq = int(r_op[0].split('-')[-1]); max_seq = max(max_seq, seq)
                        except: pass
                guia_final = f"{prefijo} {c_year}-{c_month}-{max_seq + 1:03d}"
            dest_texto = self.in_dest.text().strip().upper(); dom_texto = self.in_dom.text().strip().upper(); cel_texto = self.in_cel.text().strip(); mensaje_toast = "✅ GUARDADO EN DEPÓSITO CORRECTAMENTE"
            if prov and prov != "JETPAQ" and dest_texto and dom_texto:
                existe_dest = self.main.session.query(DestinoFrecuente).filter(DestinoFrecuente.proveedor == prov, DestinoFrecuente.sucursal == self.main.sucursal_actual, DestinoFrecuente.destinatario == dest_texto, DestinoFrecuente.domicilio == dom_texto).first()
                if not existe_dest:
                    nuevo_dest = DestinoFrecuente(proveedor=prov, sucursal=self.main.sucursal_actual, destinatario=dest_texto, domicilio=dom_texto, localidad=loc, celular=cel_texto)
                    self.main.session.add(nuevo_dest); self.main.session.flush() 
                else: mensaje_toast = "✅ GUARDADO (Destino ya existía, se evitó duplicarlo)"
            op = Operacion(fecha_ingreso=self.in_fecha.date().toPyDate(), sucursal=self.main.sucursal_actual, guia_remito=guia_final, proveedor=prov, destinatario=dest_texto, celular=cel_texto, domicilio=dom_texto, localidad=loc, bultos=bultos_total, bultos_frio=c_frio, peso=peso_manual, tipo_carga=tipo_carga_txt, tipo_urgencia=Urgencia.CLASICO, monto_servicio=precio, es_contra_reembolso=tiene_cr, monto_recaudacion=monto_cr, info_intercambio=info_cr, tipo_servicio=servicio)
            self.main.session.add(op); self.main.session.flush(); self.main.log_movimiento(op, "INGRESO A DEPOSITO", "Carga inicial en sistema"); self.main.session.commit()
            try:
                if "Retiro" in servicio: 
                    descargas_dir = os.path.join(os.path.expanduser('~'), 'Downloads'); os.makedirs(descargas_dir, exist_ok=True); ruta_pdf = os.path.join(descargas_dir, f"Comprobante_Retiro_{op.guia_remito or op.id}.pdf"); crear_pdf_retiro(ruta_pdf, op)
                    try: os.startfile(ruta_pdf)
                    except: pass
            except Exception: pass
            if hasattr(self.main, 'cargar_ruta'): self.main.cargar_ruta()
            self.in_guia.clear(); self.in_dest.clear(); self.in_cel.clear(); self.in_dom.clear(); self.in_monto_recaudar.setValue(0); self.in_info_intercambio.clear(); self.chk_cr.setChecked(False); self.in_cliente_retiro.setCurrentIndex(0); self.in_bultos_simple.setValue(1); self.in_peso_manual.setValue(0); self.in_precio_flete.setValue(0); self.radio_ida.setChecked(True); self.in_cant_comun.setValue(1); self.in_cant_frio.setValue(1); self.radio_comun.setChecked(True); self.cambiar_interfaz_tipo(); self.chk_contingencia.setChecked(False); self.in_monto_contingencia.setValue(1500.0)
            self.cargar_destinos_frecuentes_combo(prov); self.cargar_movimientos_dia(); self.in_destinos_frecuentes.setCurrentIndex(0); self.configurar_autocompletado_global(); self.main.toast.mostrar(mensaje_toast)
            if hasattr(self.main, 'cargar_monitor_global'): self.main.cargar_monitor_global()
        except Exception: self.main.session.rollback(); QMessageBox.warning(self, "Micro-corte", "La conexión parpadeó. Intenta de nuevo.")

    def importar_txt_dhl(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Seleccionar TXT de DHL", "", "Text Files (*.txt);;All Files (*)")
        if not filepath: return
        try:
            ops_data = parsear_txt_dhl_logic(filepath)
            if not ops_data: QMessageBox.warning(self, "Error", "No se encontraron guías en el archivo."); return
            dlg = PreviewImportacionDialog(ops_data, self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                datos_finales = dlg.resultados; agregadas = 0; omitidas = 0
                self.main.setWindowTitle("E.K. LOGISTICA - ⏳ Guardando, por favor espere..."); QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor); QApplication.processEvents()
                guias_txt = [d['guia'] for d in datos_finales]; guias_existentes = self.main.session.query(Operacion.guia_remito).filter(Operacion.guia_remito.in_(guias_txt)).all(); set_existentes = {g[0] for g in guias_existentes}
                for i, d in enumerate(datos_finales):
                    if i % 15 == 0: QApplication.processEvents() 
                    if d['guia'] in set_existentes: omitidas += 1; continue
                    peso_txt = d.get('peso', 0.0); bultos_txt = d['bultos']; precio = self.main.obtener_precio(self.main.sucursal_actual, bultos_txt, 0, proveedor="DHL", peso=peso_txt, bultos_totales=bultos_txt)
                    op = Operacion(fecha_ingreso=d['fecha_ingreso'], sucursal=self.main.sucursal_actual, guia_remito=d['guia'], proveedor="DHL", destinatario=d['destinatario'][:100].upper(), domicilio=d['domicilio'][:150].upper(), localidad=self.main.sucursal_actual.upper(), celular=d['celular'][:50], bultos=bultos_txt, bultos_frio=0, peso=peso_txt, tipo_carga="COMUN", tipo_urgencia=Urgencia.CLASICO, monto_servicio=precio, estado=Estados.EN_DEPOSITO, tipo_servicio="Entrega (Reparto)")
                    self.main.session.add(op); hist = Historial(operacion=op, usuario=self.main.usuario.username, accion="INGRESO IMPORTADO", detalle="Carga masiva por TXT DHL"); self.main.session.add(hist); agregadas += 1
                self.main.session.commit(); QApplication.restoreOverrideCursor(); self.main.setWindowTitle(f"E.K. LOGISTICA (NUBE) - Usuario: {self.main.usuario.username.upper()}")
                QMessageBox.information(self, "Importación Exitosa", f"✅ {agregadas} guías agregadas.\n⚠️ {omitidas} omitidas (ya existían)."); self.cargar_movimientos_dia()
                if hasattr(self.main, 'cargar_monitor_global'): self.main.cargar_monitor_global()
        except Exception: QApplication.restoreOverrideCursor(); self.main.setWindowTitle(f"E.K. LOGISTICA (NUBE) - Usuario: {self.main.usuario.username.upper()}"); self.main.session.rollback(); QMessageBox.warning(self, "Micro-corte", "Se interrumpió la conexión.")

    def cargar_movimientos_dia(self):
        try:
            self.tabla_ingresos.setRowCount(0)
            fecha_filtro = self.in_fecha.date().toPyDate()
            ops = self.main.session.query(Operacion).filter(Operacion.estado.in_([Estados.EN_DEPOSITO, 'EN DEPÓSITO']), Operacion.sucursal == self.main.sucursal_actual, text("DATE(COALESCE(fecha_salida, fecha_ingreso)) <= :f").bindparams(f=fecha_filtro)).order_by(Operacion.id.desc()).all()
            for row, op in enumerate(ops):
                if row % 10 == 0: QApplication.processEvents()
                self.tabla_ingresos.insertRow(row); self.tabla_ingresos.setItem(row, 0, QTableWidgetItem(str(op.id)))
                icon_srv = "🚚" if "Entrega" in op.tipo_servicio else ("🔄" if "Retiro" in op.tipo_servicio else "⏱️"); srv_txt = "Flete" if "Flete" in op.tipo_servicio else ("Retiro" if "Retiro" in op.tipo_servicio else "Entrega")
                self.tabla_ingresos.setItem(row, 1, QTableWidgetItem(f"{icon_srv} {srv_txt.upper()}")); self.tabla_ingresos.setItem(row, 2, QTableWidgetItem(op.guia_remito.upper())); self.tabla_ingresos.setItem(row, 3, QTableWidgetItem(op.proveedor.upper())); self.tabla_ingresos.setItem(row, 4, QTableWidgetItem(op.destinatario.upper())); self.tabla_ingresos.setItem(row, 5, QTableWidgetItem(op.domicilio.upper())); self.tabla_ingresos.setItem(row, 6, QTableWidgetItem(op.localidad.upper()))
                bultos_tot = op.bultos or 1
                bultos_fr = op.bultos_frio or 0
                det_b = str(bultos_tot)
                if bultos_fr > 0 and bultos_fr < bultos_tot: det_b += f" ({bultos_tot-bultos_fr}C/{bultos_fr}R)"
                elif bultos_fr == bultos_tot: det_b += " (R)"
                self.tabla_ingresos.setItem(row, 7, QTableWidgetItem(det_b))
        except Exception: self.main.session.rollback()