"""
Conexão e ciclo de vida do banco de dados em grafos Neo4j.
Gerencia driver, health check ativo e inicialização de restrições de esquema e índices.
"""

import logging
from typing import Optional
from neo4j import GraphDatabase, Driver
from app.core.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

logger = logging.getLogger("graphpolitics.graph.connection")

class Neo4jConnection:
    """Gerencia o ciclo de vida da conexão do driver Neo4j."""

    def __init__(self, uri: Optional[str] = None, user: Optional[str] = None, password: Optional[str] = None):
        self.uri = uri or NEO4J_URI
        self.user = user or NEO4J_USER
        self.password = password or NEO4J_PASSWORD
        self._driver: Optional[Driver] = None

    @property
    def driver(self) -> Driver:
        """Retorna o driver Neo4j, instanciando-o sob demanda caso necessário."""
        if self._driver is None:
            self._driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
        return self._driver

    def close(self):
        """Fecha a conexão do driver com segurança."""
        if self._driver is not None:
            try:
                self._driver.close()
                logger.info("[Neo4jConnection] Driver encerrado com sucesso.")
            except Exception as e:
                logger.warning(f"[Neo4jConnection] Erro ao encerrar driver Neo4j: {e}")
            finally:
                self._driver = None

    def verify_health(self) -> bool:
        """Executa ping ativo no Neo4j para validação de saúde do serviço."""
        try:
            with self.driver.session() as session:
                res = session.run("RETURN 1 AS ok").single()
                return bool(res and res["ok"] == 1)
        except Exception as e:
            logger.error(f"[Neo4jConnection] Falha no health check do Neo4j: {e}")
            return False

    def init_schema(self):
        """
        Garante restrições de unicidade, labels base e índices de busca fulltext.
        Idempotente: roda em modo IF NOT EXISTS.
        """
        with self.driver.session() as session:
            # 1. Atribui o super-label :Entity a nós existentes para busca unificada
            try:
                session.run("MATCH (n) WHERE NOT n:Entity SET n:Entity")
            except Exception as e:
                logger.warning(f"[Neo4jConnection] Aviso ao aplicar label :Entity: {e}")

            # 2. Constraints de unicidade (Neo4j 5+)
            labels_to_constrain = ["Entity", "Politician", "Party", "Bill", "Institution"]
            for label in labels_to_constrain:
                constraint_name = f"uniq_{label.lower()}_name"
                query = f"""
                CREATE CONSTRAINT {constraint_name} IF NOT EXISTS
                FOR (n:{label}) REQUIRE n.name IS UNIQUE
                """
                try:
                    session.run(query)
                except Exception as e:
                    logger.info(f"[Neo4jConnection] Constraint {label}: {e}")

            # 3. Índice Fulltext para busca aproximada e tolerante a variações de digitação
            try:
                session.run("""
                CREATE FULLTEXT INDEX entity_name_fulltext IF NOT EXISTS
                FOR (n:Politician|Party|Bill|Institution|Entity) ON EACH [n.name]
                """)
            except Exception as e:
                logger.info(f"[Neo4jConnection] Índice fulltext: {e}")
