#!/usr/bin/env python3
"""
Django MCP Server implementation.
"""

import os
import sys
import json
import asyncio
import django
from pathlib import Path

# Add the parent directory to Python path for Django imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
django.setup()

from django.apps import apps
from django.contrib.auth.models import User
from django.db import transaction
from asgiref.sync import sync_to_async
from mcp.server import Server
from mcp import stdio_server, types


# Initialize the MCP server
server = Server("django-mcp-server")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    """List available tools."""
    return [
        types.Tool(
            name="list_models",
            description="List all Django models",
            inputSchema={
                "type": "object",
                "properties": {},
            }
        ),
        types.Tool(
            name="query_model", 
            description="Query a Django model with filters",
            inputSchema={
                "type": "object",
                "properties": {
                    "model_name": {"type": "string", "description": "Name of the model"},
                    "filters": {"type": "object", "description": "Filter conditions"},
                    "limit": {"type": "integer", "description": "Maximum number of results"}
                },
                "required": ["model_name"]
            }
        ),
        types.Tool(
            name="create_model_instance",
            description="Create a new model instance",
            inputSchema={
                "type": "object", 
                "properties": {
                    "model_name": {"type": "string", "description": "Name of the model"},
                    "data": {"type": "object", "description": "Model instance data"}
                },
                "required": ["model_name", "data"]
            }
        ),
        types.Tool(
            name="update_model_instance",
            description="Update an existing model instance", 
            inputSchema={
                "type": "object",
                "properties": {
                    "model_name": {"type": "string", "description": "Name of the model"},
                    "instance_id": {"type": "integer", "description": "ID of the instance"},
                    "data": {"type": "object", "description": "Updated data"}
                },
                "required": ["model_name", "instance_id", "data"]
            }
        ),
        types.Tool(
            name="delete_model_instance",
            description="Delete a model instance",
            inputSchema={
                "type": "object",
                "properties": {
                    "model_name": {"type": "string", "description": "Name of the model"},
                    "instance_id": {"type": "integer", "description": "ID of the instance"}
                },
                "required": ["model_name", "instance_id"]
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """Handle tool calls."""
    
    try:
        if name == "list_models":
            return await handle_list_models()
        elif name == "query_model":
            return await handle_query_model(arguments)
        elif name == "create_model_instance":
            return await handle_create_instance(arguments)
        elif name == "update_model_instance":
            return await handle_update_instance(arguments)
        elif name == "delete_model_instance":
            return await handle_delete_instance(arguments)
        else:
            return [types.TextContent(type="text", text=f"Unknown tool: {name}")]
            
    except Exception as e:
        return [types.TextContent(type="text", text=f"Error: {str(e)}")]


async def handle_list_models() -> list[types.TextContent]:
    """List all Django models."""
    
    @sync_to_async
    def get_models():
        model_list = []
        for model in apps.get_models():
            model_list.append({
                "name": model.__name__,
                "app": model._meta.app_label,
                "fields": [f.name for f in model._meta.fields]
            })
        return model_list
    
    models = await get_models()
    return [types.TextContent(type="text", text=json.dumps(models, indent=2))]


async def handle_query_model(arguments: dict) -> list[types.TextContent]:
    """Query a Django model."""
    model_name = arguments["model_name"]
    filters = arguments.get("filters", {})
    limit = arguments.get("limit", 10)
    
    @sync_to_async
    def query_model():
        try:
            model = apps.get_model("mcp_app", model_name)
        except LookupError:
            # Try to get model from auth app for User model
            model = apps.get_model("auth", model_name)
        
        queryset = model.objects.filter(**filters)[:limit]
        
        results = []
        for obj in queryset:
            result = {"id": obj.pk}
            for field in model._meta.fields:
                value = getattr(obj, field.name)
                if hasattr(value, 'isoformat'):  # Handle datetime fields
                    value = value.isoformat()
                elif hasattr(value, 'pk'):  # Handle foreign key fields
                    value = value.pk
                result[field.name] = value
            results.append(result)
        
        return results
    
    results = await query_model()
    return [types.TextContent(type="text", text=json.dumps(results, indent=2))]


async def handle_create_instance(arguments: dict) -> list[types.TextContent]:
    """Create a new model instance."""
    model_name = arguments["model_name"]
    data = arguments["data"]
    
    @sync_to_async
    @transaction.atomic
    def create_instance():
        try:
            model = apps.get_model("mcp_app", model_name)
        except LookupError:
            model = apps.get_model("auth", model_name)
        
        # Handle foreign key relationships
        processed_data = {}
        for key, value in data.items():
            if key.endswith('_id') and isinstance(value, int):
                # This is likely a foreign key ID
                processed_data[key] = value
            elif key == 'user_id':
                # Special handling for user foreign key
                processed_data['user'] = User.objects.get(id=value)
            else:
                processed_data[key] = value
        
        instance = model.objects.create(**processed_data)
        return instance.pk
    
    instance_id = await create_instance()
    return [types.TextContent(
        type="text", 
        text=f"{model_name} 인스턴스가 성공적으로 생성되었습니다. ID: {instance_id}"
    )]


async def handle_update_instance(arguments: dict) -> list[types.TextContent]:
    """Update a model instance."""
    model_name = arguments["model_name"] 
    instance_id = arguments["instance_id"]
    data = arguments["data"]
    
    @sync_to_async
    @transaction.atomic
    def update_instance():
        try:
            model = apps.get_model("mcp_app", model_name)
        except LookupError:
            model = apps.get_model("auth", model_name)
        
        instance = model.objects.get(pk=instance_id)
        
        for key, value in data.items():
            if hasattr(instance, key):
                setattr(instance, key, value)
        
        instance.save()
        return instance.pk
    
    await update_instance()
    return [types.TextContent(
        type="text",
        text=f"{model_name} 인스턴스 ID {instance_id}가 성공적으로 수정되었습니다."
    )]


async def handle_delete_instance(arguments: dict) -> list[types.TextContent]:
    """Delete a model instance."""
    model_name = arguments["model_name"]
    instance_id = arguments["instance_id"]
    
    @sync_to_async
    @transaction.atomic 
    def delete_instance():
        try:
            model = apps.get_model("mcp_app", model_name)
        except LookupError:
            model = apps.get_model("auth", model_name)
        
        instance = model.objects.get(pk=instance_id)
        instance.delete()
    
    await delete_instance()
    return [types.TextContent(
        type="text",
        text=f"{model_name} 인스턴스 ID {instance_id}가 성공적으로 삭제되었습니다."
    )]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())