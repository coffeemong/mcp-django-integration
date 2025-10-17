"""
Views for MCP Django integration.
"""

from django.shortcuts import render
from django.http import JsonResponse
from .models import Memo


def index(request):
    """Index view."""
    return JsonResponse({'message': 'MCP Django Integration is running'})


def memo_list(request):
    """List all memos."""
    memos = Memo.objects.all()
    memo_data = [
        {
            'id': memo.id,
            'title': memo.title,
            'content': memo.content,
            'user': memo.user.username,
            'created_at': memo.created_at.isoformat(),
            'updated_at': memo.updated_at.isoformat(),
        }
        for memo in memos
    ]
    return JsonResponse({'memos': memo_data})