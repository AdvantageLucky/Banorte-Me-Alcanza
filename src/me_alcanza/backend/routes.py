from fastapi import APIRouter, Depends, HTTPException, Request

from . import auth
from .dtos import (
    ApartadoCreate,
    ApartadoResponse,
    ChatRequest,
    ChatResponse,
    ConfirmActionRequest,
    ConfirmActionResponse,
    ContactoCreate,
    ContactoResponse,
    ContactoUpdate,
    CuentaResponse,
    GastoFijoCreate,
    GastoFijoResponse,
    GastoFijoUpdate,
    IngresoProgramadoCreate,
    IngresoProgramadoResponse,
    IngresoProgramadoUpdate,
    LoginRequest,
    LoginResponse,
    MetaCreate,
    MetaResponse,
    MetaUpdate,
    MovimientoResponse,
    SugerenciaResponse,
)

router = APIRouter(prefix="/api")


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, request: Request) -> LoginResponse:
    try:
        account_id = await request.app.state.mcp_client.call(
            "autenticar", {"username": payload.username, "password": payload.password}
        )
    except RuntimeError as exc:
        # Falla del lado del MCP (ej. servidor caído), no credenciales inválidas:
        # no debe escapar como un 500 crudo con traceback hacia el cliente.
        raise HTTPException(
            status_code=503,
            detail="No se pudo verificar las credenciales, intenta de nuevo",
        ) from exc
    if account_id is None:
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")
    token = auth.create_token(account_id, request.app.state.jwt_secret)
    return LoginResponse(token=token)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    request: Request,
    account_id: str = Depends(auth.get_current_account_id),
) -> ChatResponse:
    messages = await request.app.state.orchestrator.handle_message(
        account_id, payload.mensaje
    )
    return ChatResponse(a2ui_messages=messages)


@router.post("/confirm-action", response_model=ConfirmActionResponse)
async def confirm_action(
    payload: ConfirmActionRequest,
    request: Request,
    account_id: str = Depends(auth.get_current_account_id),
) -> ConfirmActionResponse:
    messages = await request.app.state.orchestrator.confirm_action(
        account_id, payload.proposal_id
    )
    return ConfirmActionResponse(a2ui_messages=messages)


@router.get("/cuenta", response_model=CuentaResponse)
async def get_cuenta_route(
    request: Request, account_id: str = Depends(auth.get_current_account_id)
) -> CuentaResponse:
    try:
        cuenta = await request.app.state.mcp_client.call("get_cuenta", {"account_id": account_id})
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CuentaResponse(**cuenta)


@router.get("/movimientos", response_model=list[MovimientoResponse])
async def get_movimientos_route(
    request: Request,
    account_id: str = Depends(auth.get_current_account_id),
    limit: int = 10,
) -> list[MovimientoResponse]:
    try:
        movimientos = await request.app.state.mcp_client.call(
            "get_movimientos", {"account_id": account_id, "limit": limit}
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [MovimientoResponse(**m) for m in movimientos]


@router.get("/contactos", response_model=list[ContactoResponse])
async def list_contactos(
    request: Request, account_id: str = Depends(auth.get_current_account_id)
) -> list[ContactoResponse]:
    try:
        contactos = await request.app.state.mcp_client.call(
            "buscar_contacto", {"account_id": account_id, "query": ""}
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [ContactoResponse(**c) for c in contactos]


@router.post("/contactos", response_model=ContactoResponse, status_code=201)
async def create_contacto(
    payload: ContactoCreate,
    request: Request,
    account_id: str = Depends(auth.get_current_account_id),
) -> ContactoResponse:
    try:
        contacto = await request.app.state.mcp_client.call(
            "crear_contacto",
            {
                "account_id": account_id,
                "nombre": payload.nombre,
                "alias": payload.alias,
                "cuenta_destino": payload.cuenta_destino,
                "relacion": payload.relacion,
            },
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ContactoResponse(**contacto)


@router.patch("/contactos/{contacto_id}", response_model=ContactoResponse)
async def update_contacto(
    contacto_id: int,
    payload: ContactoUpdate,
    request: Request,
    account_id: str = Depends(auth.get_current_account_id),
) -> ContactoResponse:
    try:
        actual = await request.app.state.mcp_client.call(
            "get_contacto", {"account_id": account_id, "contacto_id": contacto_id}
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    merged = {**actual, **payload.model_dump(exclude_unset=True, exclude_none=True)}
    try:
        actualizado = await request.app.state.mcp_client.call(
            "actualizar_contacto",
            {
                "account_id": account_id,
                "contacto_id": contacto_id,
                "nombre": merged["nombre"],
                "alias": merged["alias"],
                "cuenta_destino": merged["cuenta_destino"],
                "relacion": merged["relacion"],
            },
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ContactoResponse(**actualizado)


@router.delete("/contactos/{contacto_id}", status_code=204)
async def delete_contacto(
    contacto_id: int,
    request: Request,
    account_id: str = Depends(auth.get_current_account_id),
) -> None:
    try:
        await request.app.state.mcp_client.call(
            "eliminar_contacto", {"account_id": account_id, "contacto_id": contacto_id}
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/ingresos-programados", response_model=list[IngresoProgramadoResponse])
async def list_ingresos_programados(
    request: Request, account_id: str = Depends(auth.get_current_account_id)
) -> list[IngresoProgramadoResponse]:
    try:
        ingresos = await request.app.state.mcp_client.call(
            "get_ingresos_programados", {"account_id": account_id}
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [IngresoProgramadoResponse(**i) for i in ingresos]


@router.post("/ingresos-programados", response_model=IngresoProgramadoResponse, status_code=201)
async def create_ingreso_programado(
    payload: IngresoProgramadoCreate,
    request: Request,
    account_id: str = Depends(auth.get_current_account_id),
) -> IngresoProgramadoResponse:
    try:
        ingreso = await request.app.state.mcp_client.call(
            "crear_ingreso_programado",
            {
                "account_id": account_id,
                "descripcion": payload.descripcion,
                "monto": payload.monto,
                "frecuencia": payload.frecuencia,
                "proxima_fecha": str(payload.proxima_fecha),
            },
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return IngresoProgramadoResponse(**ingreso)


@router.patch("/ingresos-programados/{ingreso_id}", response_model=IngresoProgramadoResponse)
async def update_ingreso_programado(
    ingreso_id: int,
    payload: IngresoProgramadoUpdate,
    request: Request,
    account_id: str = Depends(auth.get_current_account_id),
) -> IngresoProgramadoResponse:
    try:
        ingresos = await request.app.state.mcp_client.call(
            "get_ingresos_programados", {"account_id": account_id}
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    actual = next((i for i in ingresos if i["id"] == ingreso_id), None)
    if actual is None:
        raise HTTPException(status_code=400, detail=f"Ingreso programado no encontrado para esta cuenta: {ingreso_id}")

    merged = {**actual, **payload.model_dump(exclude_unset=True, exclude_none=True)}
    try:
        actualizado = await request.app.state.mcp_client.call(
            "actualizar_ingreso_programado",
            {
                "account_id": account_id,
                "ingreso_id": ingreso_id,
                "descripcion": merged["descripcion"],
                "monto": merged["monto"],
                "frecuencia": merged["frecuencia"],
                "proxima_fecha": str(merged["proxima_fecha"]),
            },
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return IngresoProgramadoResponse(**actualizado)


@router.delete("/ingresos-programados/{ingreso_id}", status_code=204)
async def delete_ingreso_programado(
    ingreso_id: int,
    request: Request,
    account_id: str = Depends(auth.get_current_account_id),
) -> None:
    try:
        await request.app.state.mcp_client.call(
            "eliminar_ingreso_programado", {"account_id": account_id, "ingreso_id": ingreso_id}
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/gastos-fijos", response_model=list[GastoFijoResponse])
async def list_gastos_fijos(
    request: Request, account_id: str = Depends(auth.get_current_account_id)
) -> list[GastoFijoResponse]:
    try:
        gastos = await request.app.state.mcp_client.call("get_gastos_fijos", {"account_id": account_id})
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [GastoFijoResponse(**g) for g in gastos]


@router.post("/gastos-fijos", response_model=GastoFijoResponse, status_code=201)
async def create_gasto_fijo(
    payload: GastoFijoCreate,
    request: Request,
    account_id: str = Depends(auth.get_current_account_id),
) -> GastoFijoResponse:
    try:
        gasto = await request.app.state.mcp_client.call(
            "crear_gasto_fijo",
            {
                "account_id": account_id,
                "concepto": payload.concepto,
                "monto": payload.monto,
                "frecuencia": payload.frecuencia,
                "proxima_fecha": str(payload.proxima_fecha),
            },
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return GastoFijoResponse(**gasto)


@router.patch("/gastos-fijos/{gasto_id}", response_model=GastoFijoResponse)
async def update_gasto_fijo(
    gasto_id: int,
    payload: GastoFijoUpdate,
    request: Request,
    account_id: str = Depends(auth.get_current_account_id),
) -> GastoFijoResponse:
    try:
        gastos = await request.app.state.mcp_client.call("get_gastos_fijos", {"account_id": account_id})
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    actual = next((g for g in gastos if g["id"] == gasto_id), None)
    if actual is None:
        raise HTTPException(status_code=400, detail=f"Gasto fijo no encontrado para esta cuenta: {gasto_id}")

    merged = {**actual, **payload.model_dump(exclude_unset=True, exclude_none=True)}
    try:
        actualizado = await request.app.state.mcp_client.call(
            "actualizar_gasto_fijo",
            {
                "account_id": account_id,
                "gasto_id": gasto_id,
                "concepto": merged["concepto"],
                "monto": merged["monto"],
                "frecuencia": merged["frecuencia"],
                "proxima_fecha": str(merged["proxima_fecha"]),
            },
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return GastoFijoResponse(**actualizado)


@router.delete("/gastos-fijos/{gasto_id}", status_code=204)
async def delete_gasto_fijo(
    gasto_id: int,
    request: Request,
    account_id: str = Depends(auth.get_current_account_id),
) -> None:
    try:
        await request.app.state.mcp_client.call(
            "eliminar_gasto_fijo", {"account_id": account_id, "gasto_id": gasto_id}
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/metas", response_model=list[MetaResponse])
async def list_metas(
    request: Request, account_id: str = Depends(auth.get_current_account_id)
) -> list[MetaResponse]:
    try:
        metas = await request.app.state.mcp_client.call("get_metas", {"account_id": account_id})
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [MetaResponse(**m) for m in metas]


@router.post("/metas", response_model=MetaResponse, status_code=201)
async def create_meta(
    payload: MetaCreate,
    request: Request,
    account_id: str = Depends(auth.get_current_account_id),
) -> MetaResponse:
    try:
        meta = await request.app.state.mcp_client.call(
            "crear_meta",
            {
                "account_id": account_id,
                "descripcion": payload.descripcion,
                "monto_objetivo": payload.monto_objetivo,
                "fecha_objetivo": str(payload.fecha_objetivo),
            },
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MetaResponse(**meta)


@router.patch("/metas/{meta_id}", response_model=MetaResponse)
async def update_meta(
    meta_id: int,
    payload: MetaUpdate,
    request: Request,
    account_id: str = Depends(auth.get_current_account_id),
) -> MetaResponse:
    try:
        metas = await request.app.state.mcp_client.call("get_metas", {"account_id": account_id})
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    actual = next((m for m in metas if m["id"] == meta_id), None)
    if actual is None:
        raise HTTPException(status_code=400, detail=f"Meta no encontrada para esta cuenta: {meta_id}")

    merged = {**actual, **payload.model_dump(exclude_unset=True, exclude_none=True)}
    try:
        actualizada = await request.app.state.mcp_client.call(
            "actualizar_meta",
            {
                "account_id": account_id,
                "meta_id": meta_id,
                "descripcion": merged["descripcion"],
                "monto_objetivo": merged["monto_objetivo"],
                "fecha_objetivo": str(merged["fecha_objetivo"]),
            },
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MetaResponse(**actualizada)


@router.delete("/metas/{meta_id}", status_code=204)
async def delete_meta(
    meta_id: int,
    request: Request,
    account_id: str = Depends(auth.get_current_account_id),
) -> None:
    try:
        await request.app.state.mcp_client.call("eliminar_meta", {"account_id": account_id, "meta_id": meta_id})
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/apartados", response_model=list[ApartadoResponse])
async def list_apartados(
    request: Request, account_id: str = Depends(auth.get_current_account_id)
) -> list[ApartadoResponse]:
    try:
        apartados = await request.app.state.mcp_client.call("listar_apartados", {"account_id": account_id})
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [ApartadoResponse(**a) for a in apartados]


@router.post("/apartados", response_model=ApartadoResponse, status_code=201)
async def create_apartado(
    payload: ApartadoCreate,
    request: Request,
    account_id: str = Depends(auth.get_current_account_id),
) -> ApartadoResponse:
    try:
        resultado = await request.app.state.mcp_client.call(
            "crear_apartado",
            {
                "account_id": account_id,
                "meta_id": payload.meta_id,
                "monto_por_periodo": payload.monto_por_periodo,
                "periodicidad": payload.periodicidad,
            },
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApartadoResponse(**resultado["apartado"])


@router.post("/apartados/{apartado_id}/cancelar", response_model=ApartadoResponse)
async def cancelar_apartado_route(
    apartado_id: int,
    request: Request,
    account_id: str = Depends(auth.get_current_account_id),
) -> ApartadoResponse:
    try:
        resultado = await request.app.state.mcp_client.call(
            "cancelar_apartado", {"account_id": account_id, "apartado_id": apartado_id}
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApartadoResponse(**resultado)


@router.get("/sugerencias", response_model=list[SugerenciaResponse])
async def list_sugerencias(
    request: Request, account_id: str = Depends(auth.get_current_account_id)
) -> list[SugerenciaResponse]:
    try:
        sugerencias = await request.app.state.mcp_client.call(
            "generar_y_listar_sugerencias", {"account_id": account_id}
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [SugerenciaResponse(**s) for s in sugerencias]


@router.post("/sugerencias/{sugerencia_id}/atender", response_model=SugerenciaResponse)
async def atender_sugerencia(
    sugerencia_id: int,
    request: Request,
    account_id: str = Depends(auth.get_current_account_id),
) -> SugerenciaResponse:
    try:
        actualizada = await request.app.state.mcp_client.call(
            "marcar_sugerencia",
            {"account_id": account_id, "sugerencia_id": sugerencia_id, "nuevo_estado": "atendida"},
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SugerenciaResponse(**actualizada)


@router.post("/sugerencias/{sugerencia_id}/descartar", response_model=SugerenciaResponse)
async def descartar_sugerencia(
    sugerencia_id: int,
    request: Request,
    account_id: str = Depends(auth.get_current_account_id),
) -> SugerenciaResponse:
    try:
        actualizada = await request.app.state.mcp_client.call(
            "marcar_sugerencia",
            {"account_id": account_id, "sugerencia_id": sugerencia_id, "nuevo_estado": "descartada"},
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SugerenciaResponse(**actualizada)
