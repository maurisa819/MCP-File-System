import asyncio
from fastmcp import Client

client = Client("http://localhost:8000/mcp")

async def call_tool():
    async with client:
        result = await client.call_tool("get_file_content", {"directory": '~/Downloads', "file_name": "Reid-Duke.txt"})
        print(result)

asyncio.run(call_tool())