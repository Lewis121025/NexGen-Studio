"""Router exports."""
from __future__ import annotations

from .auth import router as auth_router
from .creative import router as creative_router
from .general import router as general_router
from .governance import router as governance_router

# Note: These routers are primarily used by versioned.py
# to avoid duplication, they should not be directly included in main.py

__all__ = ["auth_router", "creative_router", "general_router", "governance_router"]
