"""
scheduler.py - Cron jobs automáticos para verificación de vencimientos.

Ejecuta diariamente (hora configurable en .env):
  1. Actualiza estados de comisiones (Programada→Activa, Activa→Vencida)
  2. Detecta comisiones vencidas y envía email con reversa adjunta
  3. Detecta comisiones próximas a vencer y envía email de warning preventivo

El scheduler usa APScheduler con timezone de Chile (America/Santiago).
"""
import os
import logging
from datetime import date, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

logger = logging.getLogger(__name__)

# Zona horaria de Chile (ajusta automáticamente DST)
TZ_CHILE = pytz.timezone("America/Santiago")

# Instancia global del scheduler
_scheduler: BackgroundScheduler = None


def _job_revision_diaria():
    """
    Job principal que corre diariamente.
    Actualiza estados y envía notificaciones según corresponda.
    """
    from database import actualizar_estados_automatico, get_connection
    from services.email_service import enviar_email_vencimiento, enviar_email_warning

    logger.info("🕐 Iniciando revisión diaria de comisiones...")

    try:
        # Paso 1: Actualizar estados automáticamente
        actualizar_estados_automatico()

        conn = get_connection()
        hoy = date.today()
        dias_aviso = int(os.getenv("DIAS_AVISO_VENCIMIENTO", "2"))

        # ── Paso 2: Detectar comisiones vencidas no notificadas ────────────────
        cursor = conn.execute("""
            SELECT id, tipo, codigo, comision_anterior, comision_nueva,
                   fecha_inicio, fecha_termino, responsable, motivo
            FROM comisiones
            WHERE estado = 'Vencida'
              AND email_vencimiento_enviado = 0
        """)
        vencidas = [dict(row) for row in cursor.fetchall()]

        if vencidas:
            logger.info(f"⚠️  Encontradas {len(vencidas)} comisiones vencidas. Enviando email...")
            enviado = enviar_email_vencimiento(vencidas)

            if enviado:
                # Marcar como notificadas para no enviar duplicados
                ids = [str(c["id"]) for c in vencidas]
                conn.execute(f"""
                    UPDATE comisiones
                    SET estado = 'Vencida_Notificada',
                        email_vencimiento_enviado = 1,
                        updated_at = datetime('now')
                    WHERE id IN ({','.join(ids)})
                """)
                conn.commit()
                logger.info(f"✅ Email de vencimiento enviado. IDs marcados: {ids}")
            else:
                logger.error("❌ No se pudo enviar el email de vencimiento")
        else:
            logger.info("✅ No hay comisiones vencidas pendientes de notificar.")

        # ── Paso 3: Warning preventivo (N días antes) ─────────────────────────
        fecha_limite = (hoy + timedelta(days=dias_aviso)).isoformat()
        hoy_str = hoy.isoformat()

        cursor = conn.execute("""
            SELECT id, tipo, codigo, comision_anterior, comision_nueva,
                   fecha_inicio, fecha_termino, responsable, motivo
            FROM comisiones
            WHERE estado IN ('Activa', 'Programada')
              AND fecha_termino <= ?
              AND fecha_termino >= ?
              AND email_warning_enviado = 0
        """, (fecha_limite, hoy_str))
        por_vencer = [dict(row) for row in cursor.fetchall()]

        if por_vencer:
            logger.info(f"🔔 {len(por_vencer)} comisiones vencen pronto. Enviando warning...")
            enviado_w = enviar_email_warning(por_vencer, dias_aviso)

            if enviado_w:
                ids_w = [str(c["id"]) for c in por_vencer]
                conn.execute(f"""
                    UPDATE comisiones
                    SET email_warning_enviado = 1,
                        updated_at = datetime('now')
                    WHERE id IN ({','.join(ids_w)})
                """)
                conn.commit()
                logger.info(f"✅ Warning enviado. IDs: {ids_w}")
        else:
            logger.info(f"✅ No hay comisiones venciendo en los próximos {dias_aviso} días.")

        conn.close()

    except Exception as e:
        logger.error(f"❌ Error en job de revisión diaria: {e}", exc_info=True)


def iniciar_scheduler():
    """
    Inicia el scheduler con el job diario configurado.
    Horario configurable vía variables de entorno (.env).
    Por defecto: 7:00 AM hora Chile.
    """
    global _scheduler

    hora = int(os.getenv("CRON_HORA_UTC", "11"))   # 7 AM Chile = 11 AM UTC
    minuto = int(os.getenv("CRON_MINUTO", "0"))

    _scheduler = BackgroundScheduler(timezone=TZ_CHILE)

    # Job principal: verificación diaria
    _scheduler.add_job(
        _job_revision_diaria,
        trigger=CronTrigger(
            hour=hora,
            minute=minuto,
            timezone=TZ_CHILE  # APScheduler convierte automáticamente
        ),
        id="revision_diaria",
        name="Revisión diaria de vencimientos",
        misfire_grace_time=3600,  # Si se perdió la hora, correr hasta 1 hora después
        max_instances=1           # No correr múltiples instancias simultáneas
    )

    _scheduler.start()
    hora_local = _convertir_utc_a_chile(hora, minuto)
    logger.info(
        f"✅ Scheduler iniciado. Job diario configurado para las "
        f"{hora_local} hora Chile ({hora:02d}:{minuto:02d} UTC)"
    )

    return _scheduler


def detener_scheduler():
    """Detiene el scheduler graciosamente al apagar la aplicación."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("🛑 Scheduler detenido.")


def ejecutar_revision_manual() -> dict:
    """
    Ejecuta la revisión diaria manualmente (para testing o trigger desde API).
    Retorna un resumen del resultado.
    """
    try:
        _job_revision_diaria()
        return {"success": True, "mensaje": "Revisión ejecutada correctamente"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _convertir_utc_a_chile(hora_utc: int, minuto: int) -> str:
    """Convierte hora UTC a hora Chile para mostrar en logs."""
    from datetime import datetime
    dt_utc = datetime.now(pytz.utc).replace(hour=hora_utc, minute=minuto, second=0)
    dt_chile = dt_utc.astimezone(TZ_CHILE)
    return dt_chile.strftime("%H:%M")
