"""
WebSocket consumers for real-time updates.
"""

import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from .models import Memo


class MemoConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for memo updates."""
    
    async def connect(self):
        """Handle WebSocket connection."""
        self.room_name = "memos"
        self.room_group_name = f"memo_{self.room_name}"
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        """Handle messages from WebSocket."""
        text_data_json = json.loads(text_data)
        message_type = text_data_json['type']
        
        if message_type == 'memo_created':
            await self.memo_created(text_data_json)
        elif message_type == 'memo_updated':
            await self.memo_updated(text_data_json)
        elif message_type == 'memo_deleted':
            await self.memo_deleted(text_data_json)
    
    async def memo_created(self, event):
        """Send memo created notification."""
        await self.send(text_data=json.dumps({
            'type': 'memo_created',
            'data': event['data']
        }))
    
    async def memo_updated(self, event):
        """Send memo updated notification."""
        await self.send(text_data=json.dumps({
            'type': 'memo_updated',
            'data': event['data']
        }))
    
    async def memo_deleted(self, event):
        """Send memo deleted notification."""
        await self.send(text_data=json.dumps({
            'type': 'memo_deleted',
            'data': event['data']
        }))