import os
import sys
import time
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from typing import List, Optional

# Garante saída UTF-8 no Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("graphpolitics.api")

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# Rate Limiting
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from database import Neo4jManager
from engine import get_entities_from_question, generate_final_answer

db = Neo4jManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicializa esquema e restrições no arranque
    try:
        db.init_schema()
        logger.info("[API] Esquema do Neo4j inicializado com sucesso.")
    except Exception as e:
        logger.warning(f"[API] Aviso ao inicializar esquema do Neo4j: {e}")
    yield
    db.close()
    logger.info("[API] Conexão com Neo4j encerrada com segurança.")

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="GraphPoliticsRAG API",
    description="API de Inteligência Política para Deputados Federais de MG usando Neo4j + Groq/Gemini",
    version="1.0.0",
    lifespan=lifespan
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configuração segura de CORS via variável de ambiente
cors_origins_env = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:4200,http://localhost:8000,http://127.0.0.1:4200,http://127.0.0.1:8000"
)
raw_origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()]

if "*" in raw_origins:
    # Se wildcard em dev, allow_credentials deve ser False para evitar vulnerabilidade de segurança do navegador
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

# Schemas com validação restritiva contra payloads maliciosos
class ChatRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=2,
        max_length=500,
        description="Pergunta do usuário sobre deputados, partidos ou projetos de lei."
    )
    depth: Optional[int] = Field(
        default=1,
        ge=1,
        le=3,
        description="Profundidade da busca no grafo (1 a 3 saltos)."
    )
    max_nodes: Optional[int] = Field(
        default=25,
        ge=5,
        le=500,
        description="Número máximo de nós retornados para o grafo visual."
    )

class ChatResponse(BaseModel):
    question: str
    entities: List[str]
    answer: str
    graph: dict
    politician: Optional[dict] = None

class GraphRequest(BaseModel):
    entities: List[str] = Field(
        default_factory=list,
        max_length=10,
        description="Lista de entidades para visualização."
    )
    depth: Optional[int] = Field(
        default=1,
        ge=1,
        le=3
    )
    max_nodes: Optional[int] = Field(
        default=25,
        ge=5,
        le=500
    )

# Cache em memória (TTL) da lista de deputados
_POLITICIANS_TTL = 600.0  # segundos
_politicians_cache = {"data": None, "ts": 0.0}

@app.get("/", tags=["Root"])
def root():
    """Endpoint raiz com informações de status e documentação da API."""
    return {
        "service": "UaiGraph - Political Graph RAG API",
        "status": "online",
        "docs": "/docs",
        "health": "/health"
    }

@app.get("/health")
@app.get("/api/health")
def health_check():
    """Health check ativo que valida a conectividade com o banco de grafos Neo4j."""
    is_db_healthy = db.verify_health()
    if not is_db_healthy:
        raise HTTPException(
            status_code=503,
            detail={"status": "degraded", "database": "unavailable", "service": "GraphPoliticsRAG"}
        )
    return {"status": "online", "database": "connected", "service": "GraphPoliticsRAG"}

@app.get("/api/stats")
@limiter.limit("60/minute")
def get_stats(request: Request):
    """Retorna contadores agregados do grafo para cards informativos no dashboard."""
    try:
        return db.get_graph_stats()
    except Exception as e:
        logger.error(f"Erro ao buscar estatísticas do grafo: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Não foi possível obter as estatísticas do grafo no momento."
        )

@app.get("/api/politicians")
@limiter.limit("60/minute")
def get_all_politicians_endpoint(request: Request):
    """Retorna a lista completa dos parlamentares com cache TTL de 10 minutos."""
    now = time.time()
    if _politicians_cache["data"] is not None and now - _politicians_cache["ts"] < _POLITICIANS_TTL:
        return _politicians_cache["data"]
    try:
        data = db.get_all_politicians()
        _politicians_cache["data"] = data
        _politicians_cache["ts"] = now
        return data
    except Exception as e:
        logger.error(f"Erro ao carregar lista de deputados: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Erro ao carregar a lista de parlamentares."
        )

@app.post("/api/graph")
@limiter.limit("40/minute")
def graph_endpoint(request: Request, payload: GraphRequest):
    """Retorna apenas o subgrafo (sem chamada de LLM), otimizado para interações visuais."""
    try:
        depth = payload.depth if payload.depth else 1
        max_nodes = payload.max_nodes if payload.max_nodes else 25
        if not payload.entities or any(e in ["Bancada MG", "Partidos", "Proposições"] for e in payload.entities):
            return db.get_parties_subgraph(max_nodes=max_nodes)
        return db.get_subgraph_data_for_entities(payload.entities, max_nodes=max_nodes, depth=depth)
    except Exception as e:
        logger.error(f"Erro ao processar subgrafo: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Não foi possível processar o subgrafo solicitado."
        )

@app.get("/api/suggestions")
@limiter.limit("60/minute")
def get_suggestions(request: Request):
    """Retorna deputados e perguntas sugeridas para quick chips."""
    try:
        popular = db.get_popular_politicians(limit=8)
        sample_questions = [
            "Quais projetos a deputada Célia Xakriabá (PSOL) apresentou?",
            "O que o deputado Aécio Neves (PSDB) propôs recentemente?",
            "Quais as principais propostas do deputado Reginaldo Lopes (PT)?",
            "Quais projetos foram apresentados por Nikolas Ferreira (PL)?",
            "Quais deputados compõem a bancada de Minas Gerais?"
        ]
        return {
            "popular_politicians": popular,
            "sample_questions": sample_questions
        }
    except Exception as e:
        logger.error(f"Erro ao buscar sugestões: {e}", exc_info=True)
        return {
            "popular_politicians": [],
            "sample_questions": [
                "Quais deputados compõem a bancada de Minas Gerais?"
            ]
        }

@app.post("/api/chat", response_model=ChatResponse)
@limiter.limit("20/minute")
def chat_endpoint(request: Request, payload: ChatRequest):
    """
    Recebe pergunta do usuário, extrai entidades, recupera o subgrafo
    e gera a resposta grounded via LLM.
    """
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="A pergunta não pode estar vazia.")

    depth = 2  # Profundidade fixa para o RAG textual
    graph_depth = payload.depth if payload.depth else 1
    max_nodes = payload.max_nodes if payload.max_nodes else 25

    try:
        # 1. Extração multi-entidade
        entities = get_entities_from_question(question)
        q_lower = question.lower()

        # Detecção de perguntas focadas em bancada, projetos ou colegas de mesmo partido
        is_party_query = any(w in q_lower for w in ['partid', 'eleito', 'sigla', 'bancada', 'legenda', 'quantos deputados'])
        is_bills_query = any(w in q_lower for w in ['projet', 'propost', 'leis', 'principais pl', 'produção'])
        is_colleagues_query = any(w in q_lower for w in ['mesmo partid', 'mesma legend', 'mesma sigl', 'colegas', 'companheiros', 'outros deputados'])

        if not entities:
            if is_bills_query:
                context = db.get_bancada_bills_context(limit=25)
                subgraph = db.get_bancada_bills_subgraph(max_nodes=max_nodes)
                entities = ["Bancada MG", "Proposições"]
            else:
                context = db.get_bancada_parties_context()
                subgraph = db.get_parties_subgraph(max_nodes=max_nodes)
                entities = ["Bancada MG", "Partidos"]
        else:
            if is_colleagues_query and len(entities) == 1:
                # Foco exclusivo no cluster do partido do parlamentar e seus colegas filiados
                subgraph = db.get_party_colleagues_subgraph(entities[0], max_nodes=max_nodes)
                context = db.get_context_for_entities(entities, depth=2, include_colleagues=True)
            else:
                context = db.get_context_for_entities(entities, depth=depth, include_colleagues=False)
                subgraph = db.get_subgraph_data_for_entities(entities, max_nodes=max_nodes, depth=graph_depth)
        
        # 2. Geração da resposta grounded
        answer = generate_final_answer(context, question)
        
        # 3. Se houver político entre as entidades consultadas, recupera o perfil oficial
        politician_card = None
        for ent in entities:
            pol = db.get_politician_details(ent)
            if pol:
                politician_card = pol
                break

        return ChatResponse(
            question=question,
            entities=entities,
            answer=answer,
            graph=subgraph,
            politician=politician_card
        )
    except Exception as e:
        logger.error(f"Erro ao processar consulta de chat: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Não foi possível processar sua consulta política no momento. Por favor, tente novamente."
        )

@app.get("/api/politician/{name}")
@limiter.limit("60/minute")
def get_politician_endpoint(request: Request, name: str):
    """Retorna dados de dossiê do parlamentar (foto oficial, partido, projetos, etc.)."""
    safe_name = name.strip()
    if not safe_name or len(safe_name) > 120:
        raise HTTPException(status_code=400, detail="Nome de parlamentar inválido.")
    try:
        profile = db.get_politician_details(safe_name)
        if not profile:
            raise HTTPException(status_code=404, detail="Parlamentar não encontrado.")
        return profile
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao carregar perfil do parlamentar {safe_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erro interno ao carregar perfil.")

@app.get("/api/bill/{bill_name:path}")
@limiter.limit("60/minute")
def get_bill_endpoint(request: Request, bill_name: str):
    """Retorna detalhes da proposição com a ementa oficial."""
    safe_bill = bill_name.strip()
    if not safe_bill or len(safe_bill) > 150:
        raise HTTPException(status_code=400, detail="Identificador de proposição inválido.")
    try:
        with db.driver.session() as s:
            res = s.run(
                "MATCH (b:Bill) WHERE toLower(b.name) = toLower($name) "
                "RETURN b.name as name, b.ementa as ementa, b.tipo as tipo, b.numero as numero, b.ano as ano "
                "LIMIT 1",
                name=safe_bill
            ).single()
            if res:
                return dict(res)
        return {"name": safe_bill, "ementa": None}
    except Exception as e:
        logger.error(f"Erro ao consultar proposição {safe_bill}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erro interno ao consultar proposição.")

# Monta o frontend Angular se compilado em modo estático
angular_dist = Path(__file__).parent / "frontend-angular" / "dist" / "frontend-angular" / "browser"
if angular_dist.exists():
    app.mount("/", StaticFiles(directory=str(angular_dist), html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    is_dev = os.getenv("ENVIRONMENT", "development").lower() != "production"
    logger.info(f"Iniciando servidor na porta {port} (modo {'desenvolvimento' if is_dev else 'produção'})...")
    uvicorn.run("api:app", host="0.0.0.0", port=port, reload=is_dev)
