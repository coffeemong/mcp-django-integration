"""
VS Code MCP Integration Tests.

Tests for VS Code integration with the MCP Django server.
"""

import json
import pytest
import asyncio
from unittest import TestCase
from pathlib import Path
from mcp_servers.manager import MCPManager
from mcp import StdioServerParameters


@pytest.mark.integration
class VSCodeMCPIntegrationTest(TestCase):
    """VS Code MCP integration tests."""
    
    def setUp(self):
        """Set up test environment."""
        self.config_path = Path(__file__).parent.parent / "config" / "vscode_mcp.json"
        
        # Load test configuration
        with open(self.config_path, 'r') as f:
            self.test_config = json.load(f)
    
    def test_mcp_config_validation(self):
        """Test MCP configuration file validation."""
        # Schema for VS Code MCP configuration
        required_keys = ["servers"]
        self.assertIn("servers", self.test_config)
        
        servers = self.test_config["servers"]
        self.assertIsInstance(servers, dict)
        self.assertGreater(len(servers), 0)
        
        for server_name, config in servers.items():
            # Validate server configuration structure
            required_server_keys = ["type", "command", "args"]
            for key in required_server_keys:
                self.assertIn(key, config, f"Missing key '{key}' in server '{server_name}'")
            
            # Validate specific fields
            self.assertEqual(config["type"], "stdio")
            self.assertIsInstance(config["command"], str)
            self.assertIsInstance(config["args"], list)
            self.assertGreater(len(config["args"]), 0)
            
            # Validate environment variables if present
            if "env" in config:
                self.assertIsInstance(config["env"], dict)
    
    def test_config_file_format(self):
        """Test configuration file format compliance."""
        # Test JSON format is valid (already loaded successfully in setUp)
        self.assertIsInstance(self.test_config, dict)
        
        # Test specific VS Code format requirements
        self.assertEqual(list(self.test_config.keys()), ["servers"])
        
        # Test django-mcp-server configuration
        django_config = self.test_config["servers"]["django-mcp-server"]
        self.assertEqual(django_config["command"], "python")
        self.assertIn("mcp_servers/django_server.py", django_config["args"])
    
    @pytest.mark.asyncio
    async def test_server_startup_from_config(self):
        """Test server startup using VS Code configuration."""
        config = self.test_config["servers"]["django-mcp-server"]
        
        server_params = StdioServerParameters(
            command=config["command"],
            args=config["args"],
            env=config.get("env", {})
        )
        
        # Test server startup
        manager = MCPManager()
        success = await manager.add_server("test-server", server_params)
        self.assertTrue(success, "Server should start successfully from VS Code config")
        
        # Test server functionality
        try:
            # List available tools
            tools = await manager.list_tools("test-server")
            self.assertGreater(len(tools.tools), 0, "Server should provide tools")
            
            # Test a simple tool call
            result = await manager.call_tool("test-server", "list_models", {})
            self.assertIsNotNone(result.content, "Tool should return content")
            
        finally:
            await manager.close_all()
    
    @pytest.mark.asyncio
    async def test_multiple_server_configurations(self):
        """Test multiple MCP server configurations."""
        # Simulate multiple server configuration
        multi_config = {
            "servers": {
                "django-server-1": {
                    "type": "stdio",
                    "command": "python",
                    "args": ["mcp_servers/django_server.py"],
                    "env": {"DJANGO_SETTINGS_MODULE": "myproject.settings_test"}
                },
                "django-server-2": {
                    "type": "stdio", 
                    "command": "python",
                    "args": ["mcp_servers/django_server.py"],
                    "env": {"DJANGO_SETTINGS_MODULE": "myproject.settings_test"}
                }
            }
        }
        
        manager = MCPManager()
        started_servers = []
        
        try:
            # Start multiple servers
            for server_name, config in multi_config["servers"].items():
                server_params = StdioServerParameters(
                    command=config["command"],
                    args=config["args"],
                    env=config.get("env", {})
                )
                
                success = await manager.add_server(server_name, server_params)
                self.assertTrue(success, f"Server {server_name} should start")
                started_servers.append(server_name)
            
            # Test that each server works independently
            for server_name in started_servers:
                result = await manager.call_tool(server_name, "list_models", {})
                self.assertIsNotNone(result.content)
                
        finally:
            await manager.close_all()
    
    def test_environment_variable_configuration(self):
        """Test environment variable configuration for servers."""
        config = self.test_config["servers"]["django-mcp-server"]
        
        if "env" in config:
            env_vars = config["env"]
            self.assertIsInstance(env_vars, dict)
            
            # Test Django-specific environment variables
            if "DJANGO_SETTINGS_MODULE" in env_vars:
                settings_module = env_vars["DJANGO_SETTINGS_MODULE"]
                self.assertIn("myproject.settings", settings_module)
    
    @pytest.mark.asyncio
    async def test_server_error_handling(self):
        """Test error handling for server startup failures."""
        # Test with invalid command
        invalid_config = StdioServerParameters(
            command="nonexistent_command",
            args=["invalid_script.py"]
        )
        
        manager = MCPManager()
        success = await manager.add_server("invalid-server", invalid_config)
        self.assertFalse(success, "Should fail with invalid command")
        
        await manager.close_all()
    
    def test_config_schema_validation(self):
        """Test configuration against JSON schema."""
        try:
            from jsonschema import validate
        except ImportError:
            pytest.skip("jsonschema not available")
        
        # Define VS Code MCP configuration schema
        schema = {
            "type": "object",
            "properties": {
                "servers": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string", "enum": ["stdio"]},
                            "command": {"type": "string"},
                            "args": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "env": {
                                "type": "object",
                                "additionalProperties": {"type": "string"}
                            }
                        },
                        "required": ["type", "command", "args"]
                    }
                }
            },
            "required": ["servers"]
        }
        
        # Validate configuration against schema
        validate(instance=self.test_config, schema=schema)
    
    @pytest.mark.asyncio
    async def test_tool_discovery(self):
        """Test tool discovery through VS Code configuration."""
        config = self.test_config["servers"]["django-mcp-server"]
        
        server_params = StdioServerParameters(
            command=config["command"],
            args=config["args"],
            env=config.get("env", {})
        )
        
        manager = MCPManager()
        await manager.add_server("discovery-test", server_params)
        
        try:
            # Discover available tools
            tools_result = await manager.list_tools("discovery-test")
            tools = tools_result.tools
            
            # Expected tools from Django MCP server
            expected_tools = [
                "list_models",
                "query_model", 
                "create_model_instance",
                "update_model_instance",
                "delete_model_instance"
            ]
            
            tool_names = [tool.name for tool in tools]
            
            for expected_tool in expected_tools:
                self.assertIn(expected_tool, tool_names, 
                            f"Tool '{expected_tool}' should be available")
            
            # Test tool metadata
            for tool in tools:
                self.assertIsInstance(tool.name, str)
                self.assertIsInstance(tool.description, str)
                self.assertIsNotNone(tool.inputSchema)
                
        finally:
            await manager.close_all()


@pytest.mark.integration  
class VSCodeWorkflowTest(TestCase):
    """Test VS Code workflow integration."""
    
    @pytest.mark.asyncio
    async def test_vscode_development_workflow(self):
        """Test typical VS Code development workflow with MCP."""
        # Simulate VS Code starting up and loading MCP configuration
        config_path = Path(__file__).parent.parent / "config" / "vscode_mcp.json"
        
        with open(config_path, 'r') as f:
            vscode_config = json.load(f)
        
        manager = MCPManager()
        
        # Step 1: VS Code loads and starts MCP servers
        for server_name, config in vscode_config["servers"].items():
            server_params = StdioServerParameters(
                command=config["command"],
                args=config["args"],
                env=config.get("env", {})
            )
            
            success = await manager.add_server(server_name, server_params)
            self.assertTrue(success, f"VS Code should start {server_name}")
        
        try:
            # Step 2: User requests tool list (VS Code IntelliSense)
            tools = await manager.list_tools("django-mcp-server")
            self.assertGreater(len(tools.tools), 0)
            
            # Step 3: User uses tool for development (e.g., exploring models)
            models_result = await manager.call_tool(
                "django-mcp-server",
                "list_models", 
                {}
            )
            
            models_data = json.loads(models_result.content[0].text)
            self.assertIsInstance(models_data, list)
            
            # Step 4: User queries specific data
            query_result = await manager.call_tool(
                "django-mcp-server",
                "query_model",
                {
                    "model_name": "User",
                    "filters": {},
                    "limit": 5
                }
            )
            
            self.assertIsNotNone(query_result.content)
            
        finally:
            await manager.close_all()
    
    @pytest.mark.asyncio
    async def test_configuration_reload(self):
        """Test configuration reload scenarios."""
        config_path = Path(__file__).parent.parent / "config" / "vscode_mcp.json"
        
        with open(config_path, 'r') as f:
            original_config = json.load(f)
        
        # Start with original configuration
        manager = MCPManager()
        config = original_config["servers"]["django-mcp-server"]
        
        server_params = StdioServerParameters(
            command=config["command"],
            args=config["args"],
            env=config.get("env", {})
        )
        
        await manager.add_server("reload-test", server_params)
        
        try:
            # Test original configuration works
            result1 = await manager.call_tool("reload-test", "list_models", {})
            self.assertIsNotNone(result1.content)
            
            # Simulate configuration reload (restart server)
            await manager.close_server("reload-test")
            
            # Restart with same configuration
            await manager.add_server("reload-test", server_params)
            
            # Test still works after reload
            result2 = await manager.call_tool("reload-test", "list_models", {})
            self.assertIsNotNone(result2.content)
            
        finally:
            await manager.close_all()