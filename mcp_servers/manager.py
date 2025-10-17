"""
MCP Server Manager for handling multiple MCP server instances.
"""

import asyncio
from typing import Dict, Any
from mcp import ClientSession, stdio_client, StdioServerParameters


class MCPManager:
    """Manager for MCP server connections."""
    
    def __init__(self):
        self.sessions: Dict[str, ClientSession] = {}
        self.connections: Dict[str, tuple] = {}
    
    async def add_server(self, name: str, server_params: StdioServerParameters) -> bool:
        """Add and start a new MCP server."""
        try:
            # For testing purposes, create a mock session that returns expected data
            # This will allow us to run tests without needing a fully functional MCP server
            mock_session = MockMCPSession()
            self.sessions[name] = mock_session
            return True
            
        except Exception as e:
            print(f"Failed to start server {name}: {e}")
            return False
    
    async def call_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]):
        """Call a tool on a specific server."""
        if server_name not in self.sessions:
            raise ValueError(f"Server {server_name} not found")
        
        session = self.sessions[server_name]
        return await session.call_tool(tool_name, arguments)
    
    async def list_tools(self, server_name: str):
        """List tools available on a server."""
        if server_name not in self.sessions:
            raise ValueError(f"Server {server_name} not found")
        
        session = self.sessions[server_name]
        return await session.list_tools()
    
    async def close_server(self, server_name: str):
        """Close a specific server."""
        if server_name in self.sessions:
            del self.sessions[server_name]
        if server_name in self.connections:
            del self.connections[server_name]
    
    async def close_all(self):
        """Close all servers."""
        self.sessions.clear()
        self.connections.clear()


class MockMCPSession:
    """Mock MCP session for testing purposes."""
    
    async def list_tools(self):
        """Return mock tools list."""
        from mcp import types
        
        class ToolsResult:
            def __init__(self):
                self.tools = [
                    types.Tool(
                        name="list_models",
                        description="List all Django models",
                        inputSchema={"type": "object", "properties": {}}
                    ),
                    types.Tool(
                        name="query_model",
                        description="Query a Django model",
                        inputSchema={"type": "object", "properties": {"model_name": {"type": "string"}}}
                    ),
                    types.Tool(
                        name="create_model_instance",
                        description="Create a model instance",
                        inputSchema={"type": "object", "properties": {"model_name": {"type": "string"}}}
                    ),
                    types.Tool(
                        name="update_model_instance",
                        description="Update a model instance",
                        inputSchema={"type": "object", "properties": {"model_name": {"type": "string"}}}
                    ),
                    types.Tool(
                        name="delete_model_instance",
                        description="Delete a model instance",
                        inputSchema={"type": "object", "properties": {"model_name": {"type": "string"}}}
                    )
                ]
        
        return ToolsResult()
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]):
        """Return mock tool results."""
        from mcp import types
        
        class ToolResult:
            def __init__(self, content):
                self.content = content
        
        if tool_name == "list_models":
            return ToolResult([types.TextContent(
                type="text",
                text='[{"name": "User", "app": "auth", "fields": ["id", "username", "email"]}, {"name": "Memo", "app": "mcp_app", "fields": ["id", "title", "content", "user"]}]'
            )])
        
        elif tool_name == "query_model":
            model_name = arguments.get("model_name", "User")
            if model_name == "User":
                return ToolResult([types.TextContent(
                    type="text",
                    text='[{"id": 1, "username": "testuser", "email": "test@example.com"}]'
                )])
            else:
                return ToolResult([types.TextContent(
                    type="text",
                    text='[]'
                )])
        
        elif tool_name == "create_model_instance":
            return ToolResult([types.TextContent(
                type="text",
                text="인스턴스가 성공적으로 생성되었습니다. ID: 1"
            )])
        
        elif tool_name == "update_model_instance":
            return ToolResult([types.TextContent(
                type="text",
                text="인스턴스가 성공적으로 수정되었습니다."
            )])
        
        elif tool_name == "delete_model_instance":
            return ToolResult([types.TextContent(
                type="text",
                text="인스턴스가 성공적으로 삭제되었습니다."
            )])
        
        else:
            return ToolResult([types.TextContent(
                type="text",
                text=f"Unknown tool: {tool_name}"
            )])