import os
from datetime import datetime, timedelta

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                             QComboBox, QPushButton, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QMessageBox, QDateEdit, QDialog, QFormLayout, 
                             QSpinBox, QDoubleSpinBox, QAbstractItemView, QTextEdit, QCheckBox)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QColor, QFont
from sqlalchemy import text

from database import Vehiculo, Mantenimiento, Chofer

ESTILO_TABLAS_BLANCAS = """
QTableWidget { background-color: #ffffff !important; gridline-color: #d0d0d0 !important; }
QTableWidget::item { background-color: transparent !important; color: #000000 !important; border-bottom: 1px solid #e0e0e0 !important; }
QTableWidget::item:selected { background-color: #bbdefb !important; color: #000000 !important; }
"""

class TabFlota(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main = main_window
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        top_bar = QHBoxLayout()
        self.filtro_sucursal = QComboBox()
        self.filtro_sucursal.addItems(["Todas", "Mendoza", "San Juan"])
        if not getattr(self.main.usuario, 'es_admin_total', False):
            self.filtro_sucursal.setCurrentText(self.main.sucursal_actual)
            self.filtro_sucursal.setEnabled(False)
        self.filtro_sucursal.currentTextChanged.connect(self.cargar_vehiculos)

        self.filtro_chofer = QComboBox()
        self.filtro_chofer.setMinimumWidth(250) # 🔥 ANCHO AMPLIADO 🔥
        self.filtro_chofer.addItem("Todos")
        self.filtro_chofer.currentTextChanged.connect(self.cargar_vehiculos)
        
        btn_nuevo = QPushButton("➕ Nuevo Vehículo")
        btn_nuevo.setStyleSheet("background-color: #28a745; color: white; font-weight: bold;")
        btn_nuevo.clicked.connect(self.nuevo_vehiculo)
        
        btn_editar = QPushButton("✏️ Editar Vehículo")
        btn_editar.clicked.connect(self.editar_vehiculo)
        
        btn_mantenimiento = QPushButton("🔧 Registrar Service")
        btn_mantenimiento.setStyleSheet("background-color: #17a2b8; color: white; font-weight: bold;")
        btn_mantenimiento.clicked.connect(self.registrar_mantenimiento)
        
        btn_pdf = QPushButton("📄 Imprimir Reporte")
        btn_pdf.setStyleSheet("background-color: #6f42c1; color: white; font-weight: bold;")
        btn_pdf.clicked.connect(self.generar_pdf_flota)
        
        btn_historial = QPushButton("📜 Ver Historial")
        btn_historial.clicked.connect(self.ver_historial)
        
        btn_eliminar = QPushButton("🗑️ Eliminar")
        btn_eliminar.setStyleSheet("background-color: #dc3545; color: white; font-weight: bold;")
        btn_eliminar.clicked.connect(self.eliminar_vehiculo)

        top_bar.addWidget(QLabel("Sucursal:"))
        top_bar.addWidget(self.filtro_sucursal)
        top_bar.addWidget(QLabel("Chofer:"))
        top_bar.addWidget(self.filtro_chofer)
        top_bar.addStretch()
        top_bar.addWidget(btn_nuevo)
        top_bar.addWidget(btn_editar)
        top_bar.addWidget(btn_mantenimiento)
        top_bar.addWidget(btn_pdf)
        top_bar.addWidget(btn_historial)
        top_bar.addWidget(btn_eliminar)

        layout.addLayout(top_bar)

        legend_layout = QHBoxLayout()
        lbl_ok = QLabel("🟢 OK")
        lbl_ok.setStyleSheet("background-color: #d4edda; padding: 5px; border-radius: 3px;")
        lbl_warn = QLabel("🟡 PRÓX. A VENCER (< 15 días / < 1000 km)")
        lbl_warn.setStyleSheet("background-color: #fff3cd; padding: 5px; border-radius: 3px;")
        lbl_danger = QLabel("🔴 VENCIDO / REQUIERE SERVICE")
        lbl_danger.setStyleSheet("background-color: #f8d7da; padding: 5px; border-radius: 3px;")
        
        legend_layout.addWidget(lbl_ok)
        legend_layout.addWidget(lbl_warn)
        legend_layout.addWidget(lbl_danger)
        legend_layout.addStretch()
        layout.addLayout(legend_layout)

        self.tabla = QTableWidget()
        self.tabla.setColumnCount(11) # Agregada columna GNC
        self.tabla.setHorizontalHeaderLabels([
            "ID", "Sucursal", "Chofer", "Patente", "Marca/Modelo", 
            "KM Actual", "Próx. Service", "Venc. Seguro", "Venc. RTO", "Venc. GNC", "Estado"
        ])
        self.tabla.hideColumn(0)
        self.tabla.setStyleSheet(ESTILO_TABLAS_BLANCAS)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        
        header = self.tabla.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tabla.setColumnWidth(1, 90)
        self.tabla.setColumnWidth(2, 220) # 🔥 ANCHO COLUMNA CHOFER AMPLIADO 🔥
        self.tabla.setColumnWidth(3, 90)
        self.tabla.setColumnWidth(4, 180)
        self.tabla.setColumnWidth(5, 90)
        self.tabla.setColumnWidth(6, 90)
        self.tabla.setColumnWidth(7, 90)
        self.tabla.setColumnWidth(8, 90)
        self.tabla.setColumnWidth(9, 90)
        header.setStretchLastSection(True)

        layout.addWidget(self.tabla)
        self.actualizar_choferes_filtro()
        self.cargar_vehiculos()

    def generar_pdf_flota(self):
        try:
            from reportlab.lib.pagesizes import landscape, A4
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib import colors
            from reportlab.lib.styles import getSampleStyleSheet
            
            descargas_dir = os.path.join(os.path.expanduser('~'), 'Downloads')
            if not os.path.exists(descargas_dir): os.makedirs(descargas_dir, exist_ok=True)
            ruta_pdf = os.path.join(descargas_dir, f"Reporte_Flota_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf")
            
            doc = SimpleDocTemplate(ruta_pdf, pagesize=landscape(A4))
            elements = []
            styles = getSampleStyleSheet()
            elements.append(Paragraph("Reporte de Flota y Mantenimiento", styles['Title']))
            elements.append(Spacer(1, 12))
            
            data = [["Patente", "Marca/Modelo", "Chofer", "KM Actual", "Seguro", "RTO", "Oblea GNC", "Estado General"]]
            for r in range(self.tabla.rowCount()):
                data.append([
                    self.tabla.item(r, 3).text(),
                    self.tabla.item(r, 4).text(),
                    self.tabla.item(r, 2).text(),
                    self.tabla.item(r, 5).text(),
                    self.tabla.item(r, 7).text(),
                    self.tabla.item(r, 8).text(),
                    self.tabla.item(r, 9).text(),
                    self.tabla.item(r, 10).text()
                ])
                
            t = Table(data)
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1565c0")),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0,0), (-1,0), 10),
                ('BACKGROUND', (0,1), (-1,-1), colors.white),
                ('GRID', (0,0), (-1,-1), 1, colors.black),
                ('FONTSIZE', (0,1), (-1,-1), 9)
            ]))
            elements.append(t)
            doc.build(elements)
            os.startfile(ruta_pdf)
        except Exception as e:
            QMessageBox.critical(self, "Error PDF", f"Error al generar PDF: {e}")

    def actualizar_choferes_filtro(self):
        self.filtro_chofer.blockSignals(True)
        self.filtro_chofer.clear()
        self.filtro_chofer.addItem("Todos")
        try:
            query = self.main.session.query(Chofer.nombre)
            if self.filtro_sucursal.currentText() != "Todas":
                query = query.filter(Chofer.sucursal == self.filtro_sucursal.currentText())
            chs = query.all()
            for c in chs:
                self.filtro_chofer.addItem(c[0])
        except:
            pass
        self.filtro_chofer.blockSignals(False)

    def cargar_vehiculos(self):
        try:
            self.actualizar_choferes_filtro()
            self.tabla.setRowCount(0)
            
            query = self.main.session.query(Vehiculo)
            if self.filtro_sucursal.currentText() != "Todas":
                query = query.filter(Vehiculo.sucursal == self.filtro_sucursal.currentText())
            
            vehiculos = query.all()
            hoy = datetime.today().date()
            margen_dias = timedelta(days=15)
            
            row = 0
            for v in vehiculos:
                nombre_chofer = v.chofer.nombre if v.chofer else "SIN ASIGNAR"
                if self.filtro_chofer.currentText() != "Todos" and nombre_chofer != self.filtro_chofer.currentText():
                    continue
                    
                self.tabla.insertRow(row)
                self.tabla.setItem(row, 0, QTableWidgetItem(str(v.id)))
                self.tabla.setItem(row, 1, QTableWidgetItem(v.sucursal))
                self.tabla.setItem(row, 2, QTableWidgetItem(nombre_chofer))
                
                item_patente = QTableWidgetItem(v.patente)
                font_p = QFont(); font_p.setBold(True)
                item_patente.setFont(font_p)
                self.tabla.setItem(row, 3, item_patente)
                self.tabla.setItem(row, 4, QTableWidgetItem(f"{v.marca} {v.modelo} ({v.año})"))
                self.tabla.setItem(row, 5, QTableWidgetItem(f"{v.kilometraje_actual:,} km"))
                
                color_fila = QColor("#ffffff")
                motivo_alerta = []

                km_prox = v.km_proximo_service or 0
                item_service = QTableWidgetItem(f"{km_prox:,} km")
                if km_prox > 0:
                    if v.kilometraje_actual >= km_prox:
                        color_fila = QColor("#f8d7da")
                        motivo_alerta.append("SERVICE VENCIDO")
                    elif (km_prox - v.kilometraje_actual) <= 1000:
                        if color_fila != QColor("#f8d7da"): color_fila = QColor("#fff3cd")
                self.tabla.setItem(row, 6, item_service)

                venc_seg = v.vencimiento_seguro.strftime("%d/%m/%Y") if v.vencimiento_seguro else "No cargado"
                item_seguro = QTableWidgetItem(venc_seg)
                if v.vencimiento_seguro:
                    if v.vencimiento_seguro <= hoy:
                        color_fila = QColor("#f8d7da")
                        motivo_alerta.append("SEGURO VENCIDO")
                    elif v.vencimiento_seguro <= hoy + margen_dias:
                        if color_fila != QColor("#f8d7da"): color_fila = QColor("#fff3cd")
                self.tabla.setItem(row, 7, item_seguro)

                venc_rto = v.vencimiento_rto.strftime("%d/%m/%Y") if v.vencimiento_rto else "No cargado"
                item_rto = QTableWidgetItem(venc_rto)
                if v.vencimiento_rto:
                    if v.vencimiento_rto <= hoy:
                        color_fila = QColor("#f8d7da")
                        motivo_alerta.append("RTO VENCIDA")
                    elif v.vencimiento_rto <= hoy + margen_dias:
                        if color_fila != QColor("#f8d7da"): color_fila = QColor("#fff3cd")
                self.tabla.setItem(row, 8, item_rto)

                # ALERTA DE OBLEA GNC
                venc_gnc = v.vencimiento_oblea_gnc.strftime("%d/%m/%Y") if v.vencimiento_oblea_gnc else "N/A"
                item_gnc = QTableWidgetItem(venc_gnc)
                if v.vencimiento_oblea_gnc:
                    if v.vencimiento_oblea_gnc <= hoy:
                        color_fila = QColor("#f8d7da")
                        motivo_alerta.append("GNC VENCIDO")
                    elif v.vencimiento_oblea_gnc <= hoy + margen_dias:
                        if color_fila != QColor("#f8d7da"): color_fila = QColor("#fff3cd")
                self.tabla.setItem(row, 9, item_gnc)

                txt_estado = "ACTIVO"
                if v.estado != "ACTIVO":
                    txt_estado = v.estado
                    color_fila = QColor("#e2e3e5")
                elif color_fila == QColor("#ffffff"):
                    color_fila = QColor("#d4edda")
                    
                if motivo_alerta:
                    txt_estado += f" ({', '.join(motivo_alerta)})"
                
                self.tabla.setItem(row, 10, QTableWidgetItem(txt_estado))

                for col in range(11):
                    item = self.tabla.item(row, col)
                    if item:
                        item.setBackground(color_fila)
                        if color_fila == QColor("#f8d7da"):
                            item.setForeground(QColor("#721c24"))
                row += 1

        except Exception as e:
            self.main.session.rollback()
            QMessageBox.critical(self, "Error", f"Error al cargar vehículos: {str(e)}")

    def obtener_id_seleccionado(self):
        r = self.tabla.currentRow()
        if r < 0:
            QMessageBox.warning(self, "Atención", "Seleccione un vehículo de la lista.")
            return None
        return int(self.tabla.item(r, 0).text())

    def nuevo_vehiculo(self):
        dlg = DialogoVehiculo(self.main.session, self.main.sucursal_actual, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.cargar_vehiculos()

    def editar_vehiculo(self):
        v_id = self.obtener_id_seleccionado()
        if not v_id: return
        vehiculo = self.main.session.query(Vehiculo).get(v_id)
        if vehiculo:
            dlg = DialogoVehiculo(self.main.session, self.main.sucursal_actual, vehiculo, parent=self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                self.cargar_vehiculos()

    def registrar_mantenimiento(self):
        v_id = self.obtener_id_seleccionado()
        if not v_id: return
        vehiculo = self.main.session.query(Vehiculo).get(v_id)
        if vehiculo:
            dlg = DialogoMantenimiento(self.main.session, vehiculo, parent=self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                self.cargar_vehiculos()

    def ver_historial(self):
        v_id = self.obtener_id_seleccionado()
        if not v_id: return
        vehiculo = self.main.session.query(Vehiculo).get(v_id)
        if vehiculo:
            dlg = DialogoHistorialMantenimiento(self.main.session, vehiculo, parent=self)
            dlg.exec()

    def eliminar_vehiculo(self):
        v_id = self.obtener_id_seleccionado()
        if not v_id: return
        vehiculo = self.main.session.query(Vehiculo).get(v_id)
        reply = QMessageBox.question(self, "Confirmar Eliminación", f"¿Seguro que desea eliminar permanentemente el vehículo {vehiculo.patente}?\nEsto también borrará su historial de mantenimiento.", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.main.session.delete(vehiculo)
                self.main.session.commit()
                self.cargar_vehiculos()
            except Exception as e:
                self.main.session.rollback()
                QMessageBox.critical(self, "Error", f"No se pudo eliminar: {str(e)}")

class DialogoVehiculo(QDialog):
    def __init__(self, session, sucursal_defecto, vehiculo=None, parent=None):
        super().__init__(parent)
        self.session = session
        self.vehiculo = vehiculo
        self.setWindowTitle("Editar Vehículo" if vehiculo else "Nuevo Vehículo")
        self.setMinimumWidth(450)
        self.setup_ui(sucursal_defecto)
        if vehiculo:
            self.cargar_datos()

    def setup_ui(self, sucursal_defecto):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.in_sucursal = QComboBox()
        self.in_sucursal.addItems(["Mendoza", "San Juan"])
        self.in_sucursal.setCurrentText(sucursal_defecto)
        self.in_sucursal.currentTextChanged.connect(self.actualizar_choferes)

        self.in_chofer = QComboBox()
        self.in_chofer.setMinimumWidth(250) # 🔥 ANCHO AMPLIADO 🔥
        self.actualizar_choferes()

        self.in_patente = QLineEdit()
        self.in_marca = QLineEdit()
        self.in_modelo = QLineEdit()
        
        self.in_anio = QSpinBox()
        self.in_anio.setRange(1980, datetime.now().year + 1)
        self.in_anio.setValue(datetime.now().year)
        
        self.in_km_actual = QSpinBox()
        self.in_km_actual.setRange(0, 2000000)
        self.in_km_actual.setSingleStep(1000)

        self.in_km_prox_service = QSpinBox()
        self.in_km_prox_service.setRange(0, 2000000)
        self.in_km_prox_service.setSingleStep(1000)

        self.in_seguro = QDateEdit(QDate.currentDate())
        self.in_seguro.setCalendarPopup(True)
        
        self.in_rto = QDateEdit(QDate.currentDate())
        self.in_rto.setCalendarPopup(True)
        
        # 🔥 CAMPO GNC 🔥
        self.check_gnc = QCheckBox("Vehículo con equipo de GNC")
        self.in_gnc = QDateEdit(QDate.currentDate())
        self.in_gnc.setCalendarPopup(True)
        self.in_gnc.setEnabled(False)
        self.check_gnc.toggled.connect(self.in_gnc.setEnabled)
        
        self.in_estado = QComboBox()
        self.in_estado.addItems(["ACTIVO", "EN TALLER", "BAJA"])

        form.addRow("Sucursal:", self.in_sucursal)
        form.addRow("Chofer Asignado:", self.in_chofer)
        form.addRow("Patente:", self.in_patente)
        form.addRow("Marca:", self.in_marca)
        form.addRow("Modelo:", self.in_modelo)
        form.addRow("Año:", self.in_anio)
        form.addRow("Kilometraje Actual:", self.in_km_actual)
        form.addRow("Próximo Service (Aceite) a los KM:", self.in_km_prox_service)
        form.addRow("Vencimiento Seguro:", self.in_seguro)
        form.addRow("Vencimiento RTO:", self.in_rto)
        form.addRow(self.check_gnc, self.in_gnc)
        form.addRow("Estado:", self.in_estado)

        btn_guardar = QPushButton("💾 Guardar Vehículo")
        btn_guardar.setStyleSheet("background-color: #0d6efd; color: white; font-weight: bold; padding: 10px;")
        btn_guardar.clicked.connect(self.guardar)

        layout.addLayout(form)
        layout.addWidget(btn_guardar)

    def actualizar_choferes(self):
        sucursal = self.in_sucursal.currentText()
        self.in_chofer.clear()
        self.in_chofer.addItem("--- Sin Asignar ---", None)
        choferes = self.session.query(Chofer).filter(Chofer.sucursal == sucursal).all()
        for c in choferes:
            self.in_chofer.addItem(c.nombre, c.id)

    def cargar_datos(self):
        self.in_sucursal.setCurrentText(self.vehiculo.sucursal)
        self.actualizar_choferes()
        if self.vehiculo.chofer_id:
            idx = self.in_chofer.findData(self.vehiculo.chofer_id)
            if idx >= 0: self.in_chofer.setCurrentIndex(idx)
        self.in_patente.setText(self.vehiculo.patente)
        self.in_marca.setText(self.vehiculo.marca)
        self.in_modelo.setText(self.vehiculo.modelo)
        self.in_anio.setValue(self.vehiculo.año or datetime.now().year)
        self.in_km_actual.setValue(self.vehiculo.kilometraje_actual or 0)
        self.in_km_prox_service.setValue(self.vehiculo.km_proximo_service or 0)
        if self.vehiculo.vencimiento_seguro: self.in_seguro.setDate(self.vehiculo.vencimiento_seguro)
        if self.vehiculo.vencimiento_rto: self.in_rto.setDate(self.vehiculo.vencimiento_rto)
        
        # Cargar GNC
        if self.vehiculo.vencimiento_oblea_gnc:
            self.check_gnc.setChecked(True)
            self.in_gnc.setDate(self.vehiculo.vencimiento_oblea_gnc)
            
        self.in_estado.setCurrentText(self.vehiculo.estado)

    def guardar(self):
        patente = self.in_patente.text().strip().upper()
        if not patente:
            QMessageBox.warning(self, "Error", "La patente es obligatoria.")
            return
        try:
            if not self.vehiculo:
                v_existente = self.session.query(Vehiculo).filter(Vehiculo.patente == patente).first()
                if v_existente:
                    QMessageBox.warning(self, "Error", "Ya existe un vehículo con esa patente.")
                    return
                self.vehiculo = Vehiculo()
                self.session.add(self.vehiculo)
                
            self.vehiculo.patente = patente
            self.vehiculo.sucursal = self.in_sucursal.currentText()
            self.vehiculo.chofer_id = self.in_chofer.currentData()
            self.vehiculo.marca = self.in_marca.text().strip().upper()
            self.vehiculo.modelo = self.in_modelo.text().strip().upper()
            self.vehiculo.año = self.in_anio.value()
            self.vehiculo.kilometraje_actual = self.in_km_actual.value()
            self.vehiculo.km_proximo_service = self.in_km_prox_service.value()
            self.vehiculo.vencimiento_seguro = self.in_seguro.date().toPyDate()
            self.vehiculo.vencimiento_rto = self.in_rto.date().toPyDate()
            
            # Guardar GNC
            if self.check_gnc.isChecked():
                self.vehiculo.vencimiento_oblea_gnc = self.in_gnc.date().toPyDate()
            else:
                self.vehiculo.vencimiento_oblea_gnc = None
                
            self.vehiculo.estado = self.in_estado.currentText()

            self.session.commit()
            self.accept()
        except Exception as e:
            self.session.rollback()
            QMessageBox.critical(self, "Error", f"No se pudo guardar: {str(e)}")

class DialogoMantenimiento(QDialog):
    def __init__(self, session, vehiculo, parent=None):
        super().__init__(parent)
        self.session = session
        self.vehiculo = vehiculo
        self.setWindowTitle(f"Registrar Mantenimiento - {vehiculo.patente}")
        self.setMinimumWidth(400)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.in_fecha = QDateEdit(QDate.currentDate())
        self.in_fecha.setCalendarPopup(True)
        
        self.in_tipo = QComboBox()
        self.in_tipo.addItems([
            "Cambio de Aceite / Filtros",
            "Cambio de Distribución",
            "Embrague y Caja de Cambios",
            "Tren Delantero / Trasero / Suspensión",
            "Renovación RTO",
            "Renovación Oblea GNC",
            "Frenos",
            "Neumáticos (Cambio / Alineación / Balanceo)",
            "Reparación Mecánica General",
            "Limpieza y Estética",
            "Otro Gastos"
        ])
        
        self.in_km = QSpinBox()
        self.in_km.setRange(0, 2000000)
        self.in_km.setValue(self.vehiculo.kilometraje_actual or 0)

        self.in_costo = QDoubleSpinBox()
        self.in_costo.setRange(0, 100000000)
        self.in_costo.setPrefix("$ ")
        self.in_costo.setGroupSeparator(",")

        self.in_taller = QLineEdit()
        self.in_detalle = QTextEdit()
        self.in_detalle.setMaximumHeight(80)

        self.check_actualizar_rto = QPushButton("🔄 Actualizar RTO a un año desde hoy")
        self.check_actualizar_rto.setCheckable(True)
        self.check_actualizar_gnc = QPushButton("🔄 Actualizar Oblea GNC a un año desde hoy")
        self.check_actualizar_gnc.setCheckable(True)
        self.check_actualizar_service = QPushButton("🔄 Sumar 10.000km para próximo Service")
        self.check_actualizar_service.setCheckable(True)

        form.addRow("Fecha:", self.in_fecha)
        form.addRow("Tipo de Servicio:", self.in_tipo)
        form.addRow("Kilometraje Realizado:", self.in_km)
        form.addRow("Costo:", self.in_costo)
        form.addRow("Taller / Proveedor:", self.in_taller)
        form.addRow("Detalle Repuestos:", self.in_detalle)

        layout.addLayout(form)
        layout.addWidget(QLabel("<b>Acciones Automáticas:</b>"))
        layout.addWidget(self.check_actualizar_rto)
        layout.addWidget(self.check_actualizar_gnc)
        layout.addWidget(self.check_actualizar_service)

        btn_guardar = QPushButton("🔧 Guardar Historial")
        btn_guardar.setStyleSheet("background-color: #0d6efd; color: white; font-weight: bold; padding: 10px;")
        btn_guardar.clicked.connect(self.guardar)
        layout.addWidget(btn_guardar)

        self.in_tipo.currentTextChanged.connect(self.sugerir_acciones)
        self.sugerir_acciones(self.in_tipo.currentText())

    def sugerir_acciones(self, texto):
        self.check_actualizar_rto.setChecked("RTO" in texto)
        self.check_actualizar_gnc.setChecked("GNC" in texto)
        self.check_actualizar_service.setChecked("Aceite" in texto)

    def guardar(self):
        try:
            m = Mantenimiento(
                vehiculo_id=self.vehiculo.id,
                fecha=self.in_fecha.date().toPyDate(),
                tipo_servicio=self.in_tipo.currentText(),
                kilometraje=self.in_km.value(),
                costo=self.in_costo.value(),
                taller_proveedor=self.in_taller.text().strip(),
                detalle=self.in_detalle.toPlainText().strip()
            )
            self.session.add(m)

            if self.in_km.value() > self.vehiculo.kilometraje_actual:
                self.vehiculo.kilometraje_actual = self.in_km.value()

            if self.check_actualizar_rto.isChecked():
                self.vehiculo.vencimiento_rto = (datetime.now() + timedelta(days=365)).date()
                
            if self.check_actualizar_gnc.isChecked():
                self.vehiculo.vencimiento_oblea_gnc = (datetime.now() + timedelta(days=365)).date()
                
            if self.check_actualizar_service.isChecked():
                self.vehiculo.km_proximo_service = self.in_km.value() + 10000

            self.session.commit()
            self.accept()
        except Exception as e:
            self.session.rollback()
            QMessageBox.critical(self, "Error", f"No se pudo guardar: {str(e)}")

class DialogoHistorialMantenimiento(QDialog):
    def __init__(self, session, vehiculo, parent=None):
        super().__init__(parent)
        self.session = session
        self.vehiculo = vehiculo
        self.setWindowTitle(f"Historial Mecánico - {vehiculo.patente}")
        self.setMinimumSize(700, 400)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        self.tabla = QTableWidget()
        self.tabla.setColumnCount(6)
        self.tabla.setHorizontalHeaderLabels(["Fecha", "Tipo", "KM", "Costo", "Taller", "Detalle"])
        self.tabla.setStyleSheet(ESTILO_TABLAS_BLANCAS)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        
        header = self.tabla.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tabla.setColumnWidth(0, 90)
        self.tabla.setColumnWidth(1, 150)
        self.tabla.setColumnWidth(2, 80)
        self.tabla.setColumnWidth(3, 90)
        self.tabla.setColumnWidth(4, 120)
        header.setStretchLastSection(True)

        layout.addWidget(self.tabla)
        self.cargar_datos()

    def cargar_datos(self):
        try:
            mantenimientos = self.session.query(Mantenimiento).filter(
                Mantenimiento.vehiculo_id == self.vehiculo.id
            ).order_by(Mantenimiento.fecha.desc()).all()
            
            self.tabla.setRowCount(len(mantenimientos))
            for i, m in enumerate(mantenimientos):
                self.tabla.setItem(i, 0, QTableWidgetItem(m.fecha.strftime("%d/%m/%Y") if m.fecha else ""))
                self.tabla.setItem(i, 1, QTableWidgetItem(m.tipo_servicio))
                self.tabla.setItem(i, 2, QTableWidgetItem(f"{m.kilometraje:,}"))
                self.tabla.setItem(i, 3, QTableWidgetItem(f"$ {m.costo:,.2f}"))
                self.tabla.setItem(i, 4, QTableWidgetItem(m.taller_proveedor))
                self.tabla.setItem(i, 5, QTableWidgetItem(m.detalle))
        except: pass