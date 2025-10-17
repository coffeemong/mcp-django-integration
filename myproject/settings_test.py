"""
Test settings for Django project.
"""

from .settings import *

# Use in-memory database for tests
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Use in-memory channel layer for tests
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    }
}

# Disable migrations for faster tests
class DisableMigrations:
    def __contains__(self, item):
        return True
    
    def __getitem__(self, item):
        return None

MIGRATION_MODULES = DisableMigrations()

# Test-specific MCP configuration
MCP_SERVER_CONFIG = {
    'command': 'python',
    'args': ['mcp_servers/django_server.py'],
    'env': {
        'DJANGO_SETTINGS_MODULE': 'myproject.settings_test'
    }
}