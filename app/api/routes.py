"""
Definição dos endpoints REST da API UaiGraph / GraphPoliticsRAG.
Isola a camada HTTP e delega as regras de negócio aos serviços e repositórios.
"""

import time
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Request

from app.api.schemas import ChatRequest, ChatResponse, GraphRequest
from app.api.limiter import limiter
from app.graph import Neo4jManager
from app.services.chat_service import ChatService

logger = logging.getLogger("graphpolitics.api.routes")

router = APIRouter()

# Instâncias padrão de banco e serviço de chat
db = Neo4jManager()
chat_service = ChatService(db=db)

# Cache em memória (TTL) da lista de deputados
_POLITICIANS_TTL = 600.0  # segundos
_politicians_cache = {"data": None, "ts": 0.0}

@router.get("/", tags=["Root"])
def root():
    """Endpoint raiz com informações de status e documentação da API."""
    return {
        "service": "UaiGraph - Political Graph RAG API",
        "status": "online",
        "docs": "/docs",
        "health": "/health"
    }

@router.get("/health", tags=["Health"])
@router.get("/api/health", tags=["Health"])
def health_check():
    """Health check ativo que valida a conectividade com o banco de grafos Neo4j."""
    is_db_healthy = db.verify_health()
    if not is_db_healthy:
        raise HTTPException(
            status_code=503,
            detail={"status": "degraded", "database": "unavailable", "service": "GraphPoliticsRAG"}
        )
    return {"status": "online", "database": "connected", "service": "GraphPoliticsRAG"}

@router.get("/api/stats", tags=["Stats"])
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

@router.get("/api/politicians", tags=["Politicians"])
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

@router.post("/api/graph", tags=["Graph"])
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

@router.get("/api/suggestions", tags=["Suggestions"])
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

@router.post("/api/chat", response_model=ChatResponse, tags=["Chat"])
@limiter.limit("20/minute")
def chat_endpoint(request: Request, payload: ChatRequest):
    """
    Recebe pergunta do usuário, orquestra extração semântica e busca no grafo,
    gerando a resposta final grounded via LLM através do ChatService.
    """
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="A pergunta não pode estar vazia.")

    try:
        result = chat_service.process_chat_query(
            question=question,
            depth=payload.depth or 1,
            max_nodes=payload.max_nodes or 25
        )
        return ChatResponse(**result)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Erro ao processar consulta de chat: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Não foi possível processar sua consulta política no momento. Por favor, tente novamente."
        )

@router.get("/api/politician/{name}", tags=["Politicians"])
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

@router.get("/api/bill/{bill_name:path}", tags=["Bills"])
@limiter.limit("60/minute")
def get_bill_endpoint(request: Request, bill_name: str):
    """Retorna detalhes da proposição com a ementa oficial."""
    safe_bill = bill_name.strip()
    if not safe_bill or len(safe_bill) > 150:
        raise HTTPException(status_code=400, detail="Identificador de proposição inválido.")
    try:
        details = db.get_bill_details(safe_bill)
        if details:
            return details
        return {"name": safe_bill, "ementa": None}
    except Exception as e:
        logger.error(f"Erro ao consultar proposição {safe_bill}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erro interno ao consultar proposição.")
