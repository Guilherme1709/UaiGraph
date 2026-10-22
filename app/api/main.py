"""
Ponto de entrada da aplicação FastAPI (UaiGraph / GraphPoliticsRAG).
Configuração de middlewares, CORS, tratamento de exceções, lifespan e montagem do frontend.
"""

import sys
import logging
from pathlib import Path
from contextlib import asynccontextmanager

# Garante saída UTF-8 no Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("graphpolitics.api")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import CORS_ORIGINS, PORT, IS_DEV
from app.api.limiter import limiter
from app.api.routes import router, db

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicializa esquema e restrições do Neo4j no arranque
    try:
        db.init_schema()
        logger.info("[API] Esquema do Neo4j inicializado com sucesso.")
    except Exception as e:
        logger.warning(f"[API] Aviso ao inicializar esquema do Neo4j: {e}")
    yield
    db.close()
    logger.info("[API] Conexão com Neo4j encerrada com segurança.")

app = FastAPI(
    title="GraphPoliticsRAG API",
    description="API de Inteligência Política para Deputados Federais de MG usando Neo4j + Groq/Gemini",
    version="1.0.0",
    lifespan=lifespan
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configuração segura de CORS
raw_origins = [o.strip() for o in CORS_ORIGINS.split(",") if o.strip()]
if "*" in raw_origins:
    cors_allowed = ["*"]
    cors_credentials = False
else:
    cors_allowed = raw_origins
    cors_credentials = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allowed,
    allow_credentials=cors_credentials,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Conecta as rotas da aplicação
app.include_router(router)

# Monta o frontend Angular se compilado em modo estático
angular_dist = Path(__file__).resolve().parent.parent.parent / "frontend-angular" / "dist" / "frontend-angular" / "browser"
if angular_dist.exists():
    app.mount("/", StaticFiles(directory=str(angular_dist), html=True), name="frontend")
    logger.info(f"[API] Frontend Angular montado a partir de: {angular_dist}")

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Iniciando servidor na porta {PORT} (modo {'desenvolvimento' if IS_DEV else 'produção'})...")
    uvicorn.run("app.api.main:app", host="0.0.0.0", port=PORT, reload=IS_DEV)
