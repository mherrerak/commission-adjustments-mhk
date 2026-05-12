"""
excel_service.py - Generación de archivos Excel para los emails de notificación.

Replica EXACTAMENTE el formato de los templates de la plataforma Falabella:
  1. Upload SKU            → entityName, id, parentEntityId, displayName
  2. Upload SKU Value New  → nota en fila 1, headers en fila 2, datos desde fila 3
  3. Reversa SKU New       → mismo formato que #2 pero columna value vacía
"""
import io
import openpyxl
from openpyxl.styles import Font, Alignment
from openpyxl.utils import get_column_letter
from typing import List, Dict, Any

# Texto de nota que aparece en A1 de los templates de valores (copiado literal del template)
_NOTA_TEMPLATE = (
    "Note:\n"
    " Entity Values Template for  global+seller+commissionsku\n"
    " 1. Do not alter this template format. Fill in the values as is.\n"
    " 1. No altere este formato de plantilla. Rellene los valores tal cual.\n"
    " 2. In the values column, enter only the numerical values. No formulas or VBA scripts "
    "and avoid duplicate rows. e. g: 25, 25.24, 5.26.\n"
    " 2. En la columna de valores, ingrese solo los valores numéricos. Sin fórmulas ni "
    "scripts VBA y evita filas duplicadas. mi. g: 25, 25,24, 5,26.\n"
    " 3. For additional terms and conditions, see the documentation: "
    "https://confluence.falabella.tech/x/FzqnFw \n"
    " 3. Para términos y condiciones adicionales, consulte la documentación: "
    "https://confluence.falabella.tech/x/FzqnFw \n"
)


def _workbook_a_bytes(wb: openpyxl.Workbook) -> bytes:
    """Serializa un Workbook a bytes para adjuntar en email."""
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


def _construir_template_valores(items: List[Dict[str, Any]], incluir_valor: bool) -> openpyxl.Workbook:
    """
    Construye el workbook para Upload SKU Value New y Reversa SKU New.
    Ambos tienen la misma estructura; la única diferencia es si la columna
    'value' (E) lleva el valor de comisión o va vacía.

    Estructura exacta del template:
      Fila 1: Nota en A1 (texto largo, wrap, alto=133.25), B1:E1 vacías
      Fila 2: Headers en negrita → attribute | specialEvent | seller | commissionsku | value
              Alto de fila = 15.5
      Fila 3+: Datos → commissionsku | (vacío) | (vacío) | {codigo} | {valor o vacío}

    Col A width=25.0 (igual al template original)
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"

    # ── Fila 1: Nota ───────────────────────────────────────────────────────────
    ws.cell(1, 1).value = _NOTA_TEMPLATE
    ws.cell(1, 1).alignment = Alignment(wrap_text=True, vertical="top")
    ws.row_dimensions[1].height = 133.25

    # ── Fila 2: Headers (negrita, tal cual el template) ────────────────────────
    headers = ["attribute", "specialEvent", "seller", "commissionsku", "value"]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(2, col)
        cell.value = h
        cell.font = Font(bold=True)
    ws.row_dimensions[2].height = 15.5

    # ── Filas de datos (desde fila 3) ─────────────────────────────────────────
    for i, item in enumerate(items):
        fila = 3 + i
        ws.cell(fila, 1).value = "commissionsku"  # attribute
        ws.cell(fila, 2).value = None              # specialEvent (vacío)
        ws.cell(fila, 3).value = None              # seller (vacío)
        ws.cell(fila, 4).value = item["codigo"]    # commissionsku
        # value: nueva comisión si es upload, vacío si es reversa
        ws.cell(fila, 5).value = item["comision_nueva"] if incluir_valor else None

    # ── Anchos de columna (igual al template) ──────────────────────────────────
    ws.column_dimensions["A"].width = 25.0

    return wb


# ── Template 1: Upload SKU ─────────────────────────────────────────────────────

def generar_upload_sku(items: List[Dict[str, Any]]) -> bytes:
    """
    Entregable 1 - 'Upload SKU':
    Replica exactamente el template de carga de entidades SKU.

    Estructura (copiada del template original):
      Fila 1 (headers): entityName | id | parentEntityId | displayName
      Fila 2+  (datos): commissionsku | {codigo} | (vacío) | (vacío)

    Anchos de columna del template:
      A=13.36, C=12.54, D=84.36

    Args:
        items: Lista de dicts con {'codigo': str/int}
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"

    # ── Fila 1: Headers (sin negrita, sin color — igual al template) ───────────
    headers = ["entityName", "id", "parentEntityId", "displayName"]
    for col, h in enumerate(headers, 1):
        ws.cell(1, col).value = h

    # ── Anchos exactos del template original ───────────────────────────────────
    ws.column_dimensions["A"].width = 13.36
    ws.column_dimensions["C"].width = 12.54
    ws.column_dimensions["D"].width = 84.36

    # ── Filas de datos ─────────────────────────────────────────────────────────
    for i, item in enumerate(items):
        fila = 2 + i
        ws.cell(fila, 1).value = "commissionsku"  # entityName
        ws.cell(fila, 2).value = item["codigo"]   # id
        ws.cell(fila, 3).value = None              # parentEntityId (vacío)
        ws.cell(fila, 4).value = None              # displayName (vacío)

    return _workbook_a_bytes(wb)


# ── Template 2: Upload SKU Value New ──────────────────────────────────────────

def generar_upload_sku_value_new(items: List[Dict[str, Any]]) -> bytes:
    """
    Entregable 2 - 'Upload SKU Value New':
    Carga de nuevas comisiones. La columna 'value' lleva el porcentaje nuevo.

    Args:
        items: Lista de dicts con {'codigo': str/int, 'comision_nueva': float}
    """
    wb = _construir_template_valores(items, incluir_valor=True)
    return _workbook_a_bytes(wb)


# ── Template 3: Reversa SKU New ───────────────────────────────────────────────

def generar_reversa_sku(items: List[Dict[str, Any]]) -> bytes:
    """
    Entregable 3 - 'Reversa SKU New':
    Reset de comisiones. La columna 'value' va VACÍA para que la plataforma
    elimine la comisión temporal.

    Args:
        items: Lista de dicts con {'codigo': str/int}
    """
    wb = _construir_template_valores(items, incluir_valor=False)
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


# ── Template para Carga Masiva ─────────────────────────────────────────────

def generar_template_masivo() -> io.BytesIO:
    """
    Genera el template Excel para carga masiva de comisiones.
    Incluye headers en verde Falabella + 2 filas de ejemplo.
    Columnas: tipo, codigo, comision_anterior, comision_nueva,
              fecha_inicio, fecha_termino, responsable, motivo
    """
    from openpyxl.styles import PatternFill

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Carga Masiva"

    headers = [
        "tipo", "codigo", "comision_anterior", "comision_nueva",
        "fecha_inicio", "fecha_termino", "responsable", "motivo"
    ]

    # Header row con color verde Falabella
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="00A650")
        cell.alignment = Alignment(horizontal="center")
    ws.row_dimensions[1].height = 18

    # Filas de ejemplo
    ws.append(["SKU", "123456789", 15.0, 18.5, "2026-05-15", "2026-05-31", "Matías Herrera", "Ejemplo de carga"])
    ws.append(["Seller", "SELLER-ABC", 10.0, 8.0, "2026-05-15", "2026-05-31", "Matías Herrera", ""])

    # Anchos de columna
    widths = {"A": 10, "B": 16, "C": 20, "D": 18, "E": 15, "F": 15, "G": 22, "H": 35}
    for col, w in widths.items():
        ws.column_dimensions[col].width = w

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
