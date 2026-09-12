from fastapi import APIRouter, Depends, HTTPException, Request

from . import auth
from .dtos import (
    ChatRequest,
    ChatResponse,
    ConfirmActionRequest,
    ConfirmActionResponse,
    ContactoCreate,
    ContactoResponse,
    ContactoUpdate,
    CuentaResponse,
    LoginRequest,
    LoginResponse,
    MovimientoResponse,
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

    merged = {**actual, **payload.model_dump(exclude_unset=True)}
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
