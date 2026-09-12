import json
import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def _params(db_path) -> StdioServerParameters:
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "me_alcanza.mcp_bank.server"],
        env={"BANK_DB_PATH": str(db_path)},
    )


async def _call(session: ClientSession, name: str, args: dict):
    result = await session.call_tool(name, args)
    if result.is_error:
        raise RuntimeError(result.content[0].text)
    # NOTE: deviation from the brief. The installed `mcp` SDK's `_convert_to_content`
    # returns raw (unquoted) text for `str` results and unrolls `list`/`tuple` results
    # into one content block per item, so `result.content[0].text` is not reliably a
    # single JSON document for every return type — only for `dict` returns. For `str`
    # and `list[...]` return types this SDK version instead populates
    # `result.structured_content` as `{"result": <value>}` (see
    # mcp/server/mcpserver/utilities/func_metadata.py: `_convert_to_content` and
    # `_create_output_model`). Prefer structured_content when present, unwrapping the
    # `{"result": ...}` envelope; fall back to parsing content[0].text (used for plain
    # `dict` returns, which this SDK version does not wrap in structured_content).
    sc = result.structured_content
    if sc is not None:
        return sc["result"] if set(sc.keys()) == {"result"} else sc
    return json.loads(result.content[0].text)


@pytest.mark.asyncio
async def test_mcp_server_expone_las_tools_esperadas(tmp_path):
    db_path = tmp_path / "test_banco.db"
    async with stdio_client(_params(db_path)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = {t.name for t in tools.tools}
            assert names == {
                "autenticar",
                "get_saldo",
                "get_cuenta",
                "get_movimientos",
                "get_ingresos_programados",
                "get_gastos_fijos",
                "get_metas",
                "buscar_contacto",
                "simular_flujo_de_caja",
                "ejecutar_transferencia",
                "crear_apartado",
            }


@pytest.mark.asyncio
async def test_mcp_server_flujo_de_caja_y_apartado(tmp_path):
    db_path = tmp_path / "test_banco.db"
    async with stdio_client(_params(db_path)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            account_id = await _call(session, "autenticar", {"username": "ana", "password": "pass123"})
            assert account_id == "ana"

            saldo = await _call(session, "get_saldo", {"account_id": "ana"})
            assert saldo == {"saldo": 500.00, "moneda": "MXN"}

            simulacion = await _call(
                session,
                "simular_flujo_de_caja",
                {"account_id": "ana", "fecha_objetivo": "2026-10-13", "monto_objetivo": 8000.0},
            )
            assert simulacion["alcanza"] is False
            assert simulacion["apartado_sugerido"]["periodicidad"] == "semanal"

            metas = await _call(session, "get_metas", {"account_id": "ana"})
            meta_id = metas[0]["id"]

            apartado = await _call(
                session,
                "crear_apartado",
                {
                    "account_id": "ana",
                    "meta_id": meta_id,
                    "monto_por_periodo": 142.5,
                    "periodicidad": "semanal",
                },
            )
            assert apartado["ok"] is True

            saldo_actualizado = await _call(session, "get_saldo", {"account_id": "ana"})
            assert saldo_actualizado["saldo"] == pytest.approx(500.00 - 142.5)


@pytest.mark.asyncio
async def test_mcp_server_desambiguacion_de_contacto(tmp_path):
    db_path = tmp_path / "test_banco.db"
    async with stdio_client(_params(db_path)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            contactos = await _call(session, "buscar_contacto", {"account_id": "ana", "query": "pepe"})
            assert len(contactos) == 2


@pytest.mark.asyncio
async def test_mcp_server_reporta_error_para_cuenta_inexistente(tmp_path):
    db_path = tmp_path / "test_banco.db"
    async with stdio_client(_params(db_path)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("get_saldo", {"account_id": "fantasma"})
            assert result.is_error is True
