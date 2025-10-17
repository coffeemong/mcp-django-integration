#!/usr/bin/env python3
"""
Simple test script to verify MCP server functionality.
"""

import asyncio
import json
from mcp_servers.manager import MCPManager
from mcp import StdioServerParameters


async def test_mcp_server():
    """Test basic MCP server functionality."""
    manager = MCPManager()
    
    server_params = StdioServerParameters(
        command="python",
        args=["mcp_servers/django_server.py"],
        env={"DJANGO_SETTINGS_MODULE": "myproject.settings_test"}
    )
    
    try:
        print("Starting MCP server...")
        success = await manager.add_server("test-server", server_params)
        
        if not success:
            print("❌ Failed to start MCP server")
            return
        
        print("✅ MCP server started successfully")
        
        # Test list tools
        print("Testing list_tools...")
        tools = await manager.list_tools("test-server")
        print(f"✅ Found {len(tools.tools)} tools:")
        for tool in tools.tools:
            print(f"  - {tool.name}: {tool.description}")
        
        # Test list_models tool
        print("\nTesting list_models tool...")
        result = await manager.call_tool("test-server", "list_models", {})
        models_data = json.loads(result.content[0].text)
        print(f"✅ Found {len(models_data)} models:")
        for model in models_data:
            print(f"  - {model['name']} ({model['app']})")
        
        # Test query_model tool 
        print("\nTesting query_model tool...")
        result = await manager.call_tool("test-server", "query_model", {
            "model_name": "User",
            "filters": {},
            "limit": 5
        })
        
        users_data = json.loads(result.content[0].text)
        print(f"✅ Query returned {len(users_data)} users")
        
        print("\n🎉 All tests passed!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await manager.close_all()


if __name__ == "__main__":
    asyncio.run(test_mcp_server())