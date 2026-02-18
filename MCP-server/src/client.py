import asyncio
from fastmcp import Client

client = Client("http://127.0.0.1:8080/mcp")

async def call_all_tools():
    """Call all available tools in the MCP server."""
    async with client:
        print("=" * 60)
        print("Testing MCP Server Tools")
        print("=" * 60)
        
        # 1. Test get_os_info
        print("\n1. Calling get_os_info...")
        try:
            result = await client.call_tool("get_os_info", {})
            print(f"   ✓ OS Info: {result}")
        except Exception as e:
            print(f"   ✗ Error: {e}")
        
        # 2. Test list_files
        print("\n2. Calling list_files...")
        try:
            result = await client.call_tool("list_files")
            print(f"   ✓ Files in current directory: {result}")
        except Exception as e:
            print(f"   ✗ Error: {e}")
        
        # 3. Test create_file
        print("\n3. Calling create_file...")
        try:
            result = await client.call_tool("create_file", {
                "file_name": "test_client.txt",
                "content": "This file was created by the MCP client"
            })
            print(f"   ✓ {result}")
        except Exception as e:
            print(f"   ✗ Error: {e}")
        
        # 4. Test get_file_content
        print("\n4. Calling get_file_content...")
        try:
            result = await client.call_tool("get_file_content", {
                "file_name": "MCP_Quad.pptx"
            })
            print(f"   ✓ File content: '{result}'")
        except Exception as e:
            print(f"   ✗ Error: {e}")
        
        # 5. Test delete_file
        print("\n5. Calling delete_file...")
        try:
            result = await client.call_tool("delete_file", {
                "file_name": "test_client.txt"
            })
            print(f"   ✓ {result}")
        except Exception as e:
            print(f"   ✗ Error: {e}")
        
        print("\n" + "=" * 60)
        print("All tools tested successfully!")
        print("=" * 60)

asyncio.run(call_all_tools())