"""
email_service.py - Envío de emails con adjuntos Excel via SMTP.

Maneja dos tipos de notificaciones:
  1. Email de carga: al registrar nuevas comisiones
  2. Email de vencimiento: cuando comisiones expiran (con reversa)
  3. Email de warning preventivo: días antes del vencimiento
"""
import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import date, datetime
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

# ── Configuración desde variables de entorno ───────────────────────────────────

def _get_smtp_config() -> dict:
    return {
        "host": os.getenv("SMTP_HOST", "smtp.gmail.com"),
        "port": int(os.getenv("SMTP_PORT", "587")),
        "user": os.getenv("SMTP_USER", ""),
        "password": os.getenv("SMTP_PASSWORD", ""),
        "use_tls": os.getenv("SMTP_USE_TLS", "true").lower() == "true",
        "destinatario": os.getenv("EMAIL_DESTINATARIO", ""),
        "remitente": os.getenv("EMAIL_REMITENTE", os.getenv("SMTP_USER", "")),
        "remitente_nombre": os.getenv("EMAIL_REMITENTE_NOMBRE", "Sistema de Comisiones"),
    }


def _adjuntar_excel(msg: MIMEMultipart, contenido_bytes: bytes, nombre_archivo: str):
    """Adjunta un archivo Excel al mensaje email."""
    adjunto = MIMEBase(
        "application",
        "vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    adjunto.set_payload(contenido_bytes)
    encoders.encode_base64(adjunto)
    adjunto.add_header(
        "Content-Disposition",
        f'attachment; filename="{nombre_archivo}"'
    )
    msg.attach(adjunto)


def _enviar_smtp(msg: MIMEMultipart, cfg: dict):
    """Establece conexión SMTP y envía el mensaje."""
    with smtplib.SMTP(cfg["host"], cfg["port"]) as server:
        server.ehlo()
        if cfg["use_tls"]:
            server.starttls()
            server.ehlo()
        if cfg["user"] and cfg["password"]:
            server.login(cfg["user"], cfg["password"])
        server.sendmail(
            cfg["remitente"],
            cfg["destinatario"],
            msg.as_string()
        )
    logger.info(f"✉️  Email enviado a {cfg['destinatario']}: {msg['Subject']}")


def _cuerpo_html_carga(items: List[Dict[str, Any]]) -> str:
    """Genera el cuerpo HTML del email de carga de comisiones."""
    hoy = datetime.now().strftime("%d/%m/%Y %H:%M")
    filas_html = ""
    for item in items:
        variacion = item["comision_nueva"] - item["comision_anterior"]
        signo = "▲" if variacion > 0 else "▼"
        color_var = "#e53935" if variacion > 0 else "#43a047"
        filas_html += f"""
        <tr>
            <td style="padding:8px 12px;border:1px solid #ddd;">{item['tipo']}</td>
            <td style="padding:8px 12px;border:1px solid #ddd;font-weight:bold;">{item['codigo']}</td>
            <td style="padding:8px 12px;border:1px solid #ddd;">{item['comision_anterior']:.1f}%</td>
            <td style="padding:8px 12px;border:1px solid #ddd;">
                {item['comision_nueva']:.1f}%
                <span style="color:{color_var};margin-left:4px;">{signo} {abs(variacion):.1f}%</span>
            </td>
            <td style="padding:8px 12px;border:1px solid #ddd;">{item['fecha_inicio']}</td>
            <td style="padding:8px 12px;border:1px solid #ddd;">{item['fecha_termino']}</td>
            <td style="padding:8px 12px;border:1px solid #ddd;">{item['responsable']}</td>
            <td style="padding:8px 12px;border:1px solid #ddd;color:#666;">{item.get('motivo') or '—'}</td>
        </tr>"""

    return f"""
    <html><body style="font-family:Arial,sans-serif;color:#333;max-width:900px;">
        <div style="background:#1F3864;color:white;padding:16px 24px;border-radius:6px 6px 0 0;">
            <h2 style="margin:0;">📋 Nueva Carga de Comisión</h2>
            <p style="margin:4px 0 0;opacity:0.8;font-size:13px;">{hoy}</p>
        </div>
        <div style="padding:20px;border:1px solid #ddd;border-top:none;border-radius:0 0 6px 6px;">
            <p>Se han registrado <strong>{len(items)}</strong> comisión(es) nueva(s).</p>
            <p>Se adjuntan los archivos para cargar en la plataforma:</p>
            <ul>
                <li><strong>Upload SKU</strong>: Archivo de entidades a crear/actualizar</li>
                <li><strong>Upload SKU Value New</strong>: Archivo con las nuevas comisiones</li>
            </ul>
            <table style="border-collapse:collapse;width:100%;font-size:13px;margin-top:16px;">
                <thead style="background:#1F3864;color:white;">
                    <tr>
                        <th style="padding:10px 12px;border:1px solid #3a5a9a;">Tipo</th>
                        <th style="padding:10px 12px;border:1px solid #3a5a9a;">Código</th>
                        <th style="padding:10px 12px;border:1px solid #3a5a9a;">Com. Anterior</th>
                        <th style="padding:10px 12px;border:1px solid #3a5a9a;">Com. Nueva</th>
                        <th style="padding:10px 12px;border:1px solid #3a5a9a;">Fecha Inicio</th>
                        <th style="padding:10px 12px;border:1px solid #3a5a9a;">Fecha Término</th>
                        <th style="padding:10px 12px;border:1px solid #3a5a9a;">Responsable</th>
                        <th style="padding:10px 12px;border:1px solid #3a5a9a;">Motivo</th>
                    </tr>
                </thead>
                <tbody>{filas_html}</tbody>
            </table>
            <p style="margin-top:20px;font-size:12px;color:#888;">
                Sistema de Gestión de Comisiones — Falabella Marketplace
            </p>
        </div>
    </body></html>"""


def _cuerpo_html_vencimiento(items: List[Dict[str, Any]]) -> str:
    """Genera el cuerpo HTML del email de vencimiento."""
    hoy = datetime.now().strftime("%d/%m/%Y %H:%M")
    filas_html = ""
    for item in items:
        filas_html += f"""
        <tr>
            <td style="padding:8px 12px;border:1px solid #ddd;">{item['tipo']}</td>
            <td style="padding:8px 12px;border:1px solid #ddd;font-weight:bold;">{item['codigo']}</td>
            <td style="padding:8px 12px;border:1px solid #ddd;">{item['comision_nueva']:.1f}%</td>
            <td style="padding:8px 12px;border:1px solid #ddd;">{item['comision_anterior']:.1f}%</td>
            <td style="padding:8px 12px;border:1px solid #ddd;">{item['fecha_termino']}</td>
            <td style="padding:8px 12px;border:1px solid #ddd;">{item['responsable']}</td>
        </tr>"""

    return f"""
    <html><body style="font-family:Arial,sans-serif;color:#333;max-width:900px;">
        <div style="background:#c62828;color:white;padding:16px 24px;border-radius:6px 6px 0 0;">
            <h2 style="margin:0;">⚠️ Comisiones Vencidas — Acción Requerida</h2>
            <p style="margin:4px 0 0;opacity:0.8;font-size:13px;">{hoy}</p>
        </div>
        <div style="padding:20px;border:1px solid #ddd;border-top:none;border-radius:0 0 6px 6px;">
            <div style="background:#ffebee;border-left:4px solid #c62828;padding:12px 16px;margin-bottom:16px;border-radius:4px;">
                <strong>Hay {len(items)} comisión(es) vencida(s) que requieren acción inmediata.</strong><br>
                Carga el archivo adjunto <em>Reversa SKU New</em> en la plataforma para
                restablecer las comisiones originales.
            </div>
            <table style="border-collapse:collapse;width:100%;font-size:13px;">
                <thead style="background:#c62828;color:white;">
                    <tr>
                        <th style="padding:10px 12px;border:1px solid #e57373;">Tipo</th>
                        <th style="padding:10px 12px;border:1px solid #e57373;">Código</th>
                        <th style="padding:10px 12px;border:1px solid #e57373;">Com. Temporal</th>
                        <th style="padding:10px 12px;border:1px solid #e57373;">Com. Original</th>
                        <th style="padding:10px 12px;border:1px solid #e57373;">Venció</th>
                        <th style="padding:10px 12px;border:1px solid #e57373;">Responsable</th>
                    </tr>
                </thead>
                <tbody>{filas_html}</tbody>
            </table>
            <p style="margin-top:20px;font-size:12px;color:#888;">
                Sistema de Gestión de Comisiones — Falabella Marketplace
            </p>
        </div>
    </body></html>"""


def _cuerpo_html_warning(items: List[Dict[str, Any]], dias_restantes: int) -> str:
    """Genera el cuerpo HTML del email de aviso preventivo."""
    hoy = datetime.now().strftime("%d/%m/%Y %H:%M")
    filas_html = ""
    for item in items:
        try:
            dias = (date.fromisoformat(item["fecha_termino"]) - date.today()).days
        except Exception:
            dias = "?"
        filas_html += f"""
        <tr>
            <td style="padding:8px 12px;border:1px solid #ddd;">{item['tipo']}</td>
            <td style="padding:8px 12px;border:1px solid #ddd;font-weight:bold;">{item['codigo']}</td>
            <td style="padding:8px 12px;border:1px solid #ddd;">{item['comision_nueva']:.1f}%</td>
            <td style="padding:8px 12px;border:1px solid #ddd;">{item['comision_anterior']:.1f}%</td>
            <td style="padding:8px 12px;border:1px solid #ddd;">{item['fecha_termino']}</td>
            <td style="padding:8px 12px;border:1px solid #ddd;color:#e65100;font-weight:bold;">{dias} día(s)</td>
            <td style="padding:8px 12px;border:1px solid #ddd;">{item['responsable']}</td>
        </tr>"""

    return f"""
    <html><body style="font-family:Arial,sans-serif;color:#333;max-width:900px;">
        <div style="background:#e65100;color:white;padding:16px 24px;border-radius:6px 6px 0 0;">
            <h2 style="margin:0;">🔔 Aviso: Comisiones próximas a vencer</h2>
            <p style="margin:4px 0 0;opacity:0.8;font-size:13px;">{hoy}</p>
        </div>
        <div style="padding:20px;border:1px solid #ddd;border-top:none;border-radius:0 0 6px 6px;">
            <div style="background:#fff3e0;border-left:4px solid #e65100;padding:12px 16px;margin-bottom:16px;border-radius:4px;">
                <strong>Hay {len(items)} comisión(es) que vencen en {dias_restantes} día(s) o menos.</strong><br>
                Prepara la reversa con anticipación para evitar pérdidas.
            </div>
            <table style="border-collapse:collapse;width:100%;font-size:13px;">
                <thead style="background:#e65100;color:white;">
                    <tr>
                        <th style="padding:10px 12px;border:1px solid #ffb74d;">Tipo</th>
                        <th style="padding:10px 12px;border:1px solid #ffb74d;">Código</th>
                        <th style="padding:10px 12px;border:1px solid #ffb74d;">Com. Temporal</th>
                        <th style="padding:10px 12px;border:1px solid #ffb74d;">Com. Original</th>
                        <th style="padding:10px 12px;border:1px solid #ffb74d;">Vence</th>
                        <th style="padding:10px 12px;border:1px solid #ffb74d;">Días Rest.</th>
                        <th style="padding:10px 12px;border:1px solid #ffb74d;">Responsable</th>
                    </tr>
                </thead>
                <tbody>{filas_html}</tbody>
            </table>
            <p style="margin-top:20px;font-size:12px;color:#888;">
                Sistema de Gestión de Comisiones — Falabella Marketplace
            </p>
        </div>
    </body></html>"""


# ── Funciones públicas ─────────────────────────────────────────────────────────

def enviar_email_carga(items: List[Dict[str, Any]]) -> bool:
    """
    Envía el email de notificación cuando se carga una nueva comisión.
    Adjunta: Upload SKU + Upload SKU Value New.

    Args:
        items: Lista de comisiones recién cargadas

    Returns:
        True si se envió correctamente, False si hubo error
    """
    from services.excel_service import generar_upload_sku, generar_upload_sku_value_new

    cfg = _get_smtp_config()
    if not cfg["destinatario"]:
        logger.warning("EMAIL_DESTINATARIO no configurado. Email no enviado.")
        return False

    try:
        hoy_str = date.today().strftime("%d/%m/%Y")
        primer_item = items[0]
        tipo_codigo = f"{primer_item['tipo']} {primer_item['codigo']}"
        if len(items) > 1:
            tipo_codigo += f" (+{len(items)-1} más)"

        msg = MIMEMultipart("mixed")
        msg["From"] = f"{cfg['remitente_nombre']} <{cfg['remitente']}>"
        msg["To"] = cfg["destinatario"]
        msg["Subject"] = f"[Comisiones] Nueva carga de comisión - {tipo_codigo} - {hoy_str}"

        # Cuerpo HTML
        msg.attach(MIMEText(_cuerpo_html_carga(items), "html", "utf-8"))

        # Adjunto 1: Upload SKU
        skus_items = [i for i in items if i["tipo"] == "SKU"]
        if skus_items:
            excel1 = generar_upload_sku(skus_items)
            _adjuntar_excel(msg, excel1, f"Upload_SKU_{date.today().isoformat()}.xlsx")

        # Adjunto 2: Upload SKU Value New
        if skus_items:
            excel2 = generar_upload_sku_value_new(skus_items)
            _adjuntar_excel(msg, excel2, f"Upload_SKU_Value_New_{date.today().isoformat()}.xlsx")

        _enviar_smtp(msg, cfg)
        return True

    except Exception as e:
        logger.error(f"Error enviando email de carga: {e}")
        return False


def enviar_email_vencimiento(items: List[Dict[str, Any]]) -> bool:
    """
    Envía el email de vencimiento con la reversa adjunta.
    Se llama cuando el cron detecta comisiones vencidas.
    Adjunta: Reversa SKU New.

    Args:
        items: Lista de comisiones vencidas

    Returns:
        True si se envió correctamente, False si hubo error
    """
    from services.excel_service import generar_reversa_sku

    cfg = _get_smtp_config()
    if not cfg["destinatario"]:
        logger.warning("EMAIL_DESTINATARIO no configurado. Email no enviado.")
        return False

    try:
        msg = MIMEMultipart("mixed")
        msg["From"] = f"{cfg['remitente_nombre']} <{cfg['remitente']}>"
        msg["To"] = cfg["destinatario"]
        msg["Subject"] = "⚠️ [Comisiones] SKUs/Sellers con comisión VENCIDA - Acción requerida"

        msg.attach(MIMEText(_cuerpo_html_vencimiento(items), "html", "utf-8"))

        # Adjunto 3: Reversa SKU (solo para SKU — agregar lógica Seller si aplica)
        skus_items = [i for i in items if i["tipo"] == "SKU"]
        if skus_items:
            excel3 = generar_reversa_sku(skus_items)
            _adjuntar_excel(msg, excel3, f"Reversa_SKU_New_{date.today().isoformat()}.xlsx")

        _enviar_smtp(msg, cfg)
        return True

    except Exception as e:
        logger.error(f"Error enviando email de vencimiento: {e}")
        return False


def enviar_email_warning(items: List[Dict[str, Any]], dias_restantes: int) -> bool:
    """
    Envía aviso preventivo antes del vencimiento.

    Args:
        items: Comisiones próximas a vencer
        dias_restantes: Días de anticipación configurados

    Returns:
        True si se envió correctamente, False si hubo error
    """
    cfg = _get_smtp_config()
    if not cfg["destinatario"]:
        return False

    try:
        msg = MIMEMultipart("mixed")
        msg["From"] = f"{cfg['remitente_nombre']} <{cfg['remitente']}>"
        msg["To"] = cfg["destinatario"]
        msg["Subject"] = f"🔔 [Comisiones] {len(items)} comisión(es) vencen en {dias_restantes} día(s)"

        msg.attach(MIMEText(_cuerpo_html_warning(items, dias_restantes), "html", "utf-8"))

        _enviar_smtp(msg, cfg)
        return True

    except Exception as e:
        logger.error(f"Error enviando email de warning: {e}")
        return False
