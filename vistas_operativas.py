import os
import re
import calendar
import requests
import base64
import io
from datetime import datetime, date
from PyQt6.QtWidgets import (QApplication, QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                             QComboBox, QPushButton, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QMessageBox, QDateEdit, QGroupBox, 
                             QFormLayout, QSpinBox, QDoubleSpinBox, QRadioButton, 
                             QButtonGroup, QListWidget, QAbstractItemView, QFrame, QFileDialog, QTabWidget, QCheckBox, QStyledItemDelegate, QScrollArea, QCompleter)
from PyQt6.QtCore import Qt, QDate, QTimer
from PyQt6.QtGui import QColor, QFont, QBrush
from sqlalchemy import text, extract

from database import Operacion, Historial, Estados, Urgencia, DestinoFrecuente, ClienteRetiro, ClientePrincipal, ReciboPago
from utilidades import parsear_txt_dhl_logic, crear_pdf_retiro, crear_pdf_facturacion, crear_pdf_resumen_diario
from dialogos import ConfirmarEntregaDialog, PreviewImportacionDialog, ReprogramarAdminDialog, EditarPrecioFacturacionDialog, AgregarCargoDialog, CargarPagoDialog, ResumenDiarioChoferDialog

class DeshacerFacturacionDialog(QDialog):
    def __init__(self, main_app, parent=None):
        super().__init__(parent)
        self.main_app = main_app
        self.setWindowTitle("⏪ Deshacer Facturación")
        self.setGeometry(400, 200, 750, 400)
        layout = QVBoxLayout(self)
        
        lbl = QLabel("Seleccione las guías que desea devolver a estado 'No Facturado':")
        lbl.setStyleSheet("font-weight: bold; color: #d32f2f;")
        layout.addWidget(lbl)
        
        self.tabla = QTableWidget()
        self.tabla.setColumnCount(7)
        self.tabla.setHorizontalHeaderLabels(["ID", "Sel.", "Fecha", "Guía", "Proveedor", "Destinatario", "Total ($)"])
        self.tabla.hideColumn(0)
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tabla.setColumnWidth(1, 40)
        self.tabla.setColumnWidth(2, 90)
        self.tabla.setColumnWidth(3, 140)
        self.tabla.setColumnWidth(4, 150)
        self.tabla.setColumnWidth(5, 200)
        self.tabla.horizontalHeader().setStretchLastSection(True)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.tabla)
        
        btn_deshacer = QPushButton("⏪ DEVOLVER A LA TABLA PRINCIPAL")
        btn_deshacer.setStyleSheet("background-color: #ff9800; font-weight: bold; padding: 10px; color: black;")
        btn_deshacer.clicked.connect(self.procesar_deshacer)
        layout.addWidget(btn_deshacer)
        
        self.cargar_datos()
        
    def cargar_datos(self):
        self.tabla.setRowCount(0)
        f_limite = QDate.currentDate().addDays(-60).toPyDate()
        try:
            ops = self.main_app.session.query(Operacion).filter(
                Operacion.facturado == True,
                Operacion.sucursal == self.main_app.sucursal_actual,
                Operacion.fecha_ingreso >= f_limite
            ).order_by(Operacion.id.desc()).limit(150).all()
            
            for r, op in enumerate(ops):
                self.tabla.insertRow(r)
                self.tabla.setItem(r, 0, QTableWidgetItem(str(op.id)))
                
                chk = QTableWidgetItem()
                chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
                chk.setCheckState(Qt.CheckState.Unchecked)
                self.tabla.setItem(r, 1, chk)
                
                self.tabla.setItem(r, 2, QTableWidgetItem(op.fecha_ingreso.strftime("%d/%m/%Y") if op.fecha_ingreso else "-"))
                self.tabla.setItem(r, 3, QTableWidgetItem(op.guia_remito or "-"))
                self.tabla.setItem(r, 4, QTableWidgetItem(op.proveedor or "-"))
                self.tabla.setItem(r, 5, QTableWidgetItem(op.destinatario or "-"))
                self.tabla.setItem(r, 6, QTableWidgetItem(f"$ {op.monto_servicio:,.2f}"))
        except Exception as e:
            pass
            
    def procesar_deshacer(self):
        ids = []
        for r in range(self.tabla.rowCount()):
            if self.tabla.item(r, 1).checkState() == Qt.CheckState.Checked:
                ids.append(int(self.tabla.item(r, 0).text()))
        
        if not ids:
            QMessageBox.warning(self, "Aviso", "Seleccione al menos una guía.")
            return
            
        try:
            ops = self.main_app.session.query(Operacion).filter(Operacion.id.in_(ids)).all()
            for op in ops:
                op.facturado = False
            self.main_app.session.commit()
            QMessageBox.information(self, "Éxito", f"Se deshizo la facturación de {len(ids)} guías. Ahora volverán a aparecer en el listado para ser editadas.")
            self.accept()
        except Exception as e:
            self.main_app.session.rollback()
            QMessageBox.critical(self, "Error", str(e))

def enviar_email_desktop(session, destinatario, guia, rutas_fotos, proveedor):
    try:
        from dotenv import load_dotenv
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        load_dotenv(os.path.join(BASE_DIR, '.env'))
    except:
        pass

    BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
    if not BREVO_API_KEY: 
        return "⚠️ Correo NO enviado: Falta configurar BREVO_API_KEY en el archivo .env de tu PC."
        
    EMAIL_REMITENTE = "eklogistica19@gmail.com"
    email_prov = None
    try:
        res = session.execute(text("SELECT email_reportes FROM clientes_principales WHERE UPPER(TRIM(nombre)) = UPPER(TRIM(:n))"), {"n": proveedor}).fetchone()
        if res: email_prov = res[0]
    except: pass
    
    destinatarios_lista = []
    if email_prov:
        correos_limpios = str(email_prov).replace(',', ' ').replace(';', ' ')
        for c in correos_limpios.split():
            if "@" in c: destinatarios_lista.append({"email": c.strip()})
    
    if not destinatarios_lista:
        destinatarios_lista = [{"email": EMAIL_REMITENTE}]
        
    adjuntos = []
    if rutas_fotos:
        for i, ruta in enumerate(rutas_fotos):
            if os.path.exists(ruta):
                try:
                    try:
                        from PIL import Image
                        img = Image.open(ruta)
                        if img.mode in ("RGBA", "P"): img = img.convert("RGB")
                        
                        # 🔥 FOTOS EN ALTA CALIDAD PARA LECTURA DE CLIENTES 🔥
                        img.thumbnail((1600, 1600)) 
                        buffer = io.BytesIO()
                        img.save(buffer, format="JPEG", quality=85, optimize=True)
                        b64_content = base64.b64encode(buffer.getvalue()).decode('utf-8')
                    except Exception as e:
                        print("Fallo compresión PIL, enviando original:", e)
                        with open(ruta, "rb") as f:
                            b64_content = base64.b64encode(f.read()).decode('utf-8')
                            
                    nombre_adjunto = f"remito_{guia}.jpg" if len(rutas_fotos) == 1 else f"remito_{guia}_parte{i+1}.jpg"
                    adjuntos.append({"content": b64_content, "name": nombre_adjunto})
                except Exception as e: 
                    pass
    
    url = "https://api.brevo.com/v3/smtp/email"
    fecha_hora = datetime.now().strftime('%d/%m/%Y %H:%M')
    
    html_content = f"""
    <html><body>
    <h3>Hola,</h3>
    <p>Se informa la entrega exitosa. <b>Adjuntamos la foto del remito/guía conformado.</b></p>
    <ul>
        <li><b>Fecha:</b> {fecha_hora}</li>
        <li><b>Guía:</b> {guia}</li>
        <li><b>Proveedor:</b> {proveedor}</li>
        <li><b>Recibió:</b> {destinatario}</li>
    </ul>
    <p>Atte.<br><b>Equipo JetPaq / EK Logística</b></p>
    </body></html>
    """
    
    payload = {
        "sender": {"name": "Logistica JetPaq", "email": EMAIL_REMITENTE},
        "subject": f"ENTREGA REALIZADA - Guía: {guia}",
        "htmlContent": html_content,
        "to": destinatarios_lista,
        "bcc": [{"email": EMAIL_REMITENTE, "name": "Archivo EK Logistica"}]
    }
    if len(destinatarios_lista) == 1 and destinatarios_lista[0]["email"] == EMAIL_REMITENTE:
        if "bcc" in payload: del payload["bcc"]
    if adjuntos: payload["attachment"] = adjuntos
    
    headers = {"accept": "application/json", "api-key": BREVO_API_KEY, "content-type": "application/json"}
    
    try: 
        r = requests.post(url, json=payload, headers=headers)
        if r.status_code in [200, 201, 202]:
            return "📧 Correo enviado exitosamente con la foto adjunta."
        else:
            if "attachment" in payload:
                del payload["attachment"]
                payload["htmlContent"] = html_content.replace(
                    "<b>Adjuntamos la foto del remito/guía conformado.</b>",
                    "<b style='color:#D32F2F;'>⚠️ La foto se guardó en nuestro sistema, pero era demasiado pesada para adjuntarse en este correo.</b>"
                )
                r2 = requests.post(url, json=payload, headers=headers)
                if r2.status_code in [200, 201, 202]:
                    return "📧 Correo enviado (Sin foto porque excedía el peso de la PC)."
                else:
                    payload["to"] = [{"email": EMAIL_REMITENTE}]
                    if "bcc" in payload: del payload["bcc"]
                    requests.post(url, json=payload, headers=headers)
                    return f"⚠️ Fallo al enviar al cliente. Error de servidor: {r2.status_code}"
            return f"⚠️ Fallo en servidor de correo. Error: {r.status_code}"
    except Exception as e: 
        return f"⚠️ Error de conexión a internet al enviar correo: {str(e)}"

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
        
        dest_layout = QHBoxLayout(); self.in_destinos_frecuentes = QComboBox(); self.in_destinos_frecuentes.addItem("--- Destinos Guardados ---"); self.in_destinos_frecuentes.setEnabled(False); self.in_destinos_frecuentes.setEditable(True); self.in_destinos_frecuentes.completer().setFilterMode(Qt.MatchFlag.MatchContains); self.in_destinos_frecuentes.currentIndexChanged.connect(self.llenar_datos_destino); self.in_codigo_rapido = QLineEdit(); self.in_codigo_rapido.setPlaceholderText("Buscar ID..."); self.in_codigo_rapido.setFixedWidth(80); self.in_codigo_rapido.returnPressed.connect(self.buscar_destino_por_codigo)
        dest_layout.addWidget(self.in_destinos_frecuentes); dest_layout.addWidget(self.in_codigo_rapido)
        
        self.in_dest = QLineEdit(); self.in_cel = QLineEdit(); self.in_cel.setPlaceholderText("Ej: 261-155..."); self.in_dom = QLineEdit(); self.in_loc_combo = QComboBox()
        
        fl.addRow("Tipo:", self.in_serv)
        fl.addRow(self.lbl_cli_ret, self.in_cliente_retiro)
        fl.addRow("Fecha (Máquina de Tiempo):", self.in_fecha)
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
        
        panel_izquierdo = QWidget()
        layout_izquierdo = QVBoxLayout(panel_izquierdo)
        layout_izquierdo.setContentsMargins(0, 0, 5, 0)
        layout_izquierdo.addWidget(self.scroll_izq) 
        layout_izquierdo.addWidget(btn_add)         
        layout_izquierdo.addWidget(self.btn_dhl)    
        
        col_der = QVBoxLayout(); h_header_ingreso = QHBoxLayout(); h_header_ingreso.addWidget(QLabel("<b>EN DEPOSITO (Mostrando hasta la Fecha Seleccionada):</b>"))
        btn_ref_ingreso = QPushButton("🔄 Actualizar")
        btn_ref_ingreso.setToolTip("Actualizar Tabla")
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
        
        l.addWidget(panel_izquierdo, 35) 
        l.addLayout(col_der, 65)
        
        self.configurar_autocompletado_global()
        self.actualizar_interfaz_peso()

    def configurar_autocompletado_global(self):
        try:
            destinos = self.main.session.query(DestinoFrecuente).filter(DestinoFrecuente.sucursal == self.main.sucursal_actual).all()
            nombres_completos = []
            self.mapa_destinos_global.clear()
            
            for d in destinos:
                # 🔥 ORDEN CORREGIDO Y LIMPIO: Destino - Domicilio [Proveedor] 🔥
                texto_completer = f"{d.destinatario} - {d.domicilio} [{d.proveedor}]"
                if texto_completer not in nombres_completos:
                    nombres_completos.append(texto_completer)
                    self.mapa_destinos_global[texto_completer] = d
                    
            if hasattr(self, 'in_dest') and isinstance(self.in_dest, QLineEdit):
                completer = QCompleter(nombres_completos)
                completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
                completer.setFilterMode(Qt.MatchFlag.MatchContains)
                
                # 🔥 CSS PARA HACER LA LISTA ANCHA Y CON LÍNEAS SEPARADORAS 🔥
                vista_lista = completer.popup()
                vista_lista.setMinimumWidth(600)
                vista_lista.setStyleSheet("""
                    QListView { background-color: #ffffff; border: 1px solid #999; font-size: 14px; outline: none; }
                    QListView::item { padding: 10px; border-bottom: 1px solid #ddd; }
                    QListView::item:selected { background-color: #bbdefb; color: black; border-bottom: 1px solid #90caf9; }
                """)
                
                self.in_dest.setCompleter(completer)
                completer.activated.connect(self.autollenar_desde_completer_global)
        except Exception:
            self.main.session.rollback()

    def autollenar_desde_completer_global(self, texto):
        try:
            if texto in self.mapa_destinos_global:
                destino_db = self.mapa_destinos_global[texto]
                
                self.in_prov.blockSignals(True) 
                self.in_prov.setCurrentText(destino_db.proveedor)
                self.in_prov.blockSignals(False)
                
                self.cargar_destinos_frecuentes_combo(destino_db.proveedor)
                self.actualizar_interfaz_peso()
                
                self.in_dest.blockSignals(True)
                self.in_dest.setText(destino_db.destinatario)
                self.in_dest.blockSignals(False)
                
                self.in_dom.setText(destino_db.domicilio)
                self.in_cel.setText(destino_db.celular or "")
                self.in_loc_combo.setCurrentText(destino_db.localidad)
                
                estilo_flash = "background-color: #d1e7dd; color: #0f5132; font-weight: bold; border: 2px solid #198754; border-radius: 4px;"
                self.in_dest.setStyleSheet(estilo_flash)
                self.in_dom.setStyleSheet(estilo_flash)
                self.in_loc_combo.setStyleSheet(estilo_flash)
                self.in_prov.setStyleSheet(estilo_flash)
                
                QTimer.singleShot(1500, self.restaurar_estilo_inputs)
        except Exception:
            self.main.session.rollback()

    def actualizar_interfaz_peso(self):
        prov = self.in_prov.currentText().upper()
        if "DHL" in prov:
            self.lbl_peso.show()
            self.in_peso_manual.show()
        else:
            self.lbl_peso.hide()
            self.in_peso_manual.hide()
            self.in_peso_manual.setValue(0.0)

    def cambiar_interfaz_tipo(self):
        if self.radio_comb.isChecked(): 
            self.widget_simple.hide()
            self.widget_comb.show()
            self.chk_contingencia.show()
        else: 
            self.widget_simple.show()
            self.widget_comb.hide()
            if self.radio_frio.isChecked():
                self.chk_contingencia.show()
            else:
                self.chk_contingencia.hide()
                self.chk_contingencia.setChecked(False)

    def actualizar_interfaz_retiro(self, texto):
        is_flete = texto.startswith("Flete")
        is_retiro = texto.startswith("Retiro")
        
        if is_retiro:
            self.lbl_guia.hide(); self.in_guia.hide()
            self.lbl_cli_ret.show(); self.in_cliente_retiro.show()
            self.in_guia.clear()
        elif is_flete:
            self.lbl_guia.hide(); self.in_guia.hide()
            self.lbl_cli_ret.hide(); self.in_cliente_retiro.hide()
            self.in_guia.clear()
        else: 
            self.lbl_guia.show(); self.in_guia.show()
            self.lbl_cli_ret.hide(); self.in_cliente_retiro.hide()

        if is_flete:
            self.widget_carga_normal.hide()
            self.widget_carga_flete.show()
            self.group_cr.hide() 
            self.chk_cr.setChecked(False) 
        else:
            self.widget_carga_normal.show()
            self.widget_carga_flete.hide()
            self.group_cr.show()

    def cargar_datos_cliente(self):
        try:
            idx = self.in_cliente_retiro.currentIndex()
            if idx <= 0: return
            id_cli = self.in_cliente_retiro.itemData(idx); c = self.main.session.query(ClienteRetiro).get(id_cli)
            if c: self.in_dest.setText(c.nombre); self.in_dom.setText(c.domicilio); self.in_cel.setText(c.celular); self.in_loc_combo.setCurrentText(c.localidad)
        except Exception: self.main.session.rollback()

    def cargar_destinos_frecuentes_combo(self, proveedor_texto):
        try:
            self.in_destinos_frecuentes.clear(); self.in_destinos_frecuentes.addItem("--- Destinos Guardados ---")
            if proveedor_texto == "JetPaq": 
                self.in_destinos_frecuentes.setEnabled(False); self.in_destinos_frecuentes.addItem("(Manual para JetPaq)")
                return
            
            destinos = self.main.session.query(DestinoFrecuente).filter(DestinoFrecuente.proveedor == proveedor_texto, DestinoFrecuente.sucursal == self.main.sucursal_actual).order_by(DestinoFrecuente.destinatario).all()
            
            if destinos:
                self.in_destinos_frecuentes.setEnabled(True)
                for d in destinos: 
                    self.in_destinos_frecuentes.addItem(f"{d.id} - {d.destinatario}", d.id)
            else: 
                self.in_destinos_frecuentes.setEnabled(False); self.in_destinos_frecuentes.addItem("(Sin destinos guardados)")
                
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
        self.in_dest.setText(destino_db.destinatario); self.in_dom.setText(destino_db.domicilio); self.in_cel.setText(destino_db.celular or ""); self.in_loc_combo.setCurrentText(destino_db.localidad)
        estilo_flash = "background-color: #d1e7dd; color: #0f5132; font-weight: bold; border: 2px solid #198754; border-radius: 4px;"
        self.in_dest.setStyleSheet(estilo_flash); self.in_dom.setStyleSheet(estilo_flash); self.in_loc_combo.setStyleSheet(estilo_flash)
        self.in_prov.setStyleSheet(estilo_flash)
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
            loc = self.in_loc_combo.currentText().strip()
            peso_manual = self.in_peso_manual.value()
            prov = self.in_prov.currentText()
            
            if "Flete" in servicio:
                c_comun = 0
                c_frio = 0
                bultos_total = 2 if self.radio_ida_vuelta.isChecked() else 1
                tipo_carga_txt = "FLETE (IDA Y VUELTA)" if bultos_total == 2 else "FLETE (SOLO IDA)"
                precio = self.in_precio_flete.value()
                tiene_cr = False
                monto_cr = 0.0
                info_cr = ""
            else:
                if self.radio_comb.isChecked(): 
                    c_comun = self.in_cant_comun.value()
                    c_frio = self.in_cant_frio.value()
                    bultos_total = c_comun + c_frio
                    tipo_carga_txt = "COMBINADO"
                else:
                    bultos_total = self.in_bultos_simple.value()
                    if self.radio_frio.isChecked(): 
                        c_frio = bultos_total
                        c_comun = 0
                        tipo_carga_txt = "REFRIGERADO"
                    else: 
                        c_frio = 0
                        c_comun = bultos_total
                        tipo_carga_txt = "COMUN"
                        
                if bultos_total == 0: 
                    QMessageBox.warning(self, "Error", "Debe ingresar al menos 1 bulto."); return
                
                precio = self.main.obtener_precio(loc, c_comun, c_frio, proveedor=prov, peso=peso_manual, bultos_totales=bultos_total)
                if self.chk_contingencia.isChecked():
                    precio += self.in_monto_contingencia.value()
                    tipo_carga_txt += " (+Contingencia)"
                    
                tiene_cr = self.chk_cr.isChecked()
                monto_cr = self.in_monto_recaudar.value() if tiene_cr else 0.0
                info_cr = self.in_info_intercambio.text() if tiene_cr else ""
            
            guia_final = self.in_guia.text()
            if ("Retiro" in servicio or "Flete" in servicio) and not guia_final: 
                now = datetime.now(); c_year = now.strftime('%Y'); c_month = now.strftime('%m')
                prefijo = "Retiro" if "Retiro" in servicio else "FLETE"
                ops_auto = self.main.session.query(Operacion.guia_remito).filter(Operacion.guia_remito.like(f"{prefijo} {c_year}-%")).all()
                max_seq = 0
                for r_op in ops_auto:
                    if r_op[0]:
                        try: seq = int(r_op[0].split('-')[-1]); max_seq = max(max_seq, seq)
                        except: pass
                guia_final = f"{prefijo} {c_year}-{c_month}-{max_seq + 1:03d}"
            
            dest_texto = self.in_dest.text().strip()
            dom_texto = self.in_dom.text().strip()
            cel_texto = self.in_cel.text().strip()
            
            mensaje_toast = "✅ GUARDADO EN DEPÓSITO CORRECTAMENTE"
            
            if prov and prov != "JetPaq" and dest_texto and dom_texto:
                # 🔥 AHORA EL SISTEMA EVITA DUPLICAR COMPROBANDO DESTINATARIO + DOMICILIO AL MISMO TIEMPO 🔥
                existe = self.main.session.query(DestinoFrecuente).filter(
                    DestinoFrecuente.proveedor == prov, 
                    DestinoFrecuente.sucursal == self.main.sucursal_actual, 
                    DestinoFrecuente.destinatario.ilike(dest_texto),
                    DestinoFrecuente.domicilio.ilike(dom_texto)
                ).first()
                
                if not existe:
                    nuevo_dest = DestinoFrecuente(
                        proveedor=prov, sucursal=self.main.sucursal_actual,
                        destinatario=dest_texto, domicilio=dom_texto,
                        localidad=loc, celular=cel_texto
                    )
                    self.main.session.add(nuevo_dest)
                    self.main.session.flush() 
                else:
                    mensaje_toast = "✅ GUARDADO (Destino ya existía, se evitó duplicarlo)"
            
            op = Operacion(fecha_ingreso=self.in_fecha.date().toPyDate(), sucursal=self.main.sucursal_actual, guia_remito=guia_final, proveedor=prov, destinatario=dest_texto, celular=cel_texto, domicilio=dom_texto, localidad=loc, bultos=bultos_total, bultos_frio=c_frio, peso=peso_manual, tipo_carga=tipo_carga_txt, tipo_urgencia=Urgencia.CLASICO, monto_servicio=precio, es_contra_reembolso=tiene_cr, monto_recaudacion=monto_cr, info_intercambio=info_cr, tipo_servicio=servicio)
            self.main.session.add(op); self.main.session.flush(); self.main.log_movimiento(op, "INGRESO A DEPOSITO", "Carga inicial en sistema"); self.main.session.commit()
            
            if "Retiro" in servicio: crear_pdf_retiro(f"Comprobante_Retiro_{op.guia_remito or op.id}.pdf", op)
            
            self.main.cargar_ruta()
            self.in_guia.clear()
            self.in_dest.clear()
            self.in_cel.clear()
            self.in_dom.clear()                 
            self.in_monto_recaudar.setValue(0)
            self.in_info_intercambio.clear()
            self.chk_cr.setChecked(False)
            self.in_cliente_retiro.setCurrentIndex(0)
            self.in_bultos_simple.setValue(1)
            self.in_peso_manual.setValue(0)
            self.in_precio_flete.setValue(0)
            self.radio_ida.setChecked(True)
            self.in_cant_comun.setValue(1)
            self.in_cant_frio.setValue(1)
            self.radio_comun.setChecked(True)
            self.cambiar_interfaz_tipo()
            self.chk_contingencia.setChecked(False)
            self.in_monto_contingencia.setValue(1500.0)
            
            self.cargar_destinos_frecuentes_combo(prov) 
            self.cargar_movimientos_dia()
            self.in_destinos_frecuentes.setCurrentIndex(0)
            
            self.configurar_autocompletado_global()
            self.main.toast.mostrar(mensaje_toast)
            
            if hasattr(self.main, 'cargar_monitor_global'): self.main.cargar_monitor_global()
        except Exception as e: 
            self.main.session.rollback(); QMessageBox.warning(self, "Micro-corte", "La conexión parpadeó. Intenta de nuevo.")

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
                    op = Operacion(fecha_ingreso=d['fecha_ingreso'], sucursal=self.main.sucursal_actual, guia_remito=d['guia'], proveedor="DHL", destinatario=d['destinatario'][:100], domicilio=d['domicilio'][:150], localidad=self.main.sucursal_actual, celular=d['celular'][:50], bultos=bultos_txt, bultos_frio=0, peso=peso_txt, tipo_carga="COMUN", tipo_urgencia=Urgencia.CLASICO, monto_servicio=precio, estado=Estados.EN_DEPOSITO, tipo_servicio="Entrega (Reparto)")
                    self.main.session.add(op); hist = Historial(operacion=op, usuario=self.main.usuario.username, accion="INGRESO IMPORTADO", detalle="Carga masiva por TXT DHL"); self.main.session.add(hist); agregadas += 1
                self.main.session.commit(); QApplication.restoreOverrideCursor(); self.main.setWindowTitle(f"E.K. LOGISTICA (NUBE) - Usuario: {self.main.usuario.username.upper()}")
                QMessageBox.information(self, "Importación Exitosa", f"✅ {agregadas} guías agregadas.\n⚠️ {omitidas} omitidas (ya existían)."); self.cargar_movimientos_dia()
                if hasattr(self.main, 'cargar_monitor_global'): self.main.cargar_monitor_global()
        except Exception: QApplication.restoreOverrideCursor(); self.main.setWindowTitle(f"E.K. LOGISTICA (NUBE) - Usuario: {self.main.usuario.username.upper()}"); self.main.session.rollback(); QMessageBox.warning(self, "Micro-corte", "Se interrumpió la conexión.")

    def cargar_movimientos_dia(self):
        try:
            self.tabla_ingresos.setRowCount(0)
            estados_deposito = [Estados.EN_DEPOSITO, 'EN DEPOSITO', 'En Depósito', 'En Deposito', 'EN DEPÓSITO']
            
            fecha_filtro = self.in_fecha.date().toPyDate()
            
            ops = self.main.session.query(Operacion).filter(
                Operacion.estado.in_(estados_deposito), 
                Operacion.sucursal == self.main.sucursal_actual,
                text("DATE(COALESCE(fecha_salida, fecha_ingreso)) <= :f").bindparams(f=fecha_filtro)
            ).order_by(Operacion.id.desc()).all()
            
            for row, op in enumerate(ops):
                self.tabla_ingresos.insertRow(row); self.tabla_ingresos.setItem(row, 0, QTableWidgetItem(str(op.id)))
                icon_srv = "🚚" if "Entrega" in op.tipo_servicio else ("🔄" if "Retiro" in op.tipo_servicio else "⏱️")
                srv_txt = "Flete" if "Flete" in op.tipo_servicio else ("Retiro" if "Retiro" in op.tipo_servicio else "Entrega")
                self.tabla_ingresos.setItem(row, 1, QTableWidgetItem(f"{icon_srv} {srv_txt}")); self.tabla_ingresos.setItem(row, 2, QTableWidgetItem(op.guia_remito)); self.tabla_ingresos.setItem(row, 3, QTableWidgetItem(op.proveedor)); self.tabla_ingresos.setItem(row, 4, QTableWidgetItem(op.destinatario)); self.tabla_ingresos.setItem(row, 5, QTableWidgetItem(op.domicilio)); self.tabla_ingresos.setItem(row, 6, QTableWidgetItem(op.localidad))
                det_b = str(op.bultos)
                if op.bultos_frio and op.bultos_frio > 0 and op.bultos_frio < op.bultos: det_b += f" ({op.bultos-op.bultos_frio}C/{op.bultos_frio}R)"
                elif op.bultos_frio == op.bultos: det_b += " (R)"
                self.tabla_ingresos.setItem(row, 7, QTableWidgetItem(det_b))
        except Exception: self.main.session.rollback()


class TabRendicion(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main = main_window
        self.setup_ui()

    def setup_ui(self):
        l = QVBoxLayout(self)
        self.tabs_rendicion = QTabWidget()
        l.addWidget(self.tabs_rendicion)
        
        tab_reparto = QWidget(); lay_reparto = QVBoxLayout(tab_reparto)
        top = QHBoxLayout()
        btn_mark = QPushButton("☑️ Todo"); btn_mark.clicked.connect(lambda: self.main.toggle_seleccion_todo(self.tabla_rendicion)); 
        btn_confirmar = QPushButton("✅ CONFIRMAR ENTREGAS"); btn_confirmar.clicked.connect(self.confirmar_entrega_rendicion)
        btn_pendiente = QPushButton("📅 REPROGRAMAR"); btn_pendiente.clicked.connect(self.marcar_pendiente_masivo); 
        btn_ref = QPushButton("🔄 Actualizar"); btn_ref.clicked.connect(self.cargar_rendicion)
        
        top.addWidget(QLabel("<b>GUIAS EN REPARTO:</b>")); top.addStretch(); top.addWidget(btn_mark); top.addWidget(btn_confirmar); top.addWidget(btn_pendiente); top.addWidget(btn_ref)
        admin_bar = QHBoxLayout(); 
        btn_deshacer = QPushButton("↩️ DESHACER (Admin)"); btn_deshacer.clicked.connect(self.deshacer_estado)
        if not self.main.usuario.es_admin_total: btn_deshacer.hide()
        admin_bar.addWidget(btn_deshacer); admin_bar.addStretch()
        self.txt_filtro_rendir = QLineEdit(); self.txt_filtro_rendir.setPlaceholderText("🔎 Filtrar por Chofer, Guía..."); self.txt_filtro_rendir.textChanged.connect(self.filtrar_tabla_rendicion)
        top.insertWidget(2, self.txt_filtro_rendir)
        
        self.tabla_rendicion = QTableWidget(); self.tabla_rendicion.setColumnCount(10); 
        self.tabla_rendicion.setHorizontalHeaderLabels(["ID", "Sel.", "Chofer", "Guía / Remito", "Destinatario", "Domicilio", "Localidad", "Bultos/Hs", "Estado", "Fecha Ingreso"]); self.tabla_rendicion.hideColumn(0); 
        self.tabla_rendicion.setStyleSheet(ESTILO_TABLAS_BLANCAS)
        self.pintor_rend = PintorCeldasDelegate(self.tabla_rendicion)
        self.tabla_rendicion.setItemDelegate(self.pintor_rend)

        header_rend = self.tabla_rendicion.horizontalHeader()
        header_rend.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tabla_rendicion.setColumnWidth(1, 60)
        self.tabla_rendicion.setColumnWidth(2, 160)
        self.tabla_rendicion.setColumnWidth(3, 140)
        self.tabla_rendicion.setColumnWidth(4, 250)
        self.tabla_rendicion.setColumnWidth(5, 350)
        self.tabla_rendicion.setColumnWidth(6, 160)
        self.tabla_rendicion.setColumnWidth(7, 100)
        self.tabla_rendicion.setColumnWidth(8, 180)
        self.tabla_rendicion.setColumnWidth(9, 100)
        header_rend.setStretchLastSection(True)
        
        self.tabla_rendicion.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.tabla_rendicion.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        lay_reparto.addLayout(top); lay_reparto.addWidget(self.tabla_rendicion); lay_reparto.addLayout(admin_bar)
        self.tabs_rendicion.addTab(tab_reparto, "1. Gestión de Rendición")
        
        tab_res = QWidget(); lay_res = QVBoxLayout(tab_res)
        top_res = QHBoxLayout()
        self.resumen_chofer = QComboBox()
        self.resumen_fecha = QDateEdit(QDate.currentDate()); self.resumen_fecha.setCalendarPopup(True)
        btn_buscar_res = QPushButton("🔍 Buscar Resumen"); btn_buscar_res.clicked.connect(self.cargar_resumen_chofer_vista)
        
        btn_pdf_res = QPushButton("Imprimir PDF")
        btn_pdf_res.setStyleSheet("background-color: #dc3545 !important; color: white !important;")
        btn_pdf_res.clicked.connect(self.imprimir_resumen_chofer)
        
        top_res.addWidget(QLabel("Seleccionar Chofer:")); top_res.addWidget(self.resumen_chofer); top_res.addWidget(QLabel("Fecha:")); top_res.addWidget(self.resumen_fecha); top_res.addWidget(btn_buscar_res); top_res.addStretch(); top_res.addWidget(btn_pdf_res)
        self.lbl_res_exitos = QLabel("✅ ENTREGAS / RETIROS EXITOSOS (0)"); self.lbl_res_exitos.setStyleSheet("font-size: 14px; font-weight: bold; color: #2e7d32; margin-top: 10px;")
        
        self.tabla_res_exitos = QTableWidget(); self.tabla_res_exitos.setColumnCount(3); self.tabla_res_exitos.setHorizontalHeaderLabels(["Guía", "Destinatario", "Domicilio"])
        
        self.tabla_res_exitos.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tabla_res_exitos.setColumnWidth(0, 150)
        self.tabla_res_exitos.setColumnWidth(1, 250)
        self.tabla_res_exitos.horizontalHeader().setStretchLastSection(True)
        self.tabla_res_exitos.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        
        self.lbl_res_fallos = QLabel("⚠️ NO ENTREGADOS / PENDIENTES (0)"); self.lbl_res_fallos.setStyleSheet("font-size: 14px; font-weight: bold; color: #c62828; margin-top: 10px;")
        
        self.tabla_res_fallos = QTableWidget(); self.tabla_res_fallos.setColumnCount(3); self.tabla_res_fallos.setHorizontalHeaderLabels(["Guía", "Destinatario", "Motivo del Chofer"])
        
        self.tabla_res_fallos.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tabla_res_fallos.setColumnWidth(0, 150)
        self.tabla_res_fallos.setColumnWidth(1, 250)
        self.tabla_res_fallos.horizontalHeader().setStretchLastSection(True)
        self.tabla_res_fallos.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        
        self.tabla_res_exitos.setStyleSheet(ESTILO_TABLAS_BLANCAS)
        self.tabla_res_fallos.setStyleSheet(ESTILO_TABLAS_BLANCAS)

        lay_res.addLayout(top_res); lay_res.addWidget(self.lbl_res_exitos); lay_res.addWidget(self.tabla_res_exitos); lay_res.addWidget(self.lbl_res_fallos); lay_res.addWidget(self.tabla_res_fallos)
        self.tabs_rendicion.addTab(tab_res, "2. Resumen Diario por Chofer")

    def cargar_resumen_chofer_vista(self):
        chofer = self.resumen_chofer.currentText(); fecha = self.resumen_fecha.date().toPyDate()
        if not chofer or chofer == "Todos": return
        try:
            sql_entregados = text("SELECT DISTINCT o.id, o.guia_remito, o.destinatario, o.domicilio, o.tipo_servicio FROM operaciones o JOIN historial_movimientos h ON o.id = h.operacion_id WHERE o.chofer_asignado = :c AND o.estado = 'ENTREGADO' AND DATE(h.fecha_hora) = :f AND (h.accion LIKE '%ENTREGA%' OR h.accion = 'APP')")
            entregados = self.main.session.execute(sql_entregados, {"c": chofer, "f": fecha}).fetchall()
            
            sql_no_ent = text("""
                SELECT o.guia_remito, o.destinatario, h.detalle, o.tipo_servicio 
                FROM historial_movimientos h 
                JOIN operaciones o ON h.operacion_id = o.id 
                WHERE DATE(h.fecha_hora) = :f 
                  AND ((h.usuario = :c AND h.detalle LIKE 'Motivo:%') 
                       OR (h.usuario = :c AND h.detalle LIKE 'Pendiente%') 
                       OR (o.chofer_asignado = :c AND h.accion LIKE '%REPROGRAMADO%'))
                UNION
                SELECT guia_remito, destinatario, 'EN CALLE (Aún no gestionado)', tipo_servicio 
                FROM operaciones 
                WHERE chofer_asignado = :c AND estado = 'EN REPARTO'
            """)
            no_entregados = self.main.session.execute(sql_no_ent, {"c": chofer, "f": fecha}).fetchall()
            
            self.datos_resumen_exitos = entregados; self.datos_resumen_fallos = no_entregados
            self.tabla_res_exitos.setRowCount(0)
            
            for r, row_data in enumerate(entregados):
                self.tabla_res_exitos.insertRow(r)
                guia_str = row_data[1] or "-"
                if row_data[4] and "Retiro" in row_data[4]:
                    guia_str = f"🔄 [RETIRO] {guia_str}"
                elif row_data[4] and "Flete" in row_data[4]:
                    guia_str = f"⏱️ {guia_str}"
                
                self.tabla_res_exitos.setItem(r, 0, QTableWidgetItem(guia_str))
                self.tabla_res_exitos.setItem(r, 1, QTableWidgetItem(row_data[2]))
                self.tabla_res_exitos.setItem(r, 2, QTableWidgetItem(row_data[3]))
                
            self.lbl_res_exitos.setText(f"✅ ENTREGAS / RETIROS EXITOSOS ({len(entregados)})")
            
            self.tabla_res_fallos.setRowCount(0)
            for r, row_data in enumerate(no_entregados):
                self.tabla_res_fallos.insertRow(r)
                guia_str = row_data[0] or "-"
                if row_data[3] and "Retiro" in row_data[3]:
                    guia_str = f"🔄 [RETIRO] {guia_str}"
                elif row_data[3] and "Flete" in row_data[3]:
                    guia_str = f"⏱️ {guia_str}"
                    
                self.tabla_res_fallos.setItem(r, 0, QTableWidgetItem(guia_str))
                self.tabla_res_fallos.setItem(r, 1, QTableWidgetItem(row_data[1]))
                self.tabla_res_fallos.setItem(r, 2, QTableWidgetItem(row_data[2]))
                
            self.lbl_res_fallos.setText(f"⚠️ NO ENTREGADOS / PENDIENTES ({len(no_entregados)})")
        except Exception as e: self.main.session.rollback(); QMessageBox.critical(self, "Error", str(e))

    def imprimir_resumen_chofer(self):
        if not hasattr(self, 'datos_resumen_exitos'): QMessageBox.warning(self, "Atención", "Busque primero."); return
        chofer = self.resumen_chofer.currentText(); fecha_str = self.resumen_fecha.date().toPyDate().strftime("%d/%m/%Y"); fecha_file = self.resumen_fecha.date().toPyDate().strftime("%Y-%m-%d")
        if not self.datos_resumen_exitos and not self.datos_resumen_fallos: QMessageBox.warning(self, "Sin datos", "No hay actividad."); return
        nombre_archivo, _ = QFileDialog.getSaveFileName(self, "Guardar", f"Resumen_{chofer}_{fecha_file}.pdf", "PDF (*.pdf)")
        if nombre_archivo: crear_pdf_resumen_diario(nombre_archivo, chofer, fecha_str, self.datos_resumen_exitos, self.datos_resumen_fallos, self.main.sucursal_actual, self.main.usuario.username); os.startfile(nombre_archivo)

    def filtrar_tabla_rendicion(self, texto):
        texto = texto.lower()
        for r in range(self.tabla_rendicion.rowCount()):
            mostrar = False
            for c in [2, 3, 4, 5, 6]:
                if self.tabla_rendicion.item(r, c) and texto in self.tabla_rendicion.item(r, c).text().lower(): mostrar = True; break
            self.tabla_rendicion.setRowHidden(r, not mostrar)

    def cargar_rendicion(self):
        try:
            self.tabla_rendicion.blockSignals(True); self.tabla_rendicion.setRowCount(0); estados = [Estados.EN_REPARTO]
            ops = self.main.session.query(Operacion).filter(Operacion.estado.in_(estados), Operacion.sucursal == self.main.sucursal_actual).order_by(Operacion.chofer_asignado.asc()).all()
            for row, op in enumerate(ops):
                self.tabla_rendicion.insertRow(row); self.tabla_rendicion.setItem(row, 0, QTableWidgetItem(str(op.id)))
                chk = QTableWidgetItem(); chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled); chk.setCheckState(Qt.CheckState.Unchecked); self.tabla_rendicion.setItem(row, 1, chk)
                guia_texto = op.guia_remito or "-"
                if op.tipo_servicio and "Retiro" in op.tipo_servicio: guia_texto = f"🔄 [RETIRO] {guia_texto}"
                elif op.tipo_servicio and "Flete" in op.tipo_servicio: guia_texto = f"⏱️ {op.guia_remito}"
                
                self.tabla_rendicion.setItem(row, 2, QTableWidgetItem(op.chofer_asignado or "SIN ASIGNAR")); self.tabla_rendicion.setItem(row, 3, QTableWidgetItem(guia_texto)); self.tabla_rendicion.setItem(row, 4, QTableWidgetItem(op.destinatario)); self.tabla_rendicion.setItem(row, 5, QTableWidgetItem(op.domicilio)); self.tabla_rendicion.setItem(row, 6, QTableWidgetItem(op.localidad)); self.tabla_rendicion.setItem(row, 7, QTableWidgetItem(str(op.bultos)))
                estado_calle = op.estado
                h_pend = self.main.session.query(Historial).filter(Historial.operacion_id == op.id, Historial.accion == 'APP').order_by(Historial.id.desc()).first()
                if h_pend and "Pendiente" in h_pend.detalle: estado_calle = "EN CALLE (Pendiente)"
                it_est = QTableWidgetItem(estado_calle)
                if "Pendiente" in estado_calle: it_est.setForeground(QColor("#f57f17"))
                self.tabla_rendicion.setItem(row, 8, it_est); 
                
                fecha_creacion_str = op.fecha_ingreso.strftime("%d/%m/%Y") if op.fecha_ingreso else "-"
                self.tabla_rendicion.setItem(row, 9, QTableWidgetItem(fecha_creacion_str)) 
                
        except Exception: self.main.session.rollback()
        finally: self.tabla_rendicion.blockSignals(False)
        
    def confirmar_entrega_rendicion(self):
        ids = []
        for r in range(self.tabla_rendicion.rowCount()):
            if self.tabla_rendicion.item(r, 1).checkState() == Qt.CheckState.Checked: ids.append(int(self.tabla_rendicion.item(r, 0).text()))
        if not ids: QMessageBox.warning(self, "Atención", "Seleccione guías para confirmar su entrega."); return
        
        dlg = ConfirmarEntregaDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted: return
        
        try:
            ops = self.main.session.query(Operacion).filter(Operacion.id.in_(ids)).all()
            count = 0
            mensajes_mail = []
            
            for op in ops:
                if op.estado == Estados.ENTREGADO: continue 
                op.estado = Estados.ENTREGADO
                op.fecha_entrega = datetime.combine(dlg.fecha_final, datetime.now().time())
                detalle = f"Recibió: {dlg.recibe_final}"
                
                if hasattr(dlg, 'rutas_fotos') and dlg.rutas_fotos:
                    detalle += f" [CON {len(dlg.rutas_fotos)} FOTO/S CARGADAS POR PC]"
                    
                    res_mail = enviar_email_desktop(self.main.session, dlg.recibe_final, op.guia_remito, dlg.rutas_fotos, op.proveedor)
                    if res_mail:
                        mensajes_mail.append(f"Guía {op.guia_remito}: {res_mail}")
                
                self.main.log_movimiento(op, "ENTREGA CONFIRMADA (ADMIN)", detalle)
                count += 1
                
            self.main.session.commit()
            
            msg_final = f"{count} guía(s) entregada(s) correctamente en el sistema."
            if mensajes_mail:
                msg_final += "\n\n📋 Estado de Correos:\n" + "\n".join(list(set(mensajes_mail)))
                
            QMessageBox.information(self, "Resultado de la Gestión", msg_final)
            
            self.cargar_rendicion()
            if hasattr(self.main, 'cargar_monitor_global'): self.main.cargar_monitor_global()
        except Exception as e: 
            self.main.session.rollback()
            QMessageBox.warning(self, "Error de Sistema", f"Ocurrió un error al procesar: {e}")

    def marcar_pendiente_masivo(self):
        ids = []
        for r in range(self.tabla_rendicion.rowCount()):
            if self.tabla_rendicion.item(r, 1).checkState() == Qt.CheckState.Checked: ids.append(int(self.tabla_rendicion.item(r, 0).text()))
        if not ids: return
        try:
            op_ref = self.main.session.query(Operacion).get(ids[0]); precio_actual = op_ref.monto_servicio if op_ref else 0.0
            last_mov = self.main.session.query(Historial).filter(Historial.operacion_id == ids[0]).order_by(Historial.id.desc()).first()
            dlg = ReprogramarAdminDialog(precio_actual, last_mov.detalle if last_mov else "Sin motivo", self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                nuevo_precio = dlg.precio_final; ops = self.main.session.query(Operacion).filter(Operacion.id.in_(ids)).all()
                for op in ops: op.estado = Estados.EN_DEPOSITO; op.monto_servicio = nuevo_precio; op.chofer_asignado = None; self.main.log_movimiento(op, "REPROGRAMADO (ADMIN)", f"Nuevo Precio: {nuevo_precio}")
                self.main.session.commit(); self.cargar_rendicion()
                if hasattr(self.main, 'cargar_monitor_global'): self.main.cargar_monitor_global()
        except Exception: self.main.session.rollback()
        
    def deshacer_estado(self):
        ids = []
        for r in range(self.tabla_rendicion.rowCount()):
            if self.tabla_rendicion.item(r, 1).checkState() == Qt.CheckState.Checked: ids.append(int(self.tabla_rendicion.item(r, 0).text()))
        if not ids: return
        try:
            ops = self.main.session.query(Operacion).filter(Operacion.id.in_(ids)).all()
            for op in ops:
                op.estado = Estados.EN_DEPOSITO
                op.chofer_asignado = None
                self.main.log_movimiento(op, "DESHACER (ADMIN)", f"Restaurado a En Deposito")
            
            self.main.session.commit()
            self.cargar_rendicion()
            
            if hasattr(self.main, 'cargar_monitor_global'): 
                self.main.cargar_monitor_global()
                
            if hasattr(self.main, 'tab_ingreso'):
                self.main.tab_ingreso.cargar_movimientos_dia()
            if hasattr(self.main, 'cargar_ruta'):
                self.main.cargar_ruta()
                
        except Exception: 
            self.main.session.rollback()

class TabFacturacion(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main = main_window
        self.setup_ui()

    def setup_ui(self):
        l = QVBoxLayout(self); self.tabs_fact = QTabWidget(); l.addWidget(self.tabs_fact)
        tab_rendicion = QWidget(); layout_rend = QVBoxLayout(tab_rendicion); panel = QFrame(); hl = QHBoxLayout(panel)
        
        self.cierre_mes = QComboBox()
        self.cierre_mes.addItems(["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"])
        self.cierre_mes.setCurrentIndex(datetime.now().month - 1) 
        
        self.cierre_anio = QSpinBox(); self.cierre_anio.setRange(2020, 2030); self.cierre_anio.setValue(datetime.now().year)
        self.cierre_sucursal = QComboBox(); self.cierre_sucursal.addItems(["Todas", "Mendoza", "San Juan"]) 
        self.cierre_prov = QComboBox(); self.cierre_prov.addItem("Todos"); self.cierre_prov.addItems(self.main.lista_proveedores)
        btn_c = QPushButton("Calcular Listado"); btn_c.clicked.connect(self.calcular_cierre)
        
        btn_pdf = QPushButton("Rendición PDF")
        btn_pdf.setStyleSheet("background-color: #dc3545 !important; color: white !important;")
        btn_pdf.clicked.connect(self.generar_pdf_fact)
        
        hl.addWidget(QLabel("Sucursal:")); hl.addWidget(self.cierre_sucursal); hl.addWidget(QLabel("Mes:")); hl.addWidget(self.cierre_mes); hl.addWidget(QLabel("Año:")); hl.addWidget(self.cierre_anio); hl.addWidget(QLabel("Proveedor:")); hl.addWidget(self.cierre_prov); hl.addWidget(btn_c); hl.addWidget(btn_pdf)
        btn_cargo_fijo = QPushButton("➕ Agregar Cargo Fijo / Extra"); btn_cargo_fijo.clicked.connect(self.agregar_cargo_fijo); hl.addWidget(btn_cargo_fijo)
        
        self.tabla_cierre = QTableWidget()
        self.tabla_cierre.setColumnCount(10) 
        
        self.tabla_cierre.setHorizontalHeaderLabels(["Fecha", "Sucursal", "Guía / Remito", "Zona", "Bultos/Hs", "Estado", "Base ($)", "Extras ($)", "Total ($)", "Ajuste"])
        self.tabla_cierre.setStyleSheet(ESTILO_TABLAS_BLANCAS)
        self.pintor_cierre = PintorCeldasDelegate(self.tabla_cierre)
        self.tabla_cierre.setItemDelegate(self.pintor_cierre)

        header = self.tabla_cierre.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tabla_cierre.setColumnWidth(0, 90)
        self.tabla_cierre.setColumnWidth(1, 100)
        self.tabla_cierre.setColumnWidth(2, 140)
        self.tabla_cierre.setColumnWidth(3, 140)
        self.tabla_cierre.setColumnWidth(4, 90)
        self.tabla_cierre.setColumnWidth(5, 140)
        self.tabla_cierre.setColumnWidth(6, 100)
        self.tabla_cierre.setColumnWidth(7, 100)
        self.tabla_cierre.setColumnWidth(8, 100)
        header.setStretchLastSection(True)
        
        self.tabla_cierre.verticalHeader().setFixedWidth(30)
        self.tabla_cierre.verticalHeader().setDefaultSectionSize(45)
        
        self.tabla_cierre.setAlternatingRowColors(False)
        self.tabla_cierre.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.tabla_cierre.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); self.tabla_cierre.cellDoubleClicked.connect(self.doble_clic_ajuste_precio)
        
        self.lbl_resumen = QLabel("Total Base: $0  |  Total Extras: $0  |  TOTAL A FACTURAR: $0"); self.lbl_resumen.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px 15px; padding: 10px; border: 1px solid #ccc;")
        
        lay_abajo = QHBoxLayout()
        self.btn_deshacer_fac = QPushButton("⏪ Deshacer Facturación")
        self.btn_deshacer_fac.setStyleSheet("background-color: #ff9800; color: black; font-weight: bold; padding: 10px; border-radius: 5px;")
        self.btn_deshacer_fac.clicked.connect(self.abrir_dialogo_deshacer_facturacion)
        lay_abajo.addWidget(self.btn_deshacer_fac)
        lay_abajo.addStretch()
        lay_abajo.addWidget(self.lbl_resumen)
        
        layout_rend.addWidget(panel); layout_rend.addWidget(self.tabla_cierre); layout_rend.addLayout(lay_abajo); self.tabs_fact.addTab(tab_rendicion, "1. Calcular Rendición")

        tab_cta = QWidget(); layout_cta = QVBoxLayout(tab_cta); top_cta = QHBoxLayout()
        btn_ref_cta = QPushButton("🔄 Actualizar Saldos"); btn_ref_cta.clicked.connect(self.cargar_ctas_ctes)
        btn_pago = QPushButton("💰 Registrar Pago Recibido"); btn_pago.clicked.connect(self.registrar_pago_ctacte)
        top_cta.addWidget(btn_ref_cta); top_cta.addStretch(); top_cta.addWidget(btn_pago)
        
        self.tabla_ctacte = QTableWidget(); self.tabla_ctacte.setColumnCount(4); self.tabla_ctacte.setHorizontalHeaderLabels(["Proveedor", "Total Facturado Histórico ($)", "Pagos Recibidos ($)", "SALDO A COBRAR ($)"])
        
        self.tabla_ctacte.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tabla_ctacte.setColumnWidth(0, 250)
        self.tabla_ctacte.setColumnWidth(1, 180)
        self.tabla_ctacte.setColumnWidth(2, 180)
        self.tabla_ctacte.horizontalHeader().setStretchLastSection(True)
        
        self.tabla_ctacte.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.tabla_ctacte.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        
        self.tabla_ctacte.setStyleSheet(ESTILO_TABLAS_BLANCAS)
        self.pintor_cta = PintorCeldasDelegate(self.tabla_ctacte)
        self.tabla_ctacte.setItemDelegate(self.pintor_cta)

        layout_cta.addLayout(top_cta); layout_cta.addWidget(self.tabla_ctacte); self.tabs_fact.addTab(tab_cta, "2. Cuentas Corrientes (Saldos)")

    def abrir_dialogo_deshacer_facturacion(self):
        dlg = DeshacerFacturacionDialog(self.main, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.calcular_cierre()
            self.cargar_ctas_ctes()

    def agregar_cargo_fijo(self):
        proveedores = [self.cierre_prov.itemText(i) for i in range(self.cierre_prov.count()) if self.cierre_prov.itemText(i) != "Todos"]
        dlg = AgregarCargoDialog(proveedores, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                op = Operacion(fecha_ingreso=datetime.now(), sucursal=self.cierre_sucursal.currentText() if self.cierre_sucursal.currentText() != "Todas" else self.main.sucursal_actual, guia_remito="CARGO-FIJO", proveedor=dlg.in_prov.currentText(), destinatario=dlg.in_concepto.text(), domicilio="-", localidad="-", bultos=1, bultos_frio=0, peso=0.0, tipo_carga="COMUN", monto_servicio=dlg.in_monto.value(), estado=Estados.ENTREGADO, facturado=False, tipo_servicio="Cargo Extra")
                self.main.session.add(op); self.main.session.commit(); self.main.toast.mostrar("✅ Cargo extra agregado."); self.calcular_cierre()
            except Exception: self.main.session.rollback(); QMessageBox.warning(self, "Error", "No se pudo guardar.")

    def registrar_pago_ctacte(self):
        r = self.tabla_ctacte.currentRow()
        if r < 0: return
        prov = self.tabla_ctacte.item(r, 0).text(); dlg = CargarPagoDialog(prov, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                pago = ReciboPago(proveedor=prov, monto=dlg.in_monto.value(), detalle=dlg.in_detalle.text(), usuario=self.main.usuario.username)
                self.main.session.add(pago); self.main.session.commit(); self.main.toast.mostrar("✅ Pago registrado."); self.cargar_ctas_ctes()
            except Exception: self.main.session.rollback()

    def cargar_ctas_ctes(self):
        try:
            self.tabla_ctacte.setRowCount(0)
            sql_fac = text("SELECT proveedor, SUM(monto_servicio) FROM operaciones WHERE (facturado = TRUE) AND UPPER(TRIM(proveedor)) != 'JETPAQ' GROUP BY proveedor")
            facturados = self.main.session.execute(sql_fac).fetchall()
            dict_saldos = {f[0]: {"fac": f[1] or 0.0, "pag": 0.0} for f in facturados}
            sql_pag = text("SELECT proveedor, SUM(monto) FROM recibos_pago GROUP BY proveedor")
            pagados = self.main.session.execute(sql_pag).fetchall()
            for p in pagados:
                if p[0] not in dict_saldos: dict_saldos[p[0]] = {"fac": 0.0, "pag": 0.0}
                dict_saldos[p[0]]["pag"] += (p[1] or 0.0)
            for i, (prov, montos) in enumerate(dict_saldos.items()):
                self.tabla_ctacte.insertRow(i); fac = montos["fac"]; pag = montos["pag"]; saldo = fac - pag
                self.tabla_ctacte.setItem(i, 0, QTableWidgetItem(prov)); self.tabla_ctacte.setItem(i, 1, QTableWidgetItem(f"$ {fac:,.2f}")); self.tabla_ctacte.setItem(i, 2, QTableWidgetItem(f"$ {pag:,.2f}"))
                it_saldo = QTableWidgetItem(f"$ {saldo:,.2f}"); it_saldo.setFont(QFont("Arial", 11, QFont.Weight.Bold))
                if saldo > 0: it_saldo.setForeground(QColor("red"))
                else: it_saldo.setForeground(QColor("green"))
                self.tabla_ctacte.setItem(i, 3, it_saldo)
        except Exception: self.main.session.rollback()

    def doble_clic_ajuste_precio(self, row, col):
        id_op = self.mapa_filas_cierre.get(row)
        if id_op: self.abrir_dialogo_ajuste_precio(id_op)

    def abrir_dialogo_ajuste_precio(self, id_op):
        try:
            op = self.main.session.query(Operacion).get(id_op)
            if not op: return
            dlg = EditarPrecioFacturacionDialog(op, self.main, self)
            if dlg.exec() == QDialog.DialogCode.Accepted: op.monto_servicio = dlg.precio_final; self.main.session.commit(); self.calcular_cierre(); self.main.toast.mostrar("✅ Precio actualizado")
        except Exception: self.main.session.rollback()

    def calcular_cierre(self):
        mes = self.cierre_mes.currentIndex() + 1
        anio = self.cierre_anio.value()
        prov = self.cierre_prov.currentText().strip()
        sucursal = self.cierre_sucursal.currentText()
        
        self.tabla_cierre.setRowCount(0)
        self.main.setWindowTitle("⏳ Calculando facturación, por favor espere...")
        QApplication.processEvents()
        
        try:
            _, last_day = calendar.monthrange(anio, mes)
            start_date = date(anio, mes, 1)
            end_date = date(anio, mes, last_day)

            query = self.main.session.query(Operacion).filter(
                Operacion.fecha_ingreso >= start_date, 
                Operacion.fecha_ingreso <= end_date,
                (Operacion.facturado == False) | (Operacion.facturado == None),
                Operacion.estado.ilike('ENTREGADO')
            )
            
            if prov != "Todos": 
                query = query.filter(Operacion.proveedor.ilike(prov))
            else:
                query = query.filter(~Operacion.proveedor.ilike('JetPaq'))
                
            if sucursal != "Todas": 
                query = query.filter(Operacion.sucursal == sucursal)
                
            query = query.order_by(Operacion.fecha_ingreso.asc())
            self.resultados_cierre = query.all()
            
            if not self.resultados_cierre:
                self.tabla_cierre.setRowCount(1)
                item_empty = QTableWidgetItem("❌ Ninguna guía en este periodo para facturar (JetPaq es interno)")
                item_empty.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.tabla_cierre.setItem(0, 0, item_empty)
                self.tabla_cierre.setSpan(0, 0, 1, 10) 
                
                self.lbl_resumen.setText("Total Base: $0  |  Total Extras: $0  |  TOTAL A FACTURAR: $0")
                self.main.setWindowTitle(f"E.K. LOGISTICA (NUBE) - Usuario: {self.main.usuario.username.upper()}")
                return

            op_ids = [op.id for op in self.resultados_cierre]
            
            conteo_repartos = {}
            if op_ids:
                hist_records = self.main.session.query(Historial.operacion_id, Historial.accion).filter(
                    Historial.operacion_id.in_(op_ids),
                    Historial.accion.in_(['SALIDA A REPARTO', 'DESHACER (ADMIN)', 'REPROGRAMADO (ADMIN)', 'SALIDA A TERCERIZADO'])
                ).all()
                for op_id, accion in hist_records:
                    if op_id not in conteo_repartos: conteo_repartos[op_id] = 0
                    if accion == 'SALIDA A REPARTO': conteo_repartos[op_id] += 1
                    elif accion in ['DESHACER (ADMIN)', 'REPROGRAMADO (ADMIN)']: 
                        conteo_repartos[op_id] -= 1

            tot_base = 0; tot_extras = 0; tot_final = 0; self.mapa_filas_cierre = {} 
            hubo_cambios_precios = False
            
            for row, op in enumerate(self.resultados_cierre):
                self.tabla_cierre.insertRow(row)
                self.mapa_filas_cierre[row] = op.id 
                
                fecha_str = op.fecha_ingreso.strftime("%d/%m/%Y") if op.fecha_ingreso else "-"
                self.tabla_cierre.setItem(row, 0, QTableWidgetItem(fecha_str))
                self.tabla_cierre.setItem(row, 1, QTableWidgetItem((op.sucursal or "").upper()))
                self.tabla_cierre.setItem(row, 2, QTableWidgetItem(op.guia_remito or "RET"))
                self.tabla_cierre.setItem(row, 3, QTableWidgetItem(op.localidad or ""))
                
                bultos_tot = op.bultos if op.bultos is not None else 1
                bultos_fr = op.bultos_frio if op.bultos_frio is not None else 0
                
                det_b = str(bultos_tot)
                if bultos_fr > 0 and bultos_fr < bultos_tot: det_b += f" ({bultos_tot-bultos_fr}C/{bultos_fr}R)"
                elif bultos_fr == bultos_tot: det_b += " (R)"
                
                self.tabla_cierre.setItem(row, 4, QTableWidgetItem(det_b))
                
                visitas = conteo_repartos.get(op.id, 1)
                if visitas < 1: visitas = 1 
                
                estado_txt = op.estado or ""
                bg_color_row = QColor("#ffffff")
                
                if visitas > 1:
                    estado_txt = f"{estado_txt} (⚠️ {visitas} Visitas)"
                    bg_color_row = QColor("#fff3cd")
                
                self.tabla_cierre.setItem(row, 5, QTableWidgetItem(estado_txt))
                
                monto_serv = op.monto_servicio or 0.0
                
                if op.guia_remito == "CARGO-FIJO" or (op.tipo_servicio and "Flete" in op.tipo_servicio): 
                    precio_base_actual = monto_serv
                else:
                    cant_comun = bultos_tot - bultos_fr
                    peso_val = op.peso or 0.0
                    precio_base_actual = self.main.obtener_precio(op.localidad, cant_comun, bultos_fr, op.sucursal, proveedor=op.proveedor, peso=peso_val, bultos_totales=bultos_tot)
                
                if monto_serv == 0 and precio_base_actual > 0:
                    nuevo_monto = precio_base_actual
                    if op.tipo_servicio == 'Entrega (Guardia)':
                        wd = op.fecha_ingreso.weekday()
                        if wd >= 5: 
                            nuevo_monto += precio_base_actual
                        if op.tipo_carga and "REFRIGERADO" in op.tipo_carga:
                            nuevo_monto += 1500.0
                            
                    op.monto_servicio = nuevo_monto
                    monto_serv = nuevo_monto
                    hubo_cambios_precios = True
                    
                    precio_base = precio_base_actual
                    extras = monto_serv - precio_base
                elif 0 < monto_serv < precio_base_actual: 
                    precio_base = monto_serv
                    extras = 0
                else: 
                    precio_base = precio_base_actual
                    extras = monto_serv - precio_base
                
                self.tabla_cierre.setItem(row, 6, QTableWidgetItem(f"$ {precio_base:,.2f}"))
                it_extras = QTableWidgetItem(f"$ {extras:,.2f}")
                if extras > 0: it_extras.setForeground(QColor("blue"))
                elif extras < 0: it_extras.setForeground(QColor("red"))
                self.tabla_cierre.setItem(row, 7, it_extras)
                
                it_final = QTableWidgetItem(f"$ {monto_serv:,.2f}")
                it_final.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                it_final.setFont(QFont("Arial", 9, QFont.Weight.Bold))
                self.tabla_cierre.setItem(row, 8, it_final)
                
                btn_ajuste = QPushButton("✏️ Editar")
                btn_ajuste.setFixedSize(85, 30) 
                btn_ajuste.setStyleSheet("background-color: #0d6efd !important; color: white !important; font-weight: bold !important; font-size: 11px !important; border-radius: 4px !important; margin: 0px !important;")
                
                widget_centrado = QWidget()
                layout_centrado = QHBoxLayout(widget_centrado)
                layout_centrado.setContentsMargins(0, 0, 0, 0)
                layout_centrado.setAlignment(Qt.AlignmentFlag.AlignCenter)
                layout_centrado.addWidget(btn_ajuste)
                
                btn_ajuste.clicked.connect(lambda checked, r=row: self.abrir_dialogo_ajuste_precio(self.mapa_filas_cierre[r]))
                self.tabla_cierre.setCellWidget(row, 9, widget_centrado)
                
                if visitas > 1:
                    brush_bg = QBrush(bg_color_row)
                    for col_idx in range(10):
                        it_celda = self.tabla_cierre.item(row, col_idx)
                        if it_celda:
                            it_celda.setBackground(brush_bg)
                            if col_idx == 5:
                                font_bold = QFont(); font_bold.setBold(True); it_celda.setFont(font_bold)
                                it_celda.setForeground(QColor("#d32f2f"))
                            else:
                                it_celda.setForeground(QColor("#000000")) 
                
                tot_base += precio_base
                tot_extras += extras
                tot_final += monto_serv
                
            self.totales_cierre = (tot_base, tot_extras, tot_final)
            self.lbl_resumen.setText(f"Total Base: ${tot_base:,.2f}  |  Total Extras: ${tot_extras:,.2f}  |  TOTAL A FACTURAR: ${tot_final:,.2f}")
            
            if hubo_cambios_precios:
                self.main.session.commit()
                
        except Exception as e:
            self.main.session.rollback()
            self.tabla_cierre.setRowCount(0)
            QMessageBox.critical(self, "Error Cálculo", f"Hubo un problema al traer la facturación:\n{e}")
        finally:
            self.main.setWindowTitle(f"E.K. LOGISTICA (NUBE) - Usuario: {self.main.usuario.username.upper()}")

    def generar_pdf_fact(self):
        if not hasattr(self, 'resultados_cierre') or not self.resultados_cierre: return
        reply = QMessageBox.question(self, "Cerrar Facturación", "¿Desea marcar estas guías como FACTURADAS?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        marcar_facturado = (reply == QMessageBox.StandardButton.Yes); mes_nombre = self.cierre_mes.currentText(); anio_num = self.cierre_anio.value(); prov_nombre = self.cierre_prov.currentText()
        nombre, _ = QFileDialog.getSaveFileName(self, "Rendicion", f"Facturacion_{prov_nombre}.pdf", "PDF (*.pdf)"); 
        if not nombre: return
        data_filas = [['FECHA', 'GUÍA', 'ZONA', 'BULTOS', 'BASE ($)', 'EXTRAS ($)', 'TOTAL ($)']]
        for op in self.resultados_cierre:
            monto_serv = op.monto_servicio or 0.0
            if op.guia_remito == "CARGO-FIJO": precio_base_actual = monto_serv
            else:
                bultos_tot = op.bultos if op.bultos is not None else 1
                bultos_fr = op.bultos_frio if op.bultos_frio is not None else 0
                peso_val = op.peso or 0.0
                cant_comun = bultos_tot - bultos_fr
                precio_base_actual = self.main.obtener_precio(op.localidad, cant_comun, bultos_fr, op.sucursal, proveedor=op.proveedor, peso=peso_val, bultos_totales=bultos_tot)
            if monto_serv == 0 and precio_base_actual > 0: precio_base = precio_base_actual; extras = 0
            elif 0 < monto_serv < precio_base_actual: precio_base = monto_serv; extras = 0
            else: precio_base = precio_base_actual; extras = monto_serv - precio_base
            desc_guia = op.guia_remito or "RET"
            
            bultos_tot = op.bultos if op.bultos is not None else 1
            bultos_fr = op.bultos_frio if op.bultos_frio is not None else 0
            det_b = str(bultos_tot)
            
            if bultos_fr > 0 and bultos_fr < bultos_tot: det_b += f" ({bultos_tot-bultos_fr}C/{bultos_fr}R)"
            elif bultos_fr == bultos_tot: det_b += " (R)"
            
            data_filas.append([op.fecha_ingreso.strftime("%d/%m/%Y") if op.fecha_ingreso else "-", desc_guia, op.localidad[:15] if op.localidad else "-", det_b, f"$ {precio_base:,.0f}", f"$ {extras:,.0f}", f"$ {monto_serv:,.0f}"])
            if marcar_facturado: op.facturado = True
        if marcar_facturado: 
            try: self.main.session.commit(); QMessageBox.information(self, "Éxito", "Guías marcadas como FACTURADAS."); self.calcular_cierre(); self.cargar_ctas_ctes()
            except: self.main.session.rollback()
        tot_base, tot_extras, tot_final = self.totales_cierre; iva = tot_final * 0.21; total_con_iva = tot_final + iva
        data_filas.append(['SUBTOTALES:', '', '', '', f"$ {tot_base:,.0f}", f"$ {tot_extras:,.0f}", f"$ {tot_final:,.0f}"]); data_filas.append(['IVA (21%):', '', '', '', '', '', f"$ {iva:,.0f}"]); data_filas.append(['TOTAL A FACTURAR:', '', '', '', '', '', f"$ {total_con_iva:,.0f}"]) 
        crear_pdf_facturacion(nombre, data_filas, prov_nombre, f"{mes_nombre} {anio_num}", self.main.usuario.username, datetime.now().strftime('%d/%m/%Y %H:%M')); os.startfile(nombre)