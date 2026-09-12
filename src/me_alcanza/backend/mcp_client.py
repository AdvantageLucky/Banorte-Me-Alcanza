import json
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class BankMcpClient:
    def __init__(self, session: ClientSession):
        self._session = session

    async def call(self, tool_name: str, arguments: dict) -> Any:
        result = await self._session.call_tool(tool_name, arguments)
        if result.is_error:
            raise RuntimeError(result.content[0].text)

        # El SDK instalado no siempre devuelve JSON en content[0].text: para
        # resultados str/list[...] usa structured_content = {"result": <valor>};
        # para dict, content[0].text sí es el JSON directo. Ver la nota
        # equivalente en tests/mcp_bank/test_server.py::_call.
        sc = result.structured_content
        if sc is not None:
            return sc["result"] if set(sc.keys()) == {"result"} else sc
        return json.loads(result.content[0].text)


@asynccontextmanager
async def connect_mcp(db_path: str) -> AsyncIterator[ClientSession]:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "me_alcanza.mcp_bank.server"],
        env={"BANK_DB_PATH": db_path},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session
