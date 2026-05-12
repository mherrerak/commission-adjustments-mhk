"""
commissions.py - Endpoints REST para gestión de comisiones.

Rutas:
  POST   /api/comisiones             - Crear nueva comisión
  GET    /api/comisiones             - Listar todas (con filtros)
  GET    /api/comisiones/activas     - Solo las activas hoy
  GET    /api/comisiones/export      - Exportar a Excel
  PUT    /api/comisiones/{id}/anular - Anular una comisión
  POST   /api/admin/revision-manual  - Trigger manual del cron job
  GET    /api/responsables           - Lista de responsables configurados
"""
import os
import io
import logging
from datetime import date
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Header
from fastapi.responses import StreamingResponse

from models import ComisionCreate
from database import get_connection, _write_lock, actualizar_estados_automatico

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Helper: convertir sqlite3.Row a dict ──────────────────────────────────────

def _row_to_dict(row) -> dict:
    """Convierte un sqlite3.Row a diccionario."""
    return dict(row)


# ── Calcular estado actual según fechas ───────────────────────────────────────

def _calcular_estado(fecha_inicio: str, fecha_termino: str, estado_bd: str) -> str:
    """
    Retorna el estado efectivo de una comisión según las fechas actuales.
    Mantiene 'Anulada' y 'Vencida_Notificada' intactos.
    """
    if estado_bd in ("Anulada", "Vencida_Notificada"):
        return estado_bd
    hoy = date.today().isoformat()
    if fecha_termino < hoy:
        return "Vencida"
    elif fecha_inicio <= hoy:
        return "Activa"
    else:
        return "Programada"


# ── POST /api/comisiones ───────────────────────────────────────────────────────

@router.post("/comisiones", status_code=201)
async def crear_comision(data: ComisionCreate):
    """
    Registra una nueva comisión temporal.

    Validaciones:
    - fecha_termino > fecha_inicio
    - comision_nueva != comision_anterior
    - No solapamiento de fechas para el mismo tipo/código
    """
    from services.email_service import enviar_email_carga

    # Actualizar estados antes de validar
    actualizar_estados_automatico()

    with _write_lock:
        conn = get_connection()
        try:
            fecha_inicio_str = data.fecha_inicio.isoformat()
            fecha_termino_str = data.fecha_termino.isoformat()

            # ── Validar solapamiento de fechas ────────────────────────────────
            cursor = conn.execute("""
                SELECT id FROM comisiones
                WHERE tipo = ?
                  AND codigo = ?
                  AND estado NOT IN ('Anulada', 'Vencida', 'Vencida_Notificada')
                  AND fecha_inicio <= ?
                  AND fecha_termino >= ?
            """, (
                data.tipo,
                data.codigo,
                fecha_termino_str,
                fecha_inicio_str
            ))
            existente = cursor.fetchone()
            if existente:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Ya existe una comisión activa o programada para {data.tipo} "
                        f"'{data.codigo}' en ese rango de fechas (ID: {existente['id']}). "
                        "Anula la comisión existente primero."
                    )
                )

            # ── Determinar estado inicial ─────────────────────────────────────
            estado = _calcular_estado(fecha_inicio_str, fecha_termino_str, "Programada")

            # ── Insertar comisión ─────────────────────────────────────────────
            cursor = conn.execute("""
                INSERT INTO comisiones (
                    tipo, codigo, comision_anterior, comision_nueva,
                    fecha_inicio, fecha_termino, responsable, motivo, estado
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data.tipo,
                data.codigo,
                data.comision_anterior,
                data.comision_nueva,
                fecha_inicio_str,
                fecha_termino_str,
                data.responsable,
                data.motivo,
                estado
            ))
            conn.commit()
            nuevo_id = cursor.lastrowid

            # Leer la comisión recién creada
            row = conn.execute(
                "SELECT * FROM comisiones WHERE id = ?", (nuevo_id,)
            ).fetchone()
            comision_dict = _row_to_dict(row)

        finally:
            conn.close()

    # ── Enviar email de notificación (async, no bloquear respuesta) ────────────
    try:
        enviar_email_carga([comision_dict])
    except Exception as e:
        logger.warning(f"No se pudo enviar email de carga: {e}")

    return {
        "success": True,
        "mensaje": "Comisión registrada correctamente",
        "comision": comision_dict
    }


# ── GET /api/comisiones ────────────────────────────────────────────────────────

@router.get("/comisiones")
async def listar_comisiones(
    tipo: Optional[str] = Query(None, description="Filtrar por 'SKU' o 'Seller'"),
    estado: Optional[str] = Query(None, description="Filtrar por estado"),
    responsable: Optional[str] = Query(None, description="Filtrar por responsable"),
    codigo: Optional[str] = Query(None, description="Buscar por código SKU/Seller"),
    fecha_inicio_desde: Optional[str] = Query(None),
    fecha_inicio_hasta: Optional[str] = Query(None),
    fecha_termino_desde: Optional[str] = Query(None),
    fecha_termino_hasta: Optional[str] = Query(None),
    orden: Optional[str] = Query("id_desc", description="Ordenamiento: campo_asc o campo_desc")
):
    """
    Lista todas las comisiones con filtros opcionales.
    Retorna el histórico completo.
    """
    # Actualizar estados antes de responder
    actualizar_estados_automatico()

    conn = get_connection()
    try:
        query = "SELECT * FROM comisiones WHERE 1=1"
        params = []

        if tipo:
            query += " AND tipo = ?"
            params.append(tipo)
        if estado:
            query += " AND estado = ?"
            params.append(estado)
        if responsable:
            query += " AND responsable = ?"
            params.append(responsable)
        if codigo:
            query += " AND codigo LIKE ?"
            params.append(f"%{codigo}%")
        if fecha_inicio_desde:
            query += " AND fecha_inicio >= ?"
            params.append(fecha_inicio_desde)
        if fecha_inicio_hasta:
            query += " AND fecha_inicio <= ?"
            params.append(fecha_inicio_hasta)
        if fecha_termino_desde:
            query += " AND fecha_termino >= ?"
            params.append(fecha_termino_desde)
        if fecha_termino_hasta:
            query += " AND fecha_termino <= ?"
            params.append(fecha_termino_hasta)

        # Ordenamiento seguro (whitelist de columnas permitidas)
        columnas_validas = {
            "id", "tipo", "codigo", "comision_anterior", "comision_nueva",
            "fecha_inicio", "fecha_termino", "responsable", "estado", "created_at"
        }
        orden_dir = "DESC"
        orden_col = "id"
        if orden:
            partes = orden.rsplit("_", 1)
            if len(partes) == 2 and partes[0] in columnas_validas and partes[1].upper() in ("ASC", "DESC"):
                orden_col = partes[0]
                orden_dir = partes[1].upper()

        query += f" ORDER BY {orden_col} {orden_dir}"

        rows = conn.execute(query, params).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


# ── GET /api/comisiones/activas ────────────────────────────────────────────────

@router.get("/comisiones/activas")
async def listar_activas():
    """Retorna solo las comisiones activas hoy."""
    actualizar_estados_automatico()

    conn = get_connection()
    try:
        hoy = date.today().isoformat()
        rows = conn.execute("""
            SELECT * FROM comisiones
            WHERE estado = 'Activa'
            ORDER BY fecha_termino ASC
        """).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


# ── GET /api/comisiones/export ─────────────────────────────────────────────────

@router.get("/comisiones/export")
async def exportar_comisiones(
    tipo: Optional[str] = Query(None),
    estado: Optional[str] = Query(None),
    responsable: Optional[str] = Query(None),
    codigo: Optional[str] = Query(None),
    solo_activas: bool = Query(False)
):
    """
    Exporta las comisiones filtradas a un archivo Excel para descarga.
    """
    from services.excel_service import generar_export_comisiones

    actualizar_estados_automatico()

    conn = get_connection()
    try:
        query = "SELECT * FROM comisiones WHERE 1=1"
        params = []
        if solo_activas:
            query += " AND estado = 'Activa'"
        elif estado:
            query += " AND estado = ?"
            params.append(estado)
        if tipo:
            query += " AND tipo = ?"
            params.append(tipo)
        if responsable:
            query += " AND responsable = ?"
            params.append(responsable)
        if codigo:
            query += " AND codigo LIKE ?"
            params.append(f"%{codigo}%")
        query += " ORDER BY fecha_termino ASC"

        rows = conn.execute(query, params).fetchall()
        comisiones = [_row_to_dict(r) for r in rows]
    finally:
        conn.close()

    titulo = "Dashboard" if solo_activas else "Histórico"
    excel_bytes = generar_export_comisiones(comisiones, titulo)

    nombre_archivo = f"comisiones_{titulo.lower()}_{date.today().isoformat()}.xlsx"
    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'}
    )

# ── GET /api/comisiones/template ───────────────────────────────────────────────

@router.get("/comisiones/template")
async def descargar_template():
    """Descarga el template Excel para carga masiva de comisiones."""
    from services.excel_service import generar_template_masivo
    buf = generar_template_masivo()
    nombre = f"Template_Carga_Masiva_{date.today().isoformat()}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'}
    )


# ── POST /api/comisiones/masivo ────────────────────────────────────────────

@router.post("/comisiones/masivo", status_code=200)
async def cargar_masivo(file: UploadFile = File(...)):
    """
    Procesa un Excel de carga masiva.
    Columnas esperadas: tipo, codigo, comision_anterior, comision_nueva,
                        fecha_inicio, fecha_termino, responsable, motivo
    Retorna: {insertados: int, errores: [{fila, errores}]}
    """
    import openpyxl
    from datetime import datetime as dt
    from services.email_service import enviar_email_carga

    content = await file.read()
    try:
        wb = openpyxl.load_workbook(io.BytesIO(content))
        ws = wb.active
    except Exception as e:
        raise HTTPException(400, f"No se pudo leer el archivo Excel: {e}")

    actualizar_estados_automatico()

    items_ok = []
    errores = []

    for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if not any(cell is not None and str(cell).strip() != '' for cell in row):
            continue  # fila vacía

        cols = list(row) + [None] * 8
        tipo, codigo, com_ant, com_nva, f_inicio, f_termino, responsable, motivo = cols[:8]

        fila_err = []
        # Validar tipo
        tipo = str(tipo).strip() if tipo else ''
        if tipo not in ('SKU', 'Seller'):
            fila_err.append("tipo debe ser 'SKU' o 'Seller'")
        # Validar codigo
        codigo = str(codigo).strip() if codigo else ''
        if not codigo:
            fila_err.append("codigo vacío")
        # Validar comisiones
        try:
            com_ant = float(com_ant)
            if not (0 <= com_ant <= 100): raise ValueError()
        except (TypeError, ValueError):
            fila_err.append("comision_anterior inválida (0-100)")
            com_ant = None
        try:
            com_nva = float(com_nva)
            if not (0 <= com_nva <= 100): raise ValueError()
        except (TypeError, ValueError):
            fila_err.append("comision_nueva inválida (0-100)")
            com_nva = None
        if com_ant is not None and com_nva is not None and com_ant == com_nva:
            fila_err.append("comision_nueva debe ser distinta a comision_anterior")
        # Validar fechas
        def _parse_fecha(v):
            if v is None: return None
            if isinstance(v, (dt,)): return v.date().isoformat()
            if hasattr(v, 'isoformat'): return v.isoformat()
            s = str(v).strip()
            for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'):
                try: return dt.strptime(s, fmt).date().isoformat()
                except: pass
            return None
        f_inicio_str = _parse_fecha(f_inicio)
        f_termino_str = _parse_fecha(f_termino)
        if not f_inicio_str:
            fila_err.append("fecha_inicio inválida (use YYYY-MM-DD)")
        if not f_termino_str:
            fila_err.append("fecha_termino inválida (use YYYY-MM-DD)")
        if f_inicio_str and f_termino_str and f_termino_str <= f_inicio_str:
            fila_err.append("fecha_termino debe ser posterior a fecha_inicio")
        # Validar responsable
        responsable = str(responsable).strip() if responsable else ''
        if not responsable:
            fila_err.append("responsable vacío")

        if fila_err:
            errores.append({"fila": row_idx, "errores": fila_err})
            continue

        items_ok.append({
            'tipo': tipo,
            'codigo': codigo,
            'comision_anterior': com_ant,
            'comision_nueva': com_nva,
            'fecha_inicio': f_inicio_str,
            'fecha_termino': f_termino_str,
            'responsable': responsable,
            'motivo': str(motivo).strip() if motivo else None
        })

    # Insertar los registros válidos
    insertados = []
    for item in items_ok:
        try:
            estado = _calcular_estado(item['fecha_inicio'], item['fecha_termino'], 'Programada')
            with _write_lock:
                conn = get_connection()
                try:
                    # Validar solapamiento
                    existe = conn.execute("""
                        SELECT id FROM comisiones
                        WHERE tipo = ? AND codigo = ?
                          AND estado NOT IN ('Anulada', 'Vencida', 'Vencida_Notificada')
                          AND fecha_inicio <= ? AND fecha_termino >= ?
                    """, (item['tipo'], item['codigo'], item['fecha_termino'], item['fecha_inicio'])).fetchone()
                    if existe:
                        errores.append({"fila": "?", "errores": [
                            f"{item['tipo']} {item['codigo']}: solapamiento con comisión ID {existe['id']}"
                        ]})
                        continue
                    cursor = conn.execute("""
                        INSERT INTO comisiones
                          (tipo, codigo, comision_anterior, comision_nueva,
                           fecha_inicio, fecha_termino, responsable, motivo, estado)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        item['tipo'], item['codigo'], item['comision_anterior'], item['comision_nueva'],
                        item['fecha_inicio'], item['fecha_termino'], item['responsable'],
                        item['motivo'], estado
                    ))
                    conn.commit()
                    row = conn.execute("SELECT * FROM comisiones WHERE id = ?", (cursor.lastrowid,)).fetchone()
                    insertados.append(_row_to_dict(row))
                finally:
                    conn.close()
        except Exception as e:
            logger.warning(f"Error insertando fila masiva: {e}")
            errores.append({"fila": "?", "errores": [str(e)]})

    # Enviar email si hay inserciones
    if insertados:
        try:
            enviar_email_carga(insertados)
        except Exception as e:
            logger.warning(f"No se pudo enviar email de carga masiva: {e}")

    return {"insertados": len(insertados), "errores": errores}

# ── PUT /api/comisiones/{id}/anular ───────────────────────────────────────────

@router.put("/comisiones/{comision_id}/anular")
async def anular_comision(comision_id: int):
    """
    Anula una comisión. Las comisiones anuladas no se pueden reactivar.
    Solo se pueden anular comisiones en estado Programada o Activa.
    """
    with _write_lock:
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM comisiones WHERE id = ?", (comision_id,)
            ).fetchone()

            if not row:
                raise HTTPException(status_code=404, detail="Comisión no encontrada")

            comision = _row_to_dict(row)
            if comision["estado"] in ("Vencida", "Vencida_Notificada", "Anulada"):
                raise HTTPException(
                    status_code=400,
                    detail=f"No se puede anular una comisión con estado '{comision['estado']}'"
                )

            conn.execute("""
                UPDATE comisiones
                SET estado = 'Anulada', updated_at = datetime('now')
                WHERE id = ?
            """, (comision_id,))
            conn.commit()

            row = conn.execute(
                "SELECT * FROM comisiones WHERE id = ?", (comision_id,)
            ).fetchone()
            return {
                "success": True,
                "mensaje": f"Comisión ID {comision_id} anulada correctamente",
                "comision": _row_to_dict(row)
            }
        finally:
            conn.close()


# ── DELETE /api/comisiones/{id} ───────────────────────────────────────────────

@router.delete("/comisiones/{comision_id}")
async def eliminar_comision(comision_id: int, x_admin_pin: str = Header(default=None)):
    """
    Elimina permanentemente una comisión anulada.
    Solo funciona para estado='Anulada' y requiere el PIN de administrador.
    """
    pin_correcto = os.getenv("ADMIN_PIN", "")
    if not pin_correcto or x_admin_pin != pin_correcto:
        raise HTTPException(status_code=403, detail="PIN incorrecto")

    with _write_lock:
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM comisiones WHERE id = ?", (comision_id,)
            ).fetchone()

            if not row:
                raise HTTPException(status_code=404, detail="Comisión no encontrada")

            comision = _row_to_dict(row)
            if comision["estado"] != "Anulada":
                raise HTTPException(
                    status_code=400,
                    detail=f"Solo se pueden eliminar comisiones con estado 'Anulada'. Estado actual: '{comision['estado']}'"
                )

            conn.execute("DELETE FROM comisiones WHERE id = ?", (comision_id,))
            conn.commit()
            return {"success": True, "mensaje": f"Comisión ID {comision_id} eliminada permanentemente"}
        finally:
            conn.close()


# ── POST /api/admin/revision-manual ──────────────────────────────────────────

@router.post("/admin/revision-manual")
async def revision_manual():
    """
    Ejecuta manualmente el job de revisión de vencimientos.
    Útil para testing o cuando el cron no corrió.
    """
    from services.scheduler import ejecutar_revision_manual
    resultado = ejecutar_revision_manual()
    return resultado


# ── GET /api/responsables ─────────────────────────────────────────────────────

@router.get("/responsables")
async def listar_responsables():
    """Retorna la lista de responsables configurados en .env."""
    responsables_str = os.getenv("RESPONSABLES", "")
    lista = [r.strip() for r in responsables_str.split(",") if r.strip()]
    return {"responsables": lista}


# ── GET /api/stats ────────────────────────────────────────────────────────────

@router.get("/stats")
async def obtener_stats():
    """Retorna estadísticas rápidas para el dashboard."""
    actualizar_estados_automatico()
    from datetime import timedelta

    conn = get_connection()
    try:
        hoy = date.today()
        stats = {}

        # Total por estado
        for estado in ["Activa", "Programada", "Vencida", "Vencida_Notificada", "Anulada"]:
            count = conn.execute(
                "SELECT COUNT(*) FROM comisiones WHERE estado = ?", (estado,)
            ).fetchone()[0]
            stats[f"total_{estado.lower()}"] = count

        # Próximas a vencer (en los próximos 2 días)
        dias_aviso = int(os.getenv("DIAS_AVISO_VENCIMIENTO", "2"))
        fecha_limite = (hoy + timedelta(days=dias_aviso)).isoformat()
        stats["proximas_a_vencer"] = conn.execute("""
            SELECT COUNT(*) FROM comisiones
            WHERE estado = 'Activa'
              AND fecha_termino <= ?
              AND fecha_termino >= ?
        """, (fecha_limite, hoy.isoformat())).fetchone()[0]

        return stats
    finally:
        conn.close()
