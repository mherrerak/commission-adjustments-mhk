"""
models.py - Modelos Pydantic para validación de request/response
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import date


class ComisionCreate(BaseModel):
    """Modelo para crear una nueva comisión."""
    tipo: str = Field(..., description="Tipo: 'SKU' o 'Seller'")
    codigo: str = Field(..., min_length=1, description="Código del SKU o ID del Seller")
    comision_anterior: float = Field(..., ge=0, le=100, description="Comisión actual en %")
    comision_nueva: float = Field(..., ge=0, le=100, description="Nueva comisión en %")
    fecha_inicio: date = Field(..., description="Fecha desde la que aplica")
    fecha_termino: date = Field(..., description="Fecha hasta la que aplica")
    responsable: str = Field(..., min_length=1, description="Nombre del responsable")
    motivo: Optional[str] = Field(None, description="Motivo del cambio (opcional)")

    @field_validator("tipo")
    @classmethod
    def tipo_valido(cls, v):
        if v not in ("SKU", "Seller"):
            raise ValueError("El tipo debe ser 'SKU' o 'Seller'")
        return v

    @field_validator("fecha_termino")
    @classmethod
    def fecha_termino_posterior(cls, fecha_termino, info):
        if "fecha_inicio" in info.data and fecha_termino <= info.data["fecha_inicio"]:
            raise ValueError("La fecha de término debe ser posterior a la fecha de inicio")
        return fecha_termino

    @field_validator("comision_nueva")
    @classmethod
    def comision_distinta(cls, comision_nueva, info):
        if "comision_anterior" in info.data and comision_nueva == info.data["comision_anterior"]:
            raise ValueError("La comisión nueva debe ser distinta a la comisión actual")
        return comision_nueva

    @field_validator("codigo")
    @classmethod
    def codigo_limpio(cls, v):
        return v.strip()

    @field_validator("responsable")
    @classmethod
    def responsable_limpio(cls, v):
        return v.strip()


class ComisionResponse(BaseModel):
    """Modelo de respuesta para una comisión."""
    id: int
    tipo: str
    codigo: str
    comision_anterior: float
    comision_nueva: float
    fecha_inicio: str
    fecha_termino: str
    responsable: str
    motivo: Optional[str]
    estado: str
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class FiltrosComisiones(BaseModel):
    """Parámetros de filtro para consultas."""
    tipo: Optional[str] = None
    estado: Optional[str] = None
    responsable: Optional[str] = None
    codigo: Optional[str] = None
    fecha_inicio_desde: Optional[str] = None
    fecha_inicio_hasta: Optional[str] = None
    fecha_termino_desde: Optional[str] = None
    fecha_termino_hasta: Optional[str] = None
    solo_activas: bool = False
