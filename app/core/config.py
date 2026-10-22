"""
Configurações centrais da aplicação UaiGraph / GraphPoliticsRAG.
Carrega variáveis de ambiente e define padrões de execução.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Carrega arquivo .env da raiz do projeto
BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")

# Neo4j
NEO4J_URI: str = os.getenv("NEO4J_URI", "")
NEO4J_USER: str = os.getenv("NEO4J_USER", "")
NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "")

# LLM Providers
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

# Modelos
GROQ_EXTRACTION_MODEL: str = os.getenv("GROQ_EXTRACTION_MODEL", "openai/gpt-oss-120b")
GROQ_CHAT_MODEL: str = os.getenv("GROQ_CHAT_MODEL", "openai/gpt-oss-20b")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Servidor / API
PORT: int = int(os.getenv("PORT", "8000"))
ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
IS_DEV: bool = ENVIRONMENT.lower() != "production"

# CORS
CORS_ORIGINS: str = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:4200,http://localhost:8000,http://127.0.0.1:4200,http://127.0.0.1:8000"
)
