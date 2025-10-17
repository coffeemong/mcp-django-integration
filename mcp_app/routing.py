"""
WebSocket routing for mcp_app.
"""

from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/memos/$', consumers.MemoConsumer.as_asgi()),
]