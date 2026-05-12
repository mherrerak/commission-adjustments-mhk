"""
database.py - Configuración y gestión de la base de datos SQLite
Utiliza sqlite3 estándar con soporte thread-safe para FastAPI
"""
import sqlite3
import os
import threading
from pathlib import Path

# Ruta de la base de datos (configurable via .env)
DB_PATH = os.getenv("DATABASE_PATH", "./data/comisiones.db")

# Lock global para operaciones de escritura (thread safety)
_write_lock = threading.Lock()


def get_db_path() -> str:
    """Retorna la ruta absoluta de la base de datos."""
    return str(Path(DB_PATH).resolve())


def get_connection() -> sqlite3.Connection:
    """
    Crea y retorna una conexión a la base de datos SQLite.
    check_same_thread=False permite uso desde múltiples threads (FastAPI).
    """
    conn = sqlite3.connect(get_db_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row  # Permite acceder columnas por nombre
    conn.execute("PRAGMA journal_mode=WAL")  # Mejor concurrencia de lectura
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """
    Inicializa la base de datos: crea el directorio y las tablas si no existen.
    Se llama al iniciar la aplicación.
    """
    # Crear directorio si no existe
    db_dir = Path(DB_PATH).parent
    db_dir.mkdir(parents=True, exist_ok=True)

    conn = get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS comisiones (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo            TEXT NOT NULL CHECK(tipo IN ('SKU', 'Seller')),
                codigo          TEXT NOT NULL,
                comision_anterior REAL NOT NULL,
                comision_nueva  REAL NOT NULL,
                fecha_inicio    TEXT NOT NULL,
                fecha_termino   TEXT NOT NULL,
                responsable     TEXT NOT NULL,
                motivo          TEXT,
                estado          TEXT NOT NULL DEFAULT 'Programada'
                                CHECK(estado IN (
                                    'Programada', 'Activa', 'Vencida',
                                    'Vencida_Notificada', 'Anulada'
                                )),
                email_carga_enviado     INTEGER DEFAULT 0,
                email_warning_enviado   INTEGER DEFAULT 0,
                email_vencimiento_enviado INTEGER DEFAULT 0,
                created_at      TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)

        # Índices para mejorar performance en consultas frecuentes
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_comisiones_estado
            ON comisiones(estado)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_comisiones_fechas
            ON comisiones(fecha_inicio, fecha_termino)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_comisiones_tipo_codigo
            ON comisiones(tipo, codigo)
        """)

        conn.commit()
        print(f"✅ Base de datos inicializada en: {get_db_path()}")
    finally:
        conn.close()


def actualizar_estados_automatico():
    """
    Actualiza automáticamente el estado de las comisiones según la fecha actual.
    - Programada → Activa: si fecha_inicio <= hoy <= fecha_termino
    - Activa → Vencida: si fecha_termino < hoy
    Se llama periódicamente desde el scheduler.
    """
    from datetime import date
    hoy = date.today().isoformat()

    with _write_lock:
        conn = get_connection()
        try:
            # Activar comisiones programadas que ya iniciaron
            conn.execute("""
                UPDATE comisiones
                SET estado = 'Activa', updated_at = datetime('now')
                WHERE estado = 'Programada'
                  AND fecha_inicio <= ?
                  AND fecha_termino >= ?
            """, (hoy, hoy))

            # Vencer comisiones activas cuya fecha término ya pasó
            conn.execute("""
                UPDATE comisiones
                SET estado = 'Vencida', updated_at = datetime('now')
                WHERE estado IN ('Activa', 'Programada')
                  AND fecha_termino < ?
            """, (hoy,))

            conn.commit()
        finally:
            conn.close()
