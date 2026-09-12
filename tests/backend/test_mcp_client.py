import pytest

from me_alcanza.backend.mcp_client import BankMcpClient, connect_mcp


@pytest.mark.asyncio
async def test_call_dict_result(tmp_path):
    db_path = tmp_path / "test_banco.db"
    async with connect_mcp(str(db_path)) as session:
        client = BankMcpClient(session)
        saldo = await client.call("get_saldo", {"account_id": "ana"})
        assert saldo == {"saldo": 500.00, "moneda": "MXN"}


@pytest.mark.asyncio
async def test_call_str_result(tmp_path):
    db_path = tmp_path / "test_banco.db"
    async with connect_mcp(str(db_path)) as session:
        client = BankMcpClient(session)
        account_id = await client.call("autenticar", {"username": "ana", "password": "pass123"})
        assert account_id == "ana"
        assert await client.call("autenticar", {"username": "ana", "password": "mala"}) is None


@pytest.mark.asyncio
async def test_call_list_result(tmp_path):
    db_path = tmp_path / "test_banco.db"
    async with connect_mcp(str(db_path)) as session:
        client = BankMcpClient(session)
        contactos = await client.call("buscar_contacto", {"account_id": "ana", "query": "pepe"})
        assert isinstance(contactos, list)
        assert len(contactos) == 2


@pytest.mark.asyncio
async def test_call_lanza_runtime_error_en_tool_error(tmp_path):
    db_path = tmp_path / "test_banco.db"
    async with connect_mcp(str(db_path)) as session:
        client = BankMcpClient(session)
        with pytest.raises(RuntimeError):
            await client.call("get_saldo", {"account_id": "fantasma"})
