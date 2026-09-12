from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

Frecuencia = Literal["semanal", "quincenal", "mensual", "anual"]


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str


class ChatRequest(BaseModel):
    mensaje: str


class ChatResponse(BaseModel):
    a2ui_messages: list[dict]


class ConfirmActionRequest(BaseModel):
    proposal_id: str


class ConfirmActionResponse(BaseModel):
    a2ui_messages: list[dict]


class CuentaResponse(BaseModel):
    titular: str
    numero_cuenta: str
    saldo: float
    moneda: str


class MovimientoResponse(BaseModel):
    fecha: str
    concepto: str
    monto: float


class ContactoCreate(BaseModel):
    nombre: str
    alias: str
    cuenta_destino: str
    relacion: str


class ContactoUpdate(BaseModel):
    nombre: str | None = None
    alias: str | None = None
    cuenta_destino: str | None = None
    relacion: str | None = None


class ContactoResponse(BaseModel):
    id: int
    nombre: str
    alias: str
    cuenta_destino: str
    relacion: str


class IngresoProgramadoCreate(BaseModel):
    descripcion: str
    monto: float = Field(gt=0)
    frecuencia: Frecuencia
    proxima_fecha: date


class IngresoProgramadoUpdate(BaseModel):
    descripcion: str | None = None
    monto: float | None = Field(default=None, gt=0)
    frecuencia: Frecuencia | None = None
    proxima_fecha: date | None = None


class IngresoProgramadoResponse(BaseModel):
    id: int
    descripcion: str
    monto: float
    frecuencia: str
    proxima_fecha: str


class GastoFijoCreate(BaseModel):
    concepto: str
    monto: float = Field(gt=0)
    frecuencia: Frecuencia
    proxima_fecha: date


class GastoFijoUpdate(BaseModel):
    concepto: str | None = None
    monto: float | None = Field(default=None, gt=0)
    frecuencia: Frecuencia | None = None
    proxima_fecha: date | None = None


class GastoFijoResponse(BaseModel):
    id: int
    concepto: str
    monto: float
    frecuencia: str
    proxima_fecha: str


class MetaCreate(BaseModel):
    descripcion: str
    monto_objetivo: float = Field(gt=0)
    fecha_objetivo: date


class MetaUpdate(BaseModel):
    descripcion: str | None = None
    monto_objetivo: float | None = Field(default=None, gt=0)
    fecha_objetivo: date | None = None


class MetaResponse(BaseModel):
    id: int
    descripcion: str
    monto_objetivo: float
    fecha_objetivo: str
    monto_ahorrado: float


class ApartadoCreate(BaseModel):
    meta_id: int
    monto_por_periodo: float = Field(gt=0)
    periodicidad: Frecuencia


class ApartadoResponse(BaseModel):
    id: int
    meta_id: int
    monto_por_periodo: float
    periodicidad: str
    fecha_inicio: str
    estado: str
