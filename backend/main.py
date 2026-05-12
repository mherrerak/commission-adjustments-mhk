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

# Railway sirve desde /app/backend, el frontend está en /app/frontend
# En local está en commission-manager/frontend (un nivel arriba del backend)
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
if not FRONTEND_DIR.exists():
    # Fallback: buscar en el mismo nivel (por si se despliega con otra estructura)
    FRONTEND_DIR = Path(__file__).parent / "frontend"

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_index():
        """Sirve el index.html del frontend SPA."""
        index_path = FRONTEND_DIR / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        return {"message": "Frontend no encontrado. Verifica la carpeta /frontend"}

    # Catch-all para rutas del SPA (si se usan rutas del lado cliente)
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        """Sirve el index.html para cualquier ruta no-API (SPA routing)."""
        if full_path.startswith("api/"):
            return {"error": "Not found"}
        index_path = FRONTEND_DIR / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        return {"message": "Frontend no encontrado"}
else:
    logger.warning(f"⚠️  Directorio frontend no encontrado: {FRONTEND_DIR}")


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
