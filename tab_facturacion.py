import os
import calendar
from datetime import datetime, date
from PyQt6.QtWidgets import (QApplication, QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                             QComboBox, QPushButton, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QMessageBox, QSpinBox, QDoubleSpinBox, QFrame, QFileDialog, QTabWidget, 
                             QAbstractItemView, QStyledItemDelegate, QProgressDialog, QFormLayout, QCheckBox, QDateEdit)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QColor, QFont, QBrush
from sqlalchemy import text, func

from database import Operacion, Historial, Estados, ReciboPago
from utilidades import crear_pdf_facturacion, crear_pdf_despacho_papeles
from dialogos import AgregarCargoDialog, CargarPagoDialog

# 🔥 CORTAFUEGOS DE SEGURIDAD PARA COMBOS DE PROVEEDORES 🔥
class RestrictedComboBox(QComboBox):
    def __init__(self, main_app, parent=None):
        super().__init__(parent)
        self.main_app = main_app

    def addItem(self, *args, **kwargs):
        es_sj = not getattr(self.main_app.usuario, 'es_admin_total', False) and getattr(self.main_app.usuario, 'sucursal_asignada', '') == "San Juan"
        if es_sj:
            if self.findText("DHL EXPRESS") == -1:
                super().addItem("DHL EXPRESS")
        else:
            super().addItem(*args, **kwargs)

    def addItems(self, texts):
        es_sj = not getattr(self.main_app.usuario, 'es_admin_total', False) and getattr(self.main_app.usuario, 'sucursal_asignada', '') == "San Juan"
        if es_sj:
            if self.findText("DHL EXPRESS") == -1:
                super().addItem("DHL EXPRESS")
        else:
            super().addItems(texts)

class DeshacerFacturacionDialog(QDialog):
    def __init__(self, main_app, parent=None):
        super().__init__(parent)
        self.main_app = main_app; self.setWindowTitle("⏪ Deshacer Facturación"); self.setGeometry(400, 200, 750, 400)
        layout = QVBoxLayout(self)
        lbl = QLabel("Seleccione las guías que desea devolver a estado 'No Facturado':"); lbl.setStyleSheet("font-weight: bold; color: #d32f2f;"); layout.addWidget(lbl)
        self.tabla = QTableWidget(); self.tabla.setColumnCount(7); self.tabla.setHorizontalHeaderLabels(["ID", "Sel.", "Fecha", "Guía", "Proveedor", "Destinatario", "Total ($)"]); self.tabla.hideColumn(0)
        header = self.tabla.horizontalHeader(); header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive); self.tabla.setColumnWidth(1, 40); self.tabla.setColumnWidth(2, 90); self.tabla.setColumnWidth(3, 140); self.tabla.setColumnWidth(4, 150); self.tabla.setColumnWidth(5, 200); header.setStretchLastSection(True); self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); layout.addWidget(self.tabla)
        btn_deshacer = QPushButton("⏪ DEVOLVER A LA TABLA PRINCIPAL"); btn_deshacer.setStyleSheet("background-color: #ff9800; font-weight: bold; padding: 10px; color: black;"); btn_deshacer.clicked.connect(self.procesar_deshacer); layout.addWidget(btn_deshacer)
        self.cargar_datos()
    def cargar_datos(self):
        self.tabla.setRowCount(0); f_limite = QDate.currentDate().addDays(-60).toPyDate()
        try:
            ops = self.main_app.session.query(Operacion).filter(Operacion.facturado == True, Operacion.sucursal == self.main_app.sucursal_actual, Operacion.fecha_ingreso >= f_limite).order_by(Operacion.id.desc()).limit(150).all()
            for r, op in enumerate(ops):
                self.tabla.insertRow(r); self.tabla.setItem(r, 0, QTableWidgetItem(str(op.id)))
                chk = QTableWidgetItem(); chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled); chk.setCheckState(Qt.CheckState.Unchecked); self.tabla.setItem(r, 1, chk)
                self.tabla.setItem(r, 2, QTableWidgetItem(op.fecha_ingreso.strftime("%d/%m/%Y") if op.fecha_ingreso else "-")); self.tabla.setItem(r, 3, QTableWidgetItem(op.guia_remito or "-")); self.tabla.setItem(r, 4, QTableWidgetItem(op.proveedor or "-")); self.tabla.setItem(r, 5, QTableWidgetItem(op.destinatario or "-")); self.tabla.setItem(r, 6, QTableWidgetItem(f"$ {op.monto_servicio:,.2f}"))
        except Exception: pass
    def procesar_deshacer(self):
        ids = [int(self.tabla.item(r, 0).text()) for r in range(self.tabla.rowCount()) if self.tabla.item(r, 1).checkState() == Qt.CheckState.Checked]
        if not ids: QMessageBox.warning(self, "Aviso", "Seleccione al menos una guía."); return
        try:
            ops = self.main_app.session.query(Operacion).filter(Operacion.id.in_(ids)).all()
            for op in ops: op.facturado = False
            self.main_app.session.commit(); QMessageBox.information(self, "Éxito", f"Se deshizo la facturación de {len(ids)} guías."); self.accept()
        except Exception as e: self.main_app.session.rollback(); QMessageBox.critical(self, "Error", str(e))

class PintorCeldasDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        bg_color = index.data(Qt.ItemDataRole.BackgroundRole)
        if bg_color: painter.fillRect(option.rect, bg_color)
        super().paint(painter, option, index)

ESTILO_TABLAS_BLANCAS = "QTableWidget { background-color: #ffffff !important; } QTableWidget::item { background-color: transparent !important; color: #000000 !important; border-bottom: 1px solid #f0f0f0 !important; } QTableWidget::item:selected { background-color: #bbdefb !important; color: #000000 !important; }"

class AjusteAvanzadoFacturacionDialog(QDialog):
    def __init__(self, op, main_app, visitas=1, parent=None):
        super().__init__(parent)
        self.op = op; self.main_app = main_app
        self.setWindowTitle(f"🛠️ Ajuste Integral de Facturación - ID: {op.id}")
        self.setFixedSize(520, 850) 
        layout = QVBoxLayout(self)

        bultos_tot = int(op.bultos) if op.bultos else 1
        bultos_fr = int(op.bultos_frio) if op.bultos_frio else 0
        bultos_com = bultos_tot - bultos_fr

        info_text = f"<span style='font-size:13px; color:#1565c0;'><b>Estado actual:</b> {op.estado} (Salidas reales a calle: <b>{visitas}</b>)</span>"
        lbl_info = QLabel(info_text)
        lbl_info.setStyleSheet("background-color: #e3f2fd; padding: 10px; border: 1px solid #90caf9; border-radius: 6px; margin-bottom: 10px;")
        layout.addWidget(lbl_info)

        form = QFormLayout()

        # --- DATOS DEL PAQUETE (ESPEJO TOTAL) ---
        self.in_guia = QLineEdit(op.guia_remito or "")
        
        self.in_prov = QComboBox()
        self.in_prov.addItems(self.main_app.lista_proveedores)
        self.in_prov.setCurrentText(op.proveedor)
        self.in_prov.setEditable(True) 
        
        self.in_dest = QLineEdit(op.destinatario or "")
        
        self.in_peso = QDoubleSpinBox()
        self.in_peso.setRange(0, 10000.0)
        self.in_peso.setSuffix(" Kg")
        self.in_peso.setSingleStep(0.5)
        self.in_peso.setValue(op.peso or 0.0)

        form.addRow("🏷️ Guía / Remito:", self.in_guia)
        form.addRow("🏢 Proveedor:", self.in_prov)
        form.addRow("👤 Destinatario:", self.in_dest)
        form.addRow("⚖️ Peso Real (Kg):", self.in_peso)
        
        linea = QFrame(); linea.setFrameShape(QFrame.Shape.HLine); linea.setFrameShadow(QFrame.Shadow.Sunken)
        form.addRow(linea)

        # --- DATOS OPERATIVOS ---
        self.in_fecha = QDateEdit()
        self.in_fecha.setCalendarPopup(True)
        self.in_fecha.setDisplayFormat("dd/MM/yyyy")
        if op.fecha_entrega:
            d = op.fecha_entrega.date()
            self.in_fecha.setDate(QDate(d.year, d.month, d.day))
        elif op.fecha_ingreso:
            d = op.fecha_ingreso
            if isinstance(d, datetime): d = d.date()
            self.in_fecha.setDate(QDate(d.year, d.month, d.day))
        else:
            self.in_fecha.setDate(QDate.currentDate())
        
        form.addRow("📅 Fecha Real de Entrega:", self.in_fecha)

        from database import Tarifa 
        zonas = [z[0] for z in self.main_app.session.query(Tarifa.localidad).filter(Tarifa.sucursal == op.sucursal).distinct().all()]

        self.combo_zona = QComboBox()
        self.combo_zona.addItems(sorted(zonas))
        self.combo_zona.setCurrentText(op.localidad)

        self.in_bultos = QSpinBox(); self.in_bultos.setRange(1, 1000); self.in_bultos.setValue(bultos_tot)
        self.in_frio = QSpinBox(); self.in_frio.setRange(0, 1000); self.in_frio.setValue(bultos_fr)

        self.chk_combinado = QCheckBox("📦 CARGA COMBINADA (Cobrar todo junto por mayor valor)")
        self.chk_combinado.setStyleSheet("color: #d32f2f; font-weight: bold; padding: 5px;")
        if bultos_com > 0 and bultos_fr > 0: 
            self.chk_combinado.setChecked(True)

        form.addRow("🗺️ Zona de Tarifa:", self.combo_zona)
        form.addRow("📦 Bultos Totales:", self.in_bultos)
        form.addRow("❄️ Bultos Refrigerados:", self.in_frio)
        form.addRow("", self.chk_combinado)
        layout.addLayout(form)

        # --- EXTRAS OPERATIVOS ---
        layout.addWidget(QLabel("<b>📅 Recargos Finde / Feriado:</b>"))
        
        h_finde = QHBoxLayout()
        self.btn_finde = QPushButton("🟡 Calcular Finde (x2)")
        self.btn_finde.setStyleSheet("background-color: #ffc107; color: black; font-weight: bold; padding: 6px; border-radius: 4px;")
        self.in_finde = QDoubleSpinBox()
        self.in_finde.setRange(0, 1000000); self.in_finde.setPrefix("$ "); self.in_finde.setSingleStep(500.0)
        h_finde.addWidget(self.btn_finde)
        h_finde.addWidget(self.in_finde)
        layout.addLayout(h_finde)

        h_feriado = QHBoxLayout()
        self.btn_feriado = QPushButton("🔴 Calcular Feriado (x3)")
        self.btn_feriado.setStyleSheet("background-color: #dc3545; color: white; font-weight: bold; padding: 6px; border-radius: 4px;")
        self.in_feriado = QDoubleSpinBox()
        self.in_feriado.setRange(0, 1000000); self.in_feriado.setPrefix("$ "); self.in_feriado.setSingleStep(500.0)
        h_feriado.addWidget(self.btn_feriado)
        h_feriado.addWidget(self.in_feriado)
        layout.addLayout(h_feriado)

        layout.addWidget(QLabel("<b>⚠️ Extras Operativos Especiales:</b>"))
        form_extras = QFormLayout()
        
        self.in_contingencia = QDoubleSpinBox(); self.in_contingencia.setRange(0, 1000000); self.in_contingencia.setPrefix("$ "); self.in_contingencia.setSingleStep(500.0)
        self.in_doble_visita = QDoubleSpinBox(); self.in_doble_visita.setRange(0, 1000000); self.in_doble_visita.setPrefix("$ "); self.in_doble_visita.setSingleStep(500.0)
        
        self.in_finde.setValue(getattr(op, 'monto_finde', 0.0) or 0.0)
        self.in_feriado.setValue(getattr(op, 'monto_feriado', 0.0) or 0.0)
        self.in_contingencia.setValue(getattr(op, 'monto_contingencia', 0.0) or 0.0)
        self.in_doble_visita.setValue(getattr(op, 'monto_espera', 0.0) or 0.0)
        
        lbl_visita = QLabel("⏳ Espera / Doble Visita:")
        if visitas > 1:
            lbl_visita.setText(f"⏳ Espera / Doble Visita (¡Tuvo {visitas} visitas!):")
            lbl_visita.setStyleSheet("color: #d32f2f; font-weight: bold;") 
        
        form_extras.addRow("⚠️ Contingencia (Solo manual):", self.in_contingencia)
        form_extras.addRow(lbl_visita, self.in_doble_visita)
        layout.addLayout(form_extras)

        self.lbl_base = QLabel("Tarifa Base: $ 0.00")
        self.lbl_base.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_base.setStyleSheet("color: #6c757d; font-style: italic;")
        layout.addWidget(self.lbl_base)

        self.lbl_total = QLabel("$ 0.00")
        self.lbl_total.setStyleSheet("font-size: 24px; font-weight: bold; color: #1565c0; padding: 15px; border: 2px dashed #1565c0; border-radius: 8px; background-color: #e3f2fd;")
        self.lbl_total.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_total)

        btn_guardar = QPushButton("💾 GUARDAR CAMBIOS")
        btn_guardar.setStyleSheet("background-color: #198754; color: white; font-weight: bold; padding: 12px; margin-top: 10px; font-size: 14px; border-radius: 6px;")
        btn_guardar.clicked.connect(self.accept)
        layout.addWidget(btn_guardar)

        self.in_prov.currentTextChanged.connect(self.evaluar_reglas_y_recalcular)
        self.in_peso.valueChanged.connect(self.recalcular)
        self.combo_zona.currentTextChanged.connect(self.recalcular)
        self.in_bultos.valueChanged.connect(self.evaluar_reglas_y_recalcular)
        self.in_frio.valueChanged.connect(self.evaluar_reglas_y_recalcular)
        self.chk_combinado.toggled.connect(self.evaluar_reglas_y_recalcular)
        self.in_fecha.dateChanged.connect(self.recalcular)
        
        self.in_finde.valueChanged.connect(self.recalcular_solo_total)
        self.in_feriado.valueChanged.connect(self.recalcular_solo_total)
        self.in_contingencia.valueChanged.connect(self.recalcular_solo_total)
        self.in_doble_visita.valueChanged.connect(self.recalcular_solo_total)
        
        self.btn_finde.clicked.connect(self.aplicar_finde)
        self.btn_feriado.clicked.connect(self.aplicar_feriado)
        
        self.base_calculada = 0.0
        self.evaluar_reglas_y_recalcular()

    def evaluar_reglas_y_recalcular(self):
        prov = self.in_prov.currentText().upper()
        exento = any(x in prov for x in ["DHL", "JETPAQ", "AMBIENTALES"])
        
        b_tot = self.in_bultos.value()
        b_fr = self.in_frio.value()
        es_comb = self.chk_combinado.isChecked()
        
        es_carga_comun = (b_fr == 0 and not es_comb)
        
        if es_carga_comun:
            self.in_contingencia.setEnabled(False)
            self.in_contingencia.setValue(0.0)
            self.in_contingencia.setStyleSheet("background-color: #f0f0f0; color: #a0a0a0;")
        else:
            self.in_contingencia.setEnabled(True)
            self.in_contingencia.setStyleSheet("font-size: 14px; font-weight: bold;")
            
        if exento:
            self.btn_finde.setEnabled(False)
            self.in_finde.setEnabled(False); self.in_finde.setValue(0.0)
            self.in_finde.setStyleSheet("background-color: #f0f0f0; color: #a0a0a0;")
            
            self.btn_feriado.setEnabled(False)
            self.in_feriado.setEnabled(False); self.in_feriado.setValue(0.0)
            self.in_feriado.setStyleSheet("background-color: #f0f0f0; color: #a0a0a0;")
            
            self.in_doble_visita.setEnabled(False); self.in_doble_visita.setValue(0.0)
            self.in_doble_visita.setStyleSheet("background-color: #f0f0f0; color: #a0a0a0;")
        else:
            self.btn_finde.setEnabled(True)
            self.in_finde.setEnabled(True); self.in_finde.setStyleSheet("font-size: 14px; font-weight: bold;")
            
            self.btn_feriado.setEnabled(True)
            self.in_feriado.setEnabled(True); self.in_feriado.setStyleSheet("font-size: 14px; font-weight: bold;")
            
            self.in_doble_visita.setEnabled(True); self.in_doble_visita.setStyleSheet("font-size: 14px; font-weight: bold;")
            
        self.recalcular()

    def aplicar_finde(self):
        self.in_finde.setValue(self.base_calculada * 1.0) 
        
    def aplicar_feriado(self):
        self.in_feriado.setValue(self.base_calculada * 2.0) 

    def recalcular(self):
        b_tot = self.in_bultos.value()
        b_frio = self.in_frio.value()
        prov_actual = self.in_prov.currentText().strip()
        peso_actual = self.in_peso.value()
        
        if b_frio > b_tot: 
            self.in_frio.blockSignals(True)
            self.in_frio.setValue(b_tot)
            b_frio = b_tot
            self.in_frio.blockSignals(False)
            
        b_com = b_tot - b_frio
        es_combinado = self.chk_combinado.isChecked()
        
        if es_combinado:
            if b_tot > 1:
                self.base_calculada = self.main_app.obtener_precio(self.combo_zona.currentText(), 1, b_tot - 1, self.op.sucursal, prov_actual, peso_actual, b_tot)
            else:
                self.base_calculada = self.main_app.obtener_precio(self.combo_zona.currentText(), 0, 1, self.op.sucursal, prov_actual, peso_actual, b_tot)
        else:
            base_comun = self.main_app.obtener_precio(self.combo_zona.currentText(), b_com, 0, self.op.sucursal, prov_actual, peso_actual, b_com) if b_com > 0 else 0.0
            base_frio = self.main_app.obtener_precio(self.combo_zona.currentText(), 0, b_frio, self.op.sucursal, prov_actual, peso_actual, b_frio) if b_frio > 0 else 0.0
            self.base_calculada = base_comun + base_frio
            
        d = self.in_fecha.date()
        es_finde_real = datetime(d.year(), d.month(), d.day()).weekday() >= 5
        exento = any(x in prov_actual.upper() for x in ["DHL", "JETPAQ", "AMBIENTALES"])
        
        if not exento and es_finde_real:
            self.in_finde.blockSignals(True)
            self.in_finde.setValue(self.base_calculada)
            self.in_finde.blockSignals(False)
            
        self.lbl_base.setText(f"Tarifa Base Calculada (S/ extras): $ {self.base_calculada:,.2f}")
        self.recalcular_solo_total()

    def recalcular_solo_total(self):
        self.precio_final = self.base_calculada + self.in_finde.value() + self.in_feriado.value() + self.in_contingencia.value() + self.in_doble_visita.value()
        self.lbl_total.setText(f"$ {self.precio_final:,.2f}")


class TabFacturacion(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main = main_window
        self.totales_cierre = (0.0, 0.0, 0.0) 
        self.setup_ui()
        
    def setup_ui(self):
        l = QVBoxLayout(self); self.tabs_fact = QTabWidget(); l.addWidget(self.tabs_fact)
        
        # --- TAB 1: RENDICIÓN / FACTURACIÓN ---
        tab_rendicion = QWidget(); layout_rend = QVBoxLayout(tab_rendicion); panel = QFrame(); hl = QHBoxLayout(panel)
        self.cierre_mes = QComboBox(); self.cierre_mes.addItems(["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]); self.cierre_mes.setCurrentIndex(datetime.now().month - 1) 
        self.cierre_anio = QSpinBox(); self.cierre_anio.setRange(2020, 2030); self.cierre_anio.setValue(datetime.now().year)
        
        self.cierre_sucursal = QComboBox(); self.cierre_sucursal.addItems(["Todas", "Mendoza", "San Juan"]) 
        
        self.cierre_prov = RestrictedComboBox(self.main)
        self.cierre_prov.addItem("Todos")
        self.cierre_prov.addItems(self.main.lista_proveedores)
        
        self.filtro_control = QComboBox()
        self.filtro_control.addItems(["Pendientes de Control", "Controladas", "Mostrar Todas"])
        self.filtro_control.setStyleSheet("background-color: #e8f5e9; font-weight: bold; color: #2e7d32; padding: 4px;")
        self.filtro_control.currentTextChanged.connect(self.calcular_cierre)
        
        self.btn_c = QPushButton("Calcular Listado"); self.btn_c.clicked.connect(self.calcular_cierre)
        
        btn_pdf = QPushButton("Rendición PDF"); btn_pdf.setStyleSheet("background-color: #dc3545 !important; color: white !important; font-weight: bold; padding: 6px;"); btn_pdf.clicked.connect(self.generar_pdf_fact)
        
        hl.addWidget(QLabel("Sucursal:")); hl.addWidget(self.cierre_sucursal); hl.addWidget(QLabel("Mes:")); hl.addWidget(self.cierre_mes); hl.addWidget(QLabel("Año:")); hl.addWidget(self.cierre_anio); hl.addWidget(QLabel("Proveedor:")); hl.addWidget(self.cierre_prov); 
        hl.addWidget(QLabel("🔎 Filtro:")); hl.addWidget(self.filtro_control); 
        hl.addWidget(self.btn_c); hl.addWidget(btn_pdf); btn_cargo_fijo = QPushButton("➕ Agregar Cargo Fijo"); btn_cargo_fijo.clicked.connect(self.agregar_cargo_fijo); hl.addWidget(btn_cargo_fijo)
        
        self.tabla_cierre = QTableWidget(); self.tabla_cierre.setColumnCount(14); 
        self.tabla_cierre.setHorizontalHeaderLabels(["Sel.", "F. Ingreso", "F. Entrega", "Sucursal", "Guía", "Destino", "Zona", "Bultos", "Estado", "Base ($)", "Finde/Fer ($)", "Otros Extras ($)", "Total ($)", "Ajustes"]); 
        self.tabla_cierre.setStyleSheet(ESTILO_TABLAS_BLANCAS); self.pintor_cierre = PintorCeldasDelegate(self.tabla_cierre); self.tabla_cierre.setItemDelegate(self.pintor_cierre)
        
        header = self.tabla_cierre.horizontalHeader(); header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive); 
        self.tabla_cierre.setColumnWidth(0, 40); self.tabla_cierre.setColumnWidth(1, 80); self.tabla_cierre.setColumnWidth(2, 80); self.tabla_cierre.setColumnWidth(3, 85); self.tabla_cierre.setColumnWidth(4, 140); self.tabla_cierre.setColumnWidth(5, 160); self.tabla_cierre.setColumnWidth(6, 120); self.tabla_cierre.setColumnWidth(7, 85); self.tabla_cierre.setColumnWidth(8, 120); self.tabla_cierre.setColumnWidth(9, 80); self.tabla_cierre.setColumnWidth(10, 80); self.tabla_cierre.setColumnWidth(11, 80); self.tabla_cierre.setColumnWidth(12, 80); self.tabla_cierre.setColumnWidth(13, 140)
        header.setStretchLastSection(True); self.tabla_cierre.verticalHeader().setFixedWidth(30); self.tabla_cierre.verticalHeader().setDefaultSectionSize(45); self.tabla_cierre.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.tabla_cierre.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); self.tabla_cierre.cellDoubleClicked.connect(self.doble_clic_ajuste_precio)
        self.tabla_cierre.itemChanged.connect(self.recalcular_totales_seleccionados)
        
        self.lbl_resumen = QLabel("Total Base: $0 | Total Extras: $0 | TOTAL: $0"); self.lbl_resumen.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px 15px; padding: 10px; border: 1px solid #ccc; background-color: #e3f2fd;")
        lay_abajo = QHBoxLayout(); 
        self.btn_deshacer_fac = QPushButton("⏪ Deshacer Facturación"); self.btn_deshacer_fac.setStyleSheet("background-color: #ff9800; color: black; padding: 8px; font-weight: bold;"); self.btn_deshacer_fac.clicked.connect(self.abrir_dialogo_deshacer_facturacion); 
        self.btn_seleccionar_todo = QPushButton("☑️ Deseleccionar Todo")
        self.btn_seleccionar_todo.setStyleSheet("background-color: #17a2b8; color: white; padding: 8px; font-weight: bold;")
        self.btn_seleccionar_todo.clicked.connect(self.toggle_seleccionar_todo)
        lay_abajo.addWidget(self.btn_deshacer_fac); lay_abajo.addWidget(self.btn_seleccionar_todo); lay_abajo.addStretch(); lay_abajo.addWidget(self.lbl_resumen); 
        layout_rend.addWidget(panel); layout_rend.addWidget(self.tabla_cierre); layout_rend.addLayout(lay_abajo); self.tabs_fact.addTab(tab_rendicion, "1. Calcular Rendición")
        
        # --- TAB 2: CUENTAS CORRIENTES ---
        tab_cta = QWidget(); layout_cta = QVBoxLayout(tab_cta); top_cta = QHBoxLayout(); btn_ref_cta = QPushButton("🔄 Actualizar Saldos"); btn_ref_cta.clicked.connect(self.cargar_ctas_ctes); btn_pago = QPushButton("💰 Registrar Pago"); btn_pago.clicked.connect(self.registrar_pago_ctacte); top_cta.addWidget(btn_ref_cta); top_cta.addStretch(); top_cta.addWidget(btn_pago)
        self.tabla_ctacte = QTableWidget(); self.tabla_ctacte.setColumnCount(4); self.tabla_ctacte.setHorizontalHeaderLabels(["Proveedor", "Total Facturado ($)", "Pagos ($)", "SALDO ($)"]); self.tabla_ctacte.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive); self.tabla_ctacte.setColumnWidth(0, 250); self.tabla_ctacte.setColumnWidth(1, 180); self.tabla_ctacte.setColumnWidth(2, 180); header_cta = self.tabla_ctacte.horizontalHeader(); header_cta.setStretchLastSection(True); self.tabla_ctacte.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.tabla_ctacte.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); self.tabla_ctacte.setStyleSheet(ESTILO_TABLAS_BLANCAS); self.pintor_cta = PintorCeldasDelegate(self.tabla_ctacte); self.tabla_ctacte.setItemDelegate(self.pintor_cta); layout_cta.addLayout(top_cta); layout_cta.addWidget(self.tabla_ctacte); self.tabs_fact.addTab(tab_cta, "2. Cuentas Corrientes")

        # --- TAB 3: DESPACHO DE PAPELES (LOGÍSTICA INVERSA) ---
        tab_despacho = QWidget(); layout_despacho = QVBoxLayout(tab_despacho)
        
        frame_busc = QFrame(); lay_busc = QHBoxLayout(frame_busc)
        lay_busc.addWidget(QLabel("🔍 <b>Rastrear Remito Original (Nº Guía):</b>"))
        self.in_buscar_papel = QLineEdit(); self.in_buscar_papel.setFixedWidth(200)
        btn_buscar_papel = QPushButton("Buscar"); btn_buscar_papel.clicked.connect(self.buscar_papel_fisico)
        self.lbl_resultado_papel = QLabel("Ingrese una guía para ver si ya se envió el papel al cliente.")
        lay_busc.addWidget(self.in_buscar_papel); lay_busc.addWidget(btn_buscar_papel); lay_busc.addWidget(self.lbl_resultado_papel)
        lay_busc.addStretch()
        layout_despacho.addWidget(frame_busc)
        
        frame_lote = QFrame(); lay_lote = QHBoxLayout(frame_lote)
        lay_lote.addWidget(QLabel("<b>📦 Armar Lote para Proveedor:</b>"))
        self.combo_prov_papel = QComboBox()
        self.combo_prov_papel.addItems(["C Y E (AEROTRANSPORTADORA)", "JORGE SANJURJO", "EMAKI"])
        self.combo_prov_papel.setStyleSheet("font-weight: bold; padding: 4px;")
        btn_cargar_papeles = QPushButton("🔄 Traer Pendientes de Envío"); btn_cargar_papeles.clicked.connect(self.cargar_papeles_pendientes)
        lay_lote.addWidget(self.combo_prov_papel); lay_lote.addWidget(btn_cargar_papeles); lay_lote.addStretch()
        layout_despacho.addWidget(frame_lote)
        
        self.tabla_papeles = QTableWidget(); self.tabla_papeles.setColumnCount(5); 
        self.tabla_papeles.setHorizontalHeaderLabels(["Sel.", "F. Entrega", "Guía / Remito", "Proveedor", "Destinatario"])
        self.tabla_papeles.setStyleSheet(ESTILO_TABLAS_BLANCAS); header_papeles = self.tabla_papeles.horizontalHeader()
        self.tabla_papeles.setColumnWidth(0, 40); self.tabla_papeles.setColumnWidth(1, 100); self.tabla_papeles.setColumnWidth(2, 180); self.tabla_papeles.setColumnWidth(3, 220)
        header_papeles.setStretchLastSection(True); self.tabla_papeles.verticalHeader().setDefaultSectionSize(35); self.tabla_papeles.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout_despacho.addWidget(self.tabla_papeles)
        
        btn_generar_lote = QPushButton("📦 Generar Lote PDF y Marcar como Enviados")
        btn_generar_lote.setStyleSheet("background-color: #198754; color: white; padding: 12px; font-weight: bold; font-size: 14px; border-radius: 6px;")
        btn_generar_lote.clicked.connect(self.generar_lote_papeles)
        layout_despacho.addWidget(btn_generar_lote)
        
        self.tabs_fact.addTab(tab_despacho, "3. Despacho Papeles (Log. Inversa)")

    def buscar_papel_fisico(self):
        texto = self.in_buscar_papel.text().strip()
        if not texto: return
        try:
            op = self.main.session.query(Operacion).filter(Operacion.guia_remito.ilike(f"%{texto}%")).first()
            if op:
                if getattr(op, 'papel_enviado', False):
                    lote = getattr(op, 'lote_papel', 'DESCONOCIDO')
                    self.lbl_resultado_papel.setText(f"✅ Guía {op.guia_remito}: ENVIADA FÍSICAMENTE en el {lote}")
                    self.lbl_resultado_papel.setStyleSheet("font-weight: bold; color: #198754; font-size: 14px;")
                else:
                    self.lbl_resultado_papel.setText(f"⚠️ Guía {op.guia_remito}: ORIGINAL AÚN EN OFICINA (No despachado)")
                    self.lbl_resultado_papel.setStyleSheet("font-weight: bold; color: #dc3545; font-size: 14px;")
            else:
                self.lbl_resultado_papel.setText("❌ Guía no encontrada en el sistema.")
                self.lbl_resultado_papel.setStyleSheet("font-weight: bold; color: #dc3545; font-size: 14px;")
        except Exception as e:
            self.main.session.rollback()

    def cargar_papeles_pendientes(self):
        prov = self.combo_prov_papel.currentText()
        try:
            self.tabla_papeles.setRowCount(0)
            query = self.main.session.query(Operacion).filter(
                Operacion.estado.in_([Estados.ENTREGADO, Estados.DEVUELTO_ORIGEN]), 
                Operacion.facturado == True, 
                (Operacion.papel_enviado == False) | (Operaciquery = self.main.session.query(Operacion).filter(
                Operacion.estado.in_([Estados.ENTREGADO, Estados.DEVUELTO_ORIGEN]), 
                Operacion.facturado == True,on.papel_enviado == None),
                Operacion.proveedor == prov
            )
            query = query.order_by(Operacion.fecha_entrega.desc().nullslast())
            self.resultados_papeles = query.all()
            self.mapa_filas_papeles = {}
            
            for row, op in enumerate(self.resultados_papeles):
                self.tabla_papeles.insertRow(row)
                self.mapa_filas_papeles[row] = op.id
                chk = QTableWidgetItem(); chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled); chk.setCheckState(Qt.CheckState.Checked)
                f_ent = op.fecha_entrega.strftime("%d/%m/%Y") if op.fecha_entrega else "-"
                self.tabla_papeles.setItem(row, 0, chk)
                self.tabla_papeles.setItem(row, 1, QTableWidgetItem(f_ent))
                self.tabla_papeles.setItem(row, 2, QTableWidgetItem(op.guia_remito or ""))
                self.tabla_papeles.setItem(row, 3, QTableWidgetItem(op.proveedor or ""))
                self.tabla_papeles.setItem(row, 4, QTableWidgetItem(op.destinatario or ""))
                
            if not self.resultados_papeles:
                QMessageBox.information(self, "Aviso", f"No hay papeles pendientes de envío para {prov} (O aún no fueron facturados).")
        except Exception as e:
            self.main.session.rollback()

    def generar_lote_papeles(self):
        if not hasattr(self, 'resultados_papeles') or not self.resultados_papeles: return
        ops_sel = []
        for r in range(self.tabla_papeles.rowCount()):
            it = self.tabla_papeles.item(r, 0)
            if it and it.checkState() == Qt.CheckState.Checked:
                op_id = self.mapa_filas_papeles.get(r)
                op = next((o for o in self.resultados_papeles if o.id == op_id), None)
                if op: ops_sel.append(op)
        if not ops_sel: return
        reply = QMessageBox.question(self, "Generar Lote", f"¿Generar PDF y despachar {len(ops_sel)} papeles físicos?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            lote_id = f"LOTE-{datetime.now().strftime('%Y%m%d-%H%M')}"
            prov_nombre = self.combo_prov_papel.currentText()
            try:
                for op in ops_sel:
                    op.papel_enviado = True
                    op.lote_papel = lote_id
                self.main.session.commit()
                descargas_dir = os.path.join(os.path.expanduser('~'), 'Downloads')
                ruta_pdf = os.path.join(descargas_dir, f"Despacho_Papeles_{lote_id}.pdf")
                crear_pdf_despacho_papeles(ruta_pdf, lote_id, ops_sel, prov_nombre, self.main.usuario.username, datetime.now().strftime('%d/%m/%Y %H:%M'))
                os.startfile(ruta_pdf)
                self.cargar_papeles_pendientes()
                QMessageBox.information(self, "Éxito", f"Lote generado correctamente.")
            except Exception as e:
                self.main.session.rollback(); QMessageBox.critical(self, "Error", str(e))

    def alternar_control(self, id_op, fila_tabla):
        try:
            op = self.main.session.query(Operacion).get(id_op)
            if op:
                estado_actual = getattr(op, 'controlada', False)
                op.controlada = not estado_actual
                
                # 🔥 INYECTOR DE AUDITORÍA INVISIBLE 🔥
                txt_auditoria = "CONTROL / VALIDACIÓN" if op.controlada else "REVERSIÓN DE CONTROL"
                txt_detalle = "Se marcó la guía como controlada en Facturación" if op.controlada else "Se quitó la marca de control en Facturación"
                self.main.log_movimiento(op, txt_auditoria, txt_detalle)
                
                self.main.session.commit()
                
                # 🔥 ACTUALIZACIÓN EN VIVO (Sin recargar toda la tabla) 🔥
                text_color = "#006400" if op.controlada else "#000000"
                font_weight = QFont.Weight.Bold if op.controlada else QFont.Weight.Normal
                
                for col_idx in range(14): 
                    it = self.tabla_cierre.item(fila_tabla, col_idx)
                    if it: 
                        it.setForeground(QBrush(QColor(text_color)))
                        font = it.font(); font.setWeight(font_weight); it.setFont(font)
                        
                btn_widget = self.tabla_cierre.cellWidget(fila_tabla, 13)
                if btn_widget:
                    btn_validar = btn_widget.findChildren(QPushButton)[0] 
                    btn_validar.setText("❌ Revertir" if op.controlada else "✔️ Validar")
                    color_btn = "#6c757d" if op.controlada else "#198754"
                    btn_validar.setStyleSheet(f"background-color: {color_btn} !important; color: white !important; font-size: 11px; font-weight: bold; padding: 4px;")
                    
        except Exception as e:
            self.main.session.rollback()

    def toggle_seleccionar_todo(self):
        self.tabla_cierre.blockSignals(True) 
        marcar = True
        if "Deseleccionar" in self.btn_seleccionar_todo.text():
            marcar = False
            self.btn_seleccionar_todo.setText("☑️ Seleccionar Todo")
        else:
            self.btn_seleccionar_todo.setText("☑️ Deseleccionar Todo")

        estado = Qt.CheckState.Checked if marcar else Qt.CheckState.Unchecked
        for r in range(self.tabla_cierre.rowCount()):
            it = self.tabla_cierre.item(r, 0)
            if it:
                it.setCheckState(estado)
        self.tabla_cierre.blockSignals(False)
        self.recalcular_totales_seleccionados()

    def recalcular_totales_seleccionados(self, item=None):
        if item and item.column() != 0: return 
        
        tot_base = 0.0; tot_extras = 0.0; tot_final = 0.0
        
        for r in range(self.tabla_cierre.rowCount()):
            it_sel = self.tabla_cierre.item(r, 0)
            if it_sel and it_sel.checkState() == Qt.CheckState.Checked:
                try:
                    it_base = self.tabla_cierre.item(r, 9)
                    val_base = float(it_base.text().replace("$", "").replace(",", "").strip()) if it_base else 0.0
                    
                    it_finde = self.tabla_cierre.item(r, 10)
                    val_finde = float(it_finde.text().replace("$", "").replace(",", "").strip()) if it_finde else 0.0
                    
                    it_otros = self.tabla_cierre.item(r, 11)
                    val_otros = float(it_otros.text().replace("$", "").replace(",", "").strip()) if it_otros else 0.0
                    
                    it_tot = self.tabla_cierre.item(r, 12)
                    val_tot = float(it_tot.text().replace("$", "").replace(",", "").strip()) if it_tot else 0.0
                    
                    tot_base += val_base
                    tot_extras += (val_finde + val_otros)
                    tot_final += val_tot
                except:
                    pass
                    
        self.totales_cierre = (tot_base, tot_extras, tot_final)
        self.lbl_resumen.setText(f"Total Base: ${tot_base:,.2f} | Extras: ${tot_extras:,.2f} | TOTAL SELECCIONADO: ${tot_final:,.2f}")

    def abrir_dialogo_deshacer_facturacion(self):
        dlg = DeshacerFacturacionDialog(self.main, self)
        if dlg.exec() == QDialog.DialogCode.Accepted: self.calcular_cierre(); self.cargar_ctas_ctes()
        
    def agregar_cargo_fijo(self):
        proveedores = [self.cierre_prov.itemText(i) for i in range(self.cierre_prov.count()) if self.cierre_prov.itemText(i) != "Todos"]
        dlg = AgregarCargoDialog(proveedores, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                op = Operacion(fecha_ingreso=datetime.now(), sucursal=self.cierre_sucursal.currentText() if self.cierre_sucursal.currentText() != "Todas" else self.main.sucursal_actual, guia_remito="CARGO-FIJO", proveedor=dlg.in_prov.currentText().upper(), destinatario=dlg.in_concepto.text().upper(), domicilio="-", localidad="-", bultos=1, bultos_frio=0, peso=0.0, tipo_carga="COMUN", monto_servicio=dlg.in_monto.value(), estado=Estados.ENTREGADO, facturado=False, tipo_servicio="Cargo Extra")
                self.main.session.add(op); self.main.session.commit(); self.main.toast.mostrar("✅ Cargo extra agregado."); self.calcular_cierre()
            except Exception: self.main.session.rollback()
            
    def registrar_pago_ctacte(self):
        r = self.tabla_ctacte.currentRow(); 
        if r < 0: return
        prov = self.tabla_ctacte.item(r, 0).text(); dlg = CargarPagoDialog(prov, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                pago = ReciboPago(proveedor=prov, monto=dlg.in_monto.value(), detalle=dlg.in_detalle.text().upper(), usuario=self.main.usuario.username)
                self.main.session.add(pago); self.main.session.commit(); self.main.toast.mostrar("✅ Pago registrado."); self.cargar_ctas_ctes()
            except Exception: self.main.session.rollback()
            
    def cargar_ctas_ctes(self):
        try:
            self.tabla_ctacte.setRowCount(0); sql_fac = text("SELECT proveedor, SUM(monto_servicio) FROM operaciones WHERE (facturado = TRUE) AND UPPER(TRIM(proveedor)) != 'JETPAQ' GROUP BY proveedor"); facturados = self.main.session.execute(sql_fac).fetchall(); dict_saldos = {f[0]: {"fac": f[1] or 0.0, "pag": 0.0} for f in facturados}; sql_pag = text("SELECT proveedor, SUM(monto) FROM recibos_pago GROUP BY proveedor"); pagados = self.main.session.execute(sql_pag).fetchall()
            for p in pagados:
                if p[0] not in dict_saldos: dict_saldos[p[0]] = {"fac": 0.0, "pag": 0.0}
                dict_saldos[p[0]]["pag"] += (p[1] or 0.0)
            for i, (prov, montos) in enumerate(dict_saldos.items()):
                self.tabla_ctacte.insertRow(i); fac = montos["fac"]; pag = montos["pag"]; saldo = fac - pag; self.tabla_ctacte.setItem(i, 0, QTableWidgetItem(prov)); self.tabla_ctacte.setItem(i, 1, QTableWidgetItem(f"$ {fac:,.2f}")); self.tabla_ctacte.setItem(i, 2, QTableWidgetItem(f"$ {pag:,.2f}")); it_saldo = QTableWidgetItem(f"$ {saldo:,.2f}"); it_saldo.setFont(QFont("Arial", 11, QFont.Weight.Bold)); it_saldo.setForeground(QColor("red") if saldo > 0 else QColor("green")); self.tabla_ctacte.setItem(i, 3, it_saldo)
        except Exception: self.main.session.rollback()
        
    def doble_clic_ajuste_precio(self, row, col):
        it = self.tabla_cierre.item(row, 0)
        if it:
            id_op = it.data(Qt.ItemDataRole.UserRole)
            if id_op: self.abrir_dialogo_ajuste_precio(id_op)
        
    # 🔥 ACTUALIZACIÓN QUIRÚRGICA BLINDADA CONTRA ORDENAMIENTO 🔥
    def abrir_dialogo_ajuste_precio(self, id_op):
        try:
            op = self.main.session.query(Operacion).get(id_op)
            if not op: return
            
            hist_records = self.main.session.query(Historial.accion).filter(
                Historial.operacion_id == id_op, 
                Historial.accion.in_([
                    'SALIDA A REPARTO', 'SALIDA A TERCERIZADO', 
                    'DESHACER (ADMIN)', 'REPROGRAMADO (ADMIN)', 'REPROGRAMADO (OFICINA)'
                ])
            ).all()
            
            visitas = 0
            for (accion,) in hist_records:
                if accion in ['SALIDA A REPARTO', 'SALIDA A TERCERIZADO']: visitas += 1
                elif accion in ['DESHACER (ADMIN)', 'REPROGRAMADO (ADMIN)', 'REPROGRAMADO (OFICINA)']: visitas -= 1
            visitas = max(1, visitas)

            dlg = AjusteAvanzadoFacturacionDialog(op, self.main, visitas, self) 
            if dlg.exec() == QDialog.DialogCode.Accepted: 
                
                op.guia_remito = dlg.in_guia.text().strip()
                op.proveedor = dlg.in_prov.currentText().strip()
                op.destinatario = dlg.in_dest.text().strip()
                op.peso = dlg.in_peso.value()
                
                qdate = dlg.in_fecha.date()
                op.fecha_entrega = datetime(qdate.year(), qdate.month(), qdate.day(), 12, 0, 0)
                op.localidad = dlg.combo_zona.currentText()
                op.bultos = dlg.in_bultos.value()
                op.bultos_frio = dlg.in_frio.value()
                
                op.monto_finde = dlg.in_finde.value()
                op.monto_feriado = dlg.in_feriado.value()
                op.monto_contingencia = dlg.in_contingencia.value()
                op.monto_espera = dlg.in_doble_visita.value()
                op.monto_servicio = dlg.precio_final 
                
                self.main.log_movimiento(op, "EDICIÓN DE FACTURACIÓN", f"Precio ajustado a ${dlg.precio_final}")
                self.main.session.commit()
                
                # Buscamos la fila visual correcta usando el RASTREADOR INVISIBLE
                fila_actual = -1
                for r in range(self.tabla_cierre.rowCount()):
                    it = self.tabla_cierre.item(r, 0)
                    if it and it.data(Qt.ItemDataRole.UserRole) == id_op:
                        fila_actual = r
                        break
                
                if fila_actual != -1:
                    m_finde = op.monto_finde or 0.0
                    m_feriado = op.monto_feriado or 0.0
                    m_esp = op.monto_espera or 0.0
                    m_cont = op.monto_contingencia or 0.0
                    m_serv = op.monto_servicio or 0.0
                    
                    extras = m_finde + m_feriado + m_esp + m_cont
                    p_base = m_serv - extras
                    
                    self.tabla_cierre.item(fila_actual, 4).setText(op.guia_remito or "RET")
                    self.tabla_cierre.item(fila_actual, 5).setText(op.destinatario or "")
                    self.tabla_cierre.item(fila_actual, 6).setText(op.localidad or "")
                    
                    b_tot = int(op.bultos) if op.bultos else 1
                    b_fr = int(op.bultos_frio) if op.bultos_frio else 0
                    det_b = str(b_tot)
                    if op.proveedor and "DHL" in op.proveedor.upper(): det_b = f"{b_tot} B | {op.peso or 0} Kg"
                    else:
                        if b_fr > 0 and b_fr < b_tot: det_b += f" ({b_tot-b_fr}C/{b_fr}R)"
                        elif b_fr == b_tot: det_b += " (R)"
                    self.tabla_cierre.item(fila_actual, 7).setText(det_b)
                    
                    self.tabla_cierre.item(fila_actual, 9).setText(f"$ {p_base:,.2f}")
                    self.tabla_cierre.item(fila_actual, 10).setText(f"$ {(m_finde + m_feriado):,.2f}")
                    self.tabla_cierre.item(fila_actual, 11).setText(f"$ {(m_esp + m_cont):,.2f}")
                    self.tabla_cierre.item(fila_actual, 12).setText(f"$ {m_serv:,.2f}")
                    
                    self.recalcular_totales_seleccionados()
                    self.main.toast.mostrar("✅ Editado y recalculado al instante")
                else:
                    self.calcular_cierre()
        except Exception as e: 
            self.main.session.rollback()
            QMessageBox.critical(self, "Error", f"Fallo al actualizar: {e}")

    def calcular_cierre(self):
        self.btn_c.setEnabled(False)
        self.tabla_cierre.blockSignals(True) 
        self.tabla_cierre.setUpdatesEnabled(False)
        
        mes = self.cierre_mes.currentIndex() + 1; anio = self.cierre_anio.value(); prov = self.cierre_prov.currentText().strip(); sucursal = self.cierre_sucursal.currentText(); self.tabla_cierre.setRowCount(0)
        try:
            _, last_day = calendar.monthrange(anio, mes); start_date = date(anio, mes, 1); end_date = date(anio, mes, last_day)
            
            fecha_ref = func.coalesce(Operacion.fecha_entrega, Operacion.fecha_ingreso)
            query = self.main.session.query(Operacion).filter(
                func.date(fecha_ref) >= start_date, 
                func.date(fecha_ref) <= end_date, 
                (Operacion.facturado == False) | (Operacion.facturado == None), 
                Operacion.estado.in_([Estados.ENTREGADO, Estados.DEVUELTO_ORIGEN])
            )
            
            if self.filtro_control.currentText() == "Pendientes de Control":
                query = query.filter((Operacion.controlada == False) | (Operacion.controlada == None))
            elif self.filtro_control.currentText() == "Controladas":
                query = query.filter(Operacion.controlada == True)
            
            if prov != "Todos" and prov != "": query = query.filter(Operacion.proveedor.ilike(prov))
            else: query = query.filter(~Operacion.proveedor.ilike('JetPaq'))
            if sucursal != "Todas": query = query.filter(Operacion.sucursal == sucursal)
            query = query.order_by(Operacion.fecha_ingreso.asc()); self.resultados_cierre = query.all()
            
            if not self.resultados_cierre: 
                self.tabla_cierre.setRowCount(1); item_empty = QTableWidgetItem("❌ Sin guías entregadas para facturar (o ya validaste todo)."); item_empty.setTextAlignment(Qt.AlignmentFlag.AlignCenter); self.tabla_cierre.setItem(0, 0, item_empty); self.tabla_cierre.setSpan(0, 0, 1, 14); self.lbl_resumen.setText("Total Base: $0 | Total Extras: $0 | TOTAL SELECCIONADO: $0")
                self.tabla_cierre.setUpdatesEnabled(True)
                self.btn_c.setEnabled(True)
                self.tabla_cierre.blockSignals(False)
                return
            
            op_ids = [op.id for op in self.resultados_cierre]; conteo_repartos = {}
            if op_ids:
                hist_records = self.main.session.query(Historial.operacion_id, Historial.accion).filter(
                    Historial.operacion_id.in_(op_ids), 
                    Historial.accion.in_([
                        'SALIDA A REPARTO', 'SALIDA A TERCERIZADO', 
                        'DESHACER (ADMIN)', 'REPROGRAMADO (ADMIN)', 'REPROGRAMADO (OFICINA)'
                    ])
                ).all()
                for op_id, accion in hist_records:
                    if op_id not in conteo_repartos: conteo_repartos[op_id] = 0
                    if accion in ['SALIDA A REPARTO', 'SALIDA A TERCERIZADO']: conteo_repartos[op_id] += 1
                    elif accion in ['DESHACER (ADMIN)', 'REPROGRAMADO (ADMIN)', 'REPROGRAMADO (OFICINA)']: conteo_repartos[op_id] -= 1
                    
            self.mapa_filas_cierre = {}; total_ops = len(self.resultados_cierre)
            
            progreso = QProgressDialog("Preparando datos de facturación...", None, 0, total_ops, self)
            progreso.setWindowTitle("⏳ Calculando Facturación")
            progreso.setWindowModality(Qt.WindowModality.WindowModal)
            progreso.setMinimumDuration(0)
            progreso.setValue(0)
            
            hubo_reparacion = False 
            
            for row, op in enumerate(self.resultados_cierre):
                if row % 2 == 0 or row == total_ops - 1: 
                    progreso.setLabelText(f"Calculando tarifa: guía {row + 1} de {total_ops}...")
                    progreso.setValue(row)
                    QApplication.processEvents()
                    
                self.tabla_cierre.insertRow(row); self.mapa_filas_cierre[row] = op.id; 
                
                chk = QTableWidgetItem()
                chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
                chk.setCheckState(Qt.CheckState.Checked)
                chk.setData(Qt.ItemDataRole.UserRole, op.id)
                self.tabla_cierre.setItem(row, 0, chk)
                
                f_ingreso = op.fecha_ingreso.strftime("%d/%m/%Y") if op.fecha_ingreso else "-"
                f_entrega = op.fecha_entrega.strftime("%d/%m/%Y") if op.fecha_entrega else "-"
                
                self.tabla_cierre.setItem(row, 1, QTableWidgetItem(f_ingreso))
                self.tabla_cierre.setItem(row, 2, QTableWidgetItem(f_entrega))
                self.tabla_cierre.setItem(row, 3, QTableWidgetItem((op.sucursal or "").upper()))
                self.tabla_cierre.setItem(row, 4, QTableWidgetItem(op.guia_remito or "RET"))
                self.tabla_cierre.setItem(row, 5, QTableWidgetItem(op.destinatario or ""))
                self.tabla_cierre.setItem(row, 6, QTableWidgetItem(op.localidad or ""))
                
                bultos_tot = int(op.bultos) if op.bultos else 1
                bultos_fr = int(op.bultos_frio) if op.bultos_frio else 0
                det_b = str(bultos_tot)
                
                prov_upper = (op.proveedor or "").upper()
                exento_extras = any(x in prov_upper for x in ["DHL", "JETPAQ", "AMBIENTALES"])
                
                if "DHL" in prov_upper:
                    det_b = f"{bultos_tot} B | {op.peso or 0} Kg"
                else:
                    if bultos_fr > 0 and bultos_fr < bultos_tot: det_b += f" ({bultos_tot-bultos_fr}C/{bultos_fr}R)"
                    elif bultos_fr == bultos_tot: det_b += " (R)"
                    
                self.tabla_cierre.setItem(row, 7, QTableWidgetItem(det_b))
                
                fecha_para_billing = op.fecha_entrega if op.fecha_entrega else op.fecha_ingreso
                es_finde = fecha_para_billing and fecha_para_billing.weekday() >= 5
                
                visitas = max(1, conteo_repartos.get(op.id, 1))
                estado_txt = f"{op.estado} ({visitas} Visitas)" if visitas > 1 else op.estado
                
                if es_finde and not exento_extras:
                    estado_txt = f"🚨 GUARDIA FINDE | {estado_txt}"
                    
                self.tabla_cierre.setItem(row, 8, QTableWidgetItem(estado_txt))
                
                # 🔥 LA CURA: RESPETA LA EDICIÓN MANUAL 🔥
                if op.guia_remito == "CARGO-FIJO" or (op.tipo_servicio and "Flete" in op.tipo_servicio): 
                    precio_base = op.monto_servicio or 0.0
                    monto_finde_db = getattr(op, 'monto_finde', 0.0) or 0.0
                    monto_feriado_db = getattr(op, 'monto_feriado', 0.0) or 0.0
                    monto_esp_db = getattr(op, 'monto_espera', 0.0) or 0.0
                    monto_cont_db = getattr(op, 'monto_contingencia', 0.0) or 0.0
                    monto_serv = precio_base + monto_finde_db + monto_feriado_db + monto_esp_db + monto_cont_db
                else: 
                    precio_base_teorico = self.main.obtener_precio(op.localidad, bultos_tot-bultos_fr, bultos_fr, op.sucursal, op.proveedor, op.peso or 0.0, bultos_tot)
                    
                    if (bultos_tot <= 1 and bultos_fr == 0) and getattr(op, 'monto_contingencia', 0.0) > 0:
                        op.monto_contingencia = 0.0
                        hubo_reparacion = True
                    
                    # Solo auto-calcula recargos si la guía NUNCA fue calculada ($0)
                    if not op.monto_servicio or op.monto_servicio == 0.0:
                        if exento_extras:
                            op.monto_finde = 0.0
                            op.monto_feriado = 0.0
                            op.monto_espera = 0.0
                        else:
                            if es_finde: op.monto_finde = precio_base_teorico
                            if visitas > 1: op.monto_espera = precio_base_teorico * (visitas - 1)
                            else: op.monto_espera = 0.0
                            
                        monto_finde_db = getattr(op, 'monto_finde', 0.0) or 0.0
                        monto_feriado_db = getattr(op, 'monto_feriado', 0.0) or 0.0
                        monto_esp_db = getattr(op, 'monto_espera', 0.0) or 0.0
                        monto_cont_db = getattr(op, 'monto_contingencia', 0.0) or 0.0
                        
                        op.monto_servicio = precio_base_teorico + monto_finde_db + monto_feriado_db + monto_esp_db + monto_cont_db
                        hubo_reparacion = True

                    monto_finde_db = getattr(op, 'monto_finde', 0.0) or 0.0
                    monto_feriado_db = getattr(op, 'monto_feriado', 0.0) or 0.0
                    monto_esp_db = getattr(op, 'monto_espera', 0.0) or 0.0
                    monto_cont_db = getattr(op, 'monto_contingencia', 0.0) or 0.0
                    
                    monto_serv = op.monto_servicio or 0.0
                    extras_calculados = monto_finde_db + monto_feriado_db + monto_esp_db + monto_cont_db
                    
                    precio_base = monto_serv - extras_calculados

                self.tabla_cierre.setItem(row, 9, QTableWidgetItem(f"$ {precio_base:,.2f}"))
                self.tabla_cierre.setItem(row, 10, QTableWidgetItem(f"$ {(monto_finde_db + monto_feriado_db):,.2f}"))
                self.tabla_cierre.setItem(row, 11, QTableWidgetItem(f"$ {(monto_esp_db + monto_cont_db):,.2f}"))
                self.tabla_cierre.setItem(row, 12, QTableWidgetItem(f"$ {monto_serv:,.2f}"))
                
                esta_controlada = getattr(op, 'controlada', False)
                if esta_controlada:
                    text_brush = QBrush(QColor("#006400")) 
                    for col_idx in range(14): 
                        it = self.tabla_cierre.item(row, col_idx)
                        if it: 
                            it.setForeground(text_brush)
                            font = it.font()
                            font.setBold(True)
                            it.setFont(font)
                
                if es_finde and not exento_extras:
                    bg_brush = QBrush(QColor("#fff3cd"))
                    for col_idx in range(14): 
                        it = self.tabla_cierre.item(row, col_idx)
                        if it: it.setBackground(bg_brush)
                
                w_acc = QWidget(); lay_acc = QHBoxLayout(w_acc); lay_acc.setContentsMargins(0,0,0,0)
                btn_validar = QPushButton("✔️ Validar" if not esta_controlada else "❌ Revertir")
                color_btn = "#198754" if not esta_controlada else "#6c757d"
                btn_validar.setStyleSheet(f"background-color: {color_btn} !important; color: white !important; font-size: 11px; font-weight: bold; padding: 4px;")
                btn_validar.clicked.connect(lambda checked, id_o=op.id: self.alternar_control(id_o))
                lay_acc.addWidget(btn_validar)
                
                btn_ajuste = QPushButton("✏️ Editar"); btn_ajuste.setStyleSheet("background-color: #0d6efd !important; color: white !important; font-size: 11px; font-weight: bold; padding: 4px;")
                btn_ajuste.clicked.connect(lambda checked, id_o=op.id: self.abrir_dialogo_ajuste_precio(id_o))
                lay_acc.addWidget(btn_ajuste)
                
                self.tabla_cierre.setCellWidget(row, 13, w_acc)
                
            progreso.setValue(total_ops)
            
            if hubo_reparacion:
                self.main.session.commit()
            
            self.tabla_cierre.setUpdatesEnabled(True)
            self.tabla_cierre.blockSignals(False)
            self.btn_seleccionar_todo.setText("☑️ Deseleccionar Todo")
            self.recalcular_totales_seleccionados()
            
        except Exception as e: 
            self.main.session.rollback()
            self.lbl_resumen.setText("Total Base: $0 | Total Extras: $0 | TOTAL: $0")
            QMessageBox.critical(self, "Error", str(e))
        finally:
            self.tabla_cierre.setUpdatesEnabled(True)
            self.tabla_cierre.blockSignals(False)
            self.btn_c.setEnabled(True)

    def generar_pdf_fact(self):
        hay_seleccion = False
        for r in range(self.tabla_cierre.rowCount()):
            it = self.tabla_cierre.item(r, 0)
            if it and it.checkState() == Qt.CheckState.Checked:
                hay_seleccion = True
                break

        if not hay_seleccion:
            QMessageBox.warning(self, "Aviso", "⚠️ No hay guías seleccionadas para facturar. Tildá al menos una.")
            return

        reply = QMessageBox.question(self, "Cerrar Facturación", f"¿Desea marcar estas guías como FACTURADAS?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        marcar_facturado = (reply == QMessageBox.StandardButton.Yes)
        
        mes_nombre = self.cierre_mes.currentText(); anio_num = self.cierre_anio.value(); prov_nombre = self.cierre_prov.currentText()
        descargas_dir = os.path.join(os.path.expanduser('~'), 'Downloads'); os.makedirs(descargas_dir, exist_ok=True)
        ruta_pdf = os.path.join(descargas_dir, f"Facturacion_{prov_nombre}_{mes_nombre}_{anio_num}.pdf")
        
        data_filas = [['FECHA', 'GUÍA', 'ZONA', 'BULTOS', 'BASE ($)', 'FINDE ($)', 'EXTRAS ($)', 'TOTAL ($)']]
        
        for r in range(self.tabla_cierre.rowCount()):
            it_sel = self.tabla_cierre.item(r, 0)
            if it_sel and it_sel.checkState() == Qt.CheckState.Checked:
                fecha = self.tabla_cierre.item(r, 2).text()
                if fecha == "-": fecha = self.tabla_cierre.item(r, 1).text()
                guia = self.tabla_cierre.item(r, 4).text()
                zona = self.tabla_cierre.item(r, 6).text()
                bultos = self.tabla_cierre.item(r, 7).text()
                base_txt = self.tabla_cierre.item(r, 9).text()
                finde_txt = self.tabla_cierre.item(r, 10).text()
                extras_txt = self.tabla_cierre.item(r, 11).text()
                total_txt = self.tabla_cierre.item(r, 12).text()
                
                data_filas.append([fecha, guia, zona[:15].upper(), bultos, base_txt, finde_txt, extras_txt, total_txt])
                
                if marcar_facturado:
                    op_id = it_sel.data(Qt.ItemDataRole.UserRole)
                    if op_id:
                        op = self.main.session.query(Operacion).get(op_id)
                        if op: op.facturado = True
            
        if marcar_facturado: 
            try: 
                self.main.session.commit()
                self.calcular_cierre()
                self.cargar_ctas_ctes()
            except Exception as e: 
                self.main.session.rollback()
                print(e)
            
        tb, te, tf = self.totales_cierre
        iva = tf * 0.21
        total_final_iva = tf + iva
        
        data_filas.append(['', '', '', '', '', '', '', '']) 
        data_filas.append(['SUBTOTALES:', '', '', '', f"$ {tb:,.2f}", f"$ {te:,.2f}", '-', f"$ {tf:,.2f}"])
        data_filas.append(['', '', '', '', '', '', 'IVA (21%):', f"$ {iva:,.2f}"])
        data_filas.append(['', '', '', '', '', '', 'TOTAL FACTURA:', f"$ {total_final_iva:,.2f}"])
        
        crear_pdf_facturacion(ruta_pdf, data_filas, prov_nombre, f"{mes_nombre} {anio_num}", self.main.usuario.username, datetime.now().strftime('%d/%m/%Y %H:%M'))
        try: os.startfile(ruta_pdf)
        except: pass