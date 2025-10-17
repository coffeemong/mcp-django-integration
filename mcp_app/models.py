"""
Models for MCP Django integration.
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Memo(models.Model):
    """Memo model for testing MCP integration."""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='memos')
    title = models.CharField(max_length=200)
    content = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} by {self.user.username}"