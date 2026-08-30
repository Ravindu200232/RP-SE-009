"""Database setup and persistence helpers."""
from . import database_server

# Compatibility name used by older callers; the real owner file is database_server.py.
mongo_lifecycle = database_server
