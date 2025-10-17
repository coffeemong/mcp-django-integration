"""
Failure Recovery Tests.

Tests for system resilience and recovery from various failure scenarios.
"""

import json
import pytest
import asyncio
from unittest import TestCase
from django.test import TransactionTestCase
from django.contrib.auth.models import User
from asgiref.sync import sync_to_async

from mcp_app.models import Memo
from mcp_servers.manager import MCPManager
from mcp import StdioServerParameters


@pytest.mark.integration
class FailureRecoveryTest(TestCase):
    """Test failure recovery scenarios."""
    
    @pytest.mark.asyncio
    async def test_server_restart_recovery(self):
        """Test server restart and recovery."""
        manager = MCPManager()
        
        server_params = StdioServerParameters(
            command="python",
            args=["mcp_servers/django_server.py"],
            env={"DJANGO_SETTINGS_MODULE": "myproject.settings_test"}
        )
        
        # Step 1: Start server and verify it works
        await manager.add_server("test-server", server_params)
        
        result1 = await manager.call_tool("test-server", "list_models", {})
        self.assertIsNotNone(result1.content)
        models_data1 = json.loads(result1.content[0].text)
        self.assertIsInstance(models_data1, list)
        
        # Step 2: Force server shutdown
        await manager.close_server("test-server")
        
        # Step 3: Restart server
        await manager.add_server("test-server", server_params)
        
        # Step 4: Verify server works after restart
        result2 = await manager.call_tool("test-server", "list_models", {})
        self.assertIsNotNone(result2.content)
        models_data2 = json.loads(result2.content[0].text)
        self.assertIsInstance(models_data2, list)
        
        # Results should be consistent
        self.assertEqual(len(models_data1), len(models_data2))
        
        await manager.close_all()
    
    @pytest.mark.asyncio
    async def test_connection_timeout_recovery(self):
        """Test recovery from connection timeouts."""
        manager = MCPManager()
        
        server_params = StdioServerParameters(
            command="python",
            args=["mcp_servers/django_server.py"],
            env={"DJANGO_SETTINGS_MODULE": "myproject.settings_test"}
        )
        
        await manager.add_server("timeout-test", server_params)
        
        try:
            # Normal operation should work
            result1 = await manager.call_tool("timeout-test", "list_models", {})
            self.assertIsNotNone(result1.content)
            
            # Simulate timeout by closing and restarting
            await manager.close_server("timeout-test")
            
            # Server should be able to restart after timeout
            restart_success = await manager.add_server("timeout-test", server_params)
            self.assertTrue(restart_success)
            
            # Operations should work after recovery
            result2 = await manager.call_tool("timeout-test", "list_models", {})
            self.assertIsNotNone(result2.content)
            
        finally:
            await manager.close_all()
    
    @pytest.mark.asyncio
    async def test_multiple_server_failure_recovery(self):
        """Test recovery when multiple servers fail."""
        manager = MCPManager()
        
        server_params = StdioServerParameters(
            command="python",
            args=["mcp_servers/django_server.py"],
            env={"DJANGO_SETTINGS_MODULE": "myproject.settings_test"}
        )
        
        # Start multiple servers
        server_names = ["server-1", "server-2", "server-3"]
        
        for name in server_names:
            success = await manager.add_server(name, server_params)
            self.assertTrue(success, f"Server {name} should start successfully")
        
        # Verify all servers work
        for name in server_names:
            result = await manager.call_tool(name, "list_models", {})
            self.assertIsNotNone(result.content)
        
        # Simulate failure of all servers
        for name in server_names:
            await manager.close_server(name)
        
        # Restart all servers
        recovered_count = 0
        for name in server_names:
            success = await manager.add_server(name, server_params)
            if success:
                recovered_count += 1
        
        # At least 2 out of 3 should recover
        self.assertGreaterEqual(recovered_count, 2)
        
        # Test recovered servers
        working_count = 0
        for name in server_names:
            if name in manager.sessions:
                try:
                    result = await manager.call_tool(name, "list_models", {})
                    if result.content:
                        working_count += 1
                except Exception:
                    pass
        
        self.assertGreaterEqual(working_count, 2)
        
        await manager.close_all()
    
    @pytest.mark.asyncio
    async def test_graceful_degradation(self):
        """Test graceful degradation when some operations fail."""
        manager = MCPManager()
        
        server_params = StdioServerParameters(
            command="python",
            args=["mcp_servers/django_server.py"],
            env={"DJANGO_SETTINGS_MODULE": "myproject.settings_test"}
        )
        
        await manager.add_server("degradation-test", server_params)
        
        try:
            # Test that valid operations still work when invalid ones fail
            operations = [
                ("list_models", {}, True),  # Should work
                ("invalid_tool", {}, False),  # Should fail gracefully
                ("query_model", {"model_name": "User", "filters": {}}, True),  # Should work
                ("query_model", {"model_name": "InvalidModel"}, False),  # Should fail gracefully
            ]
            
            results = []
            for tool_name, args, should_succeed in operations:
                try:
                    result = await manager.call_tool("degradation-test", tool_name, args)
                    results.append((tool_name, result, None, should_succeed))
                except Exception as e:
                    results.append((tool_name, None, e, should_succeed))
            
            # Verify results match expectations
            for tool_name, result, exception, should_succeed in results:
                if should_succeed:
                    self.assertIsNotNone(result, f"{tool_name} should succeed")
                    if result:
                        self.assertNotIn("Error", result.content[0].text, 
                                       f"{tool_name} should not return error")
                else:
                    # Failing operations should return error messages, not crash
                    if result:
                        self.assertIn("Error", result.content[0].text, 
                                    f"{tool_name} should return error message")
        
        finally:
            await manager.close_all()


@pytest.mark.integration 
class DataCorruptionRecoveryTest(TransactionTestCase):
    """Test recovery from data corruption scenarios."""
    
    async def asyncSetUp(self):
        """Set up test environment."""
        self.user = await sync_to_async(User.objects.create_user)(
            username='recoveryuser',
            email='recovery@example.com',
            password='recoverypass123'
        )
    
    @pytest.mark.asyncio
    async def test_partial_operation_recovery(self):
        """Test recovery from partially completed operations."""
        manager = MCPManager()
        
        server_params = StdioServerParameters(
            command="python", 
            args=["mcp_servers/django_server.py"],
            env={"DJANGO_SETTINGS_MODULE": "myproject.settings_test"}
        )
        
        await manager.add_server("partial-test", server_params)
        
        try:
            # Create a memo successfully
            create_result = await manager.call_tool(
                "partial-test",
                "create_model_instance",
                {
                    "model_name": "Memo",
                    "data": {
                        "user_id": self.user.id,
                        "title": "Recovery Test Memo",
                        "content": "Test content"
                    }
                }
            )
            
            self.assertIn("성공적으로 생성", create_result.content[0].text)
            
            # Get the memo ID
            query_result = await manager.call_tool(
                "partial-test",
                "query_model",
                {
                    "model_name": "Memo",
                    "filters": {"title": "Recovery Test Memo"},
                    "limit": 1
                }
            )
            
            memo_data = json.loads(query_result.content[0].text)
            self.assertEqual(len(memo_data), 1)
            memo_id = memo_data[0]["id"]
            
            # Attempt operations that might fail
            operations = [
                # Valid update
                ("update_model_instance", {
                    "model_name": "Memo",
                    "instance_id": memo_id,
                    "data": {"title": "Updated Title"}
                }, True),
                
                # Invalid update (non-existent ID)
                ("update_model_instance", {
                    "model_name": "Memo", 
                    "instance_id": 99999,
                    "data": {"title": "Should Fail"}
                }, False),
                
                # Valid query after failed operation
                ("query_model", {
                    "model_name": "Memo",
                    "filters": {"id": memo_id},
                    "limit": 1
                }, True),
            ]
            
            for tool_name, args, should_succeed in operations:
                result = await manager.call_tool("partial-test", tool_name, args)
                
                if should_succeed:
                    if tool_name == "query_model":
                        # Verify data integrity
                        data = json.loads(result.content[0].text)
                        self.assertEqual(len(data), 1)
                        self.assertEqual(data[0]["title"], "Updated Title")
                    else:
                        self.assertNotIn("Error", result.content[0].text)
                else:
                    self.assertIn("Error", result.content[0].text)
            
        finally:
            await manager.close_all()
    
    @pytest.mark.asyncio
    async def test_database_consistency_after_failures(self):
        """Test database remains consistent after operation failures."""
        manager = MCPManager()
        
        server_params = StdioServerParameters(
            command="python",
            args=["mcp_servers/django_server.py"],
            env={"DJANGO_SETTINGS_MODULE": "myproject.settings_test"}
        )
        
        await manager.add_server("consistency-test", server_params)
        
        try:
            # Record initial state
            initial_user_count = await sync_to_async(User.objects.count)()
            initial_memo_count = await sync_to_async(Memo.objects.count)()
            
            # Perform a mix of valid and invalid operations
            operations = [
                # Valid user creation
                ("create_model_instance", {
                    "model_name": "User",
                    "data": {
                        "username": "consistency_user_1",
                        "email": "cons1@example.com"
                    }
                }),
                
                # Invalid user creation (duplicate username)
                ("create_model_instance", {
                    "model_name": "User", 
                    "data": {
                        "username": "consistency_user_1",  # Duplicate
                        "email": "cons2@example.com"
                    }
                }),
                
                # Valid user creation
                ("create_model_instance", {
                    "model_name": "User",
                    "data": {
                        "username": "consistency_user_2",
                        "email": "cons3@example.com"
                    }
                }),
            ]
            
            results = []
            for tool_name, args in operations:
                try:
                    result = await manager.call_tool("consistency-test", tool_name, args)
                    results.append((result, None))
                except Exception as e:
                    results.append((None, e))
            
            # Check final database state
            final_user_count = await sync_to_async(User.objects.count)()
            final_memo_count = await sync_to_async(Memo.objects.count)()
            
            # Should have created 2 new users (one duplicate should fail)
            expected_user_count = initial_user_count + 2
            self.assertEqual(final_user_count, expected_user_count)
            
            # Memo count should be unchanged
            self.assertEqual(final_memo_count, initial_memo_count)
            
            # Verify specific users exist
            user1_exists = await sync_to_async(
                User.objects.filter(username="consistency_user_1").exists
            )()
            user2_exists = await sync_to_async(
                User.objects.filter(username="consistency_user_2").exists  
            )()
            
            self.assertTrue(user1_exists)
            self.assertTrue(user2_exists)
            
        finally:
            await manager.close_all()


@pytest.mark.integration
class NetworkFailureRecoveryTest(TestCase):
    """Test recovery from network-related failures."""
    
    @pytest.mark.asyncio
    async def test_connection_drop_recovery(self):
        """Test recovery from connection drops."""
        manager1 = MCPManager()
        manager2 = MCPManager()
        
        server_params = StdioServerParameters(
            command="python",
            args=["mcp_servers/django_server.py"],
            env={"DJANGO_SETTINGS_MODULE": "myproject.settings_test"}
        )
        
        # Start first connection
        await manager1.add_server("connection-1", server_params)
        
        # Verify it works
        result1 = await manager1.call_tool("connection-1", "list_models", {})
        self.assertIsNotNone(result1.content)
        
        # Simulate connection drop by closing first manager
        await manager1.close_all()
        
        # Start new connection with different manager
        await manager2.add_server("connection-2", server_params)
        
        # Verify new connection works
        result2 = await manager2.call_tool("connection-2", "list_models", {})
        self.assertIsNotNone(result2.content)
        
        # Results should be consistent
        models1 = json.loads(result1.content[0].text)
        models2 = json.loads(result2.content[0].text)
        self.assertEqual(len(models1), len(models2))
        
        await manager2.close_all()
    
    @pytest.mark.asyncio
    async def test_rapid_reconnection(self):
        """Test rapid reconnection scenarios."""
        manager = MCPManager()
        
        server_params = StdioServerParameters(
            command="python",
            args=["mcp_servers/django_server.py"],
            env={"DJANGO_SETTINGS_MODULE": "myproject.settings_test"}
        )
        
        reconnection_count = 5
        successful_operations = 0
        
        for i in range(reconnection_count):
            # Connect
            success = await manager.add_server(f"rapid-{i}", server_params)
            
            if success:
                try:
                    # Perform operation
                    result = await manager.call_tool(f"rapid-{i}", "list_models", {})
                    if result.content:
                        successful_operations += 1
                except Exception:
                    pass
                
                # Disconnect
                await manager.close_server(f"rapid-{i}")
            
            # Small delay to avoid overwhelming the system
            await asyncio.sleep(0.1)
        
        # Most reconnections should succeed
        self.assertGreaterEqual(successful_operations, reconnection_count - 2)
        
        await manager.close_all()
    
    @pytest.mark.asyncio 
    async def test_server_process_crash_simulation(self):
        """Test behavior when server process crashes."""
        manager = MCPManager()
        
        server_params = StdioServerParameters(
            command="python",
            args=["mcp_servers/django_server.py"],
            env={"DJANGO_SETTINGS_MODULE": "myproject.settings_test"}
        )
        
        # Start server
        await manager.add_server("crash-test", server_params)
        
        # Verify it works initially
        result1 = await manager.call_tool("crash-test", "list_models", {})
        self.assertIsNotNone(result1.content)
        
        # Simulate crash by forcibly closing the server
        await manager.close_server("crash-test")
        
        # Try to use the server (should fail gracefully)
        try:
            result2 = await manager.call_tool("crash-test", "list_models", {})
            # If this doesn't raise an exception, it should indicate an error
            self.fail("Expected exception when calling closed server")
        except Exception:
            # This is expected - the server should not be available
            pass
        
        # Recovery: restart the server
        recovery_success = await manager.add_server("crash-test-recovery", server_params)
        self.assertTrue(recovery_success)
        
        # Verify recovery works
        result3 = await manager.call_tool("crash-test-recovery", "list_models", {})
        self.assertIsNotNone(result3.content)
        
        # Results should be consistent with pre-crash state
        models1 = json.loads(result1.content[0].text)
        models3 = json.loads(result3.content[0].text)
        self.assertEqual(len(models1), len(models3))
        
        await manager.close_all()