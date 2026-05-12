"""
main.py - Entry point de la aplicación FastAPI.

Inicializa la base de datos, configura CORS y CORS,
monta los archivos estáticos del frontend, y arranca el scheduler.
"""
import os
import sys
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

# Cargar variables de entorno desde .env (si existe)
from dotenv import load_dotenv
load_dotenv()

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# Agregar directorio actual al path para imports relativos
sys.path.insert(0, str(Path(__file__).parent))

from database import init_db
from routes.commissions import router as commission_router


# ── Lifecycle: init/shutdown ───────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicialización y limpieza al arrancar/apagar la app."""
    # ARRANQUE
    logger.info("🚀 Iniciando Commission Manager...")
    init_db()

    # Iniciar scheduler de vencimientos
    try:
        from services.scheduler import iniciar_scheduler
        iniciar_scheduler()
    except Exception as e:
        logger.warning(f"No se pudo iniciar el scheduler: {e}")

    yield  # La app corre aquí

    # APAGADO
    try:
        from services.scheduler import detener_scheduler
        detener_scheduler()
    except Exception:
        pass
    logger.info("🛑 Commission Manager detenido.")


# ── Crear aplicación ──────────────────────────────────────────────────────────

app = FastAPI(
    title="Commission Manager",
    description="Gestión de comisiones temporales para sellers y SKUs",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# ── CORS (para desarrollo con frontend en otro puerto) ────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, restringir a la URL del frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Rutas API ─────────────────────────────────────────────────────────────────

app.include_router(commission_router, prefix="/api", tags=["Comisiones"])

# ── Archivos estáticos del frontend ──────────────────────────────────────────

# Buscar frontend en múltiples ubicaciones posibles
_base = Path(__file__).parent
_candidates = [
    _base / "frontend",          # backend/frontend (Railway con cp en build)
    _base.parent / "frontend",   # ../frontend (desarrollo local)
]
FRONTEND_DIR = next((p for p in _candidates if p.exists()), _base / "frontend")

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
    logger.info(f"✅ Frontend encontrado en: {FRONTEND_DIR}")
else:
    logger.warning(f"⚠️  Frontend no encontrado. Rutas buscadas: {_candidates}")

@app.get("/", include_in_schema=False)
async def serve_index():
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"status": "ok", "message": "Commission Manager API corriendo. Frontend no encontrado.", "api_docs": "/api/docs"}

@app.get("/{full_path:path}", include_in_schema=False)
async def serve_spa(full_path: str):
    if full_path.startswith("api/"):
        return {"error": "Not found"}
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"status": "ok", "message": "Frontend no encontrado", "path": full_path}


# ── Arranque directo ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    ambiente = os.getenv("AMBIENTE", "development")
    reload = ambiente == "development"

    logger.info(f"Servidor escuchando en http://localhost:{port}")
    logger.info(f"Documentación API: http://localhost:{port}/api/docs")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=reload,
        log_level="info"
    )
