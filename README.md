# 🔧 Argentina Habilitaciones - Backend API

API REST construida con FastAPI para el sistema de gestión de habilitaciones y certificados AFAP.

## 🛠️ Stack Tecnológico

- **Framework**: FastAPI
- **Base de datos**: MongoDB (Motor - async driver)
- **Autenticación**: JWT (python-jose)
- **Documentación**: OpenAPI/Swagger (automático)
- **PDF Generation**: ReportLab
- **Email**: SMTP

## 📋 Requisitos

- Python 3.11+
- MongoDB 6.0+
- pip o pipenv

## 🚀 Instalación Local

### 1. Clonar el repositorio

```bash
git clone https://github.com/tu-usuario/argentina-habilitaciones-backend.git
cd argentina-habilitaciones-backend
```

### 2. Crear entorno virtual

```bash
python -m venv venv

# Linux/Mac
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno

```bash
cp .env.example .env
# Editar .env con tus valores
```

**Variables requeridas:**
- `MONGO_URL`: URL de conexión a MongoDB
- `DB_NAME`: Nombre de la base de datos
- `SECRET_KEY`: Clave secreta para JWT (generar una segura)
- `CORS_ORIGINS`: Orígenes permitidos para CORS

### 5. Ejecutar el servidor

```bash
# Desarrollo (con hot reload)
uvicorn server:app --reload --host 0.0.0.0 --port 8000

# Producción
uvicorn server:app --host 0.0.0.0 --port 8000 --workers 4
```

## 📚 Documentación API

Una vez ejecutando, acceder a:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## 🔌 Endpoints Principales

### Autenticación
- `POST /api/auth/register` - Registrar usuario
- `POST /api/auth/login` - Iniciar sesión
- `GET /api/auth/me` - Obtener usuario actual

### Solicitudes AFAP
- `GET /api/afaps` - Listar solicitudes
- `POST /api/afaps` - Crear solicitud
- `GET /api/afaps/{id}` - Obtener solicitud
- `PUT /api/afaps/{id}` - Actualizar solicitud
- `GET /api/afaps/{id}/certificate` - Descargar certificado PDF

### Inspecciones
- `GET /api/inspecciones` - Listar inspecciones
- `POST /api/inspecciones` - Crear inspección
- `PUT /api/inspecciones/{id}` - Actualizar inspección

### Estadísticas
- `GET /api/stats` - Obtener estadísticas generales

### Health Check
- `GET /api/health` - Estado del servicio
- `GET /health` - Health check (para load balancers)

## 🐳 Docker

### Build de la imagen

```bash
docker build -t habilitaciones-backend .
```

### Ejecutar con Docker

```bash
docker run -d \
  --name habilitaciones-backend \
  -p 8000:8000 \
  --env-file .env \
  habilitaciones-backend
```

### Docker Compose (con MongoDB)

```bash
docker-compose up -d
```

## 🗄️ Base de Datos

### Índices recomendados

```javascript
// Ejecutar en mongosh
use habilitaciones_db

db.users.createIndex({ "email": 1 }, { unique: true })
db.users.createIndex({ "cuit_cuil": 1 }, { unique: true })
db.afaps.createIndex({ "numero_tramite": 1 }, { unique: true })
db.afaps.createIndex({ "user_id": 1 })
db.afaps.createIndex({ "estado": 1 })
db.afaps.createIndex({ "created_at": -1 })
```

### Seed Data (datos iniciales)

```bash
python seed_data.py
```

## 🧪 Testing

```bash
# Ejecutar tests
pytest

# Con coverage
pytest --cov=. --cov-report=html
```

## 📁 Estructura del Proyecto

```
backend/
├── server.py           # Aplicación principal FastAPI
├── models.py           # Modelos Pydantic
├── auth.py             # Autenticación JWT
├── pdf_generator.py    # Generación de certificados PDF
├── email_service.py    # Servicio de envío de emails
├── seed_data.py        # Datos iniciales
├── requirements.txt    # Dependencias Python
├── Dockerfile          # Imagen Docker
├── .env.example        # Template de variables de entorno
└── README.md           # Esta documentación
```

## 🔒 Seguridad

- Autenticación JWT con tokens de corta duración
- Contraseñas hasheadas con bcrypt
- CORS configurado (no usar `*` en producción)
- Validación de inputs con Pydantic
- Rate limiting recomendado en producción

## 🚀 Deploy a Producción

### Railway

1. Conectar repositorio a Railway
2. Configurar variables de entorno
3. Railway detectará el Dockerfile automáticamente

### Render

1. Crear nuevo Web Service
2. Conectar repositorio
3. Configurar:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn server:app --host 0.0.0.0 --port $PORT`

### Variables de Entorno en Producción

```bash
MONGO_URL=mongodb+srv://user:pass@cluster.mongodb.net
DB_NAME=habilitaciones_prod
SECRET_KEY=<clave-segura-de-32-caracteres>
CORS_ORIGINS=https://tu-frontend.vercel.app
ENVIRONMENT=production
DEBUG=False
```

## 📝 Licencia

[Tu licencia aquí]

## 🤝 Contribuir

1. Fork el repositorio
2. Crear branch (`git checkout -b feature/nueva-feature`)
3. Commit cambios (`git commit -am 'Agregar nueva feature'`)
4. Push al branch (`git push origin feature/nueva-feature`)
5. Crear Pull Request
