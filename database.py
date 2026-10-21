import os
import re
import time
import logging
import unicodedata
from typing import List, Optional
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("graphpolitics.database")

def normalize_party_name(party_name: str) -> str:
    """Normaliza nomes e siglas partidárias para formato canônico, eliminando duplicações como PT/MG, PODE-MG, etc."""
    if not party_name:
        return "S.PART."
    p = party_name.strip()
    p = re.sub(r'[-/_ ]+(mg|minas gerais|minas)$', '', p, flags=re.IGNORECASE).strip()
    p = re.sub(r'\(mg\)$', '', p, flags=re.IGNORECASE).strip()
    
    PARTY_CANONICAL_MAP = {
        "REPUBLICANOS": "REPUBLICANOS",
        "REPUBLICANO": "REPUBLICANOS",
        "UNIAO": "UNIÃO",
        "UNIÃO": "UNIÃO",
        "UNIAO BRASIL": "UNIÃO",
        "UNIÃO BRASIL": "UNIÃO",
        "PODEMOS": "PODE",
        "PODE": "PODE",
        "SOLIDARIEDADE": "SOLIDARIEDADE",
        "CIDADANIA": "CIDADANIA",
        "PATRIOTA": "PRD",
        "PTB": "PRD",
        "AVANTE": "AVANTE",
        "NOVO": "NOVO",
        "PARTIDO NOVO": "NOVO",
        "PSOL": "PSOL",
        "PARTIDO SOCIALISMO E LIBERDADE": "PSOL",
        "PCDB": "PCdoB",
        "PCDOB": "PCdoB",
        "PARTIDO COMUNISTA DO BRASIL": "PCdoB",
        "PSDB": "PSDB",
        "PARTIDO DA SOCIAL DEMOCRACIA BRASILEIRA": "PSDB",
        "MDB": "MDB",
        "MOVIMENTO DEMOCRATICO BRASILEIRO": "MDB",
        "PDT": "PDT",
        "PARTIDO DEMOCRATICO TRABALHISTA": "PDT",
        "PL": "PL",
        "PARTIDO LIBERAL": "PL",
        "PP": "PP",
        "PROGRESSISTAS": "PP",
        "PARTIDO PROGRESSISTA": "PP",
        "PRD": "PRD",
        "PSD": "PSD",
        "PARTIDO SOCIAL DEMOCRATICO": "PSD",
        "PT": "PT",
        "PARTIDO DOS TRABALHADORES": "PT",
        "PV": "PV",
        "PARTIDO VERDE": "PV",
        "REDE": "REDE",
        "REDE SUSTENTABILIDADE": "REDE",
    }
    
    def strip_accents(text: str) -> str:
        return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn").upper()
    
    clean_key = strip_accents(p.upper())
    if clean_key in PARTY_CANONICAL_MAP:
        return PARTY_CANONICAL_MAP[clean_key]
        
    return p.upper()

class Neo4jManager:
    def __init__(self):
        uri = os.getenv("NEO4J_URI", "")
        user = os.getenv("NEO4J_USER", "")
        password = os.getenv("NEO4J_PASSWORD", "")
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        
        # Caches em memória com proteção de tamanho e TTL
        self._resolve_cache: dict = {}
        self._entity_names_cache: Optional[List[str]] = None
        self._entity_names_cache_ts: float = 0.0
        self._ENTITY_NAMES_TTL = 3600.0  # 1 hora

    def close(self):
        try:
            self.driver.close()
        except Exception as e:
            logger.warning(f"Erro ao encerrar driver Neo4j: {e}")

    def verify_health(self) -> bool:
        """Verifica ativamente a integridade e conectividade com o cluster Neo4j."""
        try:
            with self.driver.session() as session:
                res = session.run("RETURN 1 AS ok").single()
                return bool(res and res["ok"] == 1)
        except Exception as e:
            logger.error(f"[Database] Falha no health check do Neo4j: {e}")
            return False

    def init_schema(self):
        """
        Inicializa restrições de unicidade, labels base e índices de busca textual.
        Garante integridade e alta performance em buscas de entidades.
        """
        with self.driver.session() as session:
            # 1. Atribui o super-label :Entity a nós existentes para busca unificada
            session.run("MATCH (n) WHERE NOT n:Entity SET n:Entity")

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
                    logger.info(f"[Schema] Constraint {label}: {e}")

            # 3. Índice Fulltext para busca aproximada e tolerante a variações de digitação
            try:
                session.run("""
                CREATE FULLTEXT INDEX entity_name_fulltext IF NOT EXISTS
                FOR (n:Politician|Party|Bill|Institution|Entity) ON EACH [n.name]
                """)
            except Exception as e:
                logger.info(f"[Schema] Índice fulltext: {e}")

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

        # Sanitiza labels e relações
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
        with self.driver.session() as session:
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
        with self.driver.session() as session:
            session.run(query, name=name.strip(), party=clean_party, photo_url=photo_url,
                        email=email, camara_id=camara_id, uf=uf, gabinete=gabinete, bio=bio)

    def get_politician_details(self, name: str) -> Optional[dict]:
        """
        Retorna o perfil completo do parlamentar, incluindo foto, partido, projetos recentes e métricas.
        """
        resolved = self.resolve_entity(name)
        target = resolved if resolved else name

        with self.driver.session() as session:
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
                # Score dinâmico de centralidade baseado no grau de conexões reais no grafo
                conns = data.get("total_connections") or 0
                data["centrality_score"] = round(min(0.99, max(0.12, conns / 14.0)), 2)
                return data
            return None

    def resolve_entity(self, entity_query: str) -> Optional[str]:
        """
        Versão com cache seguro de _resolve_entity_uncached. Apenas resoluções bem-sucedidas são guardadas.
        """
        key = (entity_query or "").strip().lower()
        if not key:
            return None
        if key in self._resolve_cache:
            return self._resolve_cache[key]
        result = self._resolve_entity_uncached(entity_query)
        if result:
            # Protege contra vazamento de memória em execuções prolongadas
            if len(self._resolve_cache) >= 2000:
                self._resolve_cache.clear()
            self._resolve_cache[key] = result
        return result

    def _get_all_entity_names(self) -> List[str]:
        """Lista de nomes de entidades carregada com TTL para suportar atualizações no banco."""
        now = time.time()
        if self._entity_names_cache is None or (now - self._entity_names_cache_ts > self._ENTITY_NAMES_TTL):
            with self.driver.session() as session:
                self._entity_names_cache = [r["name"] for r in session.run("MATCH (e:Entity) RETURN e.name AS name").data()]
                self._entity_names_cache_ts = now
        return self._entity_names_cache

    def _resolve_entity_uncached(self, entity_query: str) -> Optional[str]:
        """
        Resolve uma menção (ex: 'Nikolas', 'PL', 'Aecio', 'Celia Xakriaba') para o nome canônico do nó no grafo.
        Suporta match sem acento, Lucene fulltext e busca por sobreposição de termos com limiares anti-falso-positivo.
        """
        entity_query = entity_query.strip()
        if not entity_query:
            return None

        def remove_accents(text: str) -> str:
            return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn").lower()

        norm_query = remove_accents(entity_query)

        # 0. Verificação imediata se a menção se refere a um partido (sigla ou nome por extenso)
        clean_party = normalize_party_name(entity_query)
        KNOWN_PARTIES = {
            "REPUBLICANOS", "UNIÃO", "PODE", "SOLIDARIEDADE", "CIDADANIA", "PRD", "AVANTE", "NOVO",
            "PSOL", "PCdoB", "PSDB", "MDB", "PDT", "PL", "PP", "PSD", "PT", "PV", "REDE"
        }

        with self.driver.session() as session:
            if clean_party in KNOWN_PARTIES:
                party_match = session.run(
                    "MATCH (p:Party) WHERE toLower(p.name) = toLower($pty) RETURN p.name AS name LIMIT 1",
                    pty=clean_party
                ).single()
                if party_match:
                    return party_match["name"]

            # 1. Match exato no banco (case-insensitive)
            q_exact = """
            MATCH (e:Entity)
            WHERE toLower(e.name) = toLower($name)
            RETURN e.name AS name
            LIMIT 1
            """
            res = session.run(q_exact, name=entity_query).single()
            if res:
                return res["name"]

            # 2. Busca Fulltext (Lucene)
            try:
                words = re.findall(r'\w+', entity_query)
                if words:
                    lucene_query = " AND ".join([f"{w}~" if len(w) > 3 else w for w in words])
                    q_fulltext = """
                    CALL db.index.fulltext.queryNodes("entity_name_fulltext", $search_str)
                    YIELD node, score
                    RETURN node.name AS name, score
                    ORDER BY score DESC
                    LIMIT 1
                    """
                    ft_res = session.run(q_fulltext, search_str=lucene_query).single()
                    if ft_res and ft_res.get("score", 0) > 1.0:
                        return ft_res["name"]
            except Exception:
                pass

            # 3. Match sem acentos em nós de Politician e Entity
            all_entities = self._get_all_entity_names()
            
            # Match exato sem acentos
            for ent in all_entities:
                if remove_accents(ent) == norm_query:
                    return ent

            # Match por palavra inteira ou substring qualificada (evita falsos positivos em nomes curtos)
            substring_candidates = []
            for ent in all_entities:
                norm_ent = remove_accents(ent)
                if len(norm_query) < 4:
                    # Nomes curtos precisam coincidir como token isolado (ex: "PL", "PT", "BETO")
                    if re.search(r'\b' + re.escape(norm_query) + r'\b', norm_ent):
                        substring_candidates.append(ent)
                else:
                    if norm_query in norm_ent or norm_ent in norm_query:
                        substring_candidates.append(ent)

            if substring_candidates:
                substring_candidates.sort(key=lambda x: abs(len(remove_accents(x)) - len(norm_query)))
                return substring_candidates[0]

            # Match por sobreposição de termos (mínimo de 2 palavras coincidentes ou razão expressiva)
            query_words = set(re.findall(r'\b\w{3,}\b', norm_query))
            if query_words:
                best_match = None
                best_overlap = 0
                for ent in all_entities:
                    ent_words = set(re.findall(r'\b\w{3,}\b', remove_accents(ent)))
                    overlap = len(query_words.intersection(ent_words))
                    if overlap > best_overlap:
                        best_overlap = overlap
                        best_match = ent

                # Só aceita se houver pelo menos 2 termos coincidentes ou se cobrir toda a busca
                if best_match and (best_overlap >= 2 or (len(query_words) == 1 and best_overlap == 1)):
                    return best_match

        return None

    def find_paths_between(self, entity_a: str, entity_b: str, max_depth: int = 3) -> List[str]:
        """
        Encontra caminhos mais curtos conectando duas entidades no grafo com limite seguro de saltos.
        """
        safe_depth = max(1, min(int(max_depth), 4))
        query = f"""
        MATCH (a:Entity {{name: $name_a}}), (b:Entity {{name: $name_b}})
        MATCH p = allShortestPaths((a)-[*..{safe_depth}]-(b))
        RETURN [n in nodes(p) | n.name] AS node_names,
               [r in relationships(p) | {{type: type(r), from: startNode(r).name, to: endNode(r).name}}] AS rels
        LIMIT 5
        """
        paths = []
        with self.driver.session() as session:
            results = session.run(query, name_a=entity_a, name_b=entity_b).data()
            for record in results:
                node_names = record["node_names"]
                rels = record["rels"]
                path_steps = []
                for i, r in enumerate(rels):
                    from_node = node_names[i]
                    to_node = node_names[i + 1]
                    if r["from"] == from_node and r["to"] == to_node:
                        path_steps.append(f"{from_node} -[{r['type']}]-> {to_node}")
                    else:
                        path_steps.append(f"{from_node} <-[{r['type']}]- {to_node}")
                paths.append(" -> ".join(path_steps))
        return paths

    def get_context_for_entities(self, entities: List[str], depth: int = 2, include_colleagues: bool = False) -> str:
        """
        Gera contexto estruturado para RAG suportando uma ou múltiplas entidades.
        - Se 2+ entidades: descobre conexões/caminhos entre elas + relações de cada uma.
        - Se 1 entidade: recupera relações diretas (e opcionalmente 2º salto se include_colleagues=True).
        """
        if not entities:
            return "Nenhuma entidade identificada na pergunta."

        # 1. Resolve os nomes para entidades canônicas do grafo
        resolved_entities = []
        for e in entities:
            canonical = self.resolve_entity(e)
            if canonical and canonical not in resolved_entities:
                resolved_entities.append(canonical)

        if not resolved_entities:
            return f"As entidades {entities} não foram encontradas no grafo de dados."

        context_sections = []

        # 2. Se houver 2 ou mais entidades, busca conexões diretas, indiretas e coautorias entre elas
        if len(resolved_entities) >= 2:
            paths_found = []
            coauthorship_found = []

            with self.driver.session() as session:
                for i in range(len(resolved_entities)):
                    for j in range(i + 1, len(resolved_entities)):
                        e1 = resolved_entities[i]
                        e2 = resolved_entities[j]

                        # A) Busca caminhos mais curtos (até 4 saltos: ex: Partido -> Deputado -> Projeto -> Deputado -> Partido)
                        paths = self.find_paths_between(e1, e2, max_depth=4)
                        if paths:
                            paths_found.extend(paths)

                        # B) Busca direta de coautorias em matérias legislativas (apenas se não for relação direta de filiação entre elas)
                        is_direct_aff = session.run("""
                            MATCH (p:Politician)-[:FILIADO_A|MEMBER_OF]->(pty:Party)
                            WHERE (p.name = $e1 AND pty.name = $e2) OR (p.name = $e2 AND pty.name = $e1)
                            RETURN count(*) as c
                        """, e1=e1, e2=e2).single()["c"] > 0

                        if not is_direct_aff:
                            q_coauth = """
                            MATCH (e1:Entity {name: $e1})<-[:FILIADO_A|MEMBER_OF*0..1]-(p1:Politician)-[:PROPOS|PROPOSED]->(b:Bill)<-[:PROPOS|PROPOSED]-(p2:Politician)-[:FILIADO_A|MEMBER_OF*0..1]->(e2:Entity {name: $e2})
                            WHERE p1 <> p2
                            RETURN DISTINCT p1.name as dep1, p2.name as dep2, b.name as bill, substring(coalesce(b.ementa, 'Sem ementa'), 0, 160) as ementa
                            LIMIT 15
                            """
                            res_coauth = session.run(q_coauth, e1=e1, e2=e2).data()
                            for c in res_coauth:
                                coauthorship_found.append(f"- {c['dep1']} ({e1}) e {c['dep2']} ({e2}) são coautores da matéria {c['bill']}: {c['ementa']}")

            if coauthorship_found:
                context_sections.append("=== PROJETOS DE LEI EM COAUTORIA / PARCERIAS LEGISLATIVAS ENCONTRADAS ===")
                context_sections.extend(coauthorship_found)

            if paths_found:
                context_sections.append("\n=== CONEXÕES E CAMINHOS NO GRAFO ENTRE AS ENTIDADES ===")
                context_sections.extend(paths_found)
            elif not coauthorship_found:
                context_sections.append("=== DADOS E RELAÇÕES INDIVIDUAIS DE CADA ENTIDADE ===")

        # 3. Contexto individual para cada entidade resolvida
        for ent in resolved_entities:
            context_sections.append(f"\n=== RELAÇÕES DE: {ent} ===")
            
            # Adiciona métricas oficiais totais para que o LLM não deduza totais baseados no limite do contexto
            profile = self.get_politician_details(ent)
            if profile:
                context_sections.append(f"[MÉTRICAS OFICIAIS] Total de proposições no banco: {profile.get('total_bills', 0)} | Total de conexões: {profile.get('total_connections', 0)}")

            direct_relations = self._get_direct_relations(ent, limit=25)
            if direct_relations:
                context_sections.extend(direct_relations)
            else:
                context_sections.append("Sem relações diretas adicionais registradas.")

            # Multi-hop secundário: incluído APENAS se explicitamente solicitado (ex: perguntas sobre colegas ou alianças)
            if len(resolved_entities) == 1 and depth > 1 and include_colleagues:
                second_hop = self._get_second_hop_relations(ent, limit=20)
                if second_hop:
                    context_sections.append("\n=== CONTEXTO EXPANDIDO (2º SALTO - COLEGAS DE PARTIDO E COAUTORES) ===")
                    context_sections.extend(second_hop)

        return "\n".join(context_sections)

    def _get_direct_relations(self, entity_name: str, limit: int = 25) -> List[str]:
        query = """
        CALL () {
            MATCH (source:Entity {name: $name})-[r]->(target)
            RETURN (CASE WHEN source:Politician THEN source.name + ' (Deputado Federal - ' + coalesce(source.uf, 'MG') + ')' ELSE source.name END)
                   + ' -[' + type(r) + ']-> ' +
                   (CASE 
                       WHEN target:Politician THEN target.name + ' (Deputado Federal - ' + coalesce(target.uf, 'MG') + ')'
                       WHEN target:Bill AND target.ementa IS NOT NULL THEN target.name + ' (Ementa: ' + substring(target.ementa, 0, 160) + ')'
                       ELSE target.name 
                   END) AS rel
            UNION
            MATCH (target)-[r]->(source:Entity {name: $name})
            RETURN (CASE 
                       WHEN target:Politician THEN target.name + ' (Deputado Federal - ' + coalesce(target.uf, 'MG') + ')' 
                       WHEN target:Bill AND target.ementa IS NOT NULL THEN target.name + ' (Ementa: ' + substring(target.ementa, 0, 160) + ')'
                       ELSE target.name 
                   END)
                   + ' -[' + type(r) + ']-> ' +
                   (CASE WHEN source:Politician THEN source.name + ' (Deputado Federal - ' + coalesce(source.uf, 'MG') + ')' ELSE source.name END) AS rel
        }
        RETURN rel
        LIMIT $limit
        """
        with self.driver.session() as session:
            res = session.run(query, name=entity_name, limit=limit)
            return [r["rel"] for r in res]

    def _get_second_hop_relations(self, entity_name: str, limit: int = 20) -> List[str]:
        query = """
        MATCH (source:Entity {name: $name})-[r1]-(mid)-[r2]-(target:Entity)
        WHERE target <> source AND NOT (source)--(target)
        RETURN DISTINCT 
            (CASE 
                WHEN mid:Party THEN source.name + ' e ' + target.name + ' são filiados ao mesmo partido (' + mid.name + ')'
                WHEN mid:Bill THEN source.name + ' e ' + target.name + ' são coautores da matéria ' + mid.name
                ELSE mid.name + ' -[' + type(r2) + ']-> ' + target.name
            END) AS rel
        LIMIT $limit
        """
        with self.driver.session() as session:
            res = session.run(query, name=entity_name, limit=limit)
            return [f"(via) {r['rel']}" for r in res]

    def get_graph_stats(self) -> dict:
        """Retorna contagens e métricas gerais do grafo para o painel."""
        with self.driver.session() as s:
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
        """Retorna uma lista de deputados cadastrados para sugestões rápidas."""
        with self.driver.session() as s:
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
        """Retorna todos os deputados de MG com partido, foto e métricas para a gaveta de Dossiês."""
        with self.driver.session() as s:
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

    def get_bancada_parties_context(self) -> str:
        """Gera contexto estruturado sobre a composição partidária de toda a bancada de MG."""
        with self.driver.session() as s:
            query = """
            MATCH (p:Politician)-[:FILIADO_A|MEMBER_OF]->(pty:Party)
            RETURN pty.name as party, count(p) as total, collect(p.name) as deputies
            ORDER BY total DESC, pty.name ASC
            """
            rows = s.run(query).data()
            total_deputies = sum(r["total"] for r in rows)
            lines = [
                "=== COMPOSIÇÃO PARTIDÁRIA DA BANCADA DE MINAS GERAIS (57ª LEGISLATURA) ===",
                f"Total de deputados federais cadastrados: {total_deputies} parlamentares.",
                f"Total de legendas partidárias com representação: {len(rows)} partidos.\n",
                "Divisão oficial por partido (ordenada por número de deputados):"
            ]
            for r in rows:
                dep_list = ", ".join(r["deputies"])
                lines.append(f"- {r['party']} ({r['total']} deputados): {dep_list}")
            return "\n".join(lines)

    def get_parties_subgraph(self, max_nodes: int = 40) -> dict:
        """Retorna subgrafo contendo os partidos e deputados para visualização geral da bancada."""
        with self.driver.session() as s:
            query = """
            MATCH (p:Politician)-[r:FILIADO_A|MEMBER_OF]->(pty:Party)
            RETURN p.name as politician, p.photo_url as photo_url, p.camara_id as camara_id,
                   pty.name as party, type(r) as rel
            ORDER BY pty.name ASC, p.name ASC
            LIMIT $limit
            """
            rows = s.run(query, limit=max_nodes).data()
            nodes_dict = {}
            edges_list = []
            for r in rows:
                pol = r["politician"]
                pty = r["party"]
                if pty not in nodes_dict:
                    nodes_dict[pty] = {
                        "id": pty,
                        "label": pty,
                        "category": "Party"
                    }
                if pol not in nodes_dict:
                    nodes_dict[pol] = {
                        "id": pol,
                        "label": pol,
                        "category": "Politician",
                        "photo_url": r.get("photo_url"),
                        "camara_id": r.get("camara_id")
                    }
                edges_list.append({
                    "from": pol,
                    "to": pty,
                    "label": r.get("rel") or "FILIADO_A"
                })
            return {"nodes": list(nodes_dict.values()), "edges": edges_list}

    def get_party_colleagues_subgraph(self, politician_or_party: str, max_nodes: int = 50) -> dict:
        """
        Retorna subgrafo exclusivo contendo apenas o partido e seus parlamentares filiados.
        Ideal para perguntas sobre 'mesmo partido', 'colegas de bancada' ou visualização partidária pura.
        """
        canonical = self.resolve_entity(politician_or_party)
        target = canonical if canonical else politician_or_party

        with self.driver.session() as s:
            # 1. Identifica o partido de destino
            q_party = """
            MATCH (e:Entity {name: $target})
            OPTIONAL MATCH (e:Politician)-[:FILIADO_A|MEMBER_OF]->(pty:Party)
            RETURN CASE 
                       WHEN e:Party THEN e.name 
                       WHEN pty IS NOT NULL THEN pty.name 
                       ELSE null 
                   END AS party_name
            LIMIT 1
            """
            res_party = s.run(q_party, target=target).single()
            party_name = res_party["party_name"] if res_party and res_party["party_name"] else None

            if not party_name:
                return self.get_subgraph_data_for_entities([target], max_nodes=max_nodes, depth=1)

            # 2. Busca exclusivamente todos os parlamentares filiados à legenda
            query = """
            MATCH (p:Politician)-[r:FILIADO_A|MEMBER_OF]->(pty:Party {name: $party_name})
            RETURN p.name as politician, p.photo_url as photo_url, p.camara_id as camara_id,
                   pty.name as party, type(r) as rel
            ORDER BY p.name ASC
            LIMIT $limit
            """
            rows = s.run(query, party_name=party_name, limit=max_nodes).data()
            nodes_dict = {
                party_name: {
                    "id": party_name,
                    "label": party_name,
                    "category": "Party"
                }
            }
            edges_list = []
            for r in rows:
                pol = r["politician"]
                nodes_dict[pol] = {
                    "id": pol,
                    "label": pol,
                    "category": "Politician",
                    "photo_url": r.get("photo_url"),
                    "camara_id": r.get("camara_id")
                }
                edges_list.append({
                    "from": pol,
                    "to": party_name,
                    "label": "FILIADO_A"
                })

            return {"nodes": list(nodes_dict.values()), "edges": edges_list}

    def get_bancada_bills_context(self, limit: int = 25) -> str:
        """Gera contexto com as principais proposições da bancada de MG."""
        with self.driver.session() as s:
            query = """
            MATCH (p:Politician)-[:PROPOS|PROPOSED]->(b:Bill)
            RETURN p.name as author, b.name as bill, coalesce(b.ementa, 'Sem ementa detalhada') as ementa
            ORDER BY b.name DESC
            LIMIT $limit
            """
            rows = s.run(query, limit=limit).data()
            lines = [
                "=== PROPOSIÇÕES LEGISLATIVAS EM DESTAQUE NA BANCADA DE MG ===",
                f"Amostra de {len(rows)} matérias apresentadas por deputados mineiros:\n"
            ]
            for r in rows:
                lines.append(f"- {r['bill']} (Autor: {r['author']}): {r['ementa']}")
            return "\n".join(lines)

    def get_bancada_bills_subgraph(self, max_nodes: int = 40) -> dict:
        """Gera subgrafo de proposições e seus autores para visualizações gerais."""
        with self.driver.session() as s:
            query = """
            MATCH (p:Politician)-[r:PROPOS|PROPOSED]->(b:Bill)
            RETURN p.name as author, p.photo_url as photo_url, p.camara_id as camara_id,
                   b.name as bill, b.ementa as ementa, type(r) as rel
            ORDER BY b.name DESC
            LIMIT $limit
            """
            rows = s.run(query, limit=max_nodes).data()
            nodes_dict = {}
            edges_list = []
            for r in rows:
                aut = r["author"]
                bill = r["bill"]
                if aut not in nodes_dict:
                    nodes_dict[aut] = {
                        "id": aut,
                        "label": aut,
                        "category": "Politician",
                        "photo_url": r.get("photo_url"),
                        "camara_id": r.get("camara_id")
                    }
                if bill not in nodes_dict:
                    nodes_dict[bill] = {
                        "id": bill,
                        "label": bill,
                        "category": "Bill",
                        "ementa": r.get("ementa")
                    }
                edges_list.append({
                    "from": aut,
                    "to": bill,
                    "label": r.get("rel") or "PROPOS"
                })
            return {"nodes": list(nodes_dict.values()), "edges": edges_list}

    def get_subgraph_data_for_entities(self, entities: List[str], max_nodes: int = 40, depth: int = 1) -> dict:
        """
        Retorna nós e arestas estruturados para visualização gráfica interativa (Vis.js Network)
        representando o subgrafo de evidência das entidades consultadas, respeitando a profundidade (depth).
        """
        nodes_dict = {}
        edges_set = set()
        edges_list = []

        # Sanitização rígida de limites (suporta até 350 nós para modo Grafo Completo)
        safe_depth = max(1, min(int(depth or 1), 3))
        safe_max_nodes = max(5, min(int(max_nodes or 25), 350))

        resolved = []
        for e in entities:
            can = self.resolve_entity(e)
            if can and can not in resolved:
                resolved.append(can)

        if not resolved:
            return {"nodes": [], "edges": []}

        node_limit = int(max(35, min(safe_max_nodes * safe_depth, 400)))

        with self.driver.session() as session:
            # 1. Caminhos e coautorias entre entidades (se houver 2+)
            if len(resolved) >= 2:
                for i in range(len(resolved)):
                    for j in range(i + 1, len(resolved)):
                        max_p = 4
                        q_path = f"""
                        MATCH (a:Entity {{name: $a}}), (b:Entity {{name: $b}})
                        MATCH p = allShortestPaths((a)-[*..{max_p}]-(b))
                        UNWIND nodes(p) as n
                        UNWIND relationships(p) as r
                        RETURN DISTINCT n.name as node_name, labels(n) as node_labels, n.photo_url as photo_url, n.ementa as ementa, n.camara_id as camara_id,
                                startNode(r).name as from_node, endNode(r).name as to_node, type(r) as rel_type
                        LIMIT 40
                        """
                        res = session.run(q_path, a=resolved[i], b=resolved[j]).data()
                        for rec in res:
                            name = rec["node_name"]
                            labels = rec["node_labels"]
                            cat = [l for l in labels if l != "Entity"]
                            category = cat[0] if cat else "Entity"
                            node_data = {"id": name, "label": name, "category": category}
                            if rec.get("photo_url"):
                                node_data["photo_url"] = rec["photo_url"]
                            if rec.get("ementa"):
                                node_data["ementa"] = rec["ementa"]
                            if rec.get("camara_id"):
                                node_data["camara_id"] = rec["camara_id"]
                            nodes_dict[name] = node_data

                            edge_key = (rec["from_node"], rec["to_node"], rec["rel_type"])
                            if edge_key not in edges_set:
                                edges_set.add(edge_key)
                                edges_list.append({"from": rec["from_node"], "to": rec["to_node"], "label": rec["rel_type"]})

                        # Coautorias explícitas entre as duas entidades (apenas se não for relação direta de filiação entre elas)
                        is_direct_aff = session.run("""
                            MATCH (p:Politician)-[:FILIADO_A|MEMBER_OF]->(pty:Party)
                            WHERE (p.name = $a AND pty.name = $b) OR (p.name = $b AND pty.name = $a)
                            RETURN count(*) as c
                        """, a=resolved[i], b=resolved[j]).single()["c"] > 0

                        if not is_direct_aff:
                            q_coauth_sub = """
                            MATCH (e1:Entity {name: $a})<-[:FILIADO_A|MEMBER_OF*0..1]-(p1:Politician)-[:PROPOS|PROPOSED]->(b:Bill)<-[:PROPOS|PROPOSED]-(p2:Politician)-[:FILIADO_A|MEMBER_OF*0..1]->(e2:Entity {name: $b})
                            WHERE p1 <> p2
                            OPTIONAL MATCH (p1)-[:FILIADO_A|MEMBER_OF]->(pty1:Party)
                            OPTIONAL MATCH (p2)-[:FILIADO_A|MEMBER_OF]->(pty2:Party)
                            RETURN p1.name as dep1, p1.photo_url as dep1_photo, p1.camara_id as dep1_camara, pty1.name as dep1_party,
                                   p2.name as dep2, p2.photo_url as dep2_photo, p2.camara_id as dep2_camara, pty2.name as dep2_party,
                                   b.name as bill, b.ementa as bill_ementa
                            LIMIT 15
                            """
                            for co in session.run(q_coauth_sub, a=resolved[i], b=resolved[j]).data():
                                nodes_dict[co["dep1"]] = {"id": co["dep1"], "label": co["dep1"], "category": "Politician", "photo_url": co.get("dep1_photo"), "camara_id": co.get("dep1_camara")}
                                nodes_dict[co["dep2"]] = {"id": co["dep2"], "label": co["dep2"], "category": "Politician", "photo_url": co.get("dep2_photo"), "camara_id": co.get("dep2_camara")}
                                nodes_dict[co["bill"]] = {"id": co["bill"], "label": co["bill"], "category": "Bill", "ementa": co.get("bill_ementa")}
                                
                                if co.get("dep1_party"):
                                    nodes_dict[co["dep1_party"]] = {"id": co["dep1_party"], "label": co["dep1_party"], "category": "Party"}
                                    k1 = (co["dep1"], co["dep1_party"], "FILIADO_A")
                                    if k1 not in edges_set:
                                        edges_set.add(k1)
                                        edges_list.append({"from": co["dep1"], "to": co["dep1_party"], "label": "FILIADO_A"})

                                if co.get("dep2_party"):
                                    nodes_dict[co["dep2_party"]] = {"id": co["dep2_party"], "label": co["dep2_party"], "category": "Party"}
                                    k2 = (co["dep2"], co["dep2_party"], "FILIADO_A")
                                    if k2 not in edges_set:
                                        edges_set.add(k2)
                                        edges_list.append({"from": co["dep2"], "to": co["dep2_party"], "label": "FILIADO_A"})

                                for dep in [co["dep1"], co["dep2"]]:
                                    k = (dep, co["bill"], "PROPOS")
                                    if k not in edges_set:
                                        edges_set.add(k)
                                        edges_list.append({"from": dep, "to": co["bill"], "label": "PROPOS"})

            # 2. Relações diretas individuais: apenas para consultas de entidade única OU se não houver caminhos/coautorias encontradas
            if len(resolved) == 1 or not nodes_dict:
                for ent in resolved:
                    dir_limit = int(max(5, min(safe_max_nodes if len(resolved) == 1 else max(15, safe_max_nodes // len(resolved)), 350)))
                    
                    q_direct = f"""
                    MATCH (s:Entity {{name: $name}})-[r]->(t:Entity)
                    RETURN s.name as from_node, labels(s) as s_labels, s.photo_url as s_photo, s.ementa as s_ementa, s.camara_id as s_camara_id,
                           t.name as to_node, labels(t) as t_labels, t.photo_url as t_photo, t.ementa as t_ementa, t.camara_id as t_camara_id,
                           type(r) as rel_type
                    ORDER BY CASE WHEN t:Party THEN 0 WHEN t:Bill THEN 1 ELSE 2 END, t.name DESC
                    LIMIT {dir_limit}
                    """
                    res = session.run(q_direct, name=ent).data()
                    for rec in res:
                        s_cat = [l for l in rec["s_labels"] if l != "Entity"]
                        t_cat = [l for l in rec["t_labels"] if l != "Entity"]
                        s_category = s_cat[0] if s_cat else "Entity"
                        t_category = t_cat[0] if t_cat else "Entity"

                        s_node = {"id": rec["from_node"], "label": rec["from_node"], "category": s_category}
                        if rec.get("s_photo"):
                            s_node["photo_url"] = rec["s_photo"]
                        if rec.get("s_ementa"):
                            s_node["ementa"] = rec["s_ementa"]
                        if rec.get("s_camara_id"):
                            s_node["camara_id"] = rec["s_camara_id"]
                        nodes_dict[rec["from_node"]] = s_node

                        t_node = {"id": rec["to_node"], "label": rec["to_node"], "category": t_category, "relation": rec["rel_type"]}
                        if rec.get("t_photo"):
                            t_node["photo_url"] = rec["t_photo"]
                        if rec.get("t_ementa"):
                            t_node["ementa"] = rec["t_ementa"]
                        if rec.get("t_camara_id"):
                            t_node["camara_id"] = rec["t_camara_id"]
                        nodes_dict[rec["to_node"]] = t_node

                        edge_key = (rec["from_node"], rec["to_node"], rec["rel_type"])
                        if edge_key not in edges_set:
                            edges_set.add(edge_key)
                            edges_list.append({"from": rec["from_node"], "to": rec["to_node"], "label": rec["rel_type"]})

                    # Relações que chegam à entidade (ex: parlamentares filiados ao partido ou relatores de projetos)
                    # Se houver 2+ entidades consultadas (ex: Aécio e PSDB), NÃO traz outros deputados do partido via q_incoming
                    q_incoming = f"""
                    MATCH (s:Entity)-[r]->(t:Entity {{name: $name}})
                    WHERE NOT ($is_multi_entity AND t:Party AND s:Politician)
                    RETURN s.name as from_node, labels(s) as s_labels, s.photo_url as s_photo, s.ementa as s_ementa, s.camara_id as s_camara_id,
                           t.name as to_node, labels(t) as t_labels, t.photo_url as t_photo, t.ementa as t_ementa, t.camara_id as t_camara_id,
                           type(r) as rel_type
                    LIMIT {dir_limit}
                    """
                    res_in = session.run(q_incoming, name=ent, is_multi_entity=(len(resolved) >= 2)).data()
                    for rec in res_in:
                        s_cat = [l for l in rec["s_labels"] if l != "Entity"]
                        t_cat = [l for l in rec["t_labels"] if l != "Entity"]
                        s_category = s_cat[0] if s_cat else "Entity"
                        t_category = t_cat[0] if t_cat else "Entity"

                        s_node = {"id": rec["from_node"], "label": rec["from_node"], "category": s_category, "relation": rec["rel_type"]}
                        if rec.get("s_photo"):
                            s_node["photo_url"] = rec["s_photo"]
                        if rec.get("s_ementa"):
                            s_node["ementa"] = rec["s_ementa"]
                        if rec.get("s_camara_id"):
                            s_node["camara_id"] = rec["s_camara_id"]
                        nodes_dict[rec["from_node"]] = s_node

                        t_node = {"id": rec["to_node"], "label": rec["to_node"], "category": t_category}
                        if rec.get("t_photo"):
                            t_node["photo_url"] = rec["t_photo"]
                        if rec.get("t_ementa"):
                            t_node["ementa"] = rec["t_ementa"]
                        if rec.get("t_camara_id"):
                            t_node["camara_id"] = rec["t_camara_id"]
                        nodes_dict[rec["to_node"]] = t_node

                        edge_key = (rec["from_node"], rec["to_node"], rec["rel_type"])
                        if edge_key not in edges_set:
                            edges_set.add(edge_key)
                            edges_list.append({"from": rec["from_node"], "to": rec["to_node"], "label": rec["rel_type"]})

                    # 3. Se safe_depth > 1, expande relações de 2º salto (sem puxar outros deputados pelo partido)
                    if safe_depth >= 2 and len(resolved) == 1:
                        q_hop2 = f"""
                        MATCH (s:Entity {{name: $name}})-[r1]-(mid:Entity)-[r2]-(t:Entity)
                        WHERE t.name <> $name 
                          AND mid.name <> t.name 
                          AND NOT (mid:Party AND t:Party)
                          AND NOT (mid:Party AND t:Politician)
                        RETURN startNode(r2).name as from_node, labels(startNode(r2)) as mid_labels,
                               startNode(r2).photo_url as mid_photo, startNode(r2).ementa as mid_ementa, startNode(r2).camara_id as mid_camara_id,
                               endNode(r2).name as to_node, labels(endNode(r2)) as t_labels,
                               endNode(r2).photo_url as t_photo, endNode(r2).ementa as t_ementa, endNode(r2).camara_id as t_camara_id,
                               type(r2) as rel_type
                        LIMIT {dir_limit}
                        """
                        res_hop2 = session.run(q_hop2, name=ent).data()
                        for rec in res_hop2:
                            m_cat = [l for l in rec["mid_labels"] if l != "Entity"]
                            t_cat = [l for l in rec["t_labels"] if l != "Entity"]
                            m_category = m_cat[0] if m_cat else "Entity"
                            t_category = t_cat[0] if t_cat else "Entity"

                            m_node = {"id": rec["from_node"], "label": rec["from_node"], "category": m_category}
                            if rec.get("mid_photo"):
                                m_node["photo_url"] = rec["mid_photo"]
                            if rec.get("mid_ementa"):
                                m_node["ementa"] = rec["mid_ementa"]
                            if rec.get("mid_camara_id"):
                                m_node["camara_id"] = rec["mid_camara_id"]
                            nodes_dict[rec["from_node"]] = m_node

                            t_node = {"id": rec["to_node"], "label": rec["to_node"], "category": t_category, "relation": rec["rel_type"]}
                            if rec.get("t_photo"):
                                t_node["photo_url"] = rec["t_photo"]
                            if rec.get("t_ementa"):
                                t_node["ementa"] = rec["t_ementa"]
                            if rec.get("t_camara_id"):
                                t_node["camara_id"] = rec["t_camara_id"]
                            nodes_dict[rec["to_node"]] = t_node

                            edge_key = (rec["from_node"], rec["to_node"], rec["rel_type"])
                            if edge_key not in edges_set:
                                edges_set.add(edge_key)
                                edges_list.append({"from": rec["from_node"], "to": rec["to_node"], "label": rec["rel_type"]})

            # 4. Varredura garantida: se houver qualquer nó do tipo Bill sem ementa no subgrafo, carrega direto do Neo4j
            missing_bill_ids = [n["id"] for n in nodes_dict.values() if n.get("category") == "Bill" and not n.get("ementa")]
            if missing_bill_ids:
                q_fix = "MATCH (b:Bill) WHERE b.name IN $ids RETURN b.name as name, b.ementa as ementa"
                for row in session.run(q_fix, ids=missing_bill_ids).data():
                    if row.get("ementa") and row["name"] in nodes_dict:
                        nodes_dict[row["name"]]["ementa"] = row["ementa"]

        # Prioriza nós de parlamentares e partidos para garantir integridade das conexões de bancada
        sorted_nodes = sorted(nodes_dict.values(), key=lambda n: 0 if n.get("category") in ["Politician", "Party"] else 1)
        final_nodes = sorted_nodes[:node_limit]
        allowed_ids = {n["id"] for n in final_nodes}
        final_edges = [e for e in edges_list if e["from"] in allowed_ids and e["to"] in allowed_ids]

        return {
            "nodes": final_nodes,
            "edges": final_edges
        }

    def get_context_multi_hop(self, entity_name: str, depth: int = 2) -> str:
        """Mantido para compatibilidade retroativa."""
        return self.get_context_for_entities([entity_name], depth=depth)
