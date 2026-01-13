from pydantic import BaseModel, Field, EmailStr, ConfigDict
from typing import List, Optional, Literal
from datetime import datetime
import uuid

class UserBase(BaseModel):
    email: EmailStr
    cuit_cuil: str
    nombre: str
    apellido: str
    telefono: str
    role: Literal["ciudadano", "inspector", "administrador"] = "ciudadano"

class UserCreate(UserBase):
    password: str

class User(UserBase):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)

class UserInDB(User):
    hashed_password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    user: User

class LoginRequest(BaseModel):
    cuit_cuil: str
    password: str

class AFAPBase(BaseModel):
    # Datos del solicitante
    solicitante_nombre: str
    solicitante_apellido: str
    solicitante_cuit_cuil: str
    solicitante_telefono: str
    solicitante_email: EmailStr
    
    # Datos del titular
    titular_tipo: Literal["fisica", "juridica"]
    titular_nombre: Optional[str] = None
    titular_cuit: Optional[str] = None
    cuenta_abl: str
    
    # Domicilio del comercio
    domicilio_calle: str
    domicilio_altura: str
    domicilio_piso: Optional[str] = None
    domicilio_depto: Optional[str] = None
    domicilio_local: Optional[str] = None
    domicilio_localidad: str = "Argentina"
    
    # Rubro
    rubro_tipo: str
    rubro_subrubro: str
    rubro_descripcion: str
    metros_cuadrados: float
    
    # Características constructivas
    techos_cielorasos: str
    pisos_material: str
    
    # Servicios sanitarios
    tiene_sanitarios: bool
    sanitarios_acceso_directo: bool = False
    sanitarios_antecamara: bool = False
    sanitarios_lavabos_m: int = 0
    sanitarios_retretes_m: int = 0
    sanitarios_lavabos_f: int = 0
    sanitarios_retretes_f: int = 0
    sanitarios_migitorios: int = 0
    sanitarios_discapacitados: bool = False
    cantidad_trabajadores: int = 1
    
    # Documentación
    documentos_urls: List[str] = Field(default_factory=list)

class AFAPCreate(AFAPBase):
    pass

class AFAP(AFAPBase):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    numero_afap: int
    user_id: str
    estado: Literal["pendiente", "aprobado", "rechazado", "inspeccion"] = "pendiente"
    fecha_solicitud: datetime = Field(default_factory=datetime.utcnow)
    fecha_vencimiento: Optional[datetime] = None
    observaciones: Optional[str] = None
    inspector_asignado: Optional[str] = None

class InspeccionBase(BaseModel):
    afap_id: str
    inspector_id: str
    fecha_programada: datetime
    observaciones: Optional[str] = None

class InspeccionCreate(InspeccionBase):
    pass

class Inspeccion(InspeccionBase):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    estado: Literal["programada", "completada", "cancelada"] = "programada"
    fecha_realizada: Optional[datetime] = None
    resultado: Optional[Literal["aprobado", "rechazado", "requiere_correccion"]] = None
    notas: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: Optional[str] = None
    session_id: str
    role: Literal["user", "assistant"]
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class ChatRequest(BaseModel):
    message: str
    session_id: str
    context: Optional[dict] = None

class DownloadLog(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    afap_id: str
    afap_numero: int
    user_id: str
    user_nombre: str
    user_email: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    ip_address: Optional[str] = None