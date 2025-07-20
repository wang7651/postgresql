# 方法一：使用 mcp 官方 Python 客戶端
import asyncio
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def call_mcp_server():
    # 設定 server 參數
    server_params = StdioServerParameters(
        command="npx",
        args=[
            "-y",
            "@modelcontextprotocol/server-postgres",
            "postgresql://postgres:raspberry@host.docker.internal:5432/postgres"
        ]
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # 初始化
            await session.initialize()

            # 列出可用的 tools
            tools = await session.list_tools()
            print("Available tools:", [tool.name for tool in tools.tools])

            # 呼叫 SQL 查詢工具（假設有 query 工具）
            result = await session.call_tool(
                "query",
                arguments={
                    "sql": "SELECT * FROM your_table LIMIT 5"
                }
            )
            print("Query result:", result)

# 方法二：直接使用 subprocess 和 JSON-RPC
import subprocess
import json

class MCPClient:
    def __init__(self, command, args):
        self.process = subprocess.Popen(
            [command] + args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        self.request_id = 0

    def send_request(self, method, params=None):
        self.request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params or {}
        }

        request_str = json.dumps(request) + '\n'
        self.process.stdin.write(request_str)
        self.process.stdin.flush()

        # 讀取回應
        response_str = self.process.stdout.readline()
        return json.loads(response_str)

    def initialize(self):
        return self.send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {}
            },
            "clientInfo": {
                "name": "python-mcp-client",
                "version": "1.0.0"
            }
        })

    def list_tools(self):
        return self.send_request("tools/list")

    def call_tool(self, name, arguments):
        return self.send_request("tools/call", {
            "name": name,
            "arguments": arguments
        })

    def close(self):
        if self.process:
            self.process.terminate()
            self.process.wait()

# 使用範例
def main():
    client = MCPClient("npx", [
        "-y",
        "@modelcontextprotocol/server-postgres",
        "postgresql://postgres:raspberry@host.docker.internal:5432/postgres"
    ])

    try:
        # 初始化
        init_response = client.initialize()
        print("Initialized:", init_response)

        # 列出工具
        tools_response = client.list_tools()
        print("Tools:", tools_response)

        # 執行 SQL 查詢
        query_response = client.call_tool("query", {
            "sql": "SELECT version();"
        })
        print("Query result:", query_response)

    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

# 方法三：使用 asyncio 的更完整版本
import asyncio
import json
from typing import Dict, Any

class AsyncMCPClient:
    def __init__(self, command: str, args: list):
        self.command = command
        self.args = args
        self.process = None
        self.request_id = 0

    async def start(self):
        self.process = await asyncio.create_subprocess_exec(
            self.command, *self.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

    async def send_request(self, method: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        if not self.process:
            raise RuntimeError("Client not started")

        self.request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params or {}
        }

        request_json = json.dumps(request) + '\n'
        self.process.stdin.write(request_json.encode())
        await self.process.stdin.drain()

        response_line = await self.process.stdout.readline()
        return json.loads(response_line.decode())

    async def initialize(self):
        return await self.send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "clientInfo": {"name": "async-python-client", "version": "1.0.0"}
        })

    async def list_tools(self):
        return await self.send_request("tools/list")

    async def call_tool(self, name: str, arguments: Dict[str, Any]):
        return await self.send_request("tools/call", {
            "name": name,
            "arguments": arguments
        })

    async def close(self):
        if self.process:
            self.process.terminate()
            await self.process.wait()

# 異步使用範例
async def async_main():
    client = AsyncMCPClient("npx", [
        "-y",
        "@modelcontextprotocol/server-postgres",
        "postgresql://postgres:raspberry@host.docker.internal:5432/postgres"
    ])

    try:
        await client.start()

        # 初始化連接
        init_result = await client.initialize()
        print("Initialization:", init_result)

        # 獲取可用工具
        tools = await client.list_tools()
        print("Available tools:", tools)

        # 執行資料庫查詢
        result = await client.call_tool("query", {
            "sql": "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' LIMIT 5;"
        })
        print("Tables:", result)

    except Exception as e:
        print(f"Error: {e}")
    finally:
        await client.close()

if __name__ == "__main__":
    # 同步版本
    print("=== 同步版本 ===")
    main()

    # 異步版本
    print("\n=== 異步版本 ===")
    asyncio.run(async_main())