import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, Date, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DB_URL")
if not DATABASE_URL:
    raise ValueError("❌ ERROR CRÍTICO: No se encontró la variable DB_URL en el archivo .env")

engine = create_engine(
    DATABASE_URL, 
    pool_size=10, 
    max_overflow=600, 
    pool_pre_ping=True,
    pool_recycle=300
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_session():
    return engine, SessionLocal()

class Estados:
    EN_DEPOSITO = "EN DEPOSITO"
    EN_REPARTO = "EN REPARTO"
    ENTREGADO = "ENTREGADO"
    LISTA_TODOS = [EN_DEPOSITO, EN_REPARTO, ENTREGADO]

class Urgencia:
    CLASICO = "Clasico"
    URGENTE = "Urgente"
    LISTA_TODOS = [CLASICO, URGENTE]

class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)
    password = Column(String(50))
    sucursal_asignada = Column(String(50))
    es_admin_total = Column(Boolean, default=False)
    
    ver_monitor = Column(Boolean, default=True)
    ver_ingreso = Column(Boolean, default=True)
    ver_ruta = Column(Boolean, default=True)
    ver_rendicion = Column(Boolean, default=False)
    ver_facturacion = Column(Boolean, default=False)
    ver_reportes = Column(Boolean, default=False)
    ver_crm = Column(Boolean, default=True)          
    ver_estadisticas = Column(Boolean, default=True) 
    ver_configuracion = Column(Boolean, default=False)

class Tarifa(Base):
    __tablename__ = "tarifas"
    id = Column(Integer, primary_key=True, index=True)
    sucursal = Column(String(50))
    localidad = Column(String(100))
    precio_base_comun = Column(Float, default=0.0)
    precio_base_refrig = Column(Float, default=0.0)

class TarifaDHL(Base):
    __tablename__ = "tarifas_dhl"
    id = Column(Integer, primary_key=True, index=True)
    sucursal = Column(String(50))
    t2 = Column(Float, default=0.0)
    t5 = Column(Float, default=0.0)
    t10 = Column(Float, default=0.0)
    t20 = Column(Float, default=0.0)
    t30 = Column(Float, default=0.0)
    excedente = Column(Float, default=0.0)

class HistorialTarifas(Base):
    __tablename__ = "historial_tarifas"
    id = Column(Integer, primary_key=True, index=True)
    fecha_hora = Column(DateTime, default=datetime.now)
    zona = Column(String(100))
    detalle = Column(String(200))
    usuario = Column(String(50))

class Chofer(Base):
    __tablename__ = "choferes"
    id = Column(Integer, primary_key=True, index=True)
    sucursal = Column(String(50))
    nombre = Column(String(100))

class ClienteRetiro(Base):
    __tablename__ = "clientes_retiro"
    id = Column(Integer, primary_key=True, index=True)
    sucursal = Column(String(50))
    nombre = Column(String(100))
    domicilio = Column(String(200))
    celular = Column(String(50))
    localidad = Column(String(100))

class ClientePrincipal(Base):
    __tablename__ = "clientes_principales"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), unique=True)
    email_reportes = Column(String(150), nullable=True)
    
    es_facturable = Column(Boolean, default=True)
    enviar_mail = Column(Boolean, default=False)
    exige_remito = Column(Boolean, default=False)
    cadena_frio = Column(Boolean, default=False)
    cobro_puerta = Column(Boolean, default=False)

class DestinoFrecuente(Base):
    __tablename__ = "destinos_frecuentes"
    id = Column(Integer, primary_key=True, index=True)
    proveedor = Column(String(100))
    sucursal = Column(String(50))
    alias = Column(String(50))
    destinatario = Column(String(100))
    domicilio = Column(String(200))
    localidad = Column(String(100))
    celular = Column(String(50))

class Operacion(Base):
    __tablename__ = "operaciones"
    id = Column(Integer, primary_key=True, index=True)
    fecha_ingreso = Column(Date, default=datetime.today)
    sucursal = Column(String(50))
    guia_remito = Column(String(100))
    proveedor = Column(String(100))
    destinatario = Column(String(100))
    celular = Column(String(50))
    domicilio = Column(String(200))
    localidad = Column(String(100))
    bultos = Column(Integer, default=1)
    bultos_frio = Column(Integer, default=0)
    peso = Column(Float, default=0.0)
    tipo_carga = Column(String(50), default="COMUN")
    tipo_urgencia = Column(String(50), default=Urgencia.CLASICO)
    monto_servicio = Column(Float, default=0.0)
    es_contra_reembolso = Column(Boolean, default=False)
    monto_recaudacion = Column(Float, default=0.0)
    info_intercambio = Column(String(200))
    estado = Column(String(50), default=Estados.EN_DEPOSITO)
    chofer_asignado = Column(String(100), nullable=True)
    fecha_salida = Column(DateTime, nullable=True)
    fecha_entrega = Column(DateTime, nullable=True)
    facturado = Column(Boolean, default=False)
    tipo_servicio = Column(String(50), default="Entrega (Reparto)")
    historial = relationship("Historial", back_populates="operacion", cascade="all, delete-orphan")

class Historial(Base):
    __tablename__ = "historial_movimientos"
    id = Column(Integer, primary_key=True, index=True)
    operacion_id = Column(Integer, ForeignKey("operaciones.id"))
    fecha_hora = Column(DateTime, default=datetime.now)
    usuario = Column(String(50))
    accion = Column(String(100))
    detalle = Column(String(255))
    operacion = relationship("Operacion", back_populates="historial")

class ReciboPago(Base):
    __tablename__ = "recibos_pago"
    id = Column(Integer, primary_key=True, index=True)
    fecha = Column(DateTime, default=datetime.now)
    proveedor = Column(String(100))
    monto = Column(Float, default=0.0)
    detalle = Column(String(200))
    usuario = Column(String(50))

class Vehiculo(Base):
    __tablename__ = "vehiculos"
    id = Column(Integer, primary_key=True, index=True)
    sucursal = Column(String(50)) 
    patente = Column(String(20), unique=True, index=True)
    marca = Column(String(50))
    modelo = Column(String(50))
    año = Column(Integer)
    
    chofer_id = Column(Integer, ForeignKey("choferes.id"), nullable=True) 

    vencimiento_seguro = Column(Date, nullable=True)
    vencimiento_rto = Column(Date, nullable=True) 
    vencimiento_cedula = Column(Date, nullable=True)
    vencimiento_oblea_gnc = Column(Date, nullable=True)
    
    vencimiento_matafuegos = Column(Date, nullable=True)
    vencimiento_carnet = Column(Date, nullable=True)

    kilometraje_actual = Column(Integer, default=0)
    km_proximo_service = Column(Integer, default=0) 
    
    km_proximo_neumaticos = Column(Integer, default=0) # Obsoleto visualmente, mantenido por seguridad DB
    km_proximo_distribucion = Column(Integer, default=0) 
    km_proximo_alineacion = Column(Integer, default=0) # NUEVO: Alineación y balanceo (20k)
    km_proximo_poli_v = Column(Integer, default=0)     # NUEVO: Correa Poli V (60k)
    
    falla_reportada = Column(String(255), nullable=True)
    
    estado = Column(String(50), default="ACTIVO") 
    
    chofer = relationship("Chofer", backref="vehiculos")
    mantenimientos = relationship("Mantenimiento", back_populates="vehiculo", cascade="all, delete-orphan")

class Mantenimiento(Base):
    __tablename__ = "mantenimientos_flota"
    id = Column(Integer, primary_key=True, index=True)
    vehiculo_id = Column(Integer, ForeignKey("vehiculos.id"))
    fecha = Column(Date, default=datetime.today)
    tipo_servicio = Column(String(100)) 
    kilometraje = Column(Integer) 
    costo = Column(Float, default=0.0)
    taller_proveedor = Column(String(100))
    detalle = Column(String(255)) 
    vehiculo = relationship("Vehiculo", back_populates="mantenimientos")

# 🔥 AUTO-PARCHE (BORRAR DESPUÉS DE ABRIR EL PROGRAMA 1 VEZ) 🔥
try:
    from sqlalchemy import text
    _e, _s = get_session()
    _s.execute(text("ALTER TABLE vehiculos ADD COLUMN IF NOT EXISTS km_proximo_alineacion INTEGER DEFAULT 0;"))
    _s.execute(text("ALTER TABLE vehiculos ADD COLUMN IF NOT EXISTS km_proximo_poli_v INTEGER DEFAULT 0;"))
    _s.commit()
    _s.close()
except: pass