"""
Django-MCP Integration Tests.

This module contains comprehensive integration tests for the Django-MCP system,
ensuring that all components work together correctly.
"""

import json
import pytest
import asyncio
from django.test import TransactionTestCase
from django.contrib.auth.models import User
from channels.testing import WebsocketCommunicator
from asgiref.sync import sync_to_async

from mcp_app.models import Memo
from mcp_servers.manager import MCPManager
from mcp import StdioServerParameters
from myproject.asgi import application


@pytest.mark.integration
class DjangoMCPIntegrationTest(TransactionTestCase):
    """Comprehensive Django-MCP integration tests."""
    
    def setUp(self):
        """Set up test environment synchronously."""
        # Create test user synchronously
        self.user = User.objects.create_user(
            username='integrationuser',
            email='integration@example.com',
            password='integrationpass123'
        )
        
        # Initialize MCP manager
        self.mcp_manager = MCPManager()
        
    async def async_setup(self):
        """Set up MCP server asynchronously."""
        server_params = StdioServerParameters(
            command="python",
            args=["mcp_servers/django_server.py"],
            env={"DJANGO_SETTINGS_MODULE": "myproject.settings_test"}
        )
        await self.mcp_manager.add_server("django-server", server_params)
        
    async def async_teardown(self):
        """Clean up test environment."""
        await self.mcp_manager.close_all()
    
    @pytest.mark.asyncio
    async def test_complete_workflow(self):
        """Test complete workflow: create -> read -> update -> delete."""
        
        # Set up MCP server
        await self.async_setup()
        
        try:
            # 1. Create memo
            create_result = await self.mcp_manager.call_tool(
                "django-server",
                "create_model_instance",
                {
                    "model_name": "Memo",
                    "data": {
                        "user_id": self.user.id,
                        "title": "Integration Test Memo",
                        "content": "This is an integration test memo."
                    }
                }
            )
            
            self.assertIn("성공적으로 생성", create_result.content[0].text)
        
            # 2. Query memo
            query_result = await self.mcp_manager.call_tool(
                "django-server",
                "query_model",
                {
                    "model_name": "Memo",
                    "filters": {"title": "Integration Test Memo"},
                    "limit": 1
                }
            )
            
            query_data = json.loads(query_result.content[0].text)
            self.assertEqual(len(query_data), 1)
            memo_id = query_data[0]["id"]
            
            # 3. Update memo
            update_result = await self.mcp_manager.call_tool(
                "django-server",
                "update_model_instance",
                {
                    "model_name": "Memo",
                    "instance_id": memo_id,
                    "data": {"title": "Updated Integration Test Memo"}
                }
            )
            
            self.assertIn("성공적으로 수정", update_result.content[0].text)
            
            # 4. Verify update
            verify_result = await self.mcp_manager.call_tool(
                "django-server",
                "query_model",
                {
                    "model_name": "Memo",
                    "filters": {"id": memo_id},
                    "limit": 1
                }
            )
            
            verify_data = json.loads(verify_result.content[0].text)
            self.assertEqual(verify_data[0]["title"], "Updated Integration Test Memo")
            
            # 5. Delete memo
            delete_result = await self.mcp_manager.call_tool(
                "django-server",
                "delete_model_instance",
                {
                    "model_name": "Memo",
                    "instance_id": memo_id
                }
            )
            
            self.assertIn("성공적으로 삭제", delete_result.content[0].text)
            
            # 6. Verify deletion
            final_query = await self.mcp_manager.call_tool(
                "django-server",
                "query_model",
                {
                    "model_name": "Memo",
                    "filters": {"id": memo_id},
                    "limit": 1
                }
            )
            
            final_data = json.loads(final_query.content[0].text)
            self.assertEqual(len(final_data), 0)
        
        finally:
            await self.async_teardown()
    
    @pytest.mark.asyncio
    async def test_list_models_tool(self):
        """Test the list_models tool."""
        await self.async_setup()
        
        try:
            result = await self.mcp_manager.call_tool(
            "django-server",
            "list_models",
            {}
        )
        
        models_data = json.loads(result.content[0].text)
        self.assertIsInstance(models_data, list)
        self.assertGreater(len(models_data), 0)
        
        # Check that Memo model is in the list
        memo_models = [m for m in models_data if m["name"] == "Memo"]
        self.assertEqual(len(memo_models), 1)
        self.assertEqual(memo_models[0]["app"], "mcp_app")
        
        finally:
            await self.async_teardown()
    
    @pytest.mark.asyncio  
    async def test_user_model_operations(self):
        """Test operations on User model."""
        await self.async_setup()
        
        try:
            # Create user via MCP
            create_result = await self.mcp_manager.call_tool(
            "django-server",
            "create_model_instance",
            {
                "model_name": "User",
                "data": {
                    "username": "mcpuser",
                    "email": "mcp@example.com",
                    "first_name": "MCP",
                    "last_name": "User"
                }
            }
        )
        
        self.assertIn("성공적으로 생성", create_result.content[0].text)
        
        # Query created user
        query_result = await self.mcp_manager.call_tool(
            "django-server", 
            "query_model",
            {
                "model_name": "User",
                "filters": {"username": "mcpuser"},
                "limit": 1
            }
        )
        
        user_data = json.loads(query_result.content[0].text)
        self.assertEqual(len(user_data), 1)
        self.assertEqual(user_data[0]["username"], "mcpuser")
        self.assertEqual(user_data[0]["email"], "mcp@example.com")
        
        finally:
            await self.async_teardown()


@pytest.mark.integration
class RealTimeDataSyncTest(TransactionTestCase):
    """Real-time data synchronization tests."""
    
    def setUp(self):
        """Set up test environment synchronously."""
        self.user = User.objects.create_user(
            username='realtimeuser',
            email='realtime@example.com',
            password='realtimepass123'
        )
        
        self.mcp_manager = MCPManager()
        
    async def async_setup(self):
        """Set up MCP server asynchronously."""
        server_params = StdioServerParameters(
            command="python",
            args=["mcp_servers/django_server.py"],
            env={"DJANGO_SETTINGS_MODULE": "myproject.settings_test"}
        )
        await self.mcp_manager.add_server("django-server", server_params)
    
    async def async_teardown(self):
        """Clean up test environment."""
        await self.mcp_manager.close_all()
    
    @pytest.mark.asyncio
    async def test_real_time_memo_updates(self):
        """Test real-time memo updates via WebSocket."""
        
        await self.async_setup()
        
        try:
            # Create WebSocket connection
        communicator = WebsocketCommunicator(
            application, "/ws/memos/"
        )
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        try:
            # Create memo via MCP
            memo_data = {
                "user_id": self.user.id,
                "title": "Real-time Test Memo",
                "content": "Testing real-time updates"
            }
            
            create_result = await self.mcp_manager.call_tool(
                "django-server",
                "create_model_instance",
                {"model_name": "Memo", "data": memo_data}
            )
            
            self.assertIn("성공적으로 생성", create_result.content[0].text)
            
            # Send memo created event to WebSocket
            await communicator.send_json_to({
                "type": "memo_created",
                "data": {
                    "title": "Real-time Test Memo",
                    "content": "Testing real-time updates",
                    "user": self.user.username
                }
            })
            
            # Wait for WebSocket response
            response = await asyncio.wait_for(
                communicator.receive_json_from(),
                timeout=5.0
            )
            
            self.assertEqual(response["type"], "memo_created")
            self.assertEqual(response["data"]["title"], "Real-time Test Memo")
            
        finally:
            await communicator.disconnect()
        
        finally:
            await self.async_teardown()
    
    @pytest.mark.asyncio
    async def test_websocket_connection_stability(self):
        """Test WebSocket connection stability under load."""
        
        # Create multiple WebSocket connections
        communicators = []
        for i in range(3):
            communicator = WebsocketCommunicator(
                application, "/ws/memos/"
            )
            connected, _ = await communicator.connect()
            self.assertTrue(connected)
            communicators.append(communicator)
        
        try:
            # Send messages through all connections
            for i, communicator in enumerate(communicators):
                await communicator.send_json_to({
                    "type": "memo_created",
                    "data": {
                        "title": f"Load Test Memo {i}",
                        "content": f"Load testing {i}",
                        "user": self.user.username
                    }
                })
            
            # Verify all connections receive messages
            for i, communicator in enumerate(communicators):
                response = await asyncio.wait_for(
                    communicator.receive_json_from(),
                    timeout=5.0
                )
                self.assertEqual(response["type"], "memo_created")
                
        finally:
            # Clean up connections
            for communicator in communicators:
                await communicator.disconnect()


@pytest.mark.integration
class ErrorHandlingIntegrationTest(TransactionTestCase):
    """Error handling and edge case integration tests."""
    
    def setUp(self):
        """Set up test environment synchronously."""
        self.user = User.objects.create_user(
            username='erroruser',
            email='error@example.com', 
            password='errorpass123'
        )
        
        self.mcp_manager = MCPManager()
        
    async def async_setup(self):
        """Set up MCP server asynchronously."""
        server_params = StdioServerParameters(
            command="python",
            args=["mcp_servers/django_server.py"],
            env={"DJANGO_SETTINGS_MODULE": "myproject.settings_test"}
        )
        await self.mcp_manager.add_server("django-server", server_params)
    
    async def async_teardown(self):
        """Clean up test environment."""
        await self.mcp_manager.close_all()
    
    @pytest.mark.asyncio
    async def test_invalid_model_name(self):
        """Test handling of invalid model names."""
        
        await self.async_setup()
        
        try:
            result = await self.mcp_manager.call_tool(
            "django-server",
            "query_model",
            {
                "model_name": "NonexistentModel",
                "filters": {},
                "limit": 1
            }
        )
        
        self.assertIn("Error", result.content[0].text)
        
        finally:
            await self.async_teardown()
    
    @pytest.mark.asyncio
    async def test_invalid_instance_id(self):
        """Test handling of invalid instance IDs."""
        
        await self.async_setup()
        
        try:
            result = await self.mcp_manager.call_tool(
            "django-server",
            "delete_model_instance",
            {
                "model_name": "Memo", 
                "instance_id": 99999
            }
        )
        
        self.assertIn("Error", result.content[0].text)
        
        finally:
            await self.async_teardown()
    
    @pytest.mark.asyncio
    async def test_invalid_tool_name(self):
        """Test handling of invalid tool names."""
        
        await self.async_setup()
        
        try:
            result = await self.mcp_manager.call_tool(
            "django-server",
            "nonexistent_tool",
            {}
        )
        
        self.assertIn("Unknown tool", result.content[0].text)
        
        finally:
            await self.async_teardown()
    
    @pytest.mark.asyncio 
    async def test_malformed_data(self):
        """Test handling of malformed data."""
        
        await self.async_setup()
        
        try:
            result = await self.mcp_manager.call_tool(
            "django-server",
            "create_model_instance",
            {
                "model_name": "Memo",
                "data": {
                    "user_id": "invalid_id",  # Should be integer
                    "title": None,  # Should be string
                    "content": {}  # Should be string
                }
            }
        )
        
        self.assertIn("Error", result.content[0].text)
        
        finally:
            await self.async_teardown()