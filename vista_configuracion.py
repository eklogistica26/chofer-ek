from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                             QComboBox, QPushButton, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QMessageBox, QGroupBox, QFormLayout, 
                             QListWidget, QStackedWidget, QAbstractItemView, 
                             QDoubleSpinBox, QCheckBox, QTabWidget, QDialog)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from datetime import datetime
from sqlalchemy import text, desc

from database import (ClientePrincipal, DestinoFrecuente, Tarifa, TarifaDHL, 
                      HistorialTarifas, Chofer, ClienteRetiro, Usuario)
from dialogos import EditarEmpresaDialog, EditarDestinoDialog, EditarTarifaDialog, HistorialTarifasDialog, EditarUsuarioDialog

# --- NUEVO DIÁLOGO PARA EDITAR CHOFERES (CON DNI) ---
class EditarChoferDialog(QDialog):
    def __init__(self, chofer_id, nombre, sucursal, dni, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"✏️ Editar Chofer: {nombre}")
        self.setGeometry(400, 300, 350, 200)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        self.in_nom = QLineEdit(nombre)
        self.in_suc = QComboBox()
        self.in_suc.addItems(["Mendoza", "San Juan"])
        self.in_suc.setCurrentText(sucursal)
        self.in_dni = QLineEdit(dni)
        self.in_dni.setPlaceholderText("Ej: 35123456 (Sin puntos)")
        
        form.addRow("Nombre:", self.in_nom)
        form.addRow("Sucursal:", self.in_suc)
        form.addRow("DNI (Clave App):", self.in_dni)
        layout.addLayout(form)
        
        btn = QPushButton("GUARDAR CAMBIOS")
        btn.setStyleSheet("background-color: #0d6efd; color: white; font-weight: bold; padding: 10px;")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)
        
    @property
    def datos(self):
        return self.in_nom.text().strip(), self.in_suc.currentText(), self.in_dni.text().strip()

class TabConfiguracion(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main = main_window 
        self.setup_ui()

    def setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.list_menu = QListWidget()
        self.list_menu.setFixedWidth(220)
        self.list_menu.addItems(["💲 Tarifas", "🚛 Choferes", "🏢 Clientes Retiro", "🏢 Proveedores y Destinos", "👥 Usuarios"])
        self.list_menu.setCurrentRow(0)
        self.list_menu.currentRowChanged.connect(self.cambiar_panel_config)
        
        self.stack_config = QStackedWidget()
        
        self.page_tarifas = QWidget(); self.setup_panel_tarifas()
        self.page_choferes = QWidget(); self.setup_panel_choferes()
        self.page_clientes = QWidget(); self.setup_panel_clientes()
        self.page_proveedores = QWidget(); self.setup_panel_proveedores() 
        self.page_usuarios = QWidget(); self.setup_panel_usuarios()
        
        self.stack_config.addWidget(self.page_tarifas)
        self.stack_config.addWidget(self.page_choferes)
        self.stack_config.addWidget(self.page_clientes)
        self.stack_config.addWidget(self.page_proveedores)
        self.stack_config.addWidget(self.page_usuarios)
        
        main_layout.addWidget(self.list_menu)
        main_layout.addWidget(self.stack_config)
    
    def cambiar_panel_config(self, index): 
        self.stack_config.setCurrentIndex(index)
    
    # --- PANEL PROVEEDORES ---
    def setup_panel_proveedores(self):
        l = QHBoxLayout(self.page_proveedores); col_prov = QVBoxLayout(); gb_prov = QGroupBox("1. Empresas / Proveedores"); f_prov = QHBoxLayout()
        self.cfg_prov_nombre = QLineEdit(); self.cfg_prov_nombre.setPlaceholderText("Nombre Empresa")
        btn_add_prov = QPushButton("➕"); btn_add_prov.clicked.connect(self.guardar_proveedor)
        f_prov.addWidget(self.cfg_prov_nombre); f_prov.addWidget(btn_add_prov)
        self.tabla_proveedores = QTableWidget(); self.tabla_proveedores.setColumnCount(3); self.tabla_proveedores.hideColumn(0)
        self.tabla_proveedores.setHorizontalHeaderLabels(["ID", "Empresa", "Email Reportes"]); self.tabla_proveedores.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla_proveedores.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.tabla_proveedores.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla_proveedores.itemClicked.connect(self.cargar_destinos_de_proveedor) 
        btn_edit_prov = QPushButton("✏️ EDITAR EMPRESA"); btn_edit_prov.clicked.connect(self.editar_proveedor)
        btn_del_prov = QPushButton("🗑️ Eliminar Empresa"); btn_del_prov.clicked.connect(lambda: self.main.eliminar_fila(self.tabla_proveedores, ClientePrincipal))
        layout_prov = QVBoxLayout(); layout_prov.addLayout(f_prov); layout_prov.addWidget(self.tabla_proveedores); layout_prov.addWidget(btn_edit_prov); layout_prov.addWidget(btn_del_prov)
        gb_prov.setLayout(layout_prov); col_prov.addWidget(gb_prov)
        
        col_dest = QVBoxLayout(); self.gb_dest = QGroupBox("2. Destinos Frecuentes (Seleccione Empresa primero)"); self.gb_dest.setEnabled(False); f_dest = QFormLayout()
        self.cfg_dest_sucursal = QComboBox(); self.cfg_dest_sucursal.addItems(["Mendoza", "San Juan"]); f_dest.addRow("SUCURSAL:", self.cfg_dest_sucursal)
        self.cfg_dest_nombre = QLineEdit(); self.cfg_dest_nombre.setPlaceholderText("Nombre del Destinatario"); self.cfg_dest_dom = QLineEdit(); self.cfg_dest_dom.setPlaceholderText("Calle 123"); self.cfg_dest_cel = QLineEdit(); self.cfg_dest_cel.setPlaceholderText("Teléfono / Celular"); self.cfg_dest_loc = QLineEdit(); self.cfg_dest_loc.setPlaceholderText("Zona (Para la tarifa)")
        f_dest.addRow("DESTINATARIO:", self.cfg_dest_nombre); f_dest.addRow("DOMICILIO:", self.cfg_dest_dom); f_dest.addRow("CELULAR:", self.cfg_dest_cel); f_dest.addRow("ZONA:", self.cfg_dest_loc) 
        btn_add_dest = QPushButton("💾 GUARDAR DESTINO"); btn_add_dest.clicked.connect(self.guardar_destino_frecuente)
        self.tabla_destinos = QTableWidget(); self.tabla_destinos.setColumnCount(6); self.tabla_destinos.setHorizontalHeaderLabels(["ID", "SUC", "DESTINATARIO", "DOMICILIO", "CELULAR", "ZONA"]); self.tabla_destinos.verticalHeader().setVisible(False)
        header = self.tabla_destinos.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed); self.tabla_destinos.setColumnWidth(0, 40); header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed); self.tabla_destinos.setColumnWidth(1, 40)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch); header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch) 
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed); self.tabla_destinos.setColumnWidth(4, 100); header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed); self.tabla_destinos.setColumnWidth(5, 100) 
        self.tabla_destinos.verticalHeader().setDefaultSectionSize(40); self.tabla_destinos.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.tabla_destinos.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        btn_edit_dest = QPushButton("✏️ EDITAR DESTINO"); btn_edit_dest.clicked.connect(self.editar_destino_frecuente)
        btn_del_dest = QPushButton("🗑️ Eliminar Destino"); btn_del_dest.clicked.connect(lambda: self.main.eliminar_fila(self.tabla_destinos, DestinoFrecuente))
        layout_dest = QVBoxLayout(); layout_dest.addLayout(f_dest); layout_dest.addWidget(btn_add_dest); layout_dest.addWidget(self.tabla_destinos) 
        h_btns_dest = QHBoxLayout(); h_btns_dest.addWidget(btn_edit_dest); h_btns_dest.addWidget(btn_del_dest)
        layout_dest.addLayout(h_btns_dest); self.gb_dest.setLayout(layout_dest); col_dest.addWidget(self.gb_dest)
        l.addLayout(col_prov, 25); l.addLayout(col_dest, 75)

    def guardar_proveedor(self):
        n = self.cfg_prov_nombre.text().strip()
        if n:
            try: 
                self.main.session.add(ClientePrincipal(nombre=n)); self.main.session.commit()
                self.cfg_prov_nombre.clear(); self.cargar_proveedores_tabla(); self.main.actualizar_combos_dinamicos()
                QMessageBox.information(self, "Éxito", "Empresa agregada.")
            except: 
                self.main.session.rollback(); QMessageBox.warning(self, "Error", "Esa empresa ya existe o hubo un corte de red. Intenta de nuevo.")

    def editar_proveedor(self):
        r = self.tabla_proveedores.currentRow()
        if r < 0: return
        try:
            id_obj = int(self.tabla_proveedores.item(r, 0).text())
            prov = self.main.session.query(ClientePrincipal).get(id_obj)
            if prov:
                dlg = EditarEmpresaDialog(prov, self)
                if dlg.exec() == QDialog.DialogCode.Accepted:
                    self.main.session.commit(); self.cargar_proveedores_tabla(); self.main.actualizar_combos_dinamicos()
        except Exception as e: self.main.session.rollback()

    def cargar_proveedores_tabla(self):
        try:
            self.tabla_proveedores.setRowCount(0)
            for r, c in enumerate(self.main.session.query(ClientePrincipal).all()): 
                self.tabla_proveedores.insertRow(r); self.tabla_proveedores.setItem(r, 0, QTableWidgetItem(str(c.id)))
                self.tabla_proveedores.setItem(r, 1, QTableWidgetItem(c.nombre)); self.tabla_proveedores.setItem(r, 2, QTableWidgetItem(c.email_reportes or "-"))
        except Exception: self.main.session.rollback()

    def cargar_destinos_de_proveedor(self):
        r = self.tabla_proveedores.currentRow()
        if r < 0: return
        try:
            self.prov_seleccionado = self.tabla_proveedores.item(r, 1).text()
            self.gb_dest.setTitle(f"2. Destinos de: {self.prov_seleccionado}")
            self.gb_dest.setEnabled(True)
            self.tabla_destinos.setRowCount(0)
            dests = self.main.session.query(DestinoFrecuente).filter(DestinoFrecuente.proveedor == self.prov_seleccionado).order_by(DestinoFrecuente.id).all()
            for i, d in enumerate(dests):
                self.tabla_destinos.insertRow(i)
                id_item = QTableWidgetItem(str(d.id)); id_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter); id_item.setFont(QFont("Arial", 11, QFont.Weight.Bold)) 
                it_suc = QTableWidgetItem("M" if d.sucursal == "Mendoza" else ("S" if d.sucursal == "San Juan" else "-")); it_suc.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.tabla_destinos.setItem(i, 0, id_item); self.tabla_destinos.setItem(i, 1, it_suc); self.tabla_destinos.setItem(i, 2, QTableWidgetItem(d.destinatario))
                self.tabla_destinos.setItem(i, 3, QTableWidgetItem(d.domicilio)); self.tabla_destinos.setItem(i, 4, QTableWidgetItem(d.celular or "")); self.tabla_destinos.setItem(i, 5, QTableWidgetItem(d.localidad))
        except Exception: self.main.session.rollback()

    def guardar_destino_frecuente(self):
        if not hasattr(self, 'prov_seleccionado'): return
        nombre = self.cfg_dest_nombre.text()
        if not nombre: QMessageBox.warning(self, "Error", "El Destinatario es obligatorio"); return
        try:
            nuevo = DestinoFrecuente(proveedor=self.prov_seleccionado, sucursal=self.cfg_dest_sucursal.currentText(), alias=None, destinatario=nombre, domicilio=self.cfg_dest_dom.text(), localidad=self.cfg_dest_loc.text(), celular=self.cfg_dest_cel.text())
            self.main.session.add(nuevo); self.main.session.commit()
            self.cfg_dest_nombre.clear(); self.cfg_dest_dom.clear(); self.cfg_dest_loc.clear(); self.cfg_dest_cel.clear()
            self.cargar_destinos_de_proveedor(); QMessageBox.information(self, "Guardado", f"Destino guardado. ID: {nuevo.id}")
        except Exception: self.main.session.rollback(); QMessageBox.warning(self, "Micro-corte", "Conexión inestable. Intenta de nuevo.")

    def editar_destino_frecuente(self):
        r = self.tabla_destinos.currentRow()
        if r < 0: return
        try:
            id_obj = int(self.tabla_destinos.item(r, 0).text())
            destino = self.main.session.query(DestinoFrecuente).get(id_obj)
            if destino:
                dlg = EditarDestinoDialog(destino, self)
                if dlg.exec() == QDialog.DialogCode.Accepted: self.main.session.commit(); self.cargar_destinos_de_proveedor()
        except Exception: self.main.session.rollback()

    # --- PANEL TARIFAS ---
    def setup_panel_tarifas(self):
        l = QVBoxLayout(self.page_tarifas); self.tabs_tarifas = QTabWidget(); l.addWidget(self.tabs_tarifas)
        tab_gen = QWidget(); l_gen = QVBoxLayout(tab_gen)
        self.lbl_alerta_tarifa = QLabel("🟢 Tarifas actualizadas (Al día)"); l_gen.addWidget(self.lbl_alerta_tarifa)
        gb = QGroupBox("Gestión de Tarifas Generales (Por Sucursal)"); f = QFormLayout()
        self.cfg_tarifa_sucursal = QComboBox(); self.cfg_tarifa_sucursal.addItems(["Mendoza", "San Juan"]); self.cfg_tarifa_sucursal.currentTextChanged.connect(self.cargar_tarifas)
        self.cfg_zona = QLineEdit(); self.cfg_cc = QDoubleSpinBox(); self.cfg_cc.setRange(0, 9e6); self.cfg_cc.setPrefix("Común: $ "); self.cfg_rc = QDoubleSpinBox(); self.cfg_rc.setRange(0, 9e6); self.cfg_rc.setPrefix("Refrigerado: $ ")
        f.addRow("Sucursal:", self.cfg_tarifa_sucursal); f.addRow("Zona / Localidad:", self.cfg_zona); f.addRow("Común:", self.cfg_cc); f.addRow("Refrigerado:", self.cfg_rc)
        h_btn_t = QHBoxLayout(); btn = QPushButton("➕ AGREGAR TARIFA"); btn.clicked.connect(self.guardar_tarifa); btn_hist_t = QPushButton("📜 VER HISTORIAL"); btn_hist_t.clicked.connect(self.ver_historial_tarifas)
        h_btn_t.addWidget(btn); h_btn_t.addWidget(btn_hist_t); gb.setLayout(f); l_gen.addWidget(gb); l_gen.addLayout(h_btn_t)
        self.tabla_tarifas = QTableWidget(); self.tabla_tarifas.setColumnCount(4); self.tabla_tarifas.hideColumn(0); self.tabla_tarifas.setHorizontalHeaderLabels(["ID", "Zona", "Común", "Refrigerado"]); self.tabla_tarifas.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); self.tabla_tarifas.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.tabla_tarifas.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        l_gen.addWidget(self.tabla_tarifas)
        h_btn_d = QHBoxLayout(); btn_edit = QPushButton("✏️ Editar Seleccionada"); btn_edit.clicked.connect(self.editar_tarifa); btn_d = QPushButton("🗑️ Eliminar Tarifa"); btn_d.clicked.connect(lambda: self.main.eliminar_fila(self.tabla_tarifas, Tarifa))
        h_btn_d.addWidget(btn_edit); h_btn_d.addWidget(btn_d); l_gen.addLayout(h_btn_d); self.tabs_tarifas.addTab(tab_gen, "Generales (Zonas)")
        
        tab_dhl = QWidget(); l_dhl = QVBoxLayout(tab_dhl); gb_dhl = QGroupBox("Gestión de Tarifas DHL (Por Kilos y Bultos)"); f_dhl = QFormLayout()
        self.cfg_dhl_suc = QComboBox(); self.cfg_dhl_suc.addItems(["Mendoza", "San Juan"]); self.cfg_dhl_suc.currentTextChanged.connect(self.cargar_tarifas_dhl)
        self.cfg_dhl_t2 = QDoubleSpinBox(); self.cfg_dhl_t2.setRange(0, 9e6); self.cfg_dhl_t2.setPrefix("$ ")
        self.cfg_dhl_t5 = QDoubleSpinBox(); self.cfg_dhl_t5.setRange(0, 9e6); self.cfg_dhl_t5.setPrefix("$ ")
        self.cfg_dhl_t10 = QDoubleSpinBox(); self.cfg_dhl_t10.setRange(0, 9e6); self.cfg_dhl_t10.setPrefix("$ ")
        self.cfg_dhl_t20 = QDoubleSpinBox(); self.cfg_dhl_t20.setRange(0, 9e6); self.cfg_dhl_t20.setPrefix("$ ")
        self.cfg_dhl_t30 = QDoubleSpinBox(); self.cfg_dhl_t30.setRange(0, 9e6); self.cfg_dhl_t30.setPrefix("$ ")
        self.cfg_dhl_exc = QDoubleSpinBox(); self.cfg_dhl_exc.setRange(0, 9e6); self.cfg_dhl_exc.setPrefix("$ ")
        f_dhl.addRow("Sucursal:", self.cfg_dhl_suc); f_dhl.addRow("0 a 2 Kg:", self.cfg_dhl_t2); f_dhl.addRow("2 a 5 Kg:", self.cfg_dhl_t5); f_dhl.addRow("5 a 10 Kg:", self.cfg_dhl_t10); f_dhl.addRow("10 a 20 Kg:", self.cfg_dhl_t20); f_dhl.addRow("20 a 30 Kg:", self.cfg_dhl_t30); f_dhl.addRow("Excedente (x Kg):", self.cfg_dhl_exc)
        btn_dhl = QPushButton("💾 GUARDAR TARIFA DHL"); btn_dhl.clicked.connect(self.guardar_tarifa_dhl); gb_dhl.setLayout(f_dhl); l_dhl.addWidget(gb_dhl); l_dhl.addWidget(btn_dhl); l_dhl.addStretch(); self.tabs_tarifas.addTab(tab_dhl, "DHL (Por Peso)")

    def guardar_tarifa_dhl(self):
        suc_sel = self.cfg_dhl_suc.currentText()
        try:
            t = self.main.session.query(TarifaDHL).filter(TarifaDHL.sucursal == suc_sel).first()
            if not t: t = TarifaDHL(sucursal=suc_sel); self.main.session.add(t)
            t.t2 = self.cfg_dhl_t2.value(); t.t5 = self.cfg_dhl_t5.value(); t.t10 = self.cfg_dhl_t10.value()
            t.t20 = self.cfg_dhl_t20.value(); t.t30 = self.cfg_dhl_t30.value(); t.excedente = self.cfg_dhl_exc.value()
            hist = HistorialTarifas(zona=f"DHL {suc_sel}", detalle=f"Base: ${t.t2} a ${t.t30} | Exc: ${t.excedente}", usuario=self.main.usuario.username)
            self.main.session.add(hist); self.main.session.commit(); self.main.toast.mostrar("✅ Tarifa DHL guardada")
            self.calcular_alerta_tarifas()
        except Exception as e: self.main.session.rollback(); QMessageBox.critical(self, "Error", str(e))

    def cargar_tarifas_dhl(self):
        suc_sel = self.cfg_dhl_suc.currentText()
        try:
            t = self.main.session.query(TarifaDHL).filter(TarifaDHL.sucursal == suc_sel).first()
            if t:
                self.cfg_dhl_t2.setValue(t.t2); self.cfg_dhl_t5.setValue(t.t5); self.cfg_dhl_t10.setValue(t.t10)
                self.cfg_dhl_t20.setValue(t.t20); self.cfg_dhl_t30.setValue(t.t30); self.cfg_dhl_exc.setValue(t.excedente)
            else:
                self.cfg_dhl_t2.setValue(0); self.cfg_dhl_t5.setValue(0); self.cfg_dhl_t10.setValue(0)
                self.cfg_dhl_t20.setValue(0); self.cfg_dhl_t30.setValue(0); self.cfg_dhl_exc.setValue(0)
        except Exception: self.main.session.rollback()

    def guardar_tarifa(self):
        z = self.cfg_zona.text(); suc_sel = self.cfg_tarifa_sucursal.currentText()
        if z:
            try:
                t = self.main.session.query(Tarifa).filter(Tarifa.localidad == z, Tarifa.sucursal == suc_sel).first()
                if t: t.precio_base_comun = self.cfg_cc.value(); t.precio_base_refrig = self.cfg_rc.value()
                else: self.main.session.add(Tarifa(sucursal=suc_sel, localidad=z, precio_base_comun=self.cfg_cc.value(), precio_base_refrig=self.cfg_rc.value()))
                hist = HistorialTarifas(zona=f"{z} ({suc_sel})", detalle=f"Nueva/Ajuste. Común: ${self.cfg_cc.value()} | Refrig: ${self.cfg_rc.value()}", usuario=self.main.usuario.username)
                self.main.session.add(hist); self.main.session.commit()
                self.cfg_zona.clear(); self.cargar_tarifas(); self.main.actualizar_combos_dinamicos()
            except Exception: self.main.session.rollback(); QMessageBox.warning(self, "Error", "Intente de nuevo.")

    def cargar_tarifas(self):
        suc_sel = self.cfg_tarifa_sucursal.currentText()
        try:
            self.tabla_tarifas.setRowCount(0)
            tarifas = self.main.session.query(Tarifa).filter(Tarifa.sucursal == suc_sel).all()
            vistos = set()
            row = 0
            for t in tarifas:
                if t.localidad not in vistos:
                    vistos.add(t.localidad); self.tabla_tarifas.insertRow(row)
                    self.tabla_tarifas.setItem(row,0,QTableWidgetItem(str(t.id))); self.tabla_tarifas.setItem(row,1,QTableWidgetItem(t.localidad))
                    self.tabla_tarifas.setItem(row,2,QTableWidgetItem(str(t.precio_base_comun))); self.tabla_tarifas.setItem(row,3,QTableWidgetItem(str(t.precio_base_refrig)))
                    row += 1
            self.calcular_alerta_tarifas()
        except Exception: self.main.session.rollback()

    def editar_tarifa(self):
        r = self.tabla_tarifas.currentRow()
        if r < 0: QMessageBox.warning(self, "Atención", "Seleccione la tarifa a editar."); return
        try:
            id_tarifa = int(self.tabla_tarifas.item(r, 0).text())
            t_obj = self.main.session.query(Tarifa).get(id_tarifa)
            if not t_obj: return
            old_c = t_obj.precio_base_comun; old_r = t_obj.precio_base_refrig
            dlg = EditarTarifaDialog(t_obj, self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                new_c = dlg.in_cc.value(); new_r = dlg.in_rc.value()
                if new_c != old_c or new_r != old_r:
                    otras = self.main.session.query(Tarifa).filter(Tarifa.id != id_tarifa, Tarifa.precio_base_comun == old_c, Tarifa.sucursal == t_obj.sucursal).all()
                    if otras:
                        ans = QMessageBox.question(self, "Actualización", f"¿Aplicar precio a {len(otras)} zonas más con mismo precio?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                        if ans == QMessageBox.StandardButton.Yes:
                            for o_t in otras:
                                o_t.precio_base_comun = new_c; o_t.precio_base_refrig = new_r
                                h = HistorialTarifas(zona=f"{o_t.localidad} ({o_t.sucursal})", detalle=f"Actualización Masiva.", usuario=self.main.usuario.username)
                                self.main.session.add(h)
                    t_obj.precio_base_comun = new_c; t_obj.precio_base_refrig = new_r
                    h_main = HistorialTarifas(zona=f"{t_obj.localidad} ({t_obj.sucursal})", detalle=f"Cambio Manual.", usuario=self.main.usuario.username)
                    self.main.session.add(h_main); self.main.session.commit(); self.cargar_tarifas(); self.calcular_alerta_tarifas(); self.main.actualizar_combos_dinamicos()
        except Exception as e: self.main.session.rollback()

    def ver_historial_tarifas(self):
        try: dlg = HistorialTarifasDialog(self.main.session, self); dlg.exec()
        except Exception as e: self.main.session.rollback()

    def calcular_alerta_tarifas(self):
        if not hasattr(self, 'lbl_alerta_tarifa'): return
        try:
            last = self.main.session.query(HistorialTarifas).order_by(desc(HistorialTarifas.fecha_hora)).first()
            if not last: self.lbl_alerta_tarifa.setText("🔴 Sin historial de tarifas"); return
            dias = (datetime.now() - last.fecha_hora).days
            if dias > 30: self.lbl_alerta_tarifa.setText(f"🔴 ALERTA: Llevas {dias} días sin actualizar las tarifas.")
            else: self.lbl_alerta_tarifa.setText(f"🟢 Tarifas actualizadas (último cambio hace {dias} días).")
        except: self.main.session.rollback()

    # --- PANEL CHOFERES ---
    def setup_panel_choferes(self):
        l = QVBoxLayout(self.page_choferes); gb = QGroupBox("Gestión de Choferes"); f = QFormLayout()
        
        self.cfg_chofer_nombre = QLineEdit()
        self.cfg_chofer_sucursal = QComboBox()
        self.cfg_chofer_sucursal.addItems(["Mendoza", "San Juan"])
        self.cfg_chofer_dni = QLineEdit()
        self.cfg_chofer_dni.setPlaceholderText("Ej: 35123456 (Contraseña App)")
        
        f.addRow("Nombre:", self.cfg_chofer_nombre)
        f.addRow("Sucursal:", self.cfg_chofer_sucursal)
        f.addRow("DNI (Clave App):", self.cfg_chofer_dni)
        
        btn = QPushButton("➕ AGREGAR CHOFER")
        btn.clicked.connect(self.guardar_chofer)
        gb.setLayout(f); l.addWidget(gb); l.addWidget(btn)
        
        self.tabla_choferes = QTableWidget(); self.tabla_choferes.setColumnCount(4); self.tabla_choferes.hideColumn(0)
        self.tabla_choferes.setHorizontalHeaderLabels(["ID", "Nombre", "Sucursal", "DNI (Clave)"])
        self.tabla_choferes.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla_choferes.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla_choferes.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        l.addWidget(self.tabla_choferes)
        
        h_btns = QHBoxLayout()
        btn_edit = QPushButton("✏️ Editar Chofer"); btn_edit.clicked.connect(self.editar_chofer)
        btn_d = QPushButton("🗑️ Eliminar Chofer"); btn_d.clicked.connect(lambda: self.main.eliminar_fila(self.tabla_choferes, Chofer))
        h_btns.addWidget(btn_edit); h_btns.addWidget(btn_d)
        l.addLayout(h_btns)
        
    def guardar_chofer(self):
        n = self.cfg_chofer_nombre.text().strip()
        s = self.cfg_chofer_sucursal.currentText()
        d = self.cfg_chofer_dni.text().strip()
        if n: 
            try: 
                self.main.session.execute(text("INSERT INTO choferes (nombre, sucursal, dni) VALUES (:n, :s, :d)"), {"n": n, "s": s, "d": d})
                self.main.session.commit()
                self.cfg_chofer_nombre.clear()
                self.cfg_chofer_dni.clear()
                self.cargar_choferes_tabla()
                self.main.actualizar_combos_dinamicos()
            except Exception as e: 
                self.main.session.rollback()
                QMessageBox.warning(self, "Error", f"No se pudo guardar. Intente de nuevo.")
        
    def cargar_choferes_tabla(self):
        try:
            self.tabla_choferes.setRowCount(0)
            res = self.main.session.execute(text("SELECT id, nombre, sucursal, dni FROM choferes ORDER BY sucursal, nombre")).fetchall()
            for r, c in enumerate(res): 
                self.tabla_choferes.insertRow(r)
                self.tabla_choferes.setItem(r, 0, QTableWidgetItem(str(c[0])))
                self.tabla_choferes.setItem(r, 1, QTableWidgetItem(c[1]))
                self.tabla_choferes.setItem(r, 2, QTableWidgetItem(c[2]))
                self.tabla_choferes.setItem(r, 3, QTableWidgetItem(str(c[3] or "")))
        except Exception: self.main.session.rollback()

    def editar_chofer(self):
        r = self.tabla_choferes.currentRow()
        if r < 0: 
            QMessageBox.warning(self, "Atención", "Seleccione un chofer de la tabla para editar.")
            return
        id_obj = int(self.tabla_choferes.item(r, 0).text())
        n = self.tabla_choferes.item(r, 1).text()
        s = self.tabla_choferes.item(r, 2).text()
        d = self.tabla_choferes.item(r, 3).text()
        
        dlg = EditarChoferDialog(id_obj, n, s, d, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            n_new, s_new, d_new = dlg.datos
            try:
                self.main.session.execute(text("UPDATE choferes SET nombre=:n, sucursal=:s, dni=:d WHERE id=:id"), {"n": n_new, "s": s_new, "d": d_new, "id": id_obj})
                self.main.session.commit()
                self.cargar_choferes_tabla()
                self.main.actualizar_combos_dinamicos()
                self.main.toast.mostrar("✅ Chofer actualizado.")
            except Exception as e:
                self.main.session.rollback()
                QMessageBox.warning(self, "Error", "No se pudo actualizar el chofer.")
    
    def setup_panel_clientes(self):
        l = QVBoxLayout(self.page_clientes); gb = QGroupBox("Clientes Frecuentes"); f = QFormLayout()
        self.cfg_cli_nom = QLineEdit(); self.cfg_cli_dom = QLineEdit(); self.cfg_cli_cel = QLineEdit(); self.cfg_cli_loc = QLineEdit()
        f.addRow("Nombre:", self.cfg_cli_nom); f.addRow("Dirección:", self.cfg_cli_dom); f.addRow("Celular:", self.cfg_cli_cel); f.addRow("Zona:", self.cfg_cli_loc)
        btn = QPushButton("➕ AGREGAR CLIENTE"); btn.clicked.connect(self.guardar_cliente)
        gb.setLayout(f); l.addWidget(gb); l.addWidget(btn)
        self.tabla_clientes = QTableWidget(); self.tabla_clientes.setColumnCount(3); self.tabla_clientes.hideColumn(0); self.tabla_clientes.setHorizontalHeaderLabels(["ID", "Cliente", "Domicilio"]); self.tabla_clientes.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla_clientes.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.tabla_clientes.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        l.addWidget(self.tabla_clientes); btn_d = QPushButton("Eliminar Cliente"); btn_d.clicked.connect(lambda: self.main.eliminar_fila(self.tabla_clientes, ClienteRetiro)); l.addWidget(btn_d)
    
    # 🔥 PANEL USUARIOS ACTUALIZADO CON CRM Y ESTADISTICAS 🔥
    def setup_panel_usuarios(self):
        l = QVBoxLayout(self.page_usuarios); gb = QGroupBox("Usuarios y Permisos"); f = QFormLayout()
        self.u_user = QLineEdit(); self.u_pass = QLineEdit(); self.u_suc = QComboBox(); self.u_suc.addItems(["Mendoza", "San Juan"]); self.chk_admin = QCheckBox("Es Admin Total"); 
        self.chk_rep = QCheckBox("Ver Reportes"); self.chk_fac = QCheckBox("Ver Facturación"); self.chk_conf = QCheckBox("Ver Configuración"); self.chk_rend = QCheckBox("Ver Rendición")
        
        # Nuevos checkboxes
        self.chk_crm = QCheckBox("Ver CRM"); self.chk_est = QCheckBox("Ver Estadísticas")
        
        ly_checks1 = QHBoxLayout(); ly_checks1.addWidget(self.chk_rep); ly_checks1.addWidget(self.chk_fac); ly_checks1.addWidget(self.chk_conf); ly_checks1.addWidget(self.chk_rend)
        ly_checks2 = QHBoxLayout(); ly_checks2.addWidget(self.chk_crm); ly_checks2.addWidget(self.chk_est); ly_checks2.addStretch()

        f.addRow("Usuario:", self.u_user); f.addRow("Pass:", self.u_pass); f.addRow("Sucursal:", self.u_suc); f.addRow(self.chk_admin); 
        f.addRow("Permisos:", ly_checks1); f.addRow("", ly_checks2)
        btn = QPushButton("➕ CREAR USUARIO"); btn.clicked.connect(self.guardar_usuario)
        gb.setLayout(f); l.addWidget(gb); l.addWidget(btn)
        
        self.tabla_usuarios = QTableWidget(); self.tabla_usuarios.setColumnCount(5); self.tabla_usuarios.hideColumn(0); self.tabla_usuarios.setHorizontalHeaderLabels(["ID", "Usuario", "Sucursal", "Admin?", "Permisos"]); self.tabla_usuarios.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla_usuarios.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.tabla_usuarios.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        l.addWidget(self.tabla_usuarios)
        
        h_btns_u = QHBoxLayout()
        btn_edit_u = QPushButton("✏️ Editar Usuario")
        btn_edit_u.clicked.connect(self.editar_usuario)
        btn_d = QPushButton("🗑️ Eliminar Usuario")
        btn_d.clicked.connect(lambda: self.main.eliminar_fila(self.tabla_usuarios, Usuario))
        h_btns_u.addWidget(btn_edit_u); h_btns_u.addWidget(btn_d)
        l.addLayout(h_btns_u)
        self.cargar_usuarios_tabla()
    
    def guardar_usuario(self):
        u = self.u_user.text().strip().lower(); p = self.u_pass.text().strip()
        if not u or not p: return
        try: 
            usr = Usuario(username=u, password=p, sucursal_asignada=self.u_suc.currentText(), es_admin_total=self.chk_admin.isChecked(), ver_reportes=self.chk_rep.isChecked(), ver_facturacion=self.chk_fac.isChecked(), ver_configuracion=self.chk_conf.isChecked(), ver_rendicion=self.chk_rend.isChecked(), ver_crm=self.chk_crm.isChecked(), ver_estadisticas=self.chk_est.isChecked())
            self.main.session.add(usr); self.main.session.commit(); QMessageBox.information(self, "Éxito", "Usuario creado."); self.u_user.clear(); self.u_pass.clear(); self.cargar_usuarios_tabla()
        except Exception as e: self.main.session.rollback(); QMessageBox.warning(self, "Error", "El usuario ya existe.")
            
    def editar_usuario(self):
        r = self.tabla_usuarios.currentRow()
        if r < 0: 
            QMessageBox.warning(self, "Atención", "Seleccione un usuario de la tabla para editar.")
            return
        try:
            id_obj = int(self.tabla_usuarios.item(r, 0).text())
            usr = self.main.session.query(Usuario).get(id_obj)
            if usr:
                # Nota: El cuadro emergente solo editará permisos base. Para los nuevos, se respeta el valor existente (d.get).
                dlg = EditarUsuarioDialog(usr, self)
                if dlg.exec() == QDialog.DialogCode.Accepted:
                    d = dlg.datos
                    if d['user'] and d['pass']:
                        usr.username = d['user']
                        usr.password = d['pass']
                        usr.sucursal_asignada = d['suc']
                        usr.es_admin_total = d['admin']
                        usr.ver_reportes = d['rep']
                        usr.ver_facturacion = d['fac']
                        usr.ver_configuracion = d['conf']
                        usr.ver_rendicion = d['rend']
                        
                        # Mantiene los permisos de CRM y Stats si el dialog no los proveyó
                        usr.ver_crm = d.get('crm', usr.ver_crm)
                        usr.ver_estadisticas = d.get('est', usr.ver_estadisticas)
                        
                        self.main.session.commit()
                        self.cargar_usuarios_tabla()
                        QMessageBox.information(self, "Éxito", "Usuario editado correctamente.")
                    else:
                        QMessageBox.warning(self, "Error", "Usuario y contraseña no pueden estar vacíos.")
        except Exception as e:
            self.main.session.rollback()

    def cargar_usuarios_tabla(self):
        try:
            self.tabla_usuarios.setRowCount(0); us = self.main.session.query(Usuario).all()
            for r, u in enumerate(us):
                self.tabla_usuarios.insertRow(r); self.tabla_usuarios.setItem(r, 0, QTableWidgetItem(str(u.id))); self.tabla_usuarios.setItem(r, 1, QTableWidgetItem(u.username)); self.tabla_usuarios.setItem(r, 2, QTableWidgetItem(u.sucursal_asignada)); self.tabla_usuarios.setItem(r, 3, QTableWidgetItem("SI" if u.es_admin_total else "NO"))
                perms = []
                if u.ver_reportes: perms.append("Rep")
                if u.ver_facturacion: perms.append("Fac")
                if u.ver_configuracion: perms.append("Cfg")
                if u.ver_rendicion: perms.append("Rend")
                if u.ver_crm: perms.append("CRM")
                if u.ver_estadisticas: perms.append("Est")
                self.tabla_usuarios.setItem(r, 4, QTableWidgetItem(", ".join(perms)))
        except Exception: self.main.session.rollback()
        
    def guardar_cliente(self):
        n = self.cfg_cli_nom.text(); d = self.cfg_cli_dom.text(); c = self.cfg_cli_cel.text(); l = self.cfg_cli_loc.text()
        if n: 
            try: self.main.session.add(ClienteRetiro(sucursal=self.main.sucursal_actual, nombre=n, domicilio=d, celular=c, localidad=l)); self.main.session.commit(); self.cfg_cli_nom.clear(); self.cargar_clientes_tabla(); self.main.actualizar_combos_dinamicos()
            except Exception: self.main.session.rollback()
        
    def cargar_clientes_tabla(self):
        try:
            self.tabla_clientes.setRowCount(0)
            for r,l in enumerate(self.main.session.query(ClienteRetiro).order_by(ClienteRetiro.sucursal).all()): self.tabla_clientes.insertRow(r); self.tabla_clientes.setItem(r,0,QTableWidgetItem(str(l.id))); self.tabla_clientes.setItem(r,1,QTableWidgetItem(l.nombre)); self.tabla_clientes.setItem(r,2,QTableWidgetItem(l.domicilio))
        except Exception: self.main.session.rollback()