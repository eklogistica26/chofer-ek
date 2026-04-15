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
from utilidades import crear_pdf_facturacion
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

class EditarPesoDHLDialog(QDialog):
    def __init__(self, op, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"⚖️ Ajustar Peso - Guía: {op.guia_remito or 'S/N'}")
        self.setFixedSize(300, 200)
        layout = QVBoxLayout(self)
        
        self.in_bultos = QSpinBox()
        self.in_bultos.setRange(1, 1000)
        self.in_bultos.setValue(int(op.bultos) if op.bultos else 1)
        
        self.in_peso = QDoubleSpinBox()
        self.in_peso.setRange(0, 10000.0)
        self.in_peso.setSuffix(" Kg")
        self.in_peso.setSingleStep(0.5)
        self.in_peso.setValue(op.peso or 0.0)
        
        layout.addWidget(QLabel("Cantidad de Bultos:"))
        layout.addWidget(self.in_bultos)
        layout.addWidget(QLabel("Peso Real (Kg):"))
        layout.addWidget(self.in_peso)
        
        btn_guardar = QPushButton("💾 GUARDAR Y RECALCULAR")
        btn_guardar.setStyleSheet("background-color: #198754; color: white; font-weight: bold; padding: 10px;")
        btn_guardar.clicked.connect(self.accept)
        layout.addWidget(btn_guardar)
        
    @property
    def valores(self):
        return self.in_bultos.value(), self.in_peso.value()

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
        self.setWindowTitle(f"🛠️ Ajuste Integral de Facturación - Guía: {op.guia_remito or 'S/N'}")
        self.setFixedSize(520, 800) 
        layout = QVBoxLayout(self)

        bultos_tot = int(op.bultos) if op.bultos else 1
        bultos_fr = int(op.bultos_frio) if op.bultos_frio else 0
        bultos_com = bultos_tot - bultos_fr
        
        tipo_bulto_str = f"{bultos_tot} Totales"
        if bultos_fr > 0: tipo_bulto_str += f" ({bultos_com} Comunes / {bultos_fr} Refrigerados)"
        else: tipo_bulto_str += " (Todos Comunes)"

        info_text = f"<span style='font-size:14px;'><b>Guía:</b> {op.guia_remito or '-'}<br><b>Cliente:</b> {op.proveedor}<br><b>Destino:</b> {op.destinatario} ({op.domicilio})<br><b>Carga Inicial:</b> {tipo_bulto_str}<br><b>Estado actual:</b> <span style='color:#1565c0;'>{op.estado}</span> (Salidas reales: <b>{visitas}</b>)</span>"
        
        lbl_info = QLabel(info_text)
        lbl_info.setStyleSheet("background-color: #f8f9fa; padding: 12px; border: 1px solid #ced4da; border-radius: 6px;")
        layout.addWidget(lbl_info)

        form = QFormLayout()

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

        layout.addWidget(QLabel("<b>📅 Recargos Finde / Feriado:</b>"))
        
        h_finde = QHBoxLayout()
        self.btn_finde = QPushButton("🟡 Calcular Finde (x2)")
        self.btn_finde.setStyleSheet("background-color: #ffc107; color: black; font-weight: bold; padding: 6px; border-radius: 4px;")
        self.in_finde = QDoubleSpinBox()
        self.in_finde.setRange(0, 1000000); self.in_finde.setPrefix("$ "); self.in_finde.setSingleStep(500.0)
        self.in_finde.setStyleSheet("font-size: 14px; font-weight: bold;")
        h_finde.addWidget(self.btn_finde)
        h_finde.addWidget(self.in_finde)
        layout.addLayout(h_finde)

        h_feriado = QHBoxLayout()
        self.btn_feriado = QPushButton("🔴 Calcular Feriado (x3)")
        self.btn_feriado.setStyleSheet("background-color: #dc3545; color: white; font-weight: bold; padding: 6px; border-radius: 4px;")
        self.in_feriado = QDoubleSpinBox()
        self.in_feriado.setRange(0, 1000000); self.in_feriado.setPrefix("$ "); self.in_feriado.setSingleStep(500.0)
        self.in_feriado.setStyleSheet("font-size: 14px; font-weight: bold;")
        h_feriado.addWidget(self.btn_feriado)
        h_feriado.addWidget(self.in_feriado)
        layout.addLayout(h_feriado)

        layout.addWidget(QLabel("<b>⚠️ Extras Operativos:</b>"))
        form_extras = QFormLayout()
        
        self.in_contingencia = QDoubleSpinBox(); self.in_contingencia.setRange(0, 1000000); self.in_contingencia.setPrefix("$ "); self.in_contingencia.setSingleStep(500.0)
        self.in_doble_visita = QDoubleSpinBox(); self.in_doble_visita.setRange(0, 1000000); self.in_doble_visita.setPrefix("$ "); self.in_doble_visita.setSingleStep(500.0)
        
        fecha_para_billing = op.fecha_entrega if op.fecha_entrega else op.fecha_ingreso
        es_finde = fecha_para_billing and fecha_para_billing.weekday() >= 5
        
        try: base_actual = self.main_app.obtener_precio(op.localidad, bultos_com, bultos_fr, op.sucursal, op.proveedor, op.peso or 0.0, bultos_tot)
        except: base_actual = 0.0
        
        monto_serv = op.monto_servicio or 0.0
        monto_finde_db = getattr(op, 'monto_finde', 0.0) or 0.0
        monto_feriado_db = getattr(op, 'monto_feriado', 0.0) or 0.0
        monto_cont_db = getattr(op, 'monto_contingencia', 0.0) or 0.0
        monto_esp_db = getattr(op, 'monto_espera', 0.0) or 0.0
        
        if monto_finde_db == 0 and monto_feriado_db == 0 and monto_cont_db == 0 and monto_esp_db == 0 and monto_serv > base_actual:
            excedente = monto_serv - base_actual
            if es_finde and excedente >= (base_actual * 0.9):
                monto_finde_db = base_actual
                excedente -= base_actual
            if visitas > 1 and excedente > 0:
                monto_esp_db = excedente
                excedente = 0.0
            monto_cont_db = excedente
            
        self.in_finde.setValue(monto_finde_db)
        self.in_feriado.setValue(monto_feriado_db)
        self.in_contingencia.setValue(monto_cont_db)
        self.in_doble_visita.setValue(monto_esp_db)
        
        lbl_visita = QLabel("⏳ Espera / Doble Visita:")
        if visitas > 1:
            lbl_visita.setText(f"⏳ Espera / Doble Visita (¡Tuvo {visitas} visitas!):")
            lbl_visita.setStyleSheet("color: #d32f2f; font-weight: bold;") 
        
        form_extras.addRow("⚠️ Contingencia General:", self.in_contingencia)
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

        self.combo_zona.currentTextChanged.connect(self.recalcular)
        self.in_bultos.valueChanged.connect(self.recalcular)
        self.in_frio.valueChanged.connect(self.recalcular)
        self.chk_combinado.toggled.connect(self.recalcular)
        
        self.in_finde.valueChanged.connect(self.recalcular_solo_total)
        self.in_feriado.valueChanged.connect(self.recalcular_solo_total)
        self.in_contingencia.valueChanged.connect(self.recalcular_solo_total)
        self.in_doble_visita.valueChanged.connect(self.recalcular_solo_total)
        
        self.btn_finde.clicked.connect(self.aplicar_finde)
        self.btn_feriado.clicked.connect(self.aplicar_feriado)
        
        self.base_calculada = 0.0
        self.recalcular() 

    def aplicar_finde(self):
        self.in_finde.setValue(self.base_calculada * 1.0) 
        
    def aplicar_feriado(self):
        self.in_feriado.setValue(self.base_calculada * 2.0) 

    def recalcular(self):
        b_tot = self.in_bultos.value()
        b_frio = self.in_frio.value()
        
        if b_frio > b_tot: 
            self.in_frio.blockSignals(True)
            self.in_frio.setValue(b_tot)
            b_frio = b_tot
            self.in_frio.blockSignals(False)
            
        b_com = b_tot - b_frio
        es_combinado = self.chk_combinado.isChecked()
        
        if es_combinado:
            if b_tot > 1:
                self.base_calculada = self.main_app.obtener_precio(self.combo_zona.currentText(), 1, b_tot - 1, self.op.sucursal, self.op.proveedor, self.op.peso or 0.0, b_tot)
            else:
                self.base_calculada = self.main_app.obtener_precio(self.combo_zona.currentText(), 0, 1, self.op.sucursal, self.op.proveedor, self.op.peso or 0.0, b_tot)
        else:
            base_comun = self.main_app.obtener_precio(self.combo_zona.currentText(), b_com, 0, self.op.sucursal, self.op.proveedor, self.op.peso or 0.0, b_com) if b_com > 0 else 0.0
            base_frio = self.main_app.obtener_precio(self.combo_zona.currentText(), 0, b_frio, self.op.sucursal, self.op.proveedor, self.op.peso or 0.0, b_frio) if b_frio > 0 else 0.0
            self.base_calculada = base_comun + base_frio
            
        self.lbl_base.setText(f"Tarifa Base Calculada (S/ extras): $ {self.base_calculada:,.2f}")
        self.recalcular_solo_total()

    def recalcular_solo_total(self):
        self.precio_final = self.base_calculada + self.in_finde.value() + self.in_feriado.value() + self.in_contingencia.value() + self.in_doble_visita.value()
        self.lbl_total.setText(f"$ {self.precio_final:,.2f}")


class TabFacturacion(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main = main_window
        self.setup_ui()
        
    def setup_ui(self):
        l = QVBoxLayout(self); self.tabs_fact = QTabWidget(); l.addWidget(self.tabs_fact)
        tab_rendicion = QWidget(); layout_rend = QVBoxLayout(tab_rendicion); panel = QFrame(); hl = QHBoxLayout(panel)
        self.cierre_mes = QComboBox(); self.cierre_mes.addItems(["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]); self.cierre_mes.setCurrentIndex(datetime.now().month - 1) 
        self.cierre_anio = QSpinBox(); self.cierre_anio.setRange(2020, 2030); self.cierre_anio.setValue(datetime.now().year)
        
        self.cierre_sucursal = QComboBox(); self.cierre_sucursal.addItems(["Todas", "Mendoza", "San Juan"]) 
        
        self.cierre_prov = RestrictedComboBox(self.main)
        self.cierre_prov.addItem("Todos")
        self.cierre_prov.addItems(self.main.lista_proveedores)
        
        self.btn_c = QPushButton("Calcular Listado"); self.btn_c.clicked.connect(self.calcular_cierre)
        
        btn_pdf = QPushButton("Rendición PDF"); btn_pdf.setStyleSheet("background-color: #dc3545 !important; color: white !important; font-weight: bold; padding: 6px;"); btn_pdf.clicked.connect(self.generar_pdf_fact)
        hl.addWidget(QLabel("Sucursal:")); hl.addWidget(self.cierre_sucursal); hl.addWidget(QLabel("Mes:")); hl.addWidget(self.cierre_mes); hl.addWidget(QLabel("Año:")); hl.addWidget(self.cierre_anio); hl.addWidget(QLabel("Proveedor:")); hl.addWidget(self.cierre_prov); hl.addWidget(self.btn_c); hl.addWidget(btn_pdf); btn_cargo_fijo = QPushButton("➕ Agregar Cargo Fijo"); btn_cargo_fijo.clicked.connect(self.agregar_cargo_fijo); hl.addWidget(btn_cargo_fijo)
        
        # 🔥 REDISTRIBUCIÓN DE ANCHOS (GUÍA MÁS GRANDE) 🔥
        self.tabla_cierre = QTableWidget(); self.tabla_cierre.setColumnCount(13); 
        self.tabla_cierre.setHorizontalHeaderLabels(["Sel.", "F. Ingreso", "F. Entrega", "Sucursal", "Guía", "Zona", "Bultos", "Estado", "Base ($)", "Finde/Fer ($)", "Otros Extras ($)", "Total ($)", "Ajustes"]); 
        self.tabla_cierre.setStyleSheet(ESTILO_TABLAS_BLANCAS); self.pintor_cierre = PintorCeldasDelegate(self.tabla_cierre); self.tabla_cierre.setItemDelegate(self.pintor_cierre)
        
        header = self.tabla_cierre.horizontalHeader(); header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive); 
        self.tabla_cierre.setColumnWidth(0, 40)   # Sel.
        self.tabla_cierre.setColumnWidth(1, 85)   # F. Ingreso
        self.tabla_cierre.setColumnWidth(2, 85)   # F. Entrega
        self.tabla_cierre.setColumnWidth(3, 90)   # Sucursal
        self.tabla_cierre.setColumnWidth(4, 220)  # Guía (Ampliando espacio)
        self.tabla_cierre.setColumnWidth(5, 130)  # Zona
        self.tabla_cierre.setColumnWidth(6, 110)  # Bultos
        self.tabla_cierre.setColumnWidth(7, 130)  # Estado
        self.tabla_cierre.setColumnWidth(8, 90)   # Base
        self.tabla_cierre.setColumnWidth(9, 90)   # Finde/Fer
        self.tabla_cierre.setColumnWidth(10, 90)  # Otros Extras
        self.tabla_cierre.setColumnWidth(11, 90)  # Total
        self.tabla_cierre.setColumnWidth(12, 85)  # Ajustes
        
        header.setStretchLastSection(True); self.tabla_cierre.verticalHeader().setFixedWidth(30); self.tabla_cierre.verticalHeader().setDefaultSectionSize(45); self.tabla_cierre.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.tabla_cierre.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); self.tabla_cierre.cellDoubleClicked.connect(self.doble_clic_ajuste_precio)
        
        self.tabla_cierre.itemChanged.connect(self.recalcular_totales_seleccionados)
        
        self.lbl_resumen = QLabel("Total Base: $0 | Total Extras: $0 | TOTAL: $0"); self.lbl_resumen.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px 15px; padding: 10px; border: 1px solid #ccc; background-color: #e3f2fd;")
        lay_abajo = QHBoxLayout(); 
        
        self.btn_deshacer_fac = QPushButton("⏪ Deshacer Facturación"); self.btn_deshacer_fac.setStyleSheet("background-color: #ff9800; color: black; padding: 8px; font-weight: bold;"); self.btn_deshacer_fac.clicked.connect(self.abrir_dialogo_deshacer_facturacion); 
        
        self.btn_seleccionar_todo = QPushButton("☑️ Deseleccionar Todo")
        self.btn_seleccionar_todo.setStyleSheet("background-color: #17a2b8; color: white; padding: 8px; font-weight: bold;")
        self.btn_seleccionar_todo.clicked.connect(self.toggle_seleccionar_todo)

        lay_abajo.addWidget(self.btn_deshacer_fac); 
        lay_abajo.addWidget(self.btn_seleccionar_todo);
        lay_abajo.addStretch(); 
        lay_abajo.addWidget(self.lbl_resumen); 
        layout_rend.addWidget(panel); layout_rend.addWidget(self.tabla_cierre); layout_rend.addLayout(lay_abajo); self.tabs_fact.addTab(tab_rendicion, "1. Calcular Rendición")
        
        tab_cta = QWidget(); layout_cta = QVBoxLayout(tab_cta); top_cta = QHBoxLayout(); btn_ref_cta = QPushButton("🔄 Actualizar Saldos"); btn_ref_cta.clicked.connect(self.cargar_ctas_ctes); btn_pago = QPushButton("💰 Registrar Pago"); btn_pago.clicked.connect(self.registrar_pago_ctacte); top_cta.addWidget(btn_ref_cta); top_cta.addStretch(); top_cta.addWidget(btn_pago)
        self.tabla_ctacte = QTableWidget(); self.tabla_ctacte.setColumnCount(4); self.tabla_ctacte.setHorizontalHeaderLabels(["Proveedor", "Total Facturado ($)", "Pagos ($)", "SALDO ($)"]); self.tabla_ctacte.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive); self.tabla_ctacte.setColumnWidth(0, 250); self.tabla_ctacte.setColumnWidth(1, 180); self.tabla_ctacte.setColumnWidth(2, 180); header_cta = self.tabla_ctacte.horizontalHeader(); header_cta.setStretchLastSection(True); self.tabla_ctacte.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.tabla_ctacte.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); self.tabla_ctacte.setStyleSheet(ESTILO_TABLAS_BLANCAS); self.pintor_cta = PintorCeldasDelegate(self.tabla_ctacte); self.tabla_ctacte.setItemDelegate(self.pintor_cta); layout_cta.addLayout(top_cta); layout_cta.addWidget(self.tabla_ctacte); self.tabs_fact.addTab(tab_cta, "2. Cuentas Corrientes")
    
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
        
        tot_base = 0; tot_extras = 0; tot_final = 0
        for r in range(self.tabla_cierre.rowCount()):
            it = self.tabla_cierre.item(r, 0)
            if it and it.checkState() == Qt.CheckState.Checked:
                op_id = self.mapa_filas_cierre.get(r)
                op = next((o for o in self.resultados_cierre if o.id == op_id), None)
                if op:
                    bultos_tot = int(op.bultos) if op.bultos else 1
                    bultos_fr = int(op.bultos_frio) if op.bultos_frio else 0
                    monto_serv = op.monto_servicio or 0.0
                    
                    if op.guia_remito == "CARGO-FIJO" or (op.tipo_servicio and "Flete" in op.tipo_servicio):
                        precio_base = monto_serv; extras = 0
                    else:
                        precio_base = self.main.obtener_precio(op.localidad, bultos_tot-bultos_fr, bultos_fr, op.sucursal, proveedor=op.proveedor, peso=op.peso, bultos_totales=bultos_tot)
                        monto_finde_tabla = (getattr(op, 'monto_finde', 0.0) or 0.0) + (getattr(op, 'monto_feriado', 0.0) or 0.0)
                        monto_otros_tabla = (getattr(op, 'monto_contingencia', 0.0) or 0.0) + (getattr(op, 'monto_espera', 0.0) or 0.0)
                        if monto_finde_tabla == 0 and monto_otros_tabla == 0 and monto_serv > precio_base:
                            monto_otros_tabla = monto_serv - precio_base
                        extras = monto_finde_tabla + monto_otros_tabla
                        
                    tot_base += precio_base
                    tot_extras += extras
                    tot_final += monto_serv
                    
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
        id_op = self.mapa_filas_cierre.get(row)
        if id_op: self.abrir_dialogo_ajuste_precio(id_op)
        
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
                
                self.main.session.commit()
                self.calcular_cierre()
                self.main.toast.mostrar("✅ Datos operativos y tarifa actualizados")
        except Exception as e: 
            self.main.session.rollback()
            QMessageBox.critical(self, "Error", f"Fallo al actualizar: {e}")
        
    def abrir_dialogo_peso_dhl(self, id_op):
        try:
            op = self.main.session.query(Operacion).get(id_op)
            if not op: return
            dlg = EditarPesoDHLDialog(op, self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                bultos_nuevos, peso_nuevo = dlg.valores
                op.bultos = bultos_nuevos
                op.peso = peso_nuevo
                
                nuevo_precio = self.main.obtener_precio(
                    op.localidad, 
                    cant_comun=bultos_nuevos, 
                    cant_frio=0, 
                    suc_forzada=op.sucursal, 
                    proveedor="DHL EXPRESS", 
                    peso=peso_nuevo, 
                    bultos_totales=bultos_nuevos
                )
                
                op.monto_servicio = nuevo_precio
                self.main.session.commit()
                self.calcular_cierre()
                self.main.toast.mostrar("✅ Peso y tarifa DHL actualizados")
        except Exception as e:
            self.main.session.rollback()
            QMessageBox.critical(self, "Error", str(e))
        
    def calcular_cierre(self):
        self.btn_c.setEnabled(False)
        self.tabla_cierre.blockSignals(True) 
        
        mes = self.cierre_mes.currentIndex() + 1; anio = self.cierre_anio.value(); prov = self.cierre_prov.currentText().strip(); sucursal = self.cierre_sucursal.currentText(); self.tabla_cierre.setRowCount(0)
        try:
            _, last_day = calendar.monthrange(anio, mes); start_date = date(anio, mes, 1); end_date = date(anio, mes, last_day)
            
            fecha_ref = func.coalesce(Operacion.fecha_entrega, Operacion.fecha_ingreso)
            query = self.main.session.query(Operacion).filter(
                func.date(fecha_ref) >= start_date, 
                func.date(fecha_ref) <= end_date, 
                (Operacion.facturado == False) | (Operacion.facturado == None), 
                Operacion.estado.ilike('ENTREGADO')
            )
            
            if prov != "Todos" and prov != "": query = query.filter(Operacion.proveedor.ilike(prov))
            else: query = query.filter(~Operacion.proveedor.ilike('JetPaq'))
            if sucursal != "Todas": query = query.filter(Operacion.sucursal == sucursal)
            query = query.order_by(Operacion.fecha_ingreso.asc()); self.resultados_cierre = query.all()
            
            if not self.resultados_cierre: 
                self.tabla_cierre.setRowCount(1); item_empty = QTableWidgetItem("❌ Sin guías entregadas para facturar."); item_empty.setTextAlignment(Qt.AlignmentFlag.AlignCenter); self.tabla_cierre.setItem(0, 0, item_empty); self.tabla_cierre.setSpan(0, 0, 1, 13); self.lbl_resumen.setText("Total Base: $0 | Total Extras: $0 | TOTAL SELECCIONADO: $0")
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
            
            for row, op in enumerate(self.resultados_cierre):
                if row % 2 == 0 or row == total_ops - 1: 
                    progreso.setLabelText(f"Calculando tarifa: guía {row + 1} de {total_ops}...")
                    progreso.setValue(row)
                    QApplication.processEvents()
                    
                self.tabla_cierre.insertRow(row); self.mapa_filas_cierre[row] = op.id; 
                
                chk = QTableWidgetItem()
                chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
                chk.setCheckState(Qt.CheckState.Checked)
                self.tabla_cierre.setItem(row, 0, chk)
                
                f_ingreso = op.fecha_ingreso.strftime("%d/%m/%Y") if op.fecha_ingreso else "-"
                f_entrega = op.fecha_entrega.strftime("%d/%m/%Y") if op.fecha_entrega else "-"
                
                self.tabla_cierre.setItem(row, 1, QTableWidgetItem(f_ingreso))
                self.tabla_cierre.setItem(row, 2, QTableWidgetItem(f_entrega))
                self.tabla_cierre.setItem(row, 3, QTableWidgetItem((op.sucursal or "").upper()))
                self.tabla_cierre.setItem(row, 4, QTableWidgetItem(op.guia_remito or "RET"))
                self.tabla_cierre.setItem(row, 5, QTableWidgetItem(op.localidad or ""))
                
                bultos_tot = int(op.bultos) if op.bultos else 1
                bultos_fr = int(op.bultos_frio) if op.bultos_frio else 0
                det_b = str(bultos_tot)
                
                if op.proveedor and op.proveedor.upper() == "DHL EXPRESS":
                    det_b = f"{bultos_tot} B | {op.peso or 0} Kg"
                else:
                    if bultos_fr > 0 and bultos_fr < bultos_tot: det_b += f" ({bultos_tot-bultos_fr}C/{bultos_fr}R)"
                    elif bultos_fr == bultos_tot: det_b += " (R)"
                    
                self.tabla_cierre.setItem(row, 6, QTableWidgetItem(det_b))
                
                fecha_para_billing = op.fecha_entrega if op.fecha_entrega else op.fecha_ingreso
                es_finde = fecha_para_billing and fecha_para_billing.weekday() >= 5
                
                visitas = max(1, conteo_repartos.get(op.id, 1))
                estado_txt = f"{op.estado} ({visitas} Visitas)" if visitas > 1 else op.estado
                
                monto_finde = getattr(op, 'monto_finde', 0.0) or 0.0
                if es_finde and monto_finde > 0:
                    estado_txt = f"🚨 GUARDIA FINDE | {estado_txt}"
                    
                self.tabla_cierre.setItem(row, 7, QTableWidgetItem(estado_txt))
                
                monto_serv = op.monto_servicio or 0.0
                if op.guia_remito == "CARGO-FIJO" or (op.tipo_servicio and "Flete" in op.tipo_servicio): 
                    precio_base = monto_serv; extras = 0; monto_finde_tabla = 0.0; monto_otros_tabla = 0.0
                else: 
                    precio_base = self.main.obtener_precio(op.localidad, bultos_tot-bultos_fr, bultos_fr, op.sucursal, proveedor=op.proveedor, peso=op.peso, bultos_totales=bultos_tot)
                    
                    monto_finde_tabla = (getattr(op, 'monto_finde', 0.0) or 0.0) + (getattr(op, 'monto_feriado', 0.0) or 0.0)
                    monto_otros_tabla = (getattr(op, 'monto_contingencia', 0.0) or 0.0) + (getattr(op, 'monto_espera', 0.0) or 0.0)
                    
                    if monto_finde_tabla == 0 and monto_otros_tabla == 0 and monto_serv > precio_base:
                        monto_otros_tabla = monto_serv - precio_base
                        
                    extras = monto_finde_tabla + monto_otros_tabla

                self.tabla_cierre.setItem(row, 8, QTableWidgetItem(f"$ {precio_base:,.2f}"))
                self.tabla_cierre.setItem(row, 9, QTableWidgetItem(f"$ {monto_finde_tabla:,.2f}"))
                self.tabla_cierre.setItem(row, 10, QTableWidgetItem(f"$ {monto_otros_tabla:,.2f}"))
                self.tabla_cierre.setItem(row, 11, QTableWidgetItem(f"$ {monto_serv:,.2f}"))
                
                if es_finde and monto_finde > 0:
                    brush = QBrush(QColor("#fff3cd"))
                    for col_idx in range(12): 
                        it = self.tabla_cierre.item(row, col_idx)
                        if it: it.setBackground(brush)
                
                w_acc = QWidget(); lay_acc = QHBoxLayout(w_acc); lay_acc.setContentsMargins(0,0,0,0)
                btn_ajuste = QPushButton("✏️ Editar"); btn_ajuste.setStyleSheet("background-color: #0d6efd !important; color: white !important; font-size: 11px; font-weight: bold; padding: 4px;")
                btn_ajuste.clicked.connect(lambda checked, r=row: self.abrir_dialogo_ajuste_precio(self.mapa_filas_cierre[r]))
                lay_acc.addWidget(btn_ajuste)
                
                if op.proveedor and op.proveedor.upper() == "DHL EXPRESS":
                    btn_peso = QPushButton("⚖️ Peso"); btn_peso.setStyleSheet("background-color: #ff9800 !important; color: black !important; font-size: 11px; font-weight: bold; padding: 4px;")
                    btn_peso.clicked.connect(lambda checked, r=row: self.abrir_dialogo_peso_dhl(self.mapa_filas_cierre[r]))
                    lay_acc.addWidget(btn_peso)
                
                self.tabla_cierre.setCellWidget(row, 12, w_acc)
                
            progreso.setValue(total_ops)
            
            self.tabla_cierre.blockSignals(False)
            self.btn_seleccionar_todo.setText("☑️ Deseleccionar Todo")
            self.recalcular_totales_seleccionados()
            
        except Exception as e: 
            self.main.session.rollback()
            self.lbl_resumen.setText("Total Base: $0 | Total Extras: $0 | TOTAL: $0")
            QMessageBox.critical(self, "Error", str(e))
        finally:
            self.tabla_cierre.blockSignals(False)
            self.btn_c.setEnabled(True)
        
    def generar_pdf_fact(self):
        if not hasattr(self, 'resultados_cierre') or not self.resultados_cierre: return
        
        ops_seleccionadas = []
        for r in range(self.tabla_cierre.rowCount()):
            it = self.tabla_cierre.item(r, 0)
            if it and it.checkState() == Qt.CheckState.Checked:
                op_id = self.mapa_filas_cierre.get(r)
                op = next((o for o in self.resultados_cierre if o.id == op_id), None)
                if op: ops_seleccionadas.append(op)

        if not ops_seleccionadas:
            QMessageBox.warning(self, "Aviso", "⚠️ No hay guías seleccionadas para facturar. Tildá al menos una.")
            return

        reply = QMessageBox.question(self, "Cerrar Facturación", f"¿Desea marcar estas {len(ops_seleccionadas)} guías como FACTURADAS?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        marcar_facturado = (reply == QMessageBox.StandardButton.Yes)
        mes_nombre = self.cierre_mes.currentText(); anio_num = self.cierre_anio.value(); prov_nombre = self.cierre_prov.currentText()
        descargas_dir = os.path.join(os.path.expanduser('~'), 'Downloads'); os.makedirs(descargas_dir, exist_ok=True)
        ruta_pdf = os.path.join(descargas_dir, f"Facturacion_{prov_nombre}_{mes_nombre}_{anio_num}.pdf")
        
        data_filas = [['FECHA', 'GUÍA', 'ZONA', 'BULTOS', 'BASE ($)', 'FINDE ($)', 'EXTRAS ($)', 'TOTAL ($)']]
        for op in ops_seleccionadas:
            monto_serv = op.monto_servicio or 0.0; bultos_tot = int(op.bultos) if op.bultos else 1; bultos_fr = int(op.bultos_frio) if op.bultos_frio else 0; precio_base = self.main.obtener_precio(op.localidad, bultos_tot-bultos_fr, bultos_fr, op.sucursal, proveedor=op.proveedor, peso=op.peso, bultos_totales=bultos_tot); extras = monto_serv - precio_base; det_b = str(bultos_tot)
            
            if op.proveedor and op.proveedor.upper() == "DHL EXPRESS":
                det_b = f"{bultos_tot}B | {op.peso or 0}Kg"
            else:
                if bultos_fr > 0 and bultos_fr < bultos_tot: det_b += f" ({bultos_tot-bultos_fr}C/{bultos_fr}R)"; 
                elif bultos_fr == bultos_tot: det_b += " (R)"
                
            fecha_para_billing = op.fecha_entrega if op.fecha_entrega else op.fecha_ingreso
            es_finde = fecha_para_billing and fecha_para_billing.weekday() >= 5
            
            monto_finde_pdf = (getattr(op, 'monto_finde', 0.0) or 0.0) + (getattr(op, 'monto_feriado', 0.0) or 0.0)
            monto_otros_pdf = (getattr(op, 'monto_contingencia', 0.0) or 0.0) + (getattr(op, 'monto_espera', 0.0) or 0.0)
            
            if monto_finde_pdf == 0 and monto_otros_pdf == 0 and monto_serv > precio_base:
                monto_otros_pdf = monto_serv - precio_base
            
            data_filas.append([fecha_para_billing.strftime("%d/%m/%Y"), op.guia_remito or "RET", op.localidad[:15].upper(), det_b, f"$ {precio_base:,.0f}", f"$ {monto_finde_pdf:,.0f}", f"$ {monto_otros_pdf:,.0f}", f"$ {monto_serv:,.0f}"])
            if marcar_facturado: op.facturado = True
            
        if marcar_facturado: 
            try: self.main.session.commit(); self.calcular_cierre(); self.cargar_ctas_ctes()
            except: self.main.session.rollback()
            
        # 🔥 CÁLCULOS DEL IVA Y SEPARADORES EN EL PDF 🔥
        tb, te, tf = self.totales_cierre
        iva = tf * 0.21
        total_final_iva = tf + iva
        
        data_filas.append(['', '', '', '', '', '', '', '']) # Fila vacía para separar
        data_filas.append(['SUBTOTALES:', '', '', '', f"$ {tb:,.2f}", f"$ {te:,.2f}", '-', f"$ {tf:,.2f}"])
        data_filas.append(['', '', '', '', '', '', 'IVA (21%):', f"$ {iva:,.2f}"])
        data_filas.append(['', '', '', '', '', '', 'TOTAL FACTURA:', f"$ {total_final_iva:,.2f}"])
        
        crear_pdf_facturacion(ruta_pdf, data_filas, prov_nombre, f"{mes_nombre} {anio_num}", self.main.usuario.username, datetime.now().strftime('%d/%m/%Y %H:%M'))
        os.startfile(ruta_pdf)