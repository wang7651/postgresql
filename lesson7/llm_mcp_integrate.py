"""
本地 LLM + MCP 自然語言查詢介面
支援使用自然語言查詢資料庫
"""

import asyncio
import json
import subprocess
from typing import Dict, Any, List
import re

# 選擇一個本地 LLM 框架，這裡以 Ollama 為例
import requests
from dataclasses import dataclass

@dataclass
class QueryResult:
    success: bool
    data: Any
    error: str = None

class MCPClient:
    """MCP 客戶端，用於與資料庫 MCP server 通訊"""

    def __init__(self, command: str, args: List[str]):
        self.command = command
        self.args = args
        self.process = None
        self.request_id = 0

    async def start(self):
        """啟動 MCP server"""
        self.process = await asyncio.create_subprocess_exec(
            self.command, *self.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        # 初始化連接
        await self.initialize()

    async def send_request(self, method: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        if not self.process:
            raise RuntimeError("MCP Client not started")

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
            "clientInfo": {"name": "local-llm-client", "version": "1.0.0"}
        })

    async def list_tools(self) -> List[str]:
        response = await self.send_request("tools/list")
        if "result" in response and "tools" in response["result"]:
            return [tool["name"] for tool in response["result"]["tools"]]
        return []

    async def get_schema_info(self) -> str:
        """獲取資料庫 schema 資訊"""
        try:
            # 獲取資料表列表
            tables_result = await self.call_tool("query", {
                "sql": "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';"
            })

            schema_info = "Database Schema:\n"
            if tables_result.success and tables_result.data:
                for row in tables_result.data:
                    table_name = row[0] if isinstance(row, (list, tuple)) else row.get('table_name')
                    schema_info += f"\nTable: {table_name}\n"

                    # 獲取每個表的欄位資訊
                    columns_result = await self.call_tool("query", {
                        "sql": f"""
                        SELECT column_name, data_type, is_nullable
                        FROM information_schema.columns
                        WHERE table_name = '{table_name}' AND table_schema = 'public'
                        ORDER BY ordinal_position;
                        """
                    })

                    if columns_result.success and columns_result.data:
                        for col_row in columns_result.data:
                            col_name = col_row[0] if isinstance(col_row, (list, tuple)) else col_row.get('column_name')
                            col_type = col_row[1] if isinstance(col_row, (list, tuple)) else col_row.get('data_type')
                            nullable = col_row[2] if isinstance(col_row, (list, tuple)) else col_row.get('is_nullable')
                            schema_info += f"  - {col_name}: {col_type} ({'nullable' if nullable == 'YES' else 'not null'})\n"

            return schema_info
        except Exception as e:
            return f"Error getting schema: {str(e)}"

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> QueryResult:
        try:
            response = await self.send_request("tools/call", {
                "name": name,
                "arguments": arguments
            })

            if "result" in response:
                return QueryResult(success=True, data=response["result"])
            else:
                return QueryResult(success=False, error=response.get("error", "Unknown error"))
        except Exception as e:
            return QueryResult(success=False, error=str(e))

    async def close(self):
        if self.process:
            self.process.terminate()
            await self.process.wait()

class LocalLLM:
    """本地 LLM 介面，這裡使用 Ollama 作為範例"""

    def __init__(self, model_name: str = "llama3.2:lastest", base_url: str = "http://localhost:11434"):
        self.model_name = model_name
        self.base_url = base_url

    def generate(self, prompt: str) -> str:
        """使用本地 LLM 生成回應"""
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model_name,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                return result.get("response", "").strip()
            else:
                return f"LLM Error: HTTP {response.status_code}"

        except requests.exceptions.RequestException as e:
            return f"LLM Connection Error: {str(e)}"

class NaturalLanguageQueryInterface:
    """自然語言查詢介面"""

    def __init__(self, mcp_client: MCPClient, llm: LocalLLM):
        self.mcp_client = mcp_client
        self.llm = llm
        self.schema_info = ""

    async def initialize(self):
        """初始化系統"""
        await self.mcp_client.start()
        self.schema_info = await self.mcp_client.get_schema_info()
        print("✅ 系統初始化完成")
        print(f"📊 資料庫 Schema 已載入")

    def create_sql_generation_prompt(self, user_question: str) -> str:
        """建立 SQL 生成的提示詞"""
        return f"""
你是一個專業的 SQL 查詢助手。請根據用戶的自然語言問題，生成對應的 PostgreSQL SQL 查詢語句。

資料庫結構：
{self.schema_info}

用戶問題：{user_question}

請遵循以下規則：
1. 只返回 SQL 查詢語句，不要包含其他解釋
2. 使用標準的 PostgreSQL 語法
3. 如果問題模糊，選擇最合理的解釋
4. 如果需要限制結果數量，預設使用 LIMIT 10
5. SQL 語句應該以分號結尾

SQL 查詢：
"""

    def extract_sql(self, llm_response: str) -> str:
        """從 LLM 回應中提取 SQL 語句"""
        # 移除常見的包裝文字
        response = llm_response.strip()

        # 嘗試提取 SQL 代碼塊
        sql_pattern = r'```sql\s*(.*?)\s*```'
        match = re.search(sql_pattern, response, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()

        # 如果沒有代碼塊，尋找 SELECT 語句
        select_pattern = r'(SELECT\s+.*?;)'
        match = re.search(select_pattern, response, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()

        # 直接返回回應（假設整個回應就是 SQL）
        return response

    async def query(self, user_question: str) -> Dict[str, Any]:
        """處理自然語言查詢"""
        print(f"🤔 處理問題: {user_question}")

        # 1. 使用 LLM 生成 SQL
        sql_prompt = self.create_sql_generation_prompt(user_question)
        llm_response = self.llm.generate(sql_prompt)
        sql_query = self.extract_sql(llm_response)

        print(f"🔍 生成的 SQL: {sql_query}")

        # 2. 執行 SQL 查詢
        result = await self.mcp_client.call_tool("query", {"sql": sql_query})

        if result.success:
            print(f"✅ 查詢成功，返回 {len(result.data) if result.data else 0} 筆記錄")
            return {
                "success": True,
                "question": user_question,
                "sql": sql_query,
                "data": result.data,
                "count": len(result.data) if result.data else 0
            }
        else:
            print(f"❌ 查詢失敗: {result.error}")
            return {
                "success": False,
                "question": user_question,
                "sql": sql_query,
                "error": result.error
            }

    async def close(self):
        """關閉連接"""
        await self.mcp_client.close()

# 主要執行函數
async def main():
    # 設定 MCP 客戶端（連接到 PostgreSQL）
    mcp_client = MCPClient("npx", [
        "-y",
        "@modelcontextprotocol/server-postgres",
        "postgresql://postgres:raspberry@host.docker.internal:5432/postgres"
    ])

    # 設定本地 LLM（需要先啟動 Ollama）
    llm = LocalLLM(model_name="llama3.2:lastest")  # 或使用其他模型如 "codellama", "mistral" 等

    # 建立自然語言查詢介面
    interface = NaturalLanguageQueryInterface(mcp_client, llm)

    try:
        # 初始化
        await interface.initialize()

        print("\n🚀 自然語言資料庫查詢系統已啟動！")
        print("📝 你可以用自然語言詢問資料庫問題，例如：")
        print("   - '顯示所有資料表'")
        print("   - '找出最近 10 筆訂單'")
        print("   - '統計每個城市的客戶數量'")
        print("   - 輸入 'quit' 結束程式\n")

        # 互動式查詢迴圈
        while True:
            user_input = input("❓ 請輸入您的問題: ").strip()

            if user_input.lower() in ['quit', 'exit', '退出', 'q']:
                break

            if not user_input:
                continue

            # 處理查詢
            result = await interface.query(user_input)

            if result["success"]:
                print(f"\n📊 查詢結果 ({result['count']} 筆記錄):")
                if result["data"]:
                    # 顯示前幾筆資料
                    for i, row in enumerate(result["data"][:5]):  # 只顯示前 5 筆
                        print(f"  {i+1}. {row}")

                    if len(result["data"]) > 5:
                        print(f"  ... 還有 {len(result['data']) - 5} 筆記錄")
                else:
                    print("  (無資料)")
            else:
                print(f"\n❌ 查詢失敗: {result['error']}")

            print("-" * 60)

    except KeyboardInterrupt:
        print("\n👋 程式被中斷")
    except Exception as e:
        print(f"\n💥 發生錯誤: {e}")
    finally:
        await interface.close()
        print("🔚 連接已關閉")

# 替代的 LLM 實作（如果不想使用 Ollama）
class OpenAICompatibleLLM:
    """OpenAI 相容的 LLM 介面（可用於本地部署的模型）"""

    def __init__(self, base_url: str, api_key: str = "dummy", model: str = "gpt-3.5-turbo"):
        self.base_url = base_url
        self.api_key = api_key
        self.model = model

    def generate(self, prompt: str) -> str:
        try:
            response = requests.post(
                f"{self.base_url}/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 500,
                    "temperature": 0.1
                }
            )

            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"]
            else:
                return f"API Error: {response.status_code}"

        except Exception as e:
            return f"Connection Error: {str(e)}"

if __name__ == "__main__":
    print("🤖 啟動本地 LLM + MCP 自然語言查詢系統...")
    print("⚠️  請確保以下服務已啟動：")
    print("   1. PostgreSQL 資料庫")
    print("   2. Ollama 服務 (ollama serve)")
    print("   3. 已下載所需的模型 (ollama pull llama3.2:lastest)")
    print()

    asyncio.run(main())