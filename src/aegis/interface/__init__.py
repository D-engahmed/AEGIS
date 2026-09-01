"""Interface layer (layer 03): REST/gRPC boundaries, HTTP translation,
API contracts and request validation. Converts domain errors to codes.
"""

from .app import create_app
from .container import AUTH_SECRET, Container

__all__ = ["AUTH_SECRET", "Container", "create_app"]
