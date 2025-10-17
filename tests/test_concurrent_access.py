"""
Concurrent Access Tests.

Tests for handling multiple simultaneous MCP server connections and operations.
"""

import json
import pytest
import asyncio
from django.test import TransactionTestCase
from django.contrib.auth.models import User
from asgiref.sync import sync_to_async

from mcp_app.models import Memo
from mcp_servers.manager import MCPManager
from mcp import StdioServerParameters


@pytest.mark.integration
class ConcurrentAccessTest(TransactionTestCase):
    """Test concurrent access scenarios."""
    
    async def asyncSetUp(self):
        """Set up test environment."""
        self.user = await sync_to_async(User.objects.create_user)(
            username='concurrentuser',
            email='concurrent@example.com',
            password='concurrentpass123'
        )
    
    @pytest.mark.asyncio
    async def test_concurrent_mcp_calls(self):
        """Test concurrent MCP server calls."""
        
        async def create_memo(user_id, memo_index):
            """Create a memo using a separate MCP manager instance."""
            manager = MCPManager()
            server_params = StdioServerParameters(
                command="python",
                args=["mcp_servers/django_server.py"],
                env={"DJANGO_SETTINGS_MODULE": "myproject.settings_test"}
            )
            
            try:
                await manager.add_server(f"server-{memo_index}", server_params)
                
                result = await manager.call_tool(
                    f"server-{memo_index}",
                    "create_model_instance",
                    {
                        "model_name": "Memo",
                        "data": {
                            "user_id": user_id,
                            "title": f"Concurrent Memo {memo_index}",
                            "content": f"Content {memo_index}"
                        }
                    }
                )
                
                return result
                
            finally:
                await manager.close_all()
        
        # Create 5 concurrent memo creation tasks
        tasks = [
            create_memo(self.user.id, i) 
            for i in range(5)
        ]
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify all operations succeeded
        success_count = 0
        for result in results:
            if not isinstance(result, Exception):
                self.assertIn("성공적으로 생성", result.content[0].text)
                success_count += 1
        
        # At least 4 out of 5 should succeed (allowing for some race conditions)
        self.assertGreaterEqual(success_count, 4)
        
        # Verify memos were created in database
        memo_count = await sync_to_async(
            Memo.objects.filter(title__startswith="Concurrent Memo").count
        )()
        self.assertGreaterEqual(memo_count, 4)
    
    @pytest.mark.asyncio
    async def test_concurrent_read_operations(self):
        """Test concurrent read operations don't interfere with each other."""
        
        # Create some test data first
        await sync_to_async(Memo.objects.create)(
            user=self.user,
            title="Test Memo for Concurrent Reads",
            content="Test content"
        )
        
        async def query_memos(query_index):
            """Query memos using separate manager."""
            manager = MCPManager()
            server_params = StdioServerParameters(
                command="python",
                args=["mcp_servers/django_server.py"],
                env={"DJANGO_SETTINGS_MODULE": "myproject.settings_test"}
            )
            
            try:
                await manager.add_server(f"read-server-{query_index}", server_params)
                
                result = await manager.call_tool(
                    f"read-server-{query_index}",
                    "query_model",
                    {
                        "model_name": "Memo",
                        "filters": {"user": self.user.id},
                        "limit": 10
                    }
                )
                
                return json.loads(result.content[0].text)
                
            finally:
                await manager.close_all()
        
        # Create 10 concurrent read tasks
        tasks = [query_memos(i) for i in range(10)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All reads should succeed and return consistent data
        success_count = 0
        for result in results:
            if not isinstance(result, Exception):
                self.assertIsInstance(result, list)
                self.assertGreaterEqual(len(result), 1)
                success_count += 1
        
        self.assertEqual(success_count, 10)  # All reads should succeed
    
    @pytest.mark.asyncio
    async def test_mixed_concurrent_operations(self):
        """Test mixed read/write operations concurrently."""
        
        async def read_operation(op_index):
            """Perform read operation."""
            manager = MCPManager()
            server_params = StdioServerParameters(
                command="python",
                args=["mcp_servers/django_server.py"],
                env={"DJANGO_SETTINGS_MODULE": "myproject.settings_test"}
            )
            
            try:
                await manager.add_server(f"read-{op_index}", server_params)
                
                result = await manager.call_tool(
                    f"read-{op_index}",
                    "list_models",
                    {}
                )
                
                return ("read", json.loads(result.content[0].text))
                
            finally:
                await manager.close_all()
        
        async def write_operation(op_index):
            """Perform write operation."""
            manager = MCPManager()
            server_params = StdioServerParameters(
                command="python",
                args=["mcp_servers/django_server.py"],
                env={"DJANGO_SETTINGS_MODULE": "myproject.settings_test"}
            )
            
            try:
                await manager.add_server(f"write-{op_index}", server_params)
                
                result = await manager.call_tool(
                    f"write-{op_index}",
                    "create_model_instance",
                    {
                        "model_name": "Memo",
                        "data": {
                            "user_id": self.user.id,
                            "title": f"Mixed Op Memo {op_index}",
                            "content": f"Mixed operation content {op_index}"
                        }
                    }
                )
                
                return ("write", result.content[0].text)
                
            finally:
                await manager.close_all()
        
        # Mix of read and write operations
        tasks = []
        for i in range(10):
            if i % 2 == 0:
                tasks.append(read_operation(i))
            else:
                tasks.append(write_operation(i))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Analyze results
        read_success = 0
        write_success = 0
        
        for result in results:
            if not isinstance(result, Exception):
                op_type, data = result
                if op_type == "read":
                    self.assertIsInstance(data, list)
                    read_success += 1
                elif op_type == "write":
                    self.assertIn("성공적으로 생성", data)
                    write_success += 1
        
        # Most operations should succeed
        self.assertGreaterEqual(read_success, 4)
        self.assertGreaterEqual(write_success, 3)
    
    @pytest.mark.asyncio
    async def test_server_connection_limits(self):
        """Test behavior under high connection load."""
        
        async def create_connection(conn_index):
            """Create a connection and perform a simple operation."""
            manager = MCPManager()
            server_params = StdioServerParameters(
                command="python",
                args=["mcp_servers/django_server.py"],
                env={"DJANGO_SETTINGS_MODULE": "myproject.settings_test"}
            )
            
            try:
                success = await manager.add_server(f"load-{conn_index}", server_params)
                if not success:
                    return ("failed_to_connect", conn_index)
                
                result = await manager.call_tool(
                    f"load-{conn_index}",
                    "list_models",
                    {}
                )
                
                return ("success", len(json.loads(result.content[0].text)))
                
            except Exception as e:
                return ("exception", str(e))
                
            finally:
                await manager.close_all()
        
        # Create many concurrent connections
        tasks = [create_connection(i) for i in range(20)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Analyze connection results
        successful_connections = 0
        failed_connections = 0
        exceptions = 0
        
        for result in results:
            if isinstance(result, Exception):
                exceptions += 1
            else:
                status, data = result
                if status == "success":
                    successful_connections += 1
                    self.assertGreater(data, 0)
                elif status == "failed_to_connect":
                    failed_connections += 1
                elif status == "exception":
                    exceptions += 1
        
        # At least half should succeed
        self.assertGreaterEqual(successful_connections, 10)
        
        # Total should add up to 20
        total = successful_connections + failed_connections + exceptions
        self.assertEqual(total, 20)
    
    @pytest.mark.asyncio
    async def test_database_transaction_isolation(self):
        """Test database transaction isolation under concurrent access."""
        
        async def create_user_and_memo(op_index):
            """Create user and memo in a transaction-like operation."""
            manager = MCPManager()
            server_params = StdioServerParameters(
                command="python",
                args=["mcp_servers/django_server.py"],
                env={"DJANGO_SETTINGS_MODULE": "myproject.settings_test"}
            )
            
            try:
                await manager.add_server(f"txn-{op_index}", server_params)
                
                # Create user
                user_result = await manager.call_tool(
                    f"txn-{op_index}",
                    "create_model_instance",
                    {
                        "model_name": "User",
                        "data": {
                            "username": f"txn_user_{op_index}",
                            "email": f"txn_{op_index}@example.com",
                            "first_name": f"Transaction",
                            "last_name": f"User{op_index}"
                        }
                    }
                )
                
                if "성공적으로 생성" not in user_result.content[0].text:
                    return ("user_failed", op_index)
                
                # Get created user
                user_query = await manager.call_tool(
                    f"txn-{op_index}",
                    "query_model",
                    {
                        "model_name": "User",
                        "filters": {"username": f"txn_user_{op_index}"},
                        "limit": 1
                    }
                )
                
                user_data = json.loads(user_query.content[0].text)
                if len(user_data) != 1:
                    return ("user_query_failed", op_index)
                
                user_id = user_data[0]["id"]
                
                # Create memo for user
                memo_result = await manager.call_tool(
                    f"txn-{op_index}",
                    "create_model_instance",
                    {
                        "model_name": "Memo",
                        "data": {
                            "user_id": user_id,
                            "title": f"Transaction Memo {op_index}",
                            "content": f"Created by transaction {op_index}"
                        }
                    }
                )
                
                if "성공적으로 생성" not in memo_result.content[0].text:
                    return ("memo_failed", op_index)
                
                return ("success", op_index)
                
            except Exception as e:
                return ("exception", str(e))
                
            finally:
                await manager.close_all()
        
        # Run concurrent transaction-like operations
        tasks = [create_user_and_memo(i) for i in range(8)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify transaction integrity
        success_count = 0
        for result in results:
            if not isinstance(result, Exception):
                status, data = result
                if status == "success":
                    success_count += 1
        
        # Most transactions should complete successfully
        self.assertGreaterEqual(success_count, 6)
        
        # Verify data consistency in database
        created_users = await sync_to_async(
            User.objects.filter(username__startswith="txn_user_").count
        )()
        
        created_memos = await sync_to_async(
            Memo.objects.filter(title__startswith="Transaction Memo").count  
        )()
        
        # Each successful transaction should create both user and memo
        self.assertEqual(created_users, success_count)
        self.assertEqual(created_memos, success_count)


@pytest.mark.integration
class ConcurrentWebSocketTest(TransactionTestCase):
    """Test concurrent WebSocket connections."""
    
    async def asyncSetUp(self):
        """Set up test environment."""
        self.user = await sync_to_async(User.objects.create_user)(
            username='wsuser',
            email='ws@example.com', 
            password='wspass123'
        )
    
    @pytest.mark.asyncio
    async def test_multiple_websocket_connections(self):
        """Test multiple WebSocket connections handling concurrent messages."""
        from channels.testing import WebsocketCommunicator
        from myproject.asgi import application
        
        # Create multiple WebSocket connections
        communicators = []
        connection_count = 5
        
        for i in range(connection_count):
            communicator = WebsocketCommunicator(
                application, "/ws/memos/"
            )
            connected, _ = await communicator.connect()
            self.assertTrue(connected, f"Connection {i} should succeed")
            communicators.append(communicator)
        
        try:
            # Send messages from all connections concurrently
            send_tasks = []
            for i, communicator in enumerate(communicators):
                task = communicator.send_json_to({
                    "type": "memo_created",
                    "data": {
                        "title": f"Concurrent WS Memo {i}",
                        "content": f"WebSocket message {i}",
                        "user": self.user.username
                    }
                })
                send_tasks.append(task)
            
            # Wait for all sends to complete
            await asyncio.gather(*send_tasks)
            
            # Receive messages from all connections
            receive_tasks = []
            for communicator in communicators:
                task = asyncio.wait_for(
                    communicator.receive_json_from(),
                    timeout=5.0
                )
                receive_tasks.append(task)
            
            # Wait for all receives
            responses = await asyncio.gather(*receive_tasks, return_exceptions=True)
            
            # Verify responses
            success_count = 0
            for response in responses:
                if not isinstance(response, Exception):
                    self.assertEqual(response["type"], "memo_created")
                    success_count += 1
            
            # All connections should receive their messages
            self.assertEqual(success_count, connection_count)
            
        finally:
            # Clean up all connections
            disconnect_tasks = [
                communicator.disconnect() 
                for communicator in communicators
            ]
            await asyncio.gather(*disconnect_tasks, return_exceptions=True)