import sys
from datetime import datetime, date
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                             QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, 
                             QInputDialog, QDialog, QFormLayout, QLineEdit, QComboBox, 
                             QDoubleSpinBox, QDateEdit, QTabWidget, QAbstractItemView)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QColor, QFont, QBrush
from sqlalchemy import text

from database import FlotaVehiculo, FlotaVencimiento, FlotaHistorial, Chofer

class TabFlota(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main = main_window
        self.setup_ui()
        
    def setup_ui(self):
        layout_principal = QVBoxLayout(self)
        
        # --- PESTAÑAS INTERNAS DE FLOTA ---
        self.tabs_flota = QTabWidget()
        self.tab_vehiculos = QWidget()
        self.tab_historial = QWidget()
        
        self.tabs_flota.addTab(self.tab_vehiculos, "🚐 Panel de Vehículos")
        self.tabs_flota.addTab(self.tab_historial, "🛡️ Caja Negra / Auditoría")
        layout_principal.addWidget(self.tabs_flota)
        
        # =================================================================
        # TAB 1: PANEL DE VEHÍCULOS
        # =================================================================
        lay_vehiculos = QVBoxLayout(self.tab_vehiculos)
        
        top_bar = QHBoxLayout()
        btn_nuevo = QPushButton("➕ Registrar Vehículo")
        btn_nuevo.setStyleSheet("background-color: #0d6efd; color: white; font-weight: bold; padding: 8px;")
        btn_nuevo.clicked.connect(self.registrar_nuevo_vehiculo)
        
        btn_act_km = QPushButton("⛽ Actualizar Kilometraje")
        btn_act_km.setStyleSheet("background-color: #ffc107; color: black; font-weight: bold; padding: 8px;")
        btn_act_km.clicked.connect(self.pedir_actualizacion_km)
        
        btn_refresh = QPushButton("🔄 Actualizar Panel")
        btn_refresh.clicked.connect(self.cargar_vehiculos)
        
        top_bar.addWidget(btn_nuevo)
        top_bar.addWidget(btn_act_km)
        top_bar.addStretch()
        top_bar.addWidget(btn_refresh)
        
        self.tabla_vehiculos = QTableWidget()
        self.tabla_vehiculos.setColumnCount(8)
        self.tabla_vehiculos.setHorizontalHeaderLabels([
            "ID", "Patente", "Marca/Modelo", "Chofer Habitual", 
            "Kilometraje Actual", "Venc. RTO", "Venc. Seguro", "Próximo Service"
        ])
        self.tabla_vehiculos.hideColumn(0) # Ocultamos el ID
        header = self.tabla_vehiculos.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tabla_vehiculos.setColumnWidth(1, 100); self.tabla_vehiculos.setColumnWidth(2, 200)
        self.tabla_vehiculos.setColumnWidth(3, 180); self.tabla_vehiculos.setColumnWidth(4, 150)
        self.tabla_vehiculos.setColumnWidth(5, 120); self.tabla_vehiculos.setColumnWidth(6, 120)
        header.setStretchLastSection(True)
        self.tabla_vehiculos.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla_vehiculos.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        
        lay_vehiculos.addLayout(top_bar)
        lay_vehiculos.addWidget(self.tabla_vehiculos)
        
        # =================================================================
        # TAB 2: CAJA NEGRA / HISTORIAL
        # =================================================================
        lay_historial = QVBoxLayout(self.tab_historial)
        
        top_hist = QHBoxLayout()
        btn_ref_hist = QPushButton("🔄 Refrescar Caja Negra")
        btn_ref_hist.clicked.connect(self.cargar_caja_negra)
        
        self.filtro_patente = QLineEdit()
        self.filtro_patente.setPlaceholderText("Buscar por patente...")
        self.filtro_patente.textChanged.connect(self.filtrar_caja_negra)
        
        top_hist.addWidget(btn_ref_hist)
        top_hist.addWidget(self.filtro_patente)
        top_hist.addStretch()
        
        self.tabla_historial = QTableWidget()
        self.tabla_historial.setColumnCount(6)
        self.tabla_historial.setHorizontalHeaderLabels(["Fecha / Hora", "Patente", "Operador / Chofer", "Evento", "Kilometraje", "Detalle Registrado"])
        header_h = self.tabla_historial.horizontalHeader()
        header_h.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tabla_historial.setColumnWidth(0, 140); self.tabla_historial.setColumnWidth(1, 100)
        self.tabla_historial.setColumnWidth(2, 150); self.tabla_historial.setColumnWidth(3, 160)
        self.tabla_historial.setColumnWidth(4, 120)
        header_h.setStretchLastSection(True)
        self.tabla_historial.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla_historial.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        
        lay_historial.addLayout(top_hist)
        lay_historial.addWidget(self.tabla_historial)

    def cargar_vehiculos(self):
        self.tabla_vehiculos.setRowCount(0)
        try:
            vehiculos = self.main.session.query(FlotaVehiculo).filter(FlotaVehiculo.sucursal == self.main.sucursal_actual, FlotaVehiculo.activo == True).order_by(FlotaVehiculo.patente).all()
            
            for row, v in enumerate(vehiculos):
                self.tabla_vehiculos.insertRow(row)
                self.tabla_vehiculos.setItem(row, 0, QTableWidgetItem(str(v.id)))
                
                it_pat = QTableWidgetItem(v.patente)
                it_pat.setFont(QFont("Arial", 10, QFont.Weight.Bold))
                self.tabla_vehiculos.setItem(row, 1, it_pat)
                
                self.tabla_vehiculos.setItem(row, 2, QTableWidgetItem(f"{v.marca} {v.modelo}"))
                self.tabla_vehiculos.setItem(row, 3, QTableWidgetItem(v.chofer_habitual or "Sin Asignar"))
                
                it_km = QTableWidgetItem(f"{v.kilometraje_actual:,.1f} KM")
                it_km.setForeground(QBrush(QColor("#1565c0")))
                it_km.setFont(QFont("Arial", 10, QFont.Weight.Bold))
                self.tabla_vehiculos.setItem(row, 4, it_km)
                
                # Buscamos los vencimientos
                venc = self.main.session.query(FlotaVencimiento).filter(FlotaVencimiento.vehiculo_id == v.id).first()
                if venc:
                    rto_str = venc.fecha_rto.strftime("%d/%m/%Y") if venc.fecha_rto else "S/D"
                    seg_str = venc.fecha_seguro.strftime("%d/%m/%Y") if venc.fecha_seguro else "S/D"
                    serv_str = f"{venc.km_proximo_service:,.1f} KM" if venc.km_proximo_service else "S/D"
                else:
                    rto_str = "S/D"; seg_str = "S/D"; serv_str = "S/D"
                    
                self.tabla_vehiculos.setItem(row, 5, QTableWidgetItem(rto_str))
                self.tabla_vehiculos.setItem(row, 6, QTableWidgetItem(seg_str))
                self.tabla_vehiculos.setItem(row, 7, QTableWidgetItem(serv_str))
                
        except Exception as e:
            self.main.session.rollback()
            print(f"Error cargando vehículos: {e}")
            
    # 🔥 INYECTOR PRINCIPAL: ACTUALIZAR KILÓMETROS Y GUARDAR EN CAJA NEGRA 🔥
    def pedir_actualizacion_km(self):
        row = self.tabla_vehiculos.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Aviso", "Seleccioná un vehículo de la lista primero.")
            return
            
        vehiculo_id = int(self.tabla_vehiculos.item(row, 0).text())
        patente = self.tabla_vehiculos.item(row, 1).text()
        km_actual_txt = self.tabla_vehiculos.item(row, 4).text().replace(" KM", "").replace(",", "")
        km_actual = float(km_actual_txt) if km_actual_txt else 0.0
        
        nuevo_km, ok = QInputDialog.getDouble(self, f"Actualizar KM - Patente {patente}", "Ingresá el nuevo kilometraje del tablero:", km_actual, 0, 9999999, 1)
        
        if ok:
            if nuevo_km < km_actual:
                QMessageBox.critical(self, "Error de Seguridad", "El nuevo kilometraje no puede ser menor al kilometraje actual guardado.")
                return
                
            try:
                vehiculo = self.main.session.query(FlotaVehiculo).get(vehiculo_id)
                vehiculo.kilometraje_actual = nuevo_km
                
                # INYECCIÓN A LA CAJA NEGRA (Auditoría inborrable)
                log = FlotaHistorial(
                    vehiculo_id=vehiculo.id,
                    usuario_o_chofer=self.main.usuario.username, # Quien está operando el sistema ahora
                    tipo_evento="CARGA KM",
                    kilometraje_momento=nuevo_km,
                    detalle_tecnico=f"El operador actualizó los KM. Valor anterior: {km_actual} KM."
                )
                self.main.session.add(log)
                self.main.session.commit()
                
                self.main.toast.mostrar(f"✅ Kilometraje de {patente} actualizado.")
                self.cargar_vehiculos()
                self.cargar_caja_negra()
            except Exception as e:
                self.main.session.rollback()
                QMessageBox.critical(self, "Error", f"Fallo al actualizar: {e}")

    def cargar_caja_negra(self):
        self.tabla_historial.setRowCount(0)
        try:
            # Hacemos un JOIN para traer la patente junto con el historial
            query = text("""
                SELECT h.fecha_hora, v.patente, h.usuario_o_chofer, h.tipo_evento, h.kilometraje_momento, h.detalle_tecnico
                FROM flota_historial h
                JOIN flota_vehiculos v ON h.vehiculo_id = v.id
                WHERE v.sucursal = :suc
                ORDER BY h.fecha_hora DESC
                LIMIT 200
            """)
            logs = self.main.session.execute(query, {"suc": self.main.sucursal_actual}).fetchall()
            
            for r, log in enumerate(logs):
                self.tabla_historial.insertRow(r)
                f_hora = log[0].strftime("%d/%m/%Y %H:%M") if log[0] else "-"
                
                self.tabla_historial.setItem(r, 0, QTableWidgetItem(f_hora))
                
                it_pat = QTableWidgetItem(log[1])
                it_pat.setFont(QFont("Arial", 9, QFont.Weight.Bold))
                self.tabla_historial.setItem(r, 1, it_pat)
                
                self.tabla_historial.setItem(r, 2, QTableWidgetItem(log[2]))
                
                it_evento = QTableWidgetItem(log[3])
                if "CARGA KM" in log[3]: it_evento.setForeground(QBrush(QColor("#0d6efd")))
                elif "SERVICE" in log[3]: it_evento.setForeground(QBrush(QColor("#198754")))
                self.tabla_historial.setItem(r, 3, it_evento)
                
                km_txt = f"{log[4]:,.1f} KM" if log[4] else "-"
                self.tabla_historial.setItem(r, 4, QTableWidgetItem(km_txt))
                self.tabla_historial.setItem(r, 5, QTableWidgetItem(log[5] or ""))
                
        except Exception as e:
            self.main.session.rollback()
            print(f"Error cargando caja negra: {e}")

    def filtrar_caja_negra(self, texto):
        texto = texto.lower()
        for r in range(self.tabla_historial.rowCount()):
            item_pat = self.tabla_historial.item(r, 1)
            if item_pat and texto in item_pat.text().lower():
                self.tabla_historial.setRowHidden(r, False)
            else:
                self.tabla_historial.setRowHidden(r, True)

    def registrar_nuevo_vehiculo(self):
        patente, ok = QInputDialog.getText(self, "Nuevo Vehículo", "Ingresá la Patente (Sin espacios ni guiones):")
        if not ok or not patente: return
        
        try:
            nuevo = FlotaVehiculo(
                sucursal=self.main.sucursal_actual,
                patente=patente.strip().upper(),
                marca="A Completar",
                modelo="A Completar",
                kilometraje_actual=0
            )
            self.main.session.add(nuevo)
            self.main.session.flush() # Para obtener el ID temporalmente y linkearlo
            
            log = FlotaHistorial(
                vehiculo_id=nuevo.id,
                usuario_o_chofer=self.main.usuario.username,
                tipo_evento="ALTA SISTEMA",
                detalle_tecnico="Vehículo registrado por primera vez en el sistema."
            )
            self.main.session.add(log)
            self.main.session.commit()
            
            self.cargar_vehiculos()
            self.main.toast.mostrar(f"✅ Vehículo {patente.upper()} agregado con éxito.")
        except Exception as e:
            self.main.session.rollback()
            QMessageBox.warning(self, "Error", f"No se pudo crear. Verifica que la patente no esté repetida.\n{e}")