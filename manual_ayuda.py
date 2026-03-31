from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QTextBrowser, QPushButton, QSplitter
from PyQt6.QtCore import Qt

class ManualAyudaDialog(QDialog):
    def __init__(self, indice_pestana_actual=0, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📖 Manual de Operaciones Automático - E.K. Logística")
        self.resize(900, 650)
        self.setModal(True)
        
        layout = QVBoxLayout(self)
        
        # Panel dividido: Lista a la izquierda, Texto a la derecha
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        self.lista_temas = QListWidget()
        self.lista_temas.setStyleSheet("""
            QListWidget { font-size: 14px; font-weight: bold; background-color: #f8f9fa; border: 1px solid #ccc; border-radius: 5px; }
            QListWidget::item { padding: 15px; border-bottom: 1px solid #ddd; }
            QListWidget::item:selected { background-color: #0d6efd; color: white; }
        """)
        
        temas = [
            "0. 🏠 Inicio y Monitor",
            "1. 📥 Ingreso a Depósito",
            "2. 🚚 Armado de Rutas",
            "3. 💰 Facturación y Rendición (IMPORTANTE)",
            "4. 👥 CRM y Clientes",
            "5. 🚗 Flota y Mantenimiento",
            "6. 📊 Estadísticas",
            "7. ⚙️ Configuración"
        ]
        self.lista_temas.addItems(temas)
        
        self.visor_texto = QTextBrowser()
        self.visor_texto.setOpenExternalLinks(True)
        self.visor_texto.setStyleSheet("background-color: white; border: 1px solid #ccc; border-radius: 5px; padding: 10px;")
        
        splitter.addWidget(self.lista_temas)
        splitter.addWidget(self.visor_texto)
        splitter.setSizes([250, 650])
        
        layout.addWidget(splitter)
        
        btn_cerrar = QPushButton("Cerrar Manual")
        btn_cerrar.setStyleSheet("background-color: #6c757d; color: white; font-weight: bold; padding: 10px; font-size: 14px;")
        btn_cerrar.clicked.connect(self.accept)
        layout.addWidget(btn_cerrar)
        
        self.lista_temas.currentRowChanged.connect(self.mostrar_contenido)
        
        # Mapeo inteligente: Si el usuario estaba en la pestaña 3 (Facturación), le abre el manual en ese tema.
        # Ajustamos el índice por defecto si no coincide exactamente, pero intenta coincidir.
        if 0 <= indice_pestana_actual < self.lista_temas.count():
            self.lista_temas.setCurrentRow(indice_pestana_actual)
        else:
            self.lista_temas.setCurrentRow(0)

    def mostrar_contenido(self, index):
        html = ""
        
        if index == 0:
            html = """
            <h1 style="color: #0d6efd;">🏠 Monitor Global</h1>
            <p><b>¿Para qué sirve?</b> Es tu panel de control principal. Te muestra una radiografía de todo lo que está pasando en la empresa HOY.</p>
            <h3>Paso a paso:</h3>
            <ul>
                <li><b>Actualizar:</b> Usa el botón "Refrescar" para ver los datos más recientes.</li>
                <li><b>Buscador:</b> Si un cliente llama preguntando por su paquete, escribe el número de guía o su nombre en el buscador superior para encontrarlo al instante, sin importar si está en el depósito o en la calle.</li>
                <li><b>Tarjetas de Resumen:</b> Te muestran cuántos paquetes hay para entregar, cuántos se entregaron hoy, y la efectividad de los choferes.</li>
            </ul>
            """
        elif index == 1:
            html = """
            <h1 style="color: #198754;">📥 Ingreso a Depósito</h1>
            <p><b>¿Para qué sirve?</b> Aquí cargas la mercadería física que entra al galpón antes de dársela a los choferes.</p>
            <h3>¿Qué hace cada botón/campo?</h3>
            <ul>
                <li><b>Tipo de Servicio:</b> Si es una entrega normal, un retiro en cliente o un flete especial. Cambia los campos según lo que elijas.</li>
                <li><b>Proveedor y Destinos Fijos:</b> Si eliges un proveedor y luego usas la lista de "Destinos Fijos", el sistema autocompleta la dirección y la zona para que no tengas que tipear a mano.</li>
                <li><b>Bultos y Tipo de Carga (Normal/Frío/Combinado):</b> Es crucial poner esto bien, porque de aquí el sistema calcula el precio final a facturar.</li>
                <li><b>Contingencia de Frío:</b> Si la mercadería perdió frío y tuviste que meterla en la cámara, tilda esto. Suma un cargo extra automático.</li>
                <li><b>📥 IMPORTAR TXT DHL:</b> Este botón (solo visible en San Juan) lee un archivo de texto de DHL y carga 100 guías de golpe en 2 segundos. Te avisa si hay guías duplicadas para no cobrarlas dos veces.</li>
            </ul>
            """
        elif index == 2:
            html = """
            <h1 style="color: #fd7e14;">🚚 Armado de Rutas</h1>
            <p><b>¿Para qué sirve?</b> Para asignar la mercadería del depósito a la camioneta de un chofer.</p>
            <h3>Paso a paso:</h3>
            <ol>
                <li>En la tabla de arriba verás todo lo que está "EN DEPÓSITO".</li>
                <li>Selecciona a qué chofer le vas a dar la carga usando la lista desplegable del medio.</li>
                <li>Haz clic en los paquetes de arriba y usa el botón <b>"⬇ Asignar a Ruta"</b>. Pasarán a la tabla de abajo.</li>
                <li>Cuando hayas bajado todos los paquetes del chofer, presiona <b>"Imprimir Hoja de Ruta"</b>. Esto genera un PDF para que el chofer lo firme y, al mismo tiempo, manda la información al celular del chofer para que pueda usar su App.</li>
            </ol>
            """
        elif index == 3:
            html = """
            <h1 style="color: #6f42c1;">💰 Rendición y Facturación</h1>
            <div style="background-color: #fff3cd; padding: 10px; border-left: 5px solid #ffc107; margin-bottom: 15px;">
                <b>⚠️ SECCIÓN CRÍTICA:</b> Lee esto con atención para no perder dinero en la facturación.
            </div>
            <p><b>¿Para qué sirve?</b> Para cobrarle a los proveedores por el trabajo realizado y llevar las cuentas corrientes.</p>
            
            <h3>Lógica del Sistema: ¿Cómo calcula la plata?</h3>
            <p>Cuando presionas el botón <b>"Calcular Listado"</b>, el sistema hace esto automáticamente por detrás:</p>
            <ol>
                <li>Busca todas las guías de ese mes/proveedor que estén en estado <b>ENTREGADO</b> y que aún no estén facturadas.</li>
                <li><b>El Precio Base:</b> Revisa la Zona (Localidad) del paquete, mira cuántos bultos son comunes y cuántos son refrigerados. Va a la "Tabla de Tarifas" oculta y saca el precio exacto.</li>
                <li><b>Visitas Extra:</b> Si el chofer fue a una casa, no había nadie (volvió al depósito), y tuvo que volver a ir al día siguiente... ¡El sistema lo sabe! Detecta que hubo "2 Visitas" y cobra la tarifa base multiplicada por 2.</li>
                <li><b>Extras / Contingencia:</b> Si en el Ingreso le tildaron "Contingencia de Frío", suma ese valor ($1500 o lo que sea) a la columna "Extras".</li>
            </ol>
            
            <h3>¿Qué hace cada botón?</h3>
            <ul>
                <li><b>Calcular Listado:</b> Hace toda la matemática explicada arriba. <i>Nota: Verás una barra verde cargando. Esto bloquea la pantalla para que no presiones dos veces y arruines el cálculo.</i></li>
                <li><b>✏️ Editar (En la tabla):</b> Si el sistema calculó $5000, pero arreglaste cobrar $6000 con el cliente por algo excepcional, haces clic ahí y fuerzas el precio a mano.</li>
                <li><b>➕ Agregar Cargo Fijo:</b> Si tienes que cobrarle a un cliente un alquiler de depósito o un paletizado que no tiene número de guía, usas esto para meter un renglón de plata extra a la factura.</li>
                <li><b>📄 Rendición PDF:</b> Genera el documento oficial. <b>ATENCIÓN:</b> Al presionarlo te preguntará si deseas "Marcar como Facturado". Si dices que SÍ, esas guías se bloquean y pasan a la pestaña 2 (Cuentas Corrientes). Ya no saldrán en futuros cálculos.</li>
                <li><b>⏪ Deshacer Facturación:</b> Si marcaste guías por error, usas este botón, buscas las guías equivocadas, las desmarcas, y vuelven a estar disponibles para facturar.</li>
            </ul>
            
            <h3>Cuentas Corrientes (Pestaña 2):</h3>
            <p>Aquí ves el resumen general de plata. "Total Facturado" es la suma histórica de los PDFs que generaste. Usa el botón <b>💰 Registrar Pago</b> cuando el cliente te haga una transferencia. El sistema restará ese pago y te mostrará el <b>SALDO</b> real que te deben en rojo (deuda) o en verde (al día).</p>
            """
        elif index == 4:
            html = """
            <h1 style="color: #20c997;">👥 CRM y Clientes</h1>
            <p><b>¿Para qué sirve?</b> Es tu agenda comercial y configurador de inteligencia.</p>
            <h3>Funciones Clave:</h3>
            <ul>
                <li><b>Destinos Frecuentes:</b> Aquí puedes corregir o borrar direcciones que el sistema guardó automáticamente. Es la base de datos que usa la pestaña de Ingreso para autocompletar.</li>
                <li><b>Clientes Principales (Proveedores):</b> Si entras a editar un proveedor (ej: Andreani), puedes activar opciones como <i>"Exige foto de remito"</i> o <i>"Enviar mail automático"</i>. Al hacer esto, obligas a la App del chofer a que no lo deje entregar sin sacar una foto, y automatizas el envío de correos sin que tú hagas nada.</li>
            </ul>
            """
        elif index == 5:
            html = """
            <h1 style="color: #17a2b8;">🚗 Flota y Mantenimiento</h1>
            <p><b>¿Para qué sirve?</b> Para evitar que las camionetas se rompan y controlar los gastos mecánicos.</p>
            <h3>La "Radiografía" y sus Alertas:</h3>
            <ul>
                <li>A la derecha verás una ficha del vehículo.</li>
                <li><b>Barras Verdes/Rojas:</b> El chofer, desde su App celular, actualiza el kilometraje. Si los KM pasan el límite del service de aceite o distribución, la barra se pone en ROJO.</li>
                <li><b>🔧 Registrar Service:</b> Cuando mandes la chata al taller, usa este botón. Cargas cuánto gastaste y en qué. Usa los "Botones Automáticos" de abajo para que el sistema le sume 10.000km de gracia al próximo cambio de aceite sin que tengas que usar la calculadora.</li>
                <li><b>Alertas del Chofer:</b> Si el chofer nota un ruido y lo reporta desde su celular, aparecerá un cartel rojo inmenso aquí. Cuando lo arregles, presiona el botón verde "Marcar como resuelto" para limpiarlo.</li>
                <li><b>📜 Historial Gral:</b> Es la caja negra. Muestra quién cargó kilómetros, cuándo reportaron fallas y todos los gastos de taller.</li>
            </ul>
            """
        elif index == 6:
            html = """
            <h1 style="color: #d63384;">📊 Estadísticas</h1>
            <p>Simplemente selecciona las fechas arriba y dale a "Generar Reporte". El sistema te mostrará gráficos de torta indicando qué chofer es más eficiente, qué cliente te da más volumen, y cuántos paquetes rebotan por zona.</p>
            """
        elif index == 7:
            html = """
            <h1 style="color: #343a40;">⚙️ Configuración y Tarifas</h1>
            <p><b>¿Para qué sirve?</b> Para ajustar los precios del sistema y dar de alta empleados.</p>
            <ul>
                <li><b>Gestión de Usuarios:</b> Crea usuarios para que tus empleados entren al sistema de PC. Puedes darles permisos limitados (Ej: Que solo vean "Ingreso", pero que no puedan entrar a "Facturación" para ver la plata).</li>
                <li><b>Gestión de Choferes:</b> Si contratas a alguien nuevo, agrégalo aquí (con su DNI) para que pueda loguearse en la App del celular.</li>
                <li><b>Tarifas Clásicas:</b> Define cuánto cobras por zona (Capital, Godoy Cruz, etc) para un paquete común y para un paquete refrigerado. <i>(Nota: Esto es lo que usa la pestaña Facturación para calcular la plata).</i></li>
            </ul>
            """

        self.visor_texto.setHtml(f"<div style='font-family: Arial; font-size: 16px; line-height: 1.6;'>{html}</div>")