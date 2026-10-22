"""
Esquemas Pydantic para validação das requisições e respostas da API HTTP.
"""

from typing import List, Optional
from pydantic import BaseModel, Field

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
