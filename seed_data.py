import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timedelta, timezone
from auth import get_password_hash

async def seed_database():
    mongo_url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.getenv("DB_NAME", "buenosaires_permits")
    
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    # Clear existing data
    await db.users.delete_many({})
    await db.afap.delete_many({})
    await db.inspecciones.delete_many({})
    await db.chat_messages.delete_many({})
    
    print("Creando usuarios de demo...")
    
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
    print(f"✓ {len(users)} usuarios creados")
    
    print("Creando solicitudes de Habilitación Precaria de demo...")
    
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
            "solicitante_email": "ciudadano@buenosaires.gov",
            "titular_tipo": "fisica",
            "titular_nombre": "Juan Pérez",
            "titular_cuit": "20123456789",
            "cuenta_abl": "12345678",
            "domicilio_calle": "Av. Evergreen Terrace",
            "domicilio_altura": "742",
            "domicilio_piso": None,
            "domicilio_depto": None,
            "domicilio_local": "PB",
            "domicilio_localidad": "Buenos Aires",
            "rubro_tipo": "Comercio Minorista",
            "rubro_subrubro": "Panadería y Confitería",
            "rubro_descripcion": "Panadería artesanal con venta de productos de pastelería",
            "metros_cuadrados": 85.5,
            "techos_cielorasos": "Cielorraso de yeso",
            "pisos_material": "Cerámico antideslizante",
            "tiene_sanitarios": True,
            "sanitarios_acceso_directo": True,
            "sanitarios_antecamara": True,
            "sanitarios_lavabos_m": 1,
            "sanitarios_retretes_m": 1,
            "sanitarios_lavabos_f": 1,
            "sanitarios_retretes_f": 1,
            "sanitarios_migitorios": 1,
            "sanitarios_discapacitados": True,
            "cantidad_trabajadores": 3,
            "documentos_urls": [],
            "fecha_solicitud": (datetime.now(timezone.utc) - timedelta(days=5)).isoformat(),
            "fecha_vencimiento": (datetime.now(timezone.utc) + timedelta(days=25)).isoformat(),
            "observaciones": "Aprobado - Cumple con todos los requisitos",
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
            "domicilio_calle": "Boulevard Principal",
            "domicilio_altura": "1234",
            "domicilio_piso": None,
            "domicilio_depto": None,
            "domicilio_local": "Local 2",
            "domicilio_localidad": "Buenos Aires",
            "rubro_tipo": "Comercio Minorista",
            "rubro_subrubro": "Indumentaria y Accesorios",
            "rubro_descripcion": "Boutique de ropa y accesorios para damas",
            "metros_cuadrados": 120.0,
            "techos_cielorasos": "Losa de hormigón armado",
            "pisos_material": "Porcelanato",
            "tiene_sanitarios": True,
            "sanitarios_acceso_directo": True,
            "sanitarios_antecamara": False,
            "sanitarios_lavabos_m": 1,
            "sanitarios_retretes_m": 1,
            "sanitarios_lavabos_f": 1,
            "sanitarios_retretes_f": 1,
            "sanitarios_migitorios": 0,
            "sanitarios_discapacitados": False,
            "cantidad_trabajadores": 2,
            "documentos_urls": [],
            "fecha_solicitud": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
            "fecha_vencimiento": (datetime.now(timezone.utc) + timedelta(days=28)).isoformat(),
            "observaciones": None,
            "inspector_asignado": None
        },
        {
            "id": "afap-3",
            "numero_afap": 1003,
            "user_id": "user-1",
            "estado": "inspeccion",
            "solicitante_nombre": "Juan",
            "solicitante_apellido": "Pérez",
            "solicitante_cuit_cuil": "20123456789",
            "solicitante_telefono": "+54 11 1234-5678",
            "solicitante_email": "ciudadano@buenosaires.gov",
            "titular_tipo": "juridica",
            "titular_nombre": "Cafetería La Esquina SRL",
            "titular_cuit": "30123456789",
            "cuenta_abl": "11223344",
            "domicilio_calle": "Calle Principal",
            "domicilio_altura": "999",
            "domicilio_piso": None,
            "domicilio_depto": None,
            "domicilio_local": "Esquina",
            "domicilio_localidad": "Buenos Aires",
            "rubro_tipo": "Gastronomía",
            "rubro_subrubro": "Cafetería y Bar",
            "rubro_descripcion": "Cafetería con servicio de desayunos y meriendas",
            "metros_cuadrados": 95.0,
            "techos_cielorasos": "Cielorraso suspendido",
            "pisos_material": "Cerámico",
            "tiene_sanitarios": True,
            "sanitarios_acceso_directo": True,
            "sanitarios_antecamara": True,
            "sanitarios_lavabos_m": 1,
            "sanitarios_retretes_m": 1,
            "sanitarios_lavabos_f": 1,
            "sanitarios_retretes_f": 1,
            "sanitarios_migitorios": 1,
            "sanitarios_discapacitados": True,
            "cantidad_trabajadores": 4,
            "documentos_urls": [],
            "fecha_solicitud": (datetime.now(timezone.utc) - timedelta(days=10)).isoformat(),
            "fecha_vencimiento": (datetime.now(timezone.utc) + timedelta(days=20)).isoformat(),
            "observaciones": "Programada inspección para verificar condiciones de seguridad",
            "inspector_asignado": "user-2"
        }
    ]
    
    await db.afap.insert_many(afaps)
    print(f"✓ {len(afaps)} solicitudes de Habilitación Precaria creadas")
    
    print("Creando inspecciones de demo...")
    
    # Create demo inspections
    inspecciones = [
        {
            "id": "insp-1",
            "afap_id": "afap-3",
            "inspector_id": "user-2",
            "estado": "programada",
            "fecha_programada": (datetime.now(timezone.utc) + timedelta(days=3)).isoformat(),
            "fecha_realizada": None,
            "observaciones": "Verificar instalaciones eléctricas y salidas de emergencia",
            "resultado": None,
            "notas": None,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
    ]
    
    await db.inspecciones.insert_many(inspecciones)
    print(f"✓ {len(inspecciones)} inspecciones creadas")
    
    print("\n✅ Base de datos poblada con datos de demostración")
    print("\nCredenciales de acceso:")
    print("\nCiudadano:")
    print("  CUIT/CUIL: 20123456789")
    print("  Contraseña: demo123")
    print("\nInspector:")
    print("  CUIT/CUIL: 20987654321")
    print("  Contraseña: demo123")
    print("\nAdministrador:")
    print("  CUIT/CUIL: 20555555555")
    print("  Contraseña: demo123")
    
    client.close()

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    asyncio.run(seed_database())