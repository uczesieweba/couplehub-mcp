"""
WSGI entry point for Hostido - wraps ASGI MCP app with a3wsgi.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from server import mcp
from a3wsgi import ASGIMiddleware

asgi_app = mcp.sse_app()
app = ASGIMiddleware(asgi_app)
