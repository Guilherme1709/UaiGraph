"""
Modelos Pydantic para comunicação e extração estruturada de LLMs.
"""

from typing import List
from pydantic import BaseModel, Field

class Triple(BaseModel):
    subject: str = Field(description="Nome da entidade de origem")
    subj_label: str = Field(description="Categoria da origem: Politician, Party, Bill, Institution")
    relation: str = Field(description="Relação padronizada em português em UPPERCASE_SNAKE_CASE (ex: FILIADO_A, PROPOS, VOTOU_A_FAVOR, RELATOR_DE, ALTERA, REGULAMENTA, CRIA)")
    obj: str = Field(description="Nome da entidade de destino")
    obj_label: str = Field(description="Categoria do destino: Politician, Party, Bill, Institution")

class TripleList(BaseModel):
    triples: List[Triple]

class ExtractedEntities(BaseModel):
    entities: List[str] = Field(
        description="Lista de nomes de políticos, siglas ou nomes de partidos, números de projetos de lei ou instituições citados na pergunta."
    )
