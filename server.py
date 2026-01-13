from fastapi import FastAPI, APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import List, Optional
import base64
from io import BytesIO

from models import (
    User, UserCreate, UserInDB, Token, LoginRequest,
    AFAP, AFAPCreate, Inspeccion, InspeccionCreate,
    ChatMessage, ChatRequest, DownloadLog
)
from auth import (
    get_password_hash, authenticate_user, create_access_token,
    get_current_user, ACCESS_TOKEN_EXPIRE_MINUTES, security
)

from openai import AsyncOpenAI
from pdf_generator import generate_afap_certificate
from email_service import send_certificate_email, send_status_notification

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# LLM Setup - OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# Create the main app
app = FastAPI(title="Argentina Habilitaciones API")
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Dependency for getting current user
async def get_current_user_dependency(credentials: HTTPAuthorizationCredentials = Depends(security)):
    from auth import get_current_user as _get_current_user
    return await _get_current_user(credentials, db)

# ============ AUTH ENDPOINTS ============

@api_router.post("/auth/register", response_model=Token)
async def register(user_data: UserCreate):
    # Check if user exists
    existing_user = await db.users.find_one({"cuit_cuil": user_data.cuit_cuil}, {"_id": 0})
    if existing_user:
        raise HTTPException(status_code=400, detail="El CUIT/CUIL ya está registrado")
    
    existing_email = await db.users.find_one({"email": user_data.email}, {"_id": 0})
    if existing_email:
        raise HTTPException(status_code=400, detail="El email ya está registrado")
    
    # Create user
    hashed_password = get_password_hash(user_data.password)
    user_in_db = UserInDB(
        **user_data.model_dump(exclude={"password"}),
        hashed_password=hashed_password
    )
    
    user_dict = user_in_db.model_dump()
    user_dict['created_at'] = user_dict['created_at'].isoformat()
    
    await db.users.insert_one(user_dict)
    
    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user_in_db.cuit_cuil}, expires_delta=access_token_expires
    )
    
    user = User(**user_in_db.model_dump(exclude={"hashed_password"}))
    
    return Token(access_token=access_token, token_type="bearer", user=user)

@api_router.post("/auth/login", response_model=Token)
async def login(login_data: LoginRequest):
    user = await authenticate_user(db, login_data.cuit_cuil, login_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="CUIT/CUIL o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.cuit_cuil}, expires_delta=access_token_expires
    )
    
    user_response = User(**user.model_dump(exclude={"hashed_password"}))
    
    return Token(access_token=access_token, token_type="bearer", user=user_response)

@api_router.get("/auth/me", response_model=User)
async def get_me(current_user: User = Depends(get_current_user_dependency)):
    return current_user

# ============ AFAP ENDPOINTS ============

@api_router.post("/afap", response_model=AFAP)
async def create_afap(
    afap_data: AFAPCreate,
    current_user: User = Depends(get_current_user_dependency)
):
    # Get next AFAP number
    last_afap = await db.afap.find_one({}, {"_id": 0, "numero_afap": 1}, sort=[("numero_afap", -1)])
    next_number = (last_afap["numero_afap"] + 1) if last_afap else 1001
    
    # Calculate expiration date (30 days from now)
    fecha_vencimiento = datetime.now(timezone.utc) + timedelta(days=30)
    
    afap = AFAP(
        **afap_data.model_dump(),
        user_id=current_user.id,
        numero_afap=next_number,
        fecha_vencimiento=fecha_vencimiento
    )
    
    afap_dict = afap.model_dump()
    afap_dict['fecha_solicitud'] = afap_dict['fecha_solicitud'].isoformat()
    afap_dict['fecha_vencimiento'] = afap_dict['fecha_vencimiento'].isoformat()
    
    await db.afap.insert_one(afap_dict)
    
    return afap

@api_router.get("/afap", response_model=List[AFAP])
async def get_afaps(
    current_user: User = Depends(get_current_user_dependency)
):
    # Admin e inspector ven todos, ciudadano solo los suyos
    if current_user.role in ["administrador", "inspector"]:
        query = {}
    else:
        query = {"user_id": current_user.id}
    
    afaps = await db.afap.find(query, {"_id": 0}).to_list(1000)
    
    for afap in afaps:
        if isinstance(afap.get('fecha_solicitud'), str):
            afap['fecha_solicitud'] = datetime.fromisoformat(afap['fecha_solicitud'])
        if isinstance(afap.get('fecha_vencimiento'), str):
            afap['fecha_vencimiento'] = datetime.fromisoformat(afap['fecha_vencimiento'])
    
    return afaps

@api_router.get("/afap/{afap_id}", response_model=AFAP)
async def get_afap(
    afap_id: str,
    current_user: User = Depends(get_current_user_dependency)
):
    afap = await db.afap.find_one({"id": afap_id}, {"_id": 0})
    if not afap:
        raise HTTPException(status_code=404, detail="AFAP no encontrado")
    
    # Check permissions
    if current_user.role == "ciudadano" and afap["user_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="No autorizado")
    
    if isinstance(afap.get('fecha_solicitud'), str):
        afap['fecha_solicitud'] = datetime.fromisoformat(afap['fecha_solicitud'])
    if isinstance(afap.get('fecha_vencimiento'), str):
        afap['fecha_vencimiento'] = datetime.fromisoformat(afap['fecha_vencimiento'])
    
    return AFAP(**afap)

@api_router.patch("/afap/{afap_id}/estado")
async def update_afap_estado(
    afap_id: str,
    estado: str,
    observaciones: Optional[str] = None,
    current_user: User = Depends(get_current_user_dependency)
):
    # Solo inspector y admin pueden cambiar estado
    if current_user.role not in ["inspector", "administrador"]:
        raise HTTPException(status_code=403, detail="No autorizado")
    
    # Obtener AFAP actual para comparar estado
    afap_actual = await db.afap.find_one({"id": afap_id}, {"_id": 0})
    if not afap_actual:
        raise HTTPException(status_code=404, detail="AFAP no encontrado")
    
    old_estado = afap_actual.get("estado")
    
    # Actualizar estado
    update_data = {"estado": estado}
    if observaciones:
        update_data["observaciones"] = observaciones
    
    result = await db.afap.update_one(
        {"id": afap_id},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="AFAP no encontrado")
    
    # Obtener datos del usuario solicitante
    user_solicitante = await db.users.find_one(
        {"id": afap_actual["user_id"]},
        {"_id": 0, "email": 1, "nombre": 1, "apellido": 1}
    )
    
    if user_solicitante:
        user_name = f"{user_solicitante['nombre']} {user_solicitante['apellido']}"
        user_email = user_solicitante['email']
        
        # Si se aprueba, enviar email con certificado
        if estado == "aprobado" and old_estado != "aprobado":
            try:
                await send_certificate_email(
                    user_email,
                    user_name,
                    afap_actual["numero_afap"],
                    afap_actual
                )
                logger.info(f"Certificate email sent for AFAP #{afap_actual['numero_afap']}")
            except Exception as e:
                logger.error(f"Error sending certificate email: {str(e)}")
        
        # Enviar notificación de cambio de estado
        try:
            await send_status_notification(
                user_email,
                user_name,
                afap_actual["numero_afap"],
                old_estado,
                estado,
                observaciones
            )
        except Exception as e:
            logger.error(f"Error sending status notification: {str(e)}")
    
    return {
        "message": "Estado actualizado correctamente",
        "old_estado": old_estado,
        "new_estado": estado,
        "email_sent": user_solicitante is not None
    }

@api_router.get("/afap/{afap_id}/certificado")
async def download_certificado(
    afap_id: str,
    current_user: User = Depends(get_current_user_dependency)
):
    # Buscar el AFAP
    afap = await db.afap.find_one({"id": afap_id}, {"_id": 0})
    if not afap:
        raise HTTPException(status_code=404, detail="AFAP no encontrado")
    
    # Verificar que está aprobado
    if afap["estado"] != "aprobado":
        raise HTTPException(status_code=400, detail="El AFAP debe estar aprobado para generar el certificado")
    
    # Verificar permisos
    if current_user.role == "ciudadano" and afap["user_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="No autorizado")
    
    # Registrar la descarga en el historial
    try:
        download_log = DownloadLog(
            afap_id=afap_id,
            afap_numero=afap["numero_afap"],
            user_id=current_user.id,
            user_nombre=f"{current_user.nombre} {current_user.apellido}",
            user_email=current_user.email
        )
        
        log_dict = download_log.model_dump()
        log_dict['timestamp'] = log_dict['timestamp'].isoformat()
        await db.download_logs.insert_one(log_dict)
        
        logger.info(f"Certificate downloaded: AFAP #{afap['numero_afap']} by {current_user.email}")
    except Exception as e:
        logger.error(f"Error logging download: {str(e)}")
    
    # Generar PDF
    try:
        pdf_bytes = generate_afap_certificate(afap)
        
        # Crear respuesta con el PDF
        return StreamingResponse(
            BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=HabilitacionPrecaria_{afap['numero_afap']}_Argentina.pdf"
            }
        )
    except Exception as e:
        logger.error(f"Error generating certificate: {str(e)}")
        raise HTTPException(status_code=500, detail="Error al generar el certificado")

@api_router.get("/afap/{afap_id}/descargas")
async def get_download_history(
    afap_id: str,
    current_user: User = Depends(get_current_user_dependency)
):
    # Solo admin puede ver historial completo
    if current_user.role != "administrador":
        raise HTTPException(status_code=403, detail="No autorizado")
    
    logs = await db.download_logs.find(
        {"afap_id": afap_id},
        {"_id": 0}
    ).sort("timestamp", -1).to_list(100)
    
    for log in logs:
        if isinstance(log.get('timestamp'), str):
            log['timestamp'] = datetime.fromisoformat(log['timestamp'])
    
    return logs

# ============ INSPECCIONES ENDPOINTS ============

@api_router.post("/inspecciones", response_model=Inspeccion)
async def create_inspeccion(
    inspeccion_data: InspeccionCreate,
    current_user: User = Depends(get_current_user_dependency)
):
    if current_user.role not in ["inspector", "administrador"]:
        raise HTTPException(status_code=403, detail="No autorizado")
    
    inspeccion = Inspeccion(**inspeccion_data.model_dump())
    
    inspeccion_dict = inspeccion.model_dump()
    inspeccion_dict['fecha_programada'] = inspeccion_dict['fecha_programada'].isoformat()
    inspeccion_dict['created_at'] = inspeccion_dict['created_at'].isoformat()
    if inspeccion_dict.get('fecha_realizada'):
        inspeccion_dict['fecha_realizada'] = inspeccion_dict['fecha_realizada'].isoformat()
    
    await db.inspecciones.insert_one(inspeccion_dict)
    
    return inspeccion

@api_router.get("/inspecciones", response_model=List[Inspeccion])
async def get_inspecciones(
    current_user: User = Depends(get_current_user_dependency)
):
    if current_user.role == "inspector":
        query = {"inspector_id": current_user.id}
    elif current_user.role == "administrador":
        query = {}
    else:
        # Ciudadanos ven inspecciones de sus AFAPs
        user_afaps = await db.afap.find({"user_id": current_user.id}, {"_id": 0, "id": 1}).to_list(1000)
        afap_ids = [afap["id"] for afap in user_afaps]
        query = {"afap_id": {"$in": afap_ids}}
    
    inspecciones = await db.inspecciones.find(query, {"_id": 0}).to_list(1000)
    
    for inspeccion in inspecciones:
        if isinstance(inspeccion.get('fecha_programada'), str):
            inspeccion['fecha_programada'] = datetime.fromisoformat(inspeccion['fecha_programada'])
        if isinstance(inspeccion.get('fecha_realizada'), str):
            inspeccion['fecha_realizada'] = datetime.fromisoformat(inspeccion['fecha_realizada'])
        if isinstance(inspeccion.get('created_at'), str):
            inspeccion['created_at'] = datetime.fromisoformat(inspeccion['created_at'])
    
    return inspecciones

# ============ AI ASSISTANT ENDPOINTS ============

@api_router.post("/ai/chat")
async def chat_with_ai(
    chat_request: ChatRequest,
    current_user: User = Depends(get_current_user_dependency)
):
    try:
        # Save user message
        user_msg = ChatMessage(
            user_id=current_user.id,
            session_id=chat_request.session_id,
            role="user",
            content=chat_request.message
        )
        
        user_msg_dict = user_msg.model_dump()
        user_msg_dict['timestamp'] = user_msg_dict['timestamp'].isoformat()
        await db.chat_messages.insert_one(user_msg_dict)
        
        # Get conversation history
        history = await db.chat_messages.find(
            {"session_id": chat_request.session_id},
            {"_id": 0}
        ).sort("timestamp", 1).limit(10).to_list(10)
        
        # System message with context
        system_message = (
            f"Eres un asistente virtual del Argentina, especializado en habilitaciones comerciales y el sistema de Habilitación Precaria Automática.\\n\\n"
            f"Tu rol es:\\n"
            f"1. Ayudar a los ciudadanos a entender los requisitos para habilitar comercios\\n"
            f"2. Guiar paso a paso en el proceso de solicitud de AFAP\\n"
            f"3. Responder preguntas sobre documentación requerida\\n"
            f"4. Explicar el estado de los trámites\\n"
            f"5. Ser amigable, claro y usar español argentino\\n\\n"
            f"Información del usuario:\\n"
            f"- Nombre: {current_user.nombre} {current_user.apellido}\\n"
            f"- CUIT/CUIL: {current_user.cuit_cuil}\\n"
            f"- Rol: {current_user.role}\\n\\n"
            f"Requisitos principales para AFAP:\\n"
            f"- Locales menores a 200 m² (oficinas 300 m²)\\n"
            f"- Boleta de ABL\\n"
            f"- Plano o croquis del local\\n"
            f"- DNI del interesado\\n"
            f"- Para empresas: estatuto, contrato social\\n"
            f"- Constancia de IIBB\\n"
            f"- Derecho de uso del inmueble\\n\\n"
            f"El AFAP tiene validez de 30 días y permite operar mientras se gestiona la habilitación definitiva.\\n\\n"
            f"Respondé de forma concisa, amigable y en español argentino."
        )
        
        # Build messages for OpenAI
        messages = [{"role": "system", "content": system_message}]
        
        # Add conversation history
        for msg in history[:-1]:  # Exclude the current message we just saved
            messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", "")
            })
        
        # Add current user message
        messages.append({"role": "user", "content": chat_request.message})
        
        # Get AI response from OpenAI
        if openai_client:
            response = await openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                max_tokens=500,
                temperature=0.7
            )
            ai_response = response.choices[0].message.content
        else:
            ai_response = "El asistente de IA no está configurado. Por favor, contactá al administrador."
        
        # Save assistant message
        assistant_msg = ChatMessage(
            user_id=current_user.id,
            session_id=chat_request.session_id,
            role="assistant",
            content=ai_response
        )
        
        assistant_msg_dict = assistant_msg.model_dump()
        assistant_msg_dict['timestamp'] = assistant_msg_dict['timestamp'].isoformat()
        await db.chat_messages.insert_one(assistant_msg_dict)
        
        return {
            "response": ai_response,
            "session_id": chat_request.session_id
        }
        
    except Exception as e:
        logger.error(f"Error in AI chat: {str(e)}")
        # Fallback response
        fallback_response = "Disculpá, estoy teniendo problemas técnicos. Por favor, intentá de nuevo en unos momentos."
        return {
            "response": fallback_response,
            "session_id": chat_request.session_id
        }

@api_router.get("/ai/chat/history/{session_id}")
async def get_chat_history(
    session_id: str,
    current_user: User = Depends(get_current_user_dependency)
):
    messages = await db.chat_messages.find(
        {"session_id": session_id, "user_id": current_user.id},
        {"_id": 0}
    ).sort("timestamp", 1).to_list(100)
    
    for msg in messages:
        if isinstance(msg.get('timestamp'), str):
            msg['timestamp'] = datetime.fromisoformat(msg['timestamp'])
    
    return messages

# ============ STATISTICS ENDPOINTS ============


@api_router.get("/admin/descargas")
async def get_all_downloads(current_user: User = Depends(get_current_user_dependency)):
    """Obtener historial completo de descargas de certificados (solo admin)"""
    if current_user.role != "administrador":
        raise HTTPException(status_code=403, detail="Solo administradores pueden acceder")
    
    # Obtener todas las descargas
    downloads = await db.download_history.find({}, {"_id": 0}).sort("download_timestamp", -1).to_list(100)
    
    return {
        "total": len(downloads),
        "descargas": downloads
    }

@api_router.get("/stats/dashboard")
async def get_dashboard_stats(
    current_user: User = Depends(get_current_user_dependency)
):
    if current_user.role not in ["inspector", "administrador"]:
        raise HTTPException(status_code=403, detail="No autorizado")
    
    # Count AFAPs by status
    total_afaps = await db.afap.count_documents({})
    pendientes = await db.afap.count_documents({"estado": "pendiente"})
    aprobados = await db.afap.count_documents({"estado": "aprobado"})
    rechazados = await db.afap.count_documents({"estado": "rechazado"})
    en_inspeccion = await db.afap.count_documents({"estado": "inspeccion"})
    
    # Count inspections
    inspecciones_programadas = await db.inspecciones.count_documents({"estado": "programada"})
    inspecciones_completadas = await db.inspecciones.count_documents({"estado": "completada"})
    
    # Count users by role
    total_usuarios = await db.users.count_documents({})
    
    # Recent AFAPs
    recent_afaps = await db.afap.find({}, {"_id": 0}).sort("fecha_solicitud", -1).limit(5).to_list(5)
    for afap in recent_afaps:
        if isinstance(afap.get('fecha_solicitud'), str):
            afap['fecha_solicitud'] = datetime.fromisoformat(afap['fecha_solicitud'])
        if isinstance(afap.get('fecha_vencimiento'), str):
            afap['fecha_vencimiento'] = datetime.fromisoformat(afap['fecha_vencimiento'])
    
    return {
        "afaps": {
            "total": total_afaps,
            "pendientes": pendientes,
            "aprobados": aprobados,
            "rechazados": rechazados,
            "en_inspeccion": en_inspeccion
        },
        "inspecciones": {
            "programadas": inspecciones_programadas,
            "completadas": inspecciones_completadas
        },
        "usuarios": {
            "total": total_usuarios
        },
        "recent_afaps": recent_afaps
    }

# ============ UPLOAD ENDPOINT ============

@api_router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user_dependency)
):
    # Simple base64 encoding for demo purposes
    # In production, use cloud storage (S3, etc.)
    try:
        contents = await file.read()
        encoded = base64.b64encode(contents).decode('utf-8')
        
        file_data = {
            "filename": file.filename,
            "content_type": file.content_type,
            "data": encoded,
            "user_id": current_user.id,
            "uploaded_at": datetime.now(timezone.utc).isoformat()
        }
        
        result = await db.uploads.insert_one(file_data)
        
        return {
            "url": f"/api/uploads/{file.filename}",
            "filename": file.filename
        }
    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        raise HTTPException(status_code=500, detail="Error al subir el archivo")

# ============ PUBLIC VERIFICATION ENDPOINT ============

@api_router.get("/verificar/{afap_id}")
async def verificar_certificado_publico(afap_id: str):
    """
    Endpoint público para verificar certificados vía QR code
    No requiere autenticación
    """
    try:
        afap = await db.afap.find_one({"id": afap_id}, {"_id": 0})
        
        if not afap:
            raise HTTPException(
                status_code=404,
                detail="Certificado no encontrado. Verificá el código QR."
            )
        
        # Convertir fechas
        if isinstance(afap.get('fecha_solicitud'), str):
            afap['fecha_solicitud'] = datetime.fromisoformat(afap['fecha_solicitud'])
        if isinstance(afap.get('fecha_vencimiento'), str):
            afap['fecha_vencimiento'] = datetime.fromisoformat(afap['fecha_vencimiento'])
        
        # Devolver solo info pública (sin datos sensibles del solicitante)
        return {
            "id": afap["id"],
            "numero_afap": afap["numero_afap"],
            "estado": afap["estado"],
            "titular_nombre": afap["titular_nombre"],
            "titular_cuit": afap["titular_cuit"],
            "domicilio_calle": afap["domicilio_calle"],
            "domicilio_altura": afap["domicilio_altura"],
            "domicilio_local": afap.get("domicilio_local"),
            "domicilio_localidad": afap["domicilio_localidad"],
            "rubro_tipo": afap["rubro_tipo"],
            "rubro_descripcion": afap["rubro_descripcion"],
            "metros_cuadrados": afap["metros_cuadrados"],
            "fecha_solicitud": afap["fecha_solicitud"].isoformat(),
            "fecha_vencimiento": afap["fecha_vencimiento"].isoformat() if afap.get("fecha_vencimiento") else None,
            "observaciones": afap.get("observaciones")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying certificate: {str(e)}")
        raise HTTPException(status_code=500, detail="Error al verificar el certificado")

# Include the router
app.include_router(api_router)

# CORS Middleware - Configurar CORS_ORIGINS en .env para producción
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ HEALTH CHECK ENDPOINTS ============

@app.get("/")
async def root():
    """Root endpoint - API info"""
    return {
        "name": "Argentina Habilitaciones API",
        "version": "1.0",
        "status": "running",
        "docs": "/docs"
    }

@app.get("/health")
@api_router.get("/health")
async def health_check():
    """Health check endpoint para monitoreo y balanceadores de carga"""
    try:
        # Verificar conexión a MongoDB
        await db.command('ping')
        db_status = "healthy"
    except Exception as e:
        logger.error(f"Health check failed - MongoDB: {str(e)}")
        db_status = "unhealthy"
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "database": db_status,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
    
    return {
        "status": "healthy",
        "database": db_status,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

# ============ SEED DATABASE ENDPOINT ============

@api_router.post("/seed")
async def seed_database():
    """Populate database with demo data - USE ONLY ONCE"""
    try:
        # Check if users already exist
        existing_users = await db.users.count_documents({})
        if existing_users > 0:
            return {"message": "Database already has data", "users_count": existing_users}
        
        # Create demo users
        users = [
            {
                "id": "user-1",
                "email": "ciudadano@argentina.gob.ar",
                "cuit_cuil": "20123456789",
                "nombre": "Juan",
                "apellido": "Pérez",
                "telefono": "+54 11 1234-5678",
                "role": "ciudadano",
                "hashed_password": get_password_hash("demo123"),
                "created_at": datetime.now(timezone.utc).isoformat()
            },
            {
                "id": "user-2",
                "email": "inspector@argentina.gob.ar",
                "cuit_cuil": "20987654321",
                "nombre": "María",
                "apellido": "González",
                "telefono": "+54 11 9876-5432",
                "role": "inspector",
                "hashed_password": get_password_hash("demo123"),
                "created_at": datetime.now(timezone.utc).isoformat()
            },
            {
                "id": "user-3",
                "email": "admin@argentina.gob.ar",
                "cuit_cuil": "20555555555",
                "nombre": "Carlos",
                "apellido": "Rodríguez",
                "telefono": "+54 11 5555-5555",
                "role": "administrador",
                "hashed_password": get_password_hash("demo123"),
                "created_at": datetime.now(timezone.utc).isoformat()
            },
            {
                "id": "user-4",
                "email": "comerciante@email.com",
                "cuit_cuil": "20111222333",
                "nombre": "Ana",
                "apellido": "Martínez",
                "telefono": "+54 11 1112-2233",
                "role": "ciudadano",
                "hashed_password": get_password_hash("demo123"),
                "created_at": datetime.now(timezone.utc).isoformat()
            }
        ]
        
        await db.users.insert_many(users)
        
        # Create demo AFAPs
        afaps = [
            {
                "id": "afap-1",
                "numero_afap": 1001,
                "user_id": "user-1",
                "estado": "aprobado",
                "solicitante_nombre": "Juan",
                "solicitante_apellido": "Pérez",
                "solicitante_cuit_cuil": "20123456789",
                "solicitante_telefono": "+54 11 1234-5678",
                "solicitante_email": "ciudadano@argentina.gob.ar",
                "titular_tipo": "fisica",
                "titular_nombre": "Juan Pérez",
                "titular_cuit": "20123456789",
                "cuenta_abl": "12345678",
                "domicilio_calle": "Av. Rivadavia",
                "domicilio_altura": "1234",
                "domicilio_piso": None,
                "domicilio_depto": None,
                "domicilio_local": "PB",
                "domicilio_localidad": "Morón",
                "rubro_tipo": "Comercio Minorista",
                "rubro_subrubro": "Panadería y Confitería",
                "rubro_descripcion": "Panadería artesanal",
                "metros_cuadrados": 85.5,
                "cantidad_trabajadores": 3,
                "documentos_urls": [],
                "fecha_solicitud": (datetime.now(timezone.utc) - timedelta(days=5)).isoformat(),
                "fecha_vencimiento": (datetime.now(timezone.utc) + timedelta(days=25)).isoformat(),
                "observaciones": "Aprobado - Cumple requisitos",
                "inspector_asignado": "user-2"
            },
            {
                "id": "afap-2",
                "numero_afap": 1002,
                "user_id": "user-4",
                "estado": "pendiente",
                "solicitante_nombre": "Ana",
                "solicitante_apellido": "Martínez",
                "solicitante_cuit_cuil": "20111222333",
                "solicitante_telefono": "+54 11 1112-2233",
                "solicitante_email": "comerciante@email.com",
                "titular_tipo": "fisica",
                "titular_nombre": "Ana Martínez",
                "titular_cuit": "20111222333",
                "cuenta_abl": "87654321",
                "domicilio_calle": "Av. San Martín",
                "domicilio_altura": "500",
                "domicilio_piso": None,
                "domicilio_depto": None,
                "domicilio_local": "Local 2",
                "domicilio_localidad": "Morón",
                "rubro_tipo": "Comercio Minorista",
                "rubro_subrubro": "Indumentaria",
                "rubro_descripcion": "Boutique de ropa",
                "metros_cuadrados": 120.0,
                "cantidad_trabajadores": 2,
                "documentos_urls": [],
                "fecha_solicitud": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
                "fecha_vencimiento": (datetime.now(timezone.utc) + timedelta(days=28)).isoformat(),
                "observaciones": None,
                "inspector_asignado": None
            }
        ]
        
        await db.afaps.insert_many(afaps)
        
        return {
            "message": "Database seeded successfully",
            "users_created": len(users),
            "afaps_created": len(afaps)
        }
        
    except Exception as e:
        logger.error(f"Seed error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
