"""
excel_service.py - Generación de archivos Excel para los emails de notificación.

Genera tres tipos de archivos basados en los templates de la plataforma:
  1. Upload SKU: template de carga de entidades
  2. Upload SKU Value New: template de carga de nuevas comisiones
  3. Reversa SKU New: template de reset/reversa de comisiones

NOTA IMPORTANTE: La estructura de columnas está basada en las descripciones
de los templates. Si alguna columna no coincide con el template exacto de
la plataforma, ajustar los headers en las funciones correspondientes.
"""
import io
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from typing import List, Dict, Any


# ── Estilos reutilizables ──────────────────────────────────────────────────────

def _estilo_header(ws, fila: int, num_cols: int):
    """Aplica estilo de encabezado (fondo azul, texto blanco, negrita)."""
    fill = PatternFill(start_color="1F3864", end_color="1F3864", fill_type="solid")
    font = Font(color="FFFFFF", bold=True, size=11)
    borde = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin")
    )
    for col in range(1, num_cols + 1):
        cell = ws.cell(row=fila, column=col)
        cell.fill = fill
        cell.font = font
        cell.border = borde
        cell.alignment = Alignment(horizontal="center", vertical="center")


def _estilo_datos(ws, fila: int, num_cols: int, color_fila: str = "FFFFFF"):
    """Aplica estilo a una fila de datos."""
    fill = PatternFill(start_color=color_fila, end_color=color_fila, fill_type="solid")
    borde = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin")
    )
    for col in range(1, num_cols + 1):
        cell = ws.cell(row=fila, column=col)
        cell.fill = fill
        cell.border = borde
        cell.alignment = Alignment(horizontal="left", vertical="center")


def _ajustar_ancho_columnas(ws, anchos_minimos: dict = None):
    """Ajusta el ancho de columnas automáticamente."""
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            if cell.value:
                max_len = max(max_len, len(str(cell.value)))
        ancho = max(max_len + 4, 12)
        if anchos_minimos and col_letter in anchos_minimos:
            ancho = max(ancho, anchos_minimos[col_letter])
        ws.column_dimensions[col_letter].width = ancho


def _workbook_a_bytes(wb: openpyxl.Workbook) -> bytes:
    """Serializa un Workbook a bytes para adjuntar en email."""
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


# ── Template 1: Upload SKU ─────────────────────────────────────────────────────

def generar_upload_sku(items: List[Dict[str, Any]]) -> bytes:
    """
    Entregable 1 - 'Upload SKU':
    Template de carga de entidades SKU en la plataforma.

    Estructura:
      Col A: Entity Name → valor: 'commissionsku' por cada fila
      Col B: id          → valor: código del SKU

    Las demás columnas del template van vacías (se incluyen para mantener
    el formato exacto del archivo de la plataforma).

    Args:
        items: Lista de dicts con {'codigo': str, ...}

    Returns:
        bytes del archivo .xlsx generado
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Upload"

    # ── Encabezados del template ───────────────────────────────────────────────
    # AJUSTAR si el template de la plataforma tiene más columnas
    headers = ["Entity Name", "id"]
    ws.append(headers)
    _estilo_header(ws, 1, len(headers))
    ws.row_dimensions[1].height = 20

    # ── Datos ──────────────────────────────────────────────────────────────────
    colores = ["F2F7FF", "FFFFFF"]  # Filas alternadas
    for i, item in enumerate(items):
        fila = ["commissionsku", item["codigo"]]
        ws.append(fila)
        color = colores[i % 2]
        _estilo_datos(ws, i + 2, len(headers), color)

    _ajustar_ancho_columnas(ws, {"A": 18, "B": 20})
    return _workbook_a_bytes(wb)


# ── Template 2: Upload SKU Value New ──────────────────────────────────────────

def generar_upload_sku_value_new(items: List[Dict[str, Any]]) -> bytes:
    """
    Entregable 2 - 'Upload SKU Value New':
    Template de carga de nuevas comisiones por SKU.

    Estructura:
      Col A: Attribute      → valor: 'commissionsku' por cada fila
      Col B: (vacío)        → columna del template, sin datos
      Col C: (vacío)        → columna del template, sin datos
      Col D: commissionsku  → valor: código del SKU
      Col E: Value          → valor: nueva comisión (ej: 18.5)

    NOTA: Los headers de columnas B y C pueden variar según el template exacto
    de tu plataforma. Ajustar si es necesario.

    Args:
        items: Lista de dicts con {'codigo': str, 'comision_nueva': float}

    Returns:
        bytes del archivo .xlsx generado
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Upload SKU Value"

    # ── Encabezados ────────────────────────────────────────────────────────────
    headers = ["Attribute", "", "", "commissionsku", "Value"]
    ws.append(headers)
    _estilo_header(ws, 1, len(headers))
    ws.row_dimensions[1].height = 20

    # ── Datos ──────────────────────────────────────────────────────────────────
    colores = ["F2F7FF", "FFFFFF"]
    for i, item in enumerate(items):
        fila = [
            "commissionsku",  # A: tipo de atributo
            "",               # B: vacío
            "",               # C: vacío
            item["codigo"],   # D: código SKU
            item["comision_nueva"]  # E: nueva comisión
        ]
        ws.append(fila)
        color = colores[i % 2]
        _estilo_datos(ws, i + 2, len(headers), color)

    _ajustar_ancho_columnas(ws, {"A": 18, "D": 20, "E": 12})
    return _workbook_a_bytes(wb)


# ── Template 3: Reversa SKU New ───────────────────────────────────────────────

def generar_reversa_sku(items: List[Dict[str, Any]]) -> bytes:
    """
    Entregable 3 - 'Reversa SKU New':
    Template para eliminar/resetear comisiones temporales en la plataforma.
    La columna Value va VACÍA (indica al sistema que borre la comisión).

    Estructura:
      Col A: Attribute      → valor: 'commissionsku' por cada fila
      Col B: (vacío)        → columna del template, sin datos
      Col C: (vacío)        → columna del template, sin datos
      Col D: commissionsku  → valor: código del SKU
      Col E: Value          → VACÍO (reset de comisión)

    Args:
        items: Lista de dicts con {'codigo': str, ...}

    Returns:
        bytes del archivo .xlsx generado
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Reversa SKU"

    # ── Encabezados ────────────────────────────────────────────────────────────
    headers = ["Attribute", "", "", "commissionsku", "Value"]
    ws.append(headers)
    _estilo_header(ws, 1, len(headers))
    ws.row_dimensions[1].height = 20

    # ── Datos (Value siempre vacío para reversa) ───────────────────────────────
    colores = ["FFF3F0", "FFFFFF"]  # Rojo claro para indicar que es reversa
    for i, item in enumerate(items):
        fila = [
            "commissionsku",  # A: tipo de atributo
            "",               # B: vacío
            "",               # C: vacío
            item["codigo"],   # D: código SKU
            ""                # E: VACÍO (reversa/reset)
        ]
        ws.append(fila)
        color = colores[i % 2]
        _estilo_datos(ws, i + 2, len(headers), color)

    _ajustar_ancho_columnas(ws, {"A": 18, "D": 20, "E": 12})
    return _workbook_a_bytes(wb)


# ── Export Dashboard/Histórico ─────────────────────────────────────────────────

def generar_export_comisiones(comisiones: List[Dict[str, Any]], titulo: str = "Comisiones") -> bytes:
    """
    Genera un Excel con el listado de comisiones para export del dashboard/histórico.

    Args:
        comisiones: Lista de comisiones del query
        titulo: Título de la hoja

    Returns:
        bytes del archivo .xlsx generado
    """
    from datetime import date

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = titulo[:31]  # Excel limita nombres de hoja a 31 chars

    # ── Encabezados ────────────────────────────────────────────────────────────
    headers = [
        "ID", "Tipo", "Código (SKU/Seller)", "Comisión Anterior (%)",
        "Comisión Nueva (%)", "Fecha Inicio", "Fecha Término",
        "Días Restantes", "Responsable", "Estado", "Motivo", "Fecha Carga"
    ]
    ws.append(headers)
    _estilo_header(ws, 1, len(headers))
    ws.row_dimensions[1].height = 22

    # ── Datos ──────────────────────────────────────────────────────────────────
    hoy = date.today()
    colores_estado = {
        "Activa": "E8F5E9",
        "Programada": "E3F2FD",
        "Vencida": "FBE9E7",
        "Vencida_Notificada": "FFEBEE",
        "Anulada": "ECEFF1"
    }

    for i, c in enumerate(comisiones):
        # Calcular días restantes
        try:
            fecha_fin = date.fromisoformat(c["fecha_termino"])
            dias_rest = (fecha_fin - hoy).days
            dias_str = str(dias_rest) if dias_rest >= 0 else "Vencida"
        except Exception:
            dias_str = "-"

        fila = [
            c["id"],
            c["tipo"],
            c["codigo"],
            c["comision_anterior"],
            c["comision_nueva"],
            c["fecha_inicio"],
            c["fecha_termino"],
            dias_str,
            c["responsable"],
            c["estado"],
            c.get("motivo") or "",
            c["created_at"][:10] if c.get("created_at") else ""
        ]
        ws.append(fila)

        # Color según estado
        color = colores_estado.get(c["estado"], "FFFFFF")
        _estilo_datos(ws, i + 2, len(headers), color)

    # Congelar primera fila
    ws.freeze_panes = "A2"
    _ajustar_ancho_columnas(ws, {"C": 22, "I": 20, "J": 18})
    return _workbook_a_bytes(wb)
