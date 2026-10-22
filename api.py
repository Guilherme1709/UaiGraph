"""
Fachada de retrocompatibilidade para api.py.
Delega a execução para a arquitetura modular em app.api.
Permite executar: uvicorn api:app ou python api.py
"""

import os
from app.api.main import app
from app.api.schemas import ChatRequest, ChatResponse, GraphRequest
from app.api.routes import db, chat_service
from app.core.config import PORT, IS_DEV

__all__ = [
    "app",
    "ChatRequest",
    "ChatResponse",
    "GraphRequest",
    "db",
    "chat_service"
]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=PORT, reload=IS_DEV)
