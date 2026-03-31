import os
from datetime import datetime, timedelta

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                             QComboBox, QPushButton, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QMessageBox, QDateEdit, QDialog, QFormLayout, 
                             QSpinBox, QDoubleSpinBox, QAbstractItemView, QTextEdit, QCheckBox, 
                             QStyledItemDelegate, QGroupBox, QProgressBar, QSplitter)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QColor, QFont, QBrush
from sqlalchemy import text

from database import Vehiculo, Mantenimiento, Chofer

class PintorCeldasDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        bg_color = index.data(Qt.ItemDataRole.BackgroundRole)
        if bg_color:
            painter.fillRect(option.rect, bg_color)
        super().paint(painter, option, index)

ESTILO_TABLAS_BLANCAS = """
QTableWidget { background-color: #ffffff !important; gridline-color: #d0d0d0 !important; }
QTableWidget::item { background-color: transparent !important; color: #000000 !important; border-bottom: 1px solid #e0e0e0 !important; padding: 5px; }
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
        self.filtro_sucursal.setMinimumWidth(200)
        if not getattr(self.main.usuario, 'es_admin_total', False):
            self.filtro_sucursal.setCurrentText(self.main.sucursal_actual)
            self.filtro_sucursal.setEnabled(False)
        self.filtro_sucursal.currentTextChanged.connect(self.cargar_vehiculos)

        self.filtro_chofer = QComboBox()
        self.filtro_chofer.setMinimumWidth(200) 
        self.filtro_chofer.addItem("Todos")
        self.filtro_chofer.currentTextChanged.connect(self.cargar_vehiculos)
        
        btn_nuevo = QPushButton("➕ Nuevo Vehículo")
        btn_nuevo.setStyleSheet("background-color: #28a745; color: white; font-weight: bold; padding: 8px;")
        btn_nuevo.clicked.connect(self.nuevo_vehiculo)
        
        btn_editar = QPushButton("✏️ Editar Vehículo")
        btn_editar.setStyleSheet("padding: 8px;")
        btn_editar.clicked.connect(self.editar_vehiculo)
        
        btn_mantenimiento = QPushButton("🔧 Registrar Service")
        btn_mantenimiento.setStyleSheet("background-color: #17a2b8; color: white; font-weight: bold; padding: 8px;")
        btn_mantenimiento.clicked.connect(self.registrar_mantenimiento)
        
        btn_historial = QPushButton("📜 Historial Gral")
        btn_historial.setStyleSheet("padding: 8px;")
        btn_historial.clicked.connect(self.ver_historial)
        
        btn_eliminar = QPushButton("🗑️ Eliminar")
        btn_eliminar.setStyleSheet("background-color: #dc3545; color: white; font-weight: bold; padding: 8px;")
        btn_eliminar.clicked.connect(self.eliminar_vehiculo)

        top_bar.addWidget(QLabel("Sucursal:"))
        top_bar.addWidget(self.filtro_sucursal)
        top_bar.addWidget(QLabel("Chofer:"))
        top_bar.addWidget(self.filtro_chofer)
        top_bar.addStretch()
        top_bar.addWidget(btn_nuevo)
        top_bar.addWidget(btn_editar)
        top_bar.addWidget(btn_mantenimiento)
        top_bar.addWidget(btn_historial)
        top_bar.addWidget(btn_eliminar)

        layout.addLayout(top_bar)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # --- TABLA IZQUIERDA (Resumen) ---
        self.tabla = QTableWidget()
        self.tabla.setColumnCount(5)
        self.tabla.setHorizontalHeaderLabels(["ID", "Patente", "Chofer", "KM Actual", "Estado / Alertas"])
        self.tabla.hideColumn(0)
        self.tabla.setStyleSheet(ESTILO_TABLAS_BLANCAS)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.pintor = PintorCeldasDelegate(self.tabla)
        self.tabla.setItemDelegate(self.pintor)
        
        header = self.tabla.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tabla.setColumnWidth(1, 90)
        self.tabla.setColumnWidth(2, 150) 
        self.tabla.setColumnWidth(3, 90)
        header.setStretchLastSection(True)
        
        self.tabla.itemSelectionChanged.connect(self.mostrar_radiografia)

        # --- PANEL DERECHO (Radiografía) ---
        self.panel_radiografia = QGroupBox("Radiografía del Vehículo")
        self.panel_radiografia.setStyleSheet("""
            QGroupBox { font-weight: bold; border: 2px solid #1565c0; border-radius: 8px; margin-top: 10px; padding: 10px; background-color: #f8f9fa;}
            QGroupBox::title { subcontrol-origin: margin; left: 15px; color: #1565c0; }
        """)
        
        lay_rad = QVBoxLayout(self.panel_radiografia)
        
        self.lbl_vehiculo_tit = QLabel("Seleccione un vehículo en la tabla.")
        self.lbl_vehiculo_tit.setStyleSheet("font-size: 18px; font-weight: bold; color: #333; margin-bottom: 10px;")
        lay_rad.addWidget(self.lbl_vehiculo_tit)
        
        self.panel_falla = QWidget()
        lay_falla = QVBoxLayout(self.panel_falla)
        self.lbl_falla_txt = QLabel("Sin fallas reportadas.")
        self.lbl_falla_txt.setWordWrap(True)
        self.lbl_falla_txt.setStyleSheet("font-weight: bold; color: #721c24; font-size: 14px;")
        self.btn_limpiar_falla = QPushButton("✅ Marcar falla como Resuelta")
        self.btn_limpiar_falla.setStyleSheet("background-color: #28a745; color: white; font-weight: bold;")
        self.btn_limpiar_falla.clicked.connect(self.limpiar_falla_chofer)
        lay_falla.addWidget(self.lbl_falla_txt)
        lay_falla.addWidget(self.btn_limpiar_falla)
        self.panel_falla.setStyleSheet("background-color: #f8d7da; border: 2px solid #f5c6cb; border-radius: 8px; padding: 5px;")
        self.panel_falla.hide()
        lay_rad.addWidget(self.panel_falla)
        
        gb_mec = QGroupBox("Desgaste Mecánico (Progreso)")
        lay_mec = QFormLayout(gb_mec)
        
        self.pb_aceite = QProgressBar()
        self.pb_distri = QProgressBar()
        self.pb_neumaticos = QProgressBar()
        
        estilo_pb = """
            QProgressBar { border: 1px solid #bbb; border-radius: 5px; text-align: center; font-weight: bold; background-color: #e9ecef; }
            QProgressBar::chunk { background-color: #17a2b8; width: 1px; }
        """
        self.pb_aceite.setStyleSheet(estilo_pb); self.pb_distri.setStyleSheet(estilo_pb); self.pb_neumaticos.setStyleSheet(estilo_pb)
        
        lay_mec.addRow("Aceite (10k):", self.pb_aceite)
        lay_mec.addRow("Distribución (60k):", self.pb_distri)
        lay_mec.addRow("Neumáticos (40k):", self.pb_neumaticos)
        lay_rad.addWidget(gb_mec)
        
        gb_leg = QGroupBox("Vencimientos Legales")
        lay_leg = QFormLayout(gb_leg)
        self.lbl_seguro = QLabel("-")
        self.lbl_rto = QLabel("-")
        self.lbl_gnc = QLabel("-")
        self.lbl_matafuegos = QLabel("-")
        self.lbl_carnet = QLabel("-")
        
        lay_leg.addRow("🛡️ Seguro:", self.lbl_seguro)
        lay_leg.addRow("📋 RTO:", self.lbl_rto)
        lay_leg.addRow("🔥 Matafuegos:", self.lbl_matafuegos)
        lay_leg.addRow("🪪 Carnet Chofer:", self.lbl_carnet)
        lay_leg.addRow("⛽ Oblea GNC:", self.lbl_gnc)
        lay_rad.addWidget(gb_leg)
        
        lay_rad.addStretch()
        
        self.splitter.addWidget(self.tabla)
        self.splitter.addWidget(self.panel_radiografia)
        self.splitter.setSizes([500, 400]) 
        
        layout.addWidget(self.splitter)
        
        self.actualizar_choferes_filtro()
        self.cargar_vehiculos()

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
                
                item_patente = QTableWidgetItem(v.patente)
                font_p = QFont(); font_p.setBold(True)
                item_patente.setFont(font_p)
                self.tabla.setItem(row, 1, item_patente)
                
                self.tabla.setItem(row, 2, QTableWidgetItem(nombre_chofer))
                self.tabla.setItem(row, 3, QTableWidgetItem(f"{v.kilometraje_actual:,} km"))
                
                color_fila = QColor("#ffffff")
                alertas = []

                if v.km_proximo_service and v.kilometraje_actual >= v.km_proximo_service: alertas.append("ACEITE")
                if v.km_proximo_distribucion and v.kilometraje_actual >= v.km_proximo_distribucion: alertas.append("DISTRIBUCIÓN")
                if v.km_proximo_neumaticos and v.kilometraje_actual >= v.km_proximo_neumaticos: alertas.append("NEUMÁTICOS")
                
                if v.vencimiento_seguro and v.vencimiento_seguro <= hoy: alertas.append("SEGURO")
                if v.vencimiento_rto and v.vencimiento_rto <= hoy: alertas.append("RTO")
                if v.vencimiento_matafuegos and v.vencimiento_matafuegos <= hoy: alertas.append("MATAFUEGOS")
                if v.vencimiento_carnet and v.vencimiento_carnet <= hoy: alertas.append("CARNET")
                if v.vencimiento_oblea_gnc and v.vencimiento_oblea_gnc <= hoy: alertas.append("GNC")
                
                txt_estado = "🟢 AL DÍA"
                
                if v.falla_reportada:
                    txt_estado = "🔧 FALLA APP"
                    color_fila = QColor("#f8d7da")
                elif alertas:
                    txt_estado = f"🔴 VENCE: {', '.join(alertas)}"
                    color_fila = QColor("#f8d7da")
                else:
                    color_fila = QColor("#d4edda")

                self.tabla.setItem(row, 4, QTableWidgetItem(txt_estado))

                brush_bg = QBrush(color_fila)
                for col in range(5):
                    item = self.tabla.item(row, col)
                    if item:
                        item.setBackground(brush_bg)
                        if color_fila == QColor("#f8d7da"):
                            item.setForeground(QBrush(QColor("#721c24")))
                row += 1

        except Exception as e:
            self.main.session.rollback()
            QMessageBox.critical(self, "Error", f"Error al cargar vehículos: {str(e)}")

    def mostrar_radiografia(self):
        r = self.tabla.currentRow()
        if r < 0: return
        
        v_id = int(self.tabla.item(r, 0).text())
        v = self.main.session.query(Vehiculo).get(v_id)
        if not v: return
        
        # 🔥 ACÁ AGREGUÉ EL CHOFER AL TÍTULO DE LA RADIOGRAFÍA 🔥
        nombre_chofer = v.chofer.nombre if v.chofer else "Sin Asignar"
        self.lbl_vehiculo_tit.setText(f"🚗 {v.marca} {v.modelo} - {v.patente}  |  👤 Chofer: {nombre_chofer}")
        
        if v.falla_reportada:
            self.panel_falla.show()
            self.lbl_falla_txt.setText(f"⚠️ El chofer reportó:\n\"{v.falla_reportada}\"")
        else:
            self.panel_falla.hide()
            
        km_actual = v.kilometraje_actual or 0
        
        def config_pb(pb, prox_km, margen_falla):
            if prox_km <= 0:
                pb.setValue(0); pb.setFormat("No cargado"); pb.setStyleSheet("QProgressBar { background-color: #e9ecef; color: #666; text-align: center;}")
                return
            
            km_faltantes = prox_km - km_actual
            if km_faltantes <= 0:
                pb.setValue(100); pb.setFormat(f"¡VENCIDO! (Se pasó {abs(km_faltantes):,} km)")
                pb.setStyleSheet("QProgressBar { background-color: #f8d7da; border: 1px solid #f5c6cb; text-align: center; color: #721c24; font-weight: bold; } QProgressBar::chunk { background-color: #dc3545; }")
            else:
                pct = int((km_actual / prox_km) * 100) if prox_km > 0 else 0
                if pct > 100: pct = 100
                pb.setValue(pct); pb.setFormat(f"Faltan {km_faltantes:,} km")
                
                if km_faltantes <= margen_falla:
                    pb.setStyleSheet("QProgressBar { background-color: #e9ecef; border: 1px solid #bbb; text-align: center; font-weight: bold; color: black;} QProgressBar::chunk { background-color: #ffc107; }")
                else:
                    pb.setStyleSheet("QProgressBar { background-color: #e9ecef; border: 1px solid #bbb; text-align: center; font-weight: bold; color: black;} QProgressBar::chunk { background-color: #28a745; }")

        config_pb(self.pb_aceite, v.km_proximo_service or 0, 1000)
        config_pb(self.pb_distri, v.km_proximo_distribucion or 0, 5000)
        config_pb(self.pb_neumaticos, v.km_proximo_neumaticos or 0, 3000)

        hoy = datetime.today().date()
        margen = timedelta(days=15)
        
        def config_lbl(lbl, fecha):
            if not fecha:
                lbl.setText("No cargado"); lbl.setStyleSheet("color: #666;")
                return
            lbl.setText(fecha.strftime("%d/%m/%Y"))
            if fecha <= hoy:
                lbl.setStyleSheet("color: #dc3545; font-weight: bold;")
                lbl.setText(lbl.text() + " (VENCIDO)")
            elif fecha <= hoy + margen:
                lbl.setStyleSheet("color: #ffc107; font-weight: bold;")
                lbl.setText(lbl.text() + " (Próximo a vencer)")
            else:
                lbl.setStyleSheet("color: #28a745; font-weight: bold;")

        config_lbl(self.lbl_seguro, v.vencimiento_seguro)
        config_lbl(self.lbl_rto, v.vencimiento_rto)
        config_lbl(self.lbl_matafuegos, v.vencimiento_matafuegos)
        config_lbl(self.lbl_carnet, v.vencimiento_carnet)
        config_lbl(self.lbl_gnc, v.vencimiento_oblea_gnc)

    def limpiar_falla_chofer(self):
        r = self.tabla.currentRow()
        if r < 0: return
        v_id = int(self.tabla.item(r, 0).text())
        v = self.main.session.query(Vehiculo).get(v_id)
        if v:
            v.falla_reportada = None
            self.main.session.commit()
            self.mostrar_radiografia()
            self.cargar_vehiculos()

    def obtener_id_seleccionado(self):
        r = self.tabla.currentRow()
        if r < 0:
            QMessageBox.warning(self, "Atención", "Seleccione un vehículo de la lista izquierda.")
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
                self.mostrar_radiografia()

    def registrar_mantenimiento(self):
        v_id = self.obtener_id_seleccionado()
        if not v_id: return
        try:
            vehiculo = self.main.session.query(Vehiculo).get(v_id)
            if vehiculo:
                dlg = DialogoMantenimiento(self.main.session, vehiculo, parent=self)
                if dlg.exec() == QDialog.DialogCode.Accepted:
                    self.cargar_vehiculos()
                    self.mostrar_radiografia()
        except Exception as e:
            QMessageBox.critical(self, "Error Interno", f"Ocurrió un error al abrir el servicio:\n{str(e)}")

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
        reply = QMessageBox.question(self, "Confirmar Eliminación", f"¿Seguro que desea eliminar permanentemente el vehículo {vehiculo.patente}?\nEsto también borrará su historial.", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.main.session.delete(vehiculo)
                self.main.session.commit()
                self.cargar_vehiculos()
                self.panel_radiografia.hide()
            except Exception as e:
                self.main.session.rollback()
                QMessageBox.critical(self, "Error", f"No se pudo eliminar: {str(e)}")

class DialogoVehiculo(QDialog):
    def __init__(self, session, sucursal_defecto, vehiculo=None, parent=None):
        super().__init__(parent)
        self.session = session
        self.vehiculo = vehiculo
        self.setWindowTitle("Editar Vehículo" if vehiculo else "Nuevo Vehículo")
        self.setMinimumWidth(500)
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
        self.actualizar_choferes()

        self.in_patente = QLineEdit()
        self.in_marca = QLineEdit()
        self.in_modelo = QLineEdit()
        self.in_anio = QSpinBox(); self.in_anio.setRange(1980, 2030); self.in_anio.setValue(datetime.now().year)
        self.in_km_actual = QSpinBox(); self.in_km_actual.setRange(0, 2000000); self.in_km_actual.setSingleStep(1000)

        # --- MECÁNICA ---
        self.in_km_aceite = QSpinBox(); self.in_km_aceite.setRange(0, 2000000); self.in_km_aceite.setSingleStep(1000)
        self.in_km_distri = QSpinBox(); self.in_km_distri.setRange(0, 2000000); self.in_km_distri.setSingleStep(1000)
        self.in_km_neumaticos = QSpinBox(); self.in_km_neumaticos.setRange(0, 2000000); self.in_km_neumaticos.setSingleStep(1000)

        # --- LEGALES ---
        self.in_seguro = QDateEdit(QDate.currentDate()); self.in_seguro.setCalendarPopup(True)
        self.in_rto = QDateEdit(QDate.currentDate()); self.in_rto.setCalendarPopup(True)
        self.in_matafuegos = QDateEdit(QDate.currentDate()); self.in_matafuegos.setCalendarPopup(True)
        self.in_carnet = QDateEdit(QDate.currentDate()); self.in_carnet.setCalendarPopup(True)
        
        self.check_gnc = QCheckBox("Vehículo con equipo de GNC")
        self.in_gnc = QDateEdit(QDate.currentDate()); self.in_gnc.setCalendarPopup(True); self.in_gnc.setEnabled(False)
        self.check_gnc.toggled.connect(self.in_gnc.setEnabled)
        
        self.in_estado = QComboBox()
        self.in_estado.addItems(["ACTIVO", "EN TALLER", "BAJA"])

        # Armado de formulario visual
        form.addRow("Sucursal:", self.in_sucursal)
        form.addRow("Chofer Asignado:", self.in_chofer)
        form.addRow("Patente:", self.in_patente)
        form.addRow("Marca / Modelo:", QHBoxLayout()); form.itemAt(form.rowCount()-1, QFormLayout.ItemRole.FieldRole).layout().addWidget(self.in_marca); form.itemAt(form.rowCount()-1, QFormLayout.ItemRole.FieldRole).layout().addWidget(self.in_modelo)
        form.addRow("KM Actual:", self.in_km_actual)
        
        form.addRow(QLabel(" "))
        form.addRow(QLabel("<b>⚙️ ALERTAS MECÁNICAS (Próximo Cambio en KM)</b>"))
        form.addRow("Aceite / Service:", self.in_km_aceite)
        form.addRow("Correa Distribución:", self.in_km_distri)
        form.addRow("Neumáticos:", self.in_km_neumaticos)
        
        form.addRow(QLabel(" "))
        form.addRow(QLabel("<b>📄 ALERTAS LEGALES (Fecha de Vencimiento)</b>"))
        form.addRow("Seguro:", self.in_seguro)
        form.addRow("RTO:", self.in_rto)
        form.addRow("Matafuegos:", self.in_matafuegos)
        form.addRow("Carnet Conducir:", self.in_carnet)
        form.addRow(self.check_gnc, self.in_gnc)

        form.addRow(QLabel(" "))
        form.addRow("Estado Operativo:", self.in_estado)

        btn_guardar = QPushButton("💾 GUARDAR VEHÍCULO")
        btn_guardar.setStyleSheet("background-color: #0d6efd; color: white; font-weight: bold; padding: 12px;")
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
        self.in_km_actual.setValue(self.vehiculo.kilometraje_actual or 0)
        
        self.in_km_aceite.setValue(self.vehiculo.km_proximo_service or 0)
        self.in_km_distri.setValue(self.vehiculo.km_proximo_distribucion or 0)
        self.in_km_neumaticos.setValue(self.vehiculo.km_proximo_neumaticos or 0)
        
        if self.vehiculo.vencimiento_seguro: self.in_seguro.setDate(self.vehiculo.vencimiento_seguro)
        if self.vehiculo.vencimiento_rto: self.in_rto.setDate(self.vehiculo.vencimiento_rto)
        if self.vehiculo.vencimiento_matafuegos: self.in_matafuegos.setDate(self.vehiculo.vencimiento_matafuegos)
        if self.vehiculo.vencimiento_carnet: self.in_carnet.setDate(self.vehiculo.vencimiento_carnet)
        
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
                    QMessageBox.warning(self, "Error", "Ya existe esa patente.")
                    return
                self.vehiculo = Vehiculo()
                self.session.add(self.vehiculo)
                
            self.vehiculo.patente = patente
            self.vehiculo.sucursal = self.in_sucursal.currentText()
            self.vehiculo.chofer_id = self.in_chofer.currentData()
            self.vehiculo.marca = self.in_marca.text().strip().upper()
            self.vehiculo.modelo = self.in_modelo.text().strip().upper()
            self.vehiculo.kilometraje_actual = self.in_km_actual.value()
            
            self.vehiculo.km_proximo_service = self.in_km_aceite.value()
            self.vehiculo.km_proximo_distribucion = self.in_km_distri.value()
            self.vehiculo.km_proximo_neumaticos = self.in_km_neumaticos.value()
            
            self.vehiculo.vencimiento_seguro = self.in_seguro.date().toPyDate()
            self.vehiculo.vencimiento_rto = self.in_rto.date().toPyDate()
            self.vehiculo.vencimiento_matafuegos = self.in_matafuegos.date().toPyDate()
            self.vehiculo.vencimiento_carnet = self.in_carnet.date().toPyDate()
            
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
            "Otros Gastos"
        ])
        
        self.in_km = QSpinBox()
        self.in_km.setRange(0, 2000000)
        self.in_km.setValue(self.vehiculo.kilometraje_actual or 0)

        self.in_costo = QDoubleSpinBox()
        self.in_costo.setRange(0, 100000000)
        self.in_costo.setPrefix("$ ")
        self.in_costo.setGroupSeparatorShown(True)

        self.in_taller = QLineEdit()
        self.in_detalle = QTextEdit()
        self.in_detalle.setMaximumHeight(80)

        self.check_actualizar_rto = QPushButton("🔄 Posponer Vencimiento RTO a un año")
        self.check_actualizar_rto.setCheckable(True)
        self.check_actualizar_gnc = QPushButton("🔄 Posponer Oblea GNC a un año")
        self.check_actualizar_gnc.setCheckable(True)
        
        self.check_actualizar_service = QPushButton("🔄 Sumar 10.000km para Próx Aceite")
        self.check_actualizar_service.setCheckable(True)
        self.check_actualizar_distri = QPushButton("🔄 Sumar 60.000km para Próx Distribución")
        self.check_actualizar_distri.setCheckable(True)

        form.addRow("Fecha:", self.in_fecha)
        form.addRow("Tipo de Servicio:", self.in_tipo)
        form.addRow("Kilometraje Realizado:", self.in_km)
        form.addRow("Costo:", self.in_costo)
        form.addRow("Taller / Proveedor:", self.in_taller)
        form.addRow("Detalle Repuestos:", self.in_detalle)

        layout.addLayout(form)
        layout.addWidget(QLabel("<b>Acciones Automáticas Rápidas:</b>"))
        layout.addWidget(self.check_actualizar_service)
        layout.addWidget(self.check_actualizar_distri)
        layout.addWidget(self.check_actualizar_rto)
        layout.addWidget(self.check_actualizar_gnc)

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
        self.check_actualizar_distri.setChecked("Distribución" in texto)

    def guardar(self):
        try:
            m = Mantenimiento(
                vehiculo_id=self.vehiculo.id,
                fecha=self.in_fecha.date().toPyDate(),
                tipo_servicio=self.in_tipo.currentText(),
                kilometraje=self.in_km.value(),
                costo=self.in_costo.value(),
                taller_proveedor=self.in_taller.text().strip().upper(),
                detalle=self.in_detalle.toPlainText().strip().upper()
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
            if self.check_actualizar_distri.isChecked():
                self.vehiculo.km_proximo_distribucion = self.in_km.value() + 60000

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