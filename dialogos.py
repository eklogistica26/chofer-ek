from datetime import datetime
from PyQt6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox, 
                             QPushButton, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QMessageBox, QDateEdit, QGroupBox, 
                             QFormLayout, QWidget, QSpinBox, QDoubleSpinBox, 
                             QRadioButton, QButtonGroup, QCheckBox, QDialog, 
                             QTimeEdit, QAbstractItemView, QFileDialog)
from PyQt6.QtCore import Qt, QDate, QTimer, QTime
from PyQt6.QtGui import QColor, QFont
from sqlalchemy import extract, desc, text

from database import Operacion, Historial, ClientePrincipal, DestinoFrecuente, Estados, Urgencia, HistorialTarifas, Usuario

class ToastNotification(QLabel):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.SubWindow)
        self.setStyleSheet("""background-color: #28a745; color: white; padding: 15px 30px; border-radius: 10px; font-size: 18px; font-weight: bold; border: 2px solid #1e7e34;""")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hide(); self.timer = QTimer(); self.timer.timeout.connect(self.hide)
    def mostrar(self, texto):
        self.setText(texto); self.adjustSize()
        parent_geo = self.parent().geometry(); x = (parent_geo.width() - self.width()) // 2; y = parent_geo.height() - 150 
        self.move(x, y); self.show(); self.raise_(); self.timer.start(5000)

class EditarPrecioFacturacionDialog(QDialog):
    def __init__(self, operacion, main_app, parent=None):
        super().__init__(parent)
        self.op = operacion; self.main_app = main_app
        self.setWindowTitle(f"💵 Facturación Detallada - Guía: {operacion.guia_remito or 'RET'}")
        self.setGeometry(400, 200, 450, 550)
        layout = QVBoxLayout(self)
        
        conteo = 1
        try:
            sql = text("SELECT COUNT(*) FROM historial_movimientos WHERE operacion_id = :id AND accion = 'SALIDA A REPARTO'")
            res = self.main_app.session.execute(sql, {"id": operacion.id}).fetchone()
            if res and res[0] > 0: conteo = res[0]
        except: pass
        
        alerta_visitas = ""
        if conteo > 1:
            alerta_visitas = f"<br><br><span style='color: #dc3545; font-size: 16px;'>⚠️ <b>ATENCIÓN:</b> El paquete se sacó a reparto <b>{conteo} veces</b>. Considere cobrar Demora.</span>"

        info_lbl = QLabel(f"<b>Destinatario:</b> {operacion.destinatario}<br><b>Bultos:</b> {operacion.bultos} (Frío: {operacion.bultos_frio or 0})<br><b>Peso Total:</b> {operacion.peso} Kg{alerta_visitas}")
        info_lbl.setStyleSheet("background-color: #e7f1ff; padding: 10px; border: 1px solid #0d6efd; border-radius: 5px; font-size: 14px;")
        info_lbl.setWordWrap(True); layout.addWidget(info_lbl)
        
        form = QFormLayout()

        # 🔥 FIX 5: EDICIÓN DE ZONA EN FACTURACIÓN 🔥
        self.in_zona = QComboBox()
        self.in_zona.setEditable(True)
        try:
            from database import Tarifa
            zonas = [z[0] for z in self.main_app.session.query(Tarifa.localidad).filter(Tarifa.sucursal == self.op.sucursal).distinct().all()]
            self.in_zona.addItems(sorted(zonas))
        except: pass
        self.in_zona.setCurrentText(self.op.localidad or "")
        self.in_zona.currentTextChanged.connect(self.recalcular_base_por_zona)
        form.addRow("Zona / Localidad:", self.in_zona)

        if self.op.guia_remito == "CARGO-FIJO" or (self.op.tipo_servicio and "Flete" in self.op.tipo_servicio):
            self.precio_base_puro = self.op.monto_servicio
        else:
            cant_frio = self.op.bultos_frio or 0; cant_comun = self.op.bultos - cant_frio
            self.precio_base_puro = self.main_app.obtener_precio(self.op.localidad, cant_comun, cant_frio, self.op.sucursal, proveedor=self.op.proveedor, peso=self.op.peso, bultos_totales=self.op.bultos)

        self.in_precio_base = QDoubleSpinBox()
        self.in_precio_base.setRange(0, 10000000); self.in_precio_base.setPrefix("$ "); 
        self.in_precio_base.setValue(self.precio_base_puro)
        self.in_precio_base.valueChanged.connect(self.calcular_total)
        form.addRow("Precio Tarifario Base:", self.in_precio_base)
        
        gb_mod = QGroupBox("Modificadores Rápidos (Opcional)")
        gb_mod.setStyleSheet("font-weight: bold; border: 1px solid #ccc; padding-top: 15px; margin-top: 10px;")
        ly_mod = QVBoxLayout(gb_mod)
        
        self.chk_feriado = QCheckBox("🎉 Es Feriado en la semana (Tarifa x3)")
        self.chk_feriado.stateChanged.connect(self.calcular_total)
        ly_mod.addWidget(self.chk_feriado)
        
        h_demora = QHBoxLayout()
        self.chk_demora = QCheckBox("⏳ Cobrar Demora / Visitas Extra")
        self.chk_demora.stateChanged.connect(self.toggle_demora)
        self.in_monto_demora = QDoubleSpinBox(); self.in_monto_demora.setRange(0, 100000); self.in_monto_demora.setPrefix("$ ")
        self.in_monto_demora.setValue(self.precio_base_puro * (conteo - 1) if conteo > 1 else self.precio_base_puro) 
        self.in_monto_demora.setEnabled(False); self.in_monto_demora.valueChanged.connect(self.calcular_total)
        h_demora.addWidget(self.chk_demora); h_demora.addWidget(self.in_monto_demora); ly_mod.addLayout(h_demora)
        
        h_frio = QHBoxLayout()
        self.chk_frio = QCheckBox("❄️ Contingencia de Frío")
        self.chk_frio.stateChanged.connect(self.toggle_frio)
        self.in_monto_frio = QDoubleSpinBox(); self.in_monto_frio.setRange(0, 100000); self.in_monto_frio.setPrefix("$ ")
        self.in_monto_frio.setValue(1500.0) 
        self.in_monto_frio.setEnabled(False); self.in_monto_frio.valueChanged.connect(self.calcular_total)
        h_frio.addWidget(self.chk_frio); h_frio.addWidget(self.in_monto_frio); ly_mod.addLayout(h_frio)

        layout.addLayout(form)
        layout.addWidget(gb_mod)
        
        form_extra = QFormLayout()
        extra_historico = self.op.monto_servicio - self.precio_base_puro if self.op.monto_servicio > self.precio_base_puro else 0
        
        self.in_extra = QDoubleSpinBox()
        self.in_extra.setRange(-10000000, 10000000); self.in_extra.setPrefix("$ "); 
        self.in_extra.setValue(extra_historico); self.in_extra.valueChanged.connect(self.calcular_total)
        
        self.in_detalle = QLineEdit()
        self.in_detalle.setPlaceholderText("Detalle del extra (Ej: Cambio de destino)")
        
        self.lbl_total = QLabel(f"$ 0.00"); self.lbl_total.setStyleSheet("font-size: 24px; font-weight: bold; color: #198754;")
        
        form_extra.addRow("Otro Ajuste ($):", self.in_extra)
        form_extra.addRow("Detalle Ajuste:", self.in_detalle)
        form_extra.addRow("TOTAL A FACTURAR:", self.lbl_total)
        layout.addLayout(form_extra)
        
        btn_guardar = QPushButton("💾 GUARDAR FACTURACIÓN")
        btn_guardar.setStyleSheet("background-color: #0d6efd; color: white; font-weight: bold; padding: 12px; margin-top: 10px;")
        btn_guardar.clicked.connect(self.guardar_y_cerrar)
        layout.addWidget(btn_guardar)
        
        self.calcular_total()

    def recalcular_base_por_zona(self, nueva_zona):
        if self.op.guia_remito == "CARGO-FIJO" or (self.op.tipo_servicio and "Flete" in self.op.tipo_servicio):
            return
        cant_frio = self.op.bultos_frio or 0; cant_comun = self.op.bultos - cant_frio
        self.precio_base_puro = self.main_app.obtener_precio(nueva_zona, cant_comun, cant_frio, self.op.sucursal, proveedor=self.op.proveedor, peso=self.op.peso, bultos_totales=self.op.bultos)
        self.in_precio_base.blockSignals(True)
        self.in_precio_base.setValue(self.precio_base_puro)
        self.in_precio_base.blockSignals(False)
        self.calcular_total()

    def toggle_demora(self, state):
        self.in_monto_demora.setEnabled(state == Qt.CheckState.Checked.value)
        self.calcular_total()
        
    def toggle_frio(self, state):
        self.in_monto_frio.setEnabled(state == Qt.CheckState.Checked.value)
        self.calcular_total()

    def calcular_total(self): 
        base = self.in_precio_base.value()
        if self.chk_feriado.isChecked(): base = base * 3 
        extra = self.in_extra.value()
        if self.chk_demora.isChecked(): extra += self.in_monto_demora.value()
        if self.chk_frio.isChecked(): extra += self.in_monto_frio.value()
            
        self.total_calculado = base + extra
        self.lbl_total.setText(f"$ {self.total_calculado:,.2f}")
        
    def guardar_y_cerrar(self):
        nueva_zona = self.in_zona.currentText().strip().upper()
        if nueva_zona:
            self.op.localidad = nueva_zona
            
        notas = []
        if self.chk_feriado.isChecked(): notas.append("Feriado")
        if self.chk_demora.isChecked(): notas.append(f"Demora (${self.in_monto_demora.value()})")
        if self.chk_frio.isChecked(): notas.append(f"Frío (${self.in_monto_frio.value()})")
        if self.in_extra.value() > 0 and self.in_detalle.text(): notas.append(self.in_detalle.text().strip().upper())
        if notas:
            self.op.tipo_carga = f"{self.op.tipo_carga.split(' |')[0]} | Extras: {', '.join(notas)}"
        self.accept()

    @property
    def precio_final(self): return self.total_calculado

class PreviewImportacionDialog(QDialog):
    def __init__(self, ops_data, parent=None):
        super().__init__(parent); self.setWindowTitle("📥 Vista Previa: Importación DHL"); self.setGeometry(300, 200, 1000, 500); self.ops_data = ops_data; self.resultados = []
        layout = QVBoxLayout(self)
        lbl_info = QLabel("⚠️ Revise los datos extraídos. Puede cambiar la fecha y el peso a las guías antes de guardarlas.")
        lbl_info.setStyleSheet("color: #856404; background-color: #fff3cd; padding: 10px; border-radius: 5px; font-weight: bold;"); layout.addWidget(lbl_info)
        self.tabla = QTableWidget(); self.tabla.setColumnCount(7)
        self.tabla.setHorizontalHeaderLabels(["Guía", "Destinatario", "Domicilio", "Celular", "Bultos", "Peso (Kg)", "📅 Fecha Asignada"])
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tabla.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.cargar_tabla(); layout.addWidget(self.tabla)
        h_btn = QHBoxLayout(); btn_cancel = QPushButton("❌ Cancelar"); btn_cancel.clicked.connect(self.reject)
        btn_import = QPushButton("✅ CONFIRMAR E IMPORTAR"); btn_import.setStyleSheet("background-color: #198754; color: white; font-weight: bold; padding: 10px;"); btn_import.clicked.connect(self.confirmar)
        h_btn.addWidget(btn_cancel); h_btn.addWidget(btn_import); layout.addLayout(h_btn)
    def cargar_tabla(self):
        self.tabla.setRowCount(len(self.ops_data))
        for i, data in enumerate(self.ops_data):
            self.tabla.setItem(i, 0, QTableWidgetItem(data['guia'])); self.tabla.setItem(i, 1, QTableWidgetItem(data['destinatario'])); self.tabla.setItem(i, 2, QTableWidgetItem(data['domicilio'])); self.tabla.setItem(i, 3, QTableWidgetItem(data['celular'])); self.tabla.setItem(i, 4, QTableWidgetItem(str(data['bultos'])))
            peso_edit = QDoubleSpinBox(); peso_edit.setRange(0.1, 9999); peso_edit.setValue(data.get('peso', 1.0)); peso_edit.setSuffix(" Kg"); self.tabla.setCellWidget(i, 5, peso_edit)
            date_edit = QDateEdit(QDate.currentDate()); date_edit.setCalendarPopup(True); date_edit.setStyleSheet("background-color: #e2e3e5; font-weight: bold;"); self.tabla.setCellWidget(i, 6, date_edit)
    def confirmar(self):
        for i in range(self.tabla.rowCount()):
            peso_val = self.tabla.cellWidget(i, 5).value()
            fecha_sel = self.tabla.cellWidget(i, 6).date().toPyDate()
            self.resultados.append({'guia': self.tabla.item(i, 0).text().upper(), 'destinatario': self.tabla.item(i, 1).text().upper(), 'domicilio': self.tabla.item(i, 2).text().upper(), 'celular': self.tabla.item(i, 3).text(), 'bultos': int(self.tabla.item(i, 4).text()), 'peso': peso_val, 'fecha_ingreso': fecha_sel})
        self.accept()

class ConfirmarEntregaDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("✅ Confirmar Entrega")
        self.setGeometry(400, 300, 450, 350)
        layout = QVBoxLayout()
        form = QFormLayout()
        
        self.in_recibe = QLineEdit()
        self.in_recibe.setPlaceholderText("Nombre y Apellido de quien recibe")
        
        self.in_fecha = QDateEdit(QDate.currentDate())
        self.in_fecha.setCalendarPopup(True)
        
        self.in_hora = QTimeEdit(QTime.currentTime())
        self.chk_hora = QCheckBox("Especificar Hora (Opcional)")
        self.chk_hora.toggled.connect(self.in_hora.setEnabled)
        self.in_hora.setEnabled(False)
        
        self.rutas_fotos = []
        self.btn_fotos = QPushButton("📸 ADJUNTAR FOTOS DEL REMITO (PC)")
        self.btn_fotos.setStyleSheet("background-color: #17a2b8; color: white; font-weight: bold; padding: 8px;")
        self.btn_fotos.clicked.connect(self.seleccionar_fotos)
        self.lbl_fotos = QLabel("Ninguna foto adjunta.")
        self.lbl_fotos.setStyleSheet("color: #666;")
        
        form.addRow("Recibió (Obligatorio):", self.in_recibe)
        form.addRow("Fecha:", self.in_fecha)
        form.addRow(self.chk_hora, self.in_hora)
        form.addRow("", self.btn_fotos)
        form.addRow("", self.lbl_fotos)
        
        btn_ok = QPushButton("CONFIRMAR ENTREGA Y ENVIAR MAIL")
        btn_ok.setStyleSheet("background-color: #28a745; color: white; font-weight: bold; padding: 10px; margin-top: 15px;")
        btn_ok.clicked.connect(self.validar)
        
        layout.addLayout(form)
        layout.addWidget(btn_ok)
        self.setLayout(layout)
        
        self.recibe_final = ""
        self.fecha_final = ""
        self.hora_final = None
        
    def seleccionar_fotos(self):
        archivos, _ = QFileDialog.getOpenFileNames(self, "Seleccionar Fotos", "", "Images (*.png *.jpg *.jpeg)")
        if archivos:
            self.rutas_fotos = archivos
            self.lbl_fotos.setText(f"✅ {len(archivos)} foto(s) adjunta(s) listas para enviar.")
            self.lbl_fotos.setStyleSheet("color: green; font-weight: bold;")
            
    def validar(self):
        if not self.in_recibe.text().strip():
            QMessageBox.warning(self, "Error", "Debe indicar quién recibió.")
            return
        self.recibe_final = self.in_recibe.text().strip().upper()
        self.fecha_final = self.in_fecha.date().toPyDate()
        if self.chk_hora.isChecked():
            self.hora_final = self.in_hora.time().toPyTime()
        self.accept()

class ReprogramarAdminDialog(QDialog):
    def __init__(self, precio_actual, motivo_chofer, parent=None):
        super().__init__(parent); self.setWindowTitle("💵 Reprogramar y Cotizar"); self.setGeometry(400, 300, 400, 300); layout = QVBoxLayout(); form = QFormLayout()
        self.lbl_motivo = QLabel(motivo_chofer or "Sin motivo registrado"); self.lbl_motivo.setStyleSheet("font-weight: bold; color: #dc3545;"); self.lbl_motivo.setWordWrap(True)
        self.in_precio_base = QDoubleSpinBox(); self.in_precio_base.setRange(0, 1e7); self.in_precio_base.setPrefix("$ "); self.in_precio_base.setValue(precio_actual); self.in_precio_base.setEnabled(False); self.in_precio_base.setStyleSheet("color: black; background: #e9ecef;")
        self.in_extra = QDoubleSpinBox(); self.in_extra.setRange(0, 1e7); self.in_extra.setPrefix("$ "); self.in_extra.setValue(0); self.in_extra.valueChanged.connect(self.calcular_total)
        self.lbl_total = QLabel(f"$ {precio_actual:,.2f}"); self.lbl_total.setStyleSheet("font-size: 20px; font-weight: bold; color: #0d6efd;")
        form.addRow("Motivo del Chofer:", self.lbl_motivo); form.addRow("Precio del Servicio (Fijo):", self.in_precio_base); form.addRow("Costo Extra (Recargo):", self.in_extra); form.addRow("TOTAL A COBRAR:", self.lbl_total)
        btn_ok = QPushButton("REPROGRAMAR (Vuelve a Depósito)"); btn_ok.setStyleSheet("background-color: #6f42c1; color: white; font-weight: bold; padding: 10px;"); btn_ok.clicked.connect(self.accept)
        layout.addLayout(form); layout.addWidget(btn_ok); self.setLayout(layout)
    def calcular_total(self): total = self.in_precio_base.value() + self.in_extra.value(); self.lbl_total.setText(f"$ {total:,.2f}")
    @property
    def precio_final(self): return self.in_precio_base.value() + self.in_extra.value()

class HistorialHojasRutaDialog(QDialog):
    def __init__(self, session, sucursal, parent=None):
        super().__init__(parent); self.session = session; self.sucursal = sucursal; self.setWindowTitle("📜 Historial de Hojas de Ruta"); self.setGeometry(300, 200, 900, 600)
        layout = QVBoxLayout(); h_filtro = QHBoxLayout()
        self.date_desde = QDateEdit(QDate.currentDate().addDays(-7)); self.date_desde.setCalendarPopup(True); self.date_hasta = QDateEdit(QDate.currentDate()); self.date_hasta.setCalendarPopup(True)
        btn_buscar = QPushButton("🔍 Buscar"); btn_buscar.clicked.connect(self.cargar_historial)
        h_filtro.addWidget(QLabel("Desde:")); h_filtro.addWidget(self.date_desde); h_filtro.addWidget(QLabel("Hasta:")); h_filtro.addWidget(self.date_hasta); h_filtro.addWidget(btn_buscar); h_filtro.addStretch()
        self.tabla = QTableWidget(); self.tabla.setColumnCount(5); self.tabla.setHorizontalHeaderLabels(["Fecha Salida", "Chofer", "Cant. Guías", "Estado General", "Acción"]); self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addLayout(h_filtro); layout.addWidget(self.tabla); self.setLayout(layout); self.cargar_historial()
    def cargar_historial(self):
        fd = self.date_desde.date().toPyDate(); fh = self.date_hasta.date().toPyDate()
        ops = self.session.query(Operacion.fecha_salida, Operacion.chofer_asignado, Operacion.estado).filter(Operacion.fecha_salida >= fd, Operacion.fecha_salida <= fh, Operacion.sucursal == self.sucursal, Operacion.chofer_asignado != None).all()
        grupos = {} 
        for fecha, chofer, estado in ops:
            if not fecha: continue
            k = (fecha.strftime("%Y-%m-%d %H:%M"), chofer)
            if k not in grupos: grupos[k] = []
            grupos[k].append(estado)
        self.tabla.setRowCount(0)
        for (fecha_str, chofer), estados in sorted(grupos.items(), key=lambda x: x[0], reverse=True):
            r = self.tabla.rowCount(); self.tabla.insertRow(r)
            self.tabla.setItem(r, 0, QTableWidgetItem(fecha_str)); self.tabla.setItem(r, 1, QTableWidgetItem(chofer)); self.tabla.setItem(r, 2, QTableWidgetItem(str(len(estados))))
            st = "✅ COMPLETADA" if all(e == Estados.ENTREGADO for e in estados) else "🚚 EN CALLE" if any(e == Estados.EN_REPARTO for e in estados) else "⚠️ MIXTO"
            self.tabla.setItem(r, 3, QTableWidgetItem(st))
            btn_print = QPushButton("🖨️ RE-IMPRIMIR"); btn_print.setStyleSheet("background-color: #0d6efd; color: white;"); btn_print.clicked.connect(lambda checked, f=fecha_str, c=chofer: self.reimprimir(f, c))
            self.tabla.setCellWidget(r, 4, btn_print)
    def reimprimir(self, fecha_str, chofer):
        dt = datetime.strptime(fecha_str, "%Y-%m-%d %H:%M")
        ops = self.session.query(Operacion).filter(extract('year', Operacion.fecha_salida) == dt.year, extract('month', Operacion.fecha_salida) == dt.month, extract('day', Operacion.fecha_salida) == dt.day, extract('hour', Operacion.fecha_salida) == dt.hour, extract('minute', Operacion.fecha_salida) == dt.minute, Operacion.chofer_asignado == chofer).all()
        if not ops: QMessageBox.warning(self, "Error", "No se encontraron datos."); return
        if self.parent(): self.parent().generar_pdf_ruta(ids_forzados=[op.id for op in ops], nombre_sufijo=f"_COPIA_{fecha_str.replace(':','-')}")

class EditarDestinoDialog(QDialog):
    def __init__(self, destino, parent=None):
        super().__init__(parent); self.setWindowTitle("✏️ Editar Destino"); self.setGeometry(400, 300, 400, 250); self.destino = destino
        layout = QVBoxLayout(); form = QFormLayout()
        self.in_nom = QLineEdit(destino.destinatario); self.in_dom = QLineEdit(destino.domicilio); self.in_cel = QLineEdit(destino.celular or ""); self.in_loc = QLineEdit(destino.localidad)
        form.addRow("Destinatario:", self.in_nom); form.addRow("Domicilio:", self.in_dom); form.addRow("Celular:", self.in_cel); form.addRow("Zona:", self.in_loc)
        btn_save = QPushButton("GUARDAR CAMBIOS"); btn_save.setStyleSheet("background-color: #0d6efd; color: white; padding: 8px; font-weight: bold;"); btn_save.clicked.connect(self.guardar)
        layout.addLayout(form); layout.addWidget(btn_save); self.setLayout(layout)
    def guardar(self):
        if not self.in_nom.text(): QMessageBox.warning(self, "Error", "El destinatario es obligatorio"); return
        self.destino.destinatario = self.in_nom.text().strip().upper()
        self.destino.domicilio = self.in_dom.text().strip().upper()
        self.destino.celular = self.in_cel.text().strip()
        self.destino.localidad = self.in_loc.text().strip().upper()
        self.accept()

class EditarEmpresaDialog(QDialog):
    def __init__(self, empresa, parent=None):
        super().__init__(parent); self.setWindowTitle("✏️ Editar Empresa"); self.setGeometry(400, 300, 400, 200); self.empresa = empresa
        layout = QVBoxLayout(); form = QFormLayout()
        self.in_nom = QLineEdit(empresa.nombre); self.in_email = QLineEdit(empresa.email_reportes or ""); self.in_email.setPlaceholderText("ejemplo@empresa.com")
        form.addRow("Nombre Empresa:", self.in_nom); form.addRow("Email Reportes:", self.in_email)
        btn_save = QPushButton("GUARDAR CAMBIOS"); btn_save.setStyleSheet("background-color: #0d6efd; color: white; padding: 8px; font-weight: bold;"); btn_save.clicked.connect(self.guardar)
        layout.addLayout(form); layout.addWidget(btn_save); self.setLayout(layout)
    def guardar(self):
        if not self.in_nom.text(): QMessageBox.warning(self, "Error", "El nombre es obligatorio"); return
        self.empresa.nombre = self.in_nom.text().strip().upper()
        self.empresa.email_reportes = self.in_email.text()
        self.accept()

class EditarOperacionDialog(QDialog):
    def __init__(self, operacion, session, parent=None):
        super().__init__(parent); self.setWindowTitle(f"✏️ Editar Guía: {operacion.guia_remito}"); self.setGeometry(300, 200, 450, 700)
        self.op = operacion; self.session = session; layout = QVBoxLayout(); form = QFormLayout()
        
        self.in_fecha = QDateEdit(self.op.fecha_ingreso if self.op.fecha_ingreso else QDate.currentDate())
        self.in_fecha.setCalendarPopup(True)
        self.in_fecha.setStyleSheet("font-weight: bold; color: #d32f2f;")
        
        self.in_guia = QLineEdit(self.op.guia_remito or "")
        self.in_guia.setStyleSheet("font-weight: bold; color: #1565c0;")
        
        self.in_dest = QLineEdit(self.op.destinatario); self.in_dom = QLineEdit(self.op.domicilio); self.in_loc = QLineEdit(self.op.localidad); self.in_cel = QLineEdit(self.op.celular or "")
        self.in_peso = QDoubleSpinBox(); self.in_peso.setRange(0, 9999); self.in_peso.setSuffix(" Kg"); self.in_peso.setValue(self.op.peso or 0.0)
        self.in_prov = QComboBox(); clientes_db = self.session.query(ClientePrincipal).all(); lista_prov = [c.nombre for c in clientes_db] if clientes_db else ["JetPaq", "DHL", "Andreani", "MercadoLibre", "Directo", "Otro"]
        self.in_prov.addItems(lista_prov); 
        if self.op.proveedor in lista_prov: self.in_prov.setCurrentText(self.op.proveedor)
        
        self.gb_tipo = QGroupBox("Tipo de Carga"); self.radio_comun = QRadioButton("Común"); self.radio_frio = QRadioButton("Refrigerado"); self.radio_comb = QRadioButton("Combinado"); self.bg_tipo = QButtonGroup(); self.bg_tipo.addButton(self.radio_comun); self.bg_tipo.addButton(self.radio_frio); self.bg_tipo.addButton(self.radio_comb)
        ly_radio = QHBoxLayout(self.gb_tipo); ly_radio.addWidget(self.radio_comun); ly_radio.addWidget(self.radio_frio); ly_radio.addWidget(self.radio_comb)
        self.in_bultos_simple = QSpinBox(); self.in_bultos_simple.setRange(1, 999); self.container_comb = QWidget(); ly_comb = QFormLayout(self.container_comb)
        self.in_c_comun = QSpinBox(); self.in_c_comun.setRange(1, 999); self.in_c_comun.setPrefix("📦 "); self.in_c_frio = QSpinBox(); self.in_c_frio.setRange(1, 999); self.in_c_frio.setPrefix("❄️ "); ly_comb.addRow("Cant. Común:", self.in_c_comun); ly_comb.addRow("Cant. Refrigerado:", self.in_c_frio)
        total = self.op.bultos; frio = self.op.bultos_frio or 0; comun = total - frio
        if frio > 0 and comun > 0: self.radio_comb.setChecked(True); self.in_c_comun.setValue(comun); self.in_c_frio.setValue(frio); self.in_bultos_simple.hide(); self.container_comb.show()
        elif frio > 0: self.radio_frio.setChecked(True); self.in_bultos_simple.setValue(total); self.in_bultos_simple.show(); self.container_comb.hide()
        else: self.radio_comun.setChecked(True); self.in_bultos_simple.setValue(total); self.in_bultos_simple.show(); self.container_comb.hide()
        self.bg_tipo.buttonClicked.connect(self.cambiar_vista_bultos)
        self.in_precio = QDoubleSpinBox(); self.in_precio.setRange(0, 10000000); self.in_precio.setPrefix("$ "); self.in_precio.setValue(self.op.monto_servicio)
        if self.op.estado == Estados.EN_DEPOSITO: self.in_precio.setEnabled(True); self.lbl_aviso = QLabel("🟢 ESTADO INICIAL: Puede modificar el precio (Extra)."); self.lbl_aviso.setStyleSheet("color: green; font-weight: bold;")
        else: self.in_precio.setEnabled(False); self.lbl_aviso = QLabel("🔒 PRECIO BLOQUEADO (Solo editable en estado 'En Deposito')"); self.lbl_aviso.setStyleSheet("color: red; font-size: 10px;")
        
        form.addRow("Fecha Ingreso:", self.in_fecha)
        form.addRow("Guía / Remito:", self.in_guia)
        form.addRow("Destinatario:", self.in_dest); form.addRow("Domicilio:", self.in_dom); form.addRow("Localidad:", self.in_loc); form.addRow("Celular:", self.in_cel); form.addRow("Proveedor:", self.in_prov); form.addRow("Peso Total:", self.in_peso);
        layout.addLayout(form); layout.addWidget(self.gb_tipo); layout.addWidget(self.in_bultos_simple); layout.addWidget(self.container_comb)
        form2 = QFormLayout(); form2.addRow("Precio Servicio:", self.in_precio); layout.addLayout(form2)
        btn_save = QPushButton("GUARDAR CAMBIOS"); btn_save.setStyleSheet("background-color: #0d6efd; color: white; padding: 10px; font-weight: bold;"); btn_save.clicked.connect(self.guardar)
        layout.addWidget(self.lbl_aviso); layout.addWidget(btn_save); self.setLayout(layout)
    def cambiar_vista_bultos(self):
        if self.radio_comb.isChecked(): self.in_bultos_simple.hide(); self.container_comb.show()
        else: self.in_bultos_simple.show(); self.container_comb.hide()
    def guardar(self):
        try:
            self.op.fecha_ingreso = self.in_fecha.date().toPyDate()
            self.op.guia_remito = self.in_guia.text().strip().upper()
            
            self.op.destinatario = self.in_dest.text().strip().upper()
            self.op.domicilio = self.in_dom.text().strip().upper()
            self.op.localidad = self.in_loc.text().strip().upper()
            self.op.celular = self.in_cel.text().strip()
            self.op.proveedor = self.in_prov.currentText().strip().upper()
            self.op.peso = self.in_peso.value()
            if self.radio_comb.isChecked(): c = self.in_c_comun.value(); f = self.in_c_frio.value(); self.op.bultos = c + f; self.op.bultos_frio = f; self.op.tipo_carga = "COMBINADO"
            else: self.op.bultos = self.in_bultos_simple.value(); self.op.bultos_frio = self.op.bultos if self.radio_frio.isChecked() else 0; self.op.tipo_carga = "REFRIGERADO" if self.radio_frio.isChecked() else "COMUN"
            if self.in_precio.isEnabled(): self.op.monto_servicio = self.in_precio.value()
            self.session.commit(); QMessageBox.information(self, "Listo", "Datos actualizados."); self.accept()
        except Exception as e: QMessageBox.critical(self, "Error", f"No se pudo guardar: {e}")

class EditarTarifaDialog(QDialog):
    def __init__(self, tarifa_obj, parent=None):
        super().__init__(parent); self.tarifa = tarifa_obj
        self.setWindowTitle(f"✏️ Editar Tarifa: {tarifa_obj.localidad}")
        self.setGeometry(400, 300, 300, 150)
        layout = QVBoxLayout(self); form = QFormLayout()
        self.in_cc = QDoubleSpinBox(); self.in_cc.setRange(0, 9e6); self.in_cc.setPrefix("$ "); self.in_cc.setValue(tarifa_obj.precio_base_comun)
        self.in_rc = QDoubleSpinBox(); self.in_rc.setRange(0, 9e6); self.in_rc.setPrefix("$ "); self.in_rc.setValue(tarifa_obj.precio_base_refrig)
        form.addRow("Común:", self.in_cc); form.addRow("Refrigerado:", self.in_rc); layout.addLayout(form)
        btn = QPushButton("GUARDAR CAMBIOS"); btn.setStyleSheet("background-color: #0d6efd; color: white; font-weight: bold;")
        btn.clicked.connect(self.accept); layout.addWidget(btn)

class HistorialTarifasDialog(QDialog):
    def __init__(self, session, parent=None):
        super().__init__(parent); self.setWindowTitle("📜 Historial de Cambios de Tarifas")
        self.setGeometry(300, 200, 700, 400); layout = QVBoxLayout(self)
        self.tabla = QTableWidget(); self.tabla.setColumnCount(4)
        self.tabla.setHorizontalHeaderLabels(["Fecha / Hora", "Zona / Afectado", "Detalle del Cambio", "Usuario"])
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.tabla)
        try:
            logs = session.query(HistorialTarifas).order_by(HistorialTarifas.fecha_hora.desc()).all()
            self.tabla.setRowCount(len(logs))
            for i, log in enumerate(logs):
                self.tabla.setItem(i, 0, QTableWidgetItem(log.fecha_hora.strftime("%d/%m/%Y %H:%M")))
                self.tabla.setItem(i, 1, QTableWidgetItem(log.zona))
                self.tabla.setItem(i, 2, QTableWidgetItem(log.detalle))
                self.tabla.setItem(i, 3, QTableWidgetItem(log.usuario))
        except Exception as e: pass

class AgregarCargoDialog(QDialog):
    def __init__(self, proveedores, parent=None):
        super().__init__(parent); self.setWindowTitle("➕ Cargar Alquiler / Cargo Fijo"); self.setGeometry(400, 300, 350, 200)
        layout = QVBoxLayout(self); form = QFormLayout()
        self.in_prov = QComboBox(); self.in_prov.addItems(proveedores)
        self.in_concepto = QLineEdit("Permanencia de carga en depósito")
        self.in_monto = QDoubleSpinBox(); self.in_monto.setRange(0, 10000000); self.in_monto.setPrefix("$ ")
        form.addRow("Proveedor:", self.in_prov); form.addRow("Concepto:", self.in_concepto); form.addRow("Monto ($):", self.in_monto)
        layout.addLayout(form)
        btn = QPushButton("AGREGAR A RENDICIÓN"); btn.setStyleSheet("background-color: #28a745; color: white; font-weight: bold;")
        btn.clicked.connect(self.accept); layout.addWidget(btn)

class CargarPagoDialog(QDialog):
    def __init__(self, proveedor, parent=None):
        super().__init__(parent); self.setWindowTitle(f"💰 Registrar Pago: {proveedor}"); self.setGeometry(400, 300, 350, 200)
        layout = QVBoxLayout(self); form = QFormLayout()
        self.in_monto = QDoubleSpinBox(); self.in_monto.setRange(0.01, 100000000); self.in_monto.setPrefix("$ ")
        self.in_detalle = QLineEdit(); self.in_detalle.setPlaceholderText("Ej: Transferencia Banco Santander...")
        form.addRow("Monto Recibido:", self.in_monto); form.addRow("Detalle / Comprobante:", self.in_detalle)
        layout.addLayout(form)
        btn = QPushButton("REGISTRAR COBRO"); btn.setStyleSheet("background-color: #0d6efd; color: white; font-weight: bold;")
        btn.clicked.connect(self.accept); layout.addWidget(btn)

class CambiarFechaDialog(QDialog):
    def __init__(self, op_guia, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"📅 Mover Fecha: {op_guia}")
        self.setGeometry(400, 300, 350, 200)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.in_fecha = QDateEdit(QDate.currentDate())
        self.in_fecha.setCalendarPopup(True)
        self.in_motivo = QLineEdit()
        self.in_motivo.setPlaceholderText("Ej: Cliente pidió cambio de día")
        form.addRow("Nueva Fecha:", self.in_fecha)
        form.addRow("Motivo / Nota:", self.in_motivo)
        layout.addLayout(form)
        btn = QPushButton("GUARDAR NUEVA FECHA")
        btn.setStyleSheet("background-color: #9c27b0; color: white; font-weight: bold; padding: 10px;")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)
    
    @property
    def fecha_str(self):
        return self.in_fecha.date().toPyDate().strftime("%d/%m/%Y")
    
    @property
    def motivo(self):
        return self.in_motivo.text()

class ResumenDiarioChoferDialog(QDialog):
    def __init__(self, choferes, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📊 Resumen Diario Chofer")
        self.setGeometry(400, 300, 350, 150)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        self.in_chofer = QComboBox()
        self.in_chofer.addItems(choferes)
        
        self.in_fecha = QDateEdit(QDate.currentDate())
        self.in_fecha.setCalendarPopup(True)
        
        form.addRow("Chofer:", self.in_chofer)
        form.addRow("Fecha:", self.in_fecha)
        layout.addLayout(form)
        
        btn = QPushButton("GENERAR RESUMEN (PDF)")
        btn.setStyleSheet("background-color: #0d6efd; color: white; font-weight: bold; padding: 10px;")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)

class EditarUsuarioDialog(QDialog):
    def __init__(self, usuario_obj, parent=None):
        super().__init__(parent)
        self.u = usuario_obj
        self.setWindowTitle(f"✏️ Editar Usuario: {self.u.username}")
        self.setGeometry(400, 300, 350, 350)
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.in_user = QLineEdit(self.u.username)
        self.in_pass = QLineEdit(self.u.password)
        
        self.in_suc = QComboBox()
        self.in_suc.addItems(["Mendoza", "San Juan"])
        self.in_suc.setCurrentText(self.u.sucursal_asignada)

        self.chk_admin = QCheckBox("Es Admin Total"); self.chk_admin.setChecked(bool(self.u.es_admin_total))
        self.chk_rep = QCheckBox("Ver Reportes"); self.chk_rep.setChecked(bool(self.u.ver_reportes))
        self.chk_fac = QCheckBox("Ver Facturación"); self.chk_fac.setChecked(bool(self.u.ver_facturacion))
        self.chk_conf = QCheckBox("Ver Configuración"); self.chk_conf.setChecked(bool(self.u.ver_configuracion))
        self.chk_rend = QCheckBox("Ver Rendición (Paso 3)"); self.chk_rend.setChecked(bool(self.u.ver_rendicion))

        form.addRow("Usuario:", self.in_user)
        form.addRow("Pass:", self.in_pass)
        form.addRow("Sucursal:", self.in_suc)
        form.addRow(self.chk_admin)
        form.addRow("Permisos:", self.chk_rep)
        form.addRow("", self.chk_fac)
        form.addRow("", self.chk_conf)
        form.addRow("", self.chk_rend)

        btn = QPushButton("GUARDAR CAMBIOS")
        btn.setStyleSheet("background-color: #0d6efd; color: white; font-weight: bold; padding: 10px;")
        btn.clicked.connect(self.accept)

        layout.addLayout(form)
        layout.addWidget(btn)

    @property
    def datos(self):
        return {
            "user": self.in_user.text().strip().lower(),
            "pass": self.in_pass.text().strip(),
            "suc": self.in_suc.currentText(),
            "admin": self.chk_admin.isChecked(),
            "rep": self.chk_rep.isChecked(),
            "fac": self.chk_fac.isChecked(),
            "conf": self.chk_conf.isChecked(),
            "rend": self.chk_rend.isChecked()
        }