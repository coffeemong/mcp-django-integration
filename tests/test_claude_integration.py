"""
Claude Desktop MCP Integration Tests.

Tests for Claude Desktop integration with the MCP Django server.
"""

import json
import pytest
import asyncio
from unittest import TestCase
from pathlib import Path
from mcp_servers.manager import MCPManager
from mcp import StdioServerParameters, stdio_client, ClientSession


@pytest.mark.integration
class ClaudeDesktopIntegrationTest(TestCase):
    """Claude Desktop MCP integration tests."""
    
    def setUp(self):
        """Set up test environment."""
        self.config_path = Path(__file__).parent.parent / "config" / "claude_desktop.json"
        
        # Load Claude Desktop configuration
        with open(self.config_path, 'r') as f:
            self.claude_config = json.load(f)
    
    def test_claude_config_format(self):
        """Test Claude Desktop configuration format."""
        # Validate top-level structure
        self.assertIn("mcpServers", self.claude_config)
        
        mcp_servers = self.claude_config["mcpServers"]
        self.assertIsInstance(mcp_servers, dict)
        self.assertGreater(len(mcp_servers), 0)
        
        for server_name, config in mcp_servers.items():
            # Validate required fields
            self.assertIn("command", config, f"Missing 'command' in {server_name}")
            self.assertIn("args", config, f"Missing 'args' in {server_name}")
            
            # Validate field types
            self.assertIsInstance(config["command"], str)
            self.assertIsInstance(config["args"], list)
            self.assertGreater(len(config["args"]), 0)
            
            # Validate environment if present
            if "env" in config:
                self.assertIsInstance(config["env"], dict)
    
    def test_django_server_config(self):
        """Test Django server specific configuration."""
        django_config = self.claude_config["mcpServers"]["django-server"]
        
        # Check command and args
        self.assertEqual(django_config["command"], "python")
        self.assertIn("mcp_servers/django_server.py", django_config["args"])
        
        # Check environment variables
        if "env" in django_config:
            env = django_config["env"]
            self.assertIn("DJANGO_SETTINGS_MODULE", env)
            self.assertIn("myproject.settings", env["DJANGO_SETTINGS_MODULE"])
    
    @pytest.mark.asyncio
    async def test_server_communication_protocol(self):
        """Test MCP protocol compatibility with Claude Desktop."""
        django_config = self.claude_config["mcpServers"]["django-server"]
        
        server_params = StdioServerParameters(
            command=django_config["command"],
            args=django_config["args"],
            env=django_config.get("env", {})
        )
        
        # Test direct protocol communication (as Claude Desktop would)
        read, write = await stdio_client(server_params)
        
        try:
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                # Test tool listing (Claude Desktop capability discovery)
                tools = await session.list_tools()
                self.assertGreater(len(tools.tools), 0)
                
                # Verify expected tools are available
                tool_names = [tool.name for tool in tools.tools]
                expected_tools = [
                    "list_models",
                    "query_model", 
                    "create_model_instance",
                    "update_model_instance",
                    "delete_model_instance"
                ]
                
                for expected_tool in expected_tools:
                    self.assertIn(expected_tool, tool_names)
                
                # Test tool execution (Claude Desktop interaction)
                result = await session.call_tool("list_models", {})
                self.assertIsNotNone(result.content)
                
                # Validate response format
                content = result.content[0]
                self.assertEqual(content.type, "text")
                
                # Parse and validate JSON response
                models_data = json.loads(content.text)
                self.assertIsInstance(models_data, list)
                
        finally:
            await write.aclose()
            await read.aclose()
    
    @pytest.mark.asyncio
    async def test_claude_conversation_simulation(self):
        """Simulate a conversation between Claude and the Django server."""
        manager = MCPManager()
        django_config = self.claude_config["mcpServers"]["django-server"]
        
        server_params = StdioServerParameters(
            command=django_config["command"],
            args=django_config["args"],
            env=django_config.get("env", {})
        )
        
        await manager.add_server("claude-server", server_params)
        
        try:
            # Conversation Step 1: Claude asks "What models are available?"
            models_result = await manager.call_tool(
                "claude-server",
                "list_models",
                {}
            )
            
            models_data = json.loads(models_result.content[0].text)
            self.assertIsInstance(models_data, list)
            
            # Conversation Step 2: Claude asks "Show me all users"
            users_result = await manager.call_tool(
                "claude-server", 
                "query_model",
                {
                    "model_name": "User",
                    "filters": {},
                    "limit": 10
                }
            )
            
            users_data = json.loads(users_result.content[0].text)
            self.assertIsInstance(users_data, list)
            
            # Conversation Step 3: Claude creates a new user
            create_result = await manager.call_tool(
                "claude-server",
                "create_model_instance", 
                {
                    "model_name": "User",
                    "data": {
                        "username": "claude_user",
                        "email": "claude@anthropic.com",
                        "first_name": "Claude",
                        "last_name": "Assistant"
                    }
                }
            )
            
            self.assertIn("성공적으로 생성", create_result.content[0].text)
            
            # Conversation Step 4: Claude verifies the user was created
            verify_result = await manager.call_tool(
                "claude-server",
                "query_model",
                {
                    "model_name": "User", 
                    "filters": {"username": "claude_user"},
                    "limit": 1
                }
            )
            
            verify_data = json.loads(verify_result.content[0].text)
            self.assertEqual(len(verify_data), 1)
            self.assertEqual(verify_data[0]["username"], "claude_user")
            
        finally:
            await manager.close_all()
    
    @pytest.mark.asyncio
    async def test_error_handling_for_claude(self):
        """Test error handling that Claude Desktop would encounter."""
        manager = MCPManager()
        django_config = self.claude_config["mcpServers"]["django-server"]
        
        server_params = StdioServerParameters(
            command=django_config["command"],
            args=django_config["args"],
            env=django_config.get("env", {})
        )
        
        await manager.add_server("claude-error-test", server_params)
        
        try:
            # Test 1: Invalid tool name
            invalid_tool_result = await manager.call_tool(
                "claude-error-test",
                "invalid_tool_name",
                {}
            )
            
            self.assertIn("Unknown tool", invalid_tool_result.content[0].text)
            
            # Test 2: Invalid model name
            invalid_model_result = await manager.call_tool(
                "claude-error-test",
                "query_model",
                {
                    "model_name": "NonExistentModel",
                    "filters": {},
                    "limit": 1
                }
            )
            
            self.assertIn("Error", invalid_model_result.content[0].text)
            
            # Test 3: Missing required parameters
            missing_params_result = await manager.call_tool(
                "claude-error-test",
                "create_model_instance",
                {
                    "model_name": "User"
                    # Missing 'data' parameter
                }
            )
            
            self.assertIn("Error", missing_params_result.content[0].text)
            
        finally:
            await manager.close_all()
    
    def test_configuration_schema_compliance(self):
        """Test configuration compliance with Claude Desktop schema."""
        # Claude Desktop specific schema
        required_top_level = ["mcpServers"]
        for key in required_top_level:
            self.assertIn(key, self.claude_config)
        
        # Each server should have required fields
        for server_name, config in self.claude_config["mcpServers"].items():
            required_server_fields = ["command", "args"]
            for field in required_server_fields:
                self.assertIn(field, config, f"Server {server_name} missing {field}")
    
    @pytest.mark.asyncio
    async def test_concurrent_claude_sessions(self):
        """Test multiple concurrent Claude sessions."""
        django_config = self.claude_config["mcpServers"]["django-server"]
        
        async def create_session():
            """Create a session and perform operations."""
            server_params = StdioServerParameters(
                command=django_config["command"],
                args=django_config["args"],
                env=django_config.get("env", {})
            )
            
            read, write = await stdio_client(server_params)
            
            try:
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    # Perform operations
                    tools = await session.list_tools()
                    result = await session.call_tool("list_models", {})
                    
                    return len(tools.tools), len(json.loads(result.content[0].text))
                    
            finally:
                await write.aclose()
                await read.aclose()
        
        # Create multiple concurrent sessions
        tasks = [create_session() for _ in range(3)]
        results = await asyncio.gather(*tasks)
        
        # Verify all sessions worked correctly
        for tools_count, models_count in results:
            self.assertGreater(tools_count, 0)
            self.assertGreater(models_count, 0)
    
    @pytest.mark.asyncio
    async def test_tool_input_schema_validation(self):
        """Test tool input schema for Claude Desktop compatibility."""
        manager = MCPManager()
        django_config = self.claude_config["mcpServers"]["django-server"]
        
        server_params = StdioServerParameters(
            command=django_config["command"],
            args=django_config["args"],
            env=django_config.get("env", {})
        )
        
        await manager.add_server("schema-test", server_params)
        
        try:
            # Get tool definitions
            tools_result = await manager.list_tools("schema-test")
            tools = tools_result.tools
            
            # Validate each tool has proper input schema
            for tool in tools:
                self.assertIsNotNone(tool.inputSchema, f"Tool {tool.name} missing input schema")
                
                schema = tool.inputSchema
                self.assertIn("type", schema, f"Tool {tool.name} schema missing type")
                self.assertEqual(schema["type"], "object", f"Tool {tool.name} schema should be object type")
                
                # Validate properties exist for tools that require them
                if tool.name in ["query_model", "create_model_instance", "update_model_instance", "delete_model_instance"]:
                    self.assertIn("properties", schema, f"Tool {tool.name} missing properties")
                    self.assertIn("required", schema, f"Tool {tool.name} missing required fields")
                    
                    # Validate model_name is required for all model operations
                    self.assertIn("model_name", schema["required"], f"Tool {tool.name} should require model_name")
        
        finally:
            await manager.close_all()


@pytest.mark.integration
class ClaudeWorkflowTest(TestCase):
    """Test realistic Claude Desktop workflows."""
    
    @pytest.mark.asyncio
    async def test_data_exploration_workflow(self):
        """Test Claude's data exploration workflow."""
        config_path = Path(__file__).parent.parent / "config" / "claude_desktop.json"
        
        with open(config_path, 'r') as f:
            claude_config = json.load(f)
        
        manager = MCPManager()
        django_config = claude_config["mcpServers"]["django-server"]
        
        server_params = StdioServerParameters(
            command=django_config["command"],
            args=django_config["args"],
            env=django_config.get("env", {})
        )
        
        await manager.add_server("exploration-test", server_params)
        
        try:
            # Step 1: Claude discovers available models
            models_result = await manager.call_tool(
                "exploration-test",
                "list_models",
                {}
            )
            
            models = json.loads(models_result.content[0].text)
            self.assertGreater(len(models), 0)
            
            # Step 2: Claude explores User model
            users_result = await manager.call_tool(
                "exploration-test",
                "query_model",
                {
                    "model_name": "User",
                    "filters": {},
                    "limit": 5
                }
            )
            
            users = json.loads(users_result.content[0].text)
            self.assertIsInstance(users, list)
            
            # Step 3: Claude creates test data
            create_result = await manager.call_tool(
                "exploration-test",
                "create_model_instance",
                {
                    "model_name": "User",
                    "data": {
                        "username": "exploration_user",
                        "email": "explore@test.com",
                        "first_name": "Exploration",
                        "last_name": "User"
                    }
                }
            )
            
            self.assertIn("성공적으로 생성", create_result.content[0].text)
            
            # Step 4: Claude verifies and analyzes the data
            verify_result = await manager.call_tool(
                "exploration-test",
                "query_model",
                {
                    "model_name": "User",
                    "filters": {"username": "exploration_user"},
                    "limit": 1
                }
            )
            
            verified_users = json.loads(verify_result.content[0].text)
            self.assertEqual(len(verified_users), 1)
            self.assertEqual(verified_users[0]["first_name"], "Exploration")
            
        finally:
            await manager.close_all()
    
    @pytest.mark.asyncio
    async def test_content_management_workflow(self):
        """Test Claude's content management workflow with memos."""
        config_path = Path(__file__).parent.parent / "config" / "claude_desktop.json"
        
        with open(config_path, 'r') as f:
            claude_config = json.load(f)
        
        manager = MCPManager()
        django_config = claude_config["mcpServers"]["django-server"]
        
        server_params = StdioServerParameters(
            command=django_config["command"],
            args=django_config["args"],
            env=django_config.get("env", {})
        )
        
        await manager.add_server("content-test", server_params)
        
        try:
            # Step 1: Create a user for memo operations
            user_result = await manager.call_tool(
                "content-test",
                "create_model_instance",
                {
                    "model_name": "User",
                    "data": {
                        "username": "memo_user",
                        "email": "memo@test.com",
                        "first_name": "Memo",
                        "last_name": "User"
                    }
                }
            )
            
            self.assertIn("성공적으로 생성", user_result.content[0].text)
            
            # Get the created user
            user_query = await manager.call_tool(
                "content-test",
                "query_model",
                {
                    "model_name": "User",
                    "filters": {"username": "memo_user"},
                    "limit": 1
                }
            )
            
            user_data = json.loads(user_query.content[0].text)
            user_id = user_data[0]["id"]
            
            # Step 2: Create memos (Claude managing content)
            memo_titles = ["Meeting Notes", "Project Ideas", "Task List"]
            created_memo_ids = []
            
            for title in memo_titles:
                memo_result = await manager.call_tool(
                    "content-test",
                    "create_model_instance",
                    {
                        "model_name": "Memo",
                        "data": {
                            "user_id": user_id,
                            "title": title,
                            "content": f"Content for {title}"
                        }
                    }
                )
                
                self.assertIn("성공적으로 생성", memo_result.content[0].text)
            
            # Step 3: Query all memos for user
            all_memos = await manager.call_tool(
                "content-test",
                "query_model",
                {
                    "model_name": "Memo",
                    "filters": {"user": user_id},
                    "limit": 10
                }
            )
            
            memos_data = json.loads(all_memos.content[0].text)
            self.assertEqual(len(memos_data), 3)
            
            # Step 4: Update a memo (Claude editing content)
            memo_id = memos_data[0]["id"]
            update_result = await manager.call_tool(
                "content-test",
                "update_model_instance",
                {
                    "model_name": "Memo",
                    "instance_id": memo_id,
                    "data": {
                        "title": "Updated Meeting Notes",
                        "content": "Updated content with new information"
                    }
                }
            )
            
            self.assertIn("성공적으로 수정", update_result.content[0].text)
            
            # Step 5: Verify update
            updated_memo = await manager.call_tool(
                "content-test",
                "query_model",
                {
                    "model_name": "Memo",
                    "filters": {"id": memo_id},
                    "limit": 1
                }
            )
            
            updated_data = json.loads(updated_memo.content[0].text)
            self.assertEqual(updated_data[0]["title"], "Updated Meeting Notes")
            
        finally:
            await manager.close_all()