"""
Repositório de persistência e leitura de dados no grafo Neo4j.
Operações CRUD fundamentais sobre parlamentares, partidos, proposições e triplas estruturadas.
"""

import logging
from typing import List, Optional, Callable
from neo4j import Driver
from app.core.normalization import normalize_party_name

logger = logging.getLogger("graphpolitics.graph.repositories")

class GraphRepository:
    """Concentra as consultas e mutações de leitura e escrita simples no Neo4j."""

    def __init__(self, driver: Driver, resolve_fn: Optional[Callable[[str], Optional[str]]] = None):
        self._driver = driver
        self._resolve_fn = resolve_fn or (lambda x: x)

    def save_structured_triple(self, subj: str, subj_label: str, rel: str, obj: str, obj_label: str):
        """
        Salva triplas com tipagem de nós e relações padronizadas.
        Usa o super-label :Entity para garantir que nós com o mesmo nome nunca sejam duplicados.
        """
        subj = subj.strip()
        obj = obj.strip()
        if not subj or not obj:
            return

        if subj_label == "Party":
            subj = normalize_party_name(subj)
        if obj_label == "Party":
            obj = normalize_party_name(obj)

        clean_subj_label = "".join(c for c in subj_label if c.isalnum() or c == "_") or "Entity"
        clean_obj_label = "".join(c for c in obj_label if c.isalnum() or c == "_") or "Entity"
        rel_type = rel.upper().replace(" ", "_").replace("-", "_")
        rel_type = "".join(c for c in rel_type if c.isalnum() or c == "_") or "RELACIONADO_A"

        query = f"""
        MERGE (s:Entity {{name: $subj}})
        ON CREATE SET s:{clean_subj_label}
        ON MATCH SET s:{clean_subj_label}
        MERGE (o:Entity {{name: $obj}})
        ON CREATE SET o:{clean_obj_label}
        ON MATCH SET o:{clean_obj_label}
        MERGE (s)-[:{rel_type}]->(o)
        """
        with self._driver.session() as session:
            session.run(query, subj=subj, obj=obj)

    def save_politician_profile(self, name: str, party: str, photo_url: Optional[str] = None, 
                                email: Optional[str] = None, camara_id: Optional[int] = None, 
                                uf: str = "MG", gabinete: Optional[str] = None, bio: Optional[str] = None):
        """
        Salva ou atualiza os metadados do parlamentar (foto oficial, gabinete, e-mail, etc.).
        """
        clean_party = normalize_party_name(party)

        query = """
        MERGE (p:Entity {name: $name})
        ON CREATE SET p:Politician
        ON MATCH SET p:Politician
        SET p.photo_url = COALESCE($photo_url, p.photo_url),
            p.email = COALESCE($email, p.email),
            p.camara_id = COALESCE($camara_id, p.camara_id),
            p.uf = $uf,
            p.gabinete = COALESCE($gabinete, p.gabinete),
            p.bio = COALESCE($bio, p.bio)
        WITH p
        MERGE (pty:Entity {name: $party})
        ON CREATE SET pty:Party
        ON MATCH SET pty:Party
        MERGE (p)-[:FILIADO_A]->(pty)
        """
        with self._driver.session() as session:
            session.run(
                query,
                name=name.strip(),
                party=clean_party,
                photo_url=photo_url,
                email=email,
                camara_id=camara_id,
                uf=uf,
                gabinete=gabinete,
                bio=bio
            )

    def get_politician_details(self, name: str) -> Optional[dict]:
        """
        Retorna o perfil completo do parlamentar, incluindo foto, partido, projetos recentes e métricas.
        """
        resolved = self._resolve_fn(name)
        target = resolved if resolved else name

        with self._driver.session() as session:
            query = """
            MATCH (p:Politician)
            WHERE toLower(p.name) = toLower($name)
            OPTIONAL MATCH (p)-[:FILIADO_A|MEMBER_OF]->(pty:Party)
            OPTIONAL MATCH (p)-[:PROPOS|PROPOSED]->(b:Bill)
            WITH p, pty, count(DISTINCT b) as total_bills, collect(DISTINCT b.name)[..15] as sample_bills
            OPTIONAL MATCH (p)-[r]-(connected:Entity)
            WITH p, pty, total_bills, sample_bills, count(r) as total_connections
            RETURN p.name as name,
                   p.photo_url as photo_url,
                   p.email as email,
                   p.camara_id as camara_id,
                   p.uf as uf,
                   p.gabinete as gabinete,
                   p.bio as bio,
                   pty.name as party,
                   total_bills,
                   sample_bills,
                   total_connections
            LIMIT 1
            """
            res = session.run(query, name=target).single()
            if res:
                data = dict(res)
                conns = data.get("total_connections") or 0
                data["centrality_score"] = round(min(0.99, max(0.12, conns / 14.0)), 2)
                return data
            return None

    def get_bill_details(self, bill_name: str) -> Optional[dict]:
        """Retorna detalhes da proposição com a ementa oficial cadastrada."""
        safe_bill = bill_name.strip()
        if not safe_bill:
            return None
        with self._driver.session() as s:
            res = s.run(
                "MATCH (b:Bill) WHERE toLower(b.name) = toLower($name) "
                "RETURN b.name as name, b.ementa as ementa, b.tipo as tipo, b.numero as numero, b.ano as ano "
                "LIMIT 1",
                name=safe_bill
            ).single()
            if res:
                return dict(res)
        return None

    def get_graph_stats(self) -> dict:
        """Retorna contagens e métricas gerais do grafo para os cards do dashboard."""
        with self._driver.session() as s:
            n_count = s.run('MATCH (n) RETURN count(n) as c').single()['c']
            r_count = s.run('MATCH ()-[r]->() RETURN count(r) as c').single()['c']
            pol_count = s.run('MATCH (p:Politician) RETURN count(p) as c').single()['c']
            pty_count = s.run('MATCH (p:Party) RETURN count(p) as c').single()['c']
            bill_count = s.run('MATCH (b:Bill) RETURN count(b) as c').single()['c']
            return {
                "nodes": n_count,
                "relationships": r_count,
                "politicians": pol_count,
                "parties": pty_count,
                "bills": bill_count,
            }

    def get_popular_politicians(self, limit: int = 8) -> List[dict]:
        """Retorna parlamentares em destaque com base no volume de proposições cadastradas."""
        with self._driver.session() as s:
            query = """
            MATCH (p:Politician)-[:FILIADO_A|MEMBER_OF]->(pty:Party)
            OPTIONAL MATCH (p)-[:PROPOS|PROPOSED]->(b:Bill)
            WITH p, pty, count(b) as bills_count
            RETURN p.name as name, pty.name as party, bills_count
            ORDER BY bills_count DESC, p.name ASC
            LIMIT $limit
            """
            return s.run(query, limit=limit).data()

    def get_all_politicians(self) -> List[dict]:
        """Retorna lista completa dos parlamentares mineiros para gaveta de dossiês."""
        with self._driver.session() as s:
            query = """
            MATCH (p:Politician)
            OPTIONAL MATCH (p)-[:FILIADO_A|MEMBER_OF]->(pty:Party)
            RETURN p.name as name,
                   coalesce(pty.name, 'S.PART.') as party,
                   p.photo_url as photo_url,
                   p.camara_id as camara_id,
                   p.email as email,
                   COUNT { (p)-[:PROPOS|PROPOSED]->(:Bill) } as total_bills,
                   COUNT { (p)--(:Entity) } as total_connections
            ORDER BY p.name ASC
            """
            return s.run(query).data()
