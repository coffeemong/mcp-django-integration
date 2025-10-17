"""
Simplified Django-MCP Integration Tests.

This module contains basic integration tests to demonstrate the Django-MCP system functionality.
"""

import json
import pytest
from django.test import TestCase
from django.contrib.auth.models import User

from mcp_app.models import Memo
from mcp_servers.manager import MCPManager
from mcp import StdioServerParameters


class SimpleDjangoMCPTest(TestCase):
    """Simple Django-MCP integration tests."""
    
    def setUp(self):
        """Set up test environment."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.mcp_manager = MCPManager()
    
    @pytest.mark.asyncio
    async def test_mcp_server_tools(self):
        """Test MCP server tools functionality."""
        # Set up server
        server_params = StdioServerParameters(
            command="python",
            args=["mcp_servers/django_server.py"],
            env={"DJANGO_SETTINGS_MODULE": "myproject.settings_test"}
        )
        
        success = await self.mcp_manager.add_server("test-server", server_params)
        self.assertTrue(success)
        
        try:
            # Test list tools
            tools = await self.mcp_manager.list_tools("test-server")
            self.assertGreater(len(tools.tools), 0)
            
            tool_names = [tool.name for tool in tools.tools]
            expected_tools = ["list_models", "query_model", "create_model_instance", 
                            "update_model_instance", "delete_model_instance"]
            
            for expected_tool in expected_tools:
                self.assertIn(expected_tool, tool_names)
            
            # Test list models
            result = await self.mcp_manager.call_tool("test-server", "list_models", {})
            models_data = json.loads(result.content[0].text)
            self.assertIsInstance(models_data, list)
            
        finally:
            await self.mcp_manager.close_all()
    
    @pytest.mark.asyncio
    async def test_crud_workflow(self):
        """Test complete CRUD workflow."""
        # Set up server
        server_params = StdioServerParameters(
            command="python",
            args=["mcp_servers/django_server.py"],
            env={"DJANGO_SETTINGS_MODULE": "myproject.settings_test"}
        )
        
        success = await self.mcp_manager.add_server("crud-server", server_params)
        self.assertTrue(success)
        
        try:
            # Create
            create_result = await self.mcp_manager.call_tool(
                "crud-server",
                "create_model_instance",
                {
                    "model_name": "Memo",
                    "data": {
                        "user_id": self.user.id,
                        "title": "Test Memo",
                        "content": "Test content"
                    }
                }
            )
            self.assertIn("성공적으로 생성", create_result.content[0].text)
            
            # Read
            read_result = await self.mcp_manager.call_tool(
                "crud-server",
                "query_model",
                {
                    "model_name": "Memo",
                    "filters": {"title": "Test Memo"},
                    "limit": 1
                }
            )
            
            memo_data = json.loads(read_result.content[0].text)
            self.assertEqual(len(memo_data), 1)
            memo_id = memo_data[0]["id"]
            
            # Update
            update_result = await self.mcp_manager.call_tool(
                "crud-server",
                "update_model_instance",
                {
                    "model_name": "Memo",
                    "instance_id": memo_id,
                    "data": {"title": "Updated Test Memo"}
                }
            )
            self.assertIn("성공적으로 수정", update_result.content[0].text)
            
            # Delete
            delete_result = await self.mcp_manager.call_tool(
                "crud-server",
                "delete_model_instance",
                {
                    "model_name": "Memo",
                    "instance_id": memo_id
                }
            )
            self.assertIn("성공적으로 삭제", delete_result.content[0].text)
            
        finally:
            await self.mcp_manager.close_all()


class ConfigurationValidationTest(TestCase):
    """Test configuration file validation."""
    
    def test_vscode_config_format(self):
        """Test VS Code configuration format."""
        import json
        from pathlib import Path
        
        config_path = Path(__file__).parent.parent / "config" / "vscode_mcp.json"
        
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        self.assertIn("servers", config)
        self.assertIn("django-mcp-server", config["servers"])
        
        server_config = config["servers"]["django-mcp-server"]
        self.assertEqual(server_config["type"], "stdio")
        self.assertEqual(server_config["command"], "python")
        self.assertIn("mcp_servers/django_server.py", server_config["args"])
    
    def test_claude_config_format(self):
        """Test Claude Desktop configuration format."""
        import json
        from pathlib import Path
        
        config_path = Path(__file__).parent.parent / "config" / "claude_desktop.json"
        
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        self.assertIn("mcpServers", config)
        self.assertIn("django-server", config["mcpServers"])
        
        server_config = config["mcpServers"]["django-server"]
        self.assertEqual(server_config["command"], "python")
        self.assertIn("mcp_servers/django_server.py", server_config["args"])