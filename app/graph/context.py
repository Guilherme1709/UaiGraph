"""
Geração de contexto textual estruturado a partir do grafo para o LLM (RAG).
Inclui descoberta de caminhos mais curtos, coautorias, relações diretas e de 2º salto.
"""

import logging
from typing import List, Optional, Callable
from neo4j import Driver

logger = logging.getLogger("graphpolitics.graph.context")

class GraphContextProvider:
    """Gera prompts de contexto semântico fundamentado para o LLM."""

    def __init__(
        self,
        driver: Driver,
        resolve_fn: Optional[Callable[[str], Optional[str]]] = None,
        get_profile_fn: Optional[Callable[[str], Optional[dict]]] = None
    ):
        self._driver = driver
        self._resolve_fn = resolve_fn or (lambda x: x)
        self._get_profile_fn = get_profile_fn or (lambda x: None)

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
        with self._driver.session() as session:
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
        with self._driver.session() as session:
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
        with self._driver.session() as session:
            res = session.run(query, name=entity_name, limit=limit)
            return [f"(via) {r['rel']}" for r in res]

    def get_context_for_entities(self, entities: List[str], depth: int = 2, include_colleagues: bool = False) -> str:
        """
        Gera contexto textual para o RAG:
        - Para 2+ entidades: descobre caminhos, coautorias e alianças mútuas.
        - Para 1 entidade: relações diretas e opcionalmente segundo salto (colegas de partido/coautores).
        """
        if not entities:
            return "Nenhuma entidade identificada na pergunta."

        resolved_entities = []
        for e in entities:
            canonical = self._resolve_fn(e)
            if canonical and canonical not in resolved_entities:
                resolved_entities.append(canonical)

        if not resolved_entities:
            return f"As entidades {entities} não foram encontradas no grafo de dados."

        context_sections = []

        if len(resolved_entities) >= 2:
            paths_found = []
            coauthorship_found = []

            with self._driver.session() as session:
                for i in range(len(resolved_entities)):
                    for j in range(i + 1, len(resolved_entities)):
                        e1 = resolved_entities[i]
                        e2 = resolved_entities[j]

                        paths = self.find_paths_between(e1, e2, max_depth=4)
                        if paths:
                            paths_found.extend(paths)

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
                                coauthorship_found.append(
                                    f"- {c['dep1']} ({e1}) e {c['dep2']} ({e2}) são coautores da matéria {c['bill']}: {c['ementa']}"
                                )

            if coauthorship_found:
                context_sections.append("=== PROJETOS DE LEI EM COAUTORIA / PARCERIAS LEGISLATIVAS ENCONTRADAS ===")
                context_sections.extend(coauthorship_found)

            if paths_found:
                context_sections.append("\n=== CONEXÕES E CAMINHOS NO GRAFO ENTRE AS ENTIDADES ===")
                context_sections.extend(paths_found)
            elif not coauthorship_found:
                context_sections.append("=== DADOS E RELAÇÕES INDIVIDUAIS DE CADA ENTIDADE ===")

        for ent in resolved_entities:
            context_sections.append(f"\n=== RELAÇÕES DE: {ent} ===")
            profile = self._get_profile_fn(ent)
            if profile:
                context_sections.append(
                    f"[MÉTRICAS OFICIAIS] Total de proposições no banco: {profile.get('total_bills', 0)} | Total de conexões: {profile.get('total_connections', 0)}"
                )

            direct_relations = self._get_direct_relations(ent, limit=25)
            if direct_relations:
                context_sections.extend(direct_relations)
            else:
                context_sections.append("Sem relações diretas adicionais registradas.")

            if len(resolved_entities) == 1 and depth > 1 and include_colleagues:
                second_hop = self._get_second_hop_relations(ent, limit=20)
                if second_hop:
                    context_sections.append("\n=== CONTEXTO EXPANDIDO (2º SALTO - COLEGAS DE PARTIDO E COAUTORES) ===")
                    context_sections.extend(second_hop)

        return "\n".join(context_sections)

    def get_bancada_parties_context(self) -> str:
        """Gera contexto estruturado sobre a composição partidária de toda a bancada de MG."""
        with self._driver.session() as s:
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

    def get_bancada_bills_context(self, limit: int = 25) -> str:
        """Gera contexto com as principais proposições da bancada de MG."""
        with self._driver.session() as s:
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

    def get_context_multi_hop(self, entity_name: str, depth: int = 2) -> str:
        """Compatibilidade retroativa com código legado."""
        return self.get_context_for_entities([entity_name], depth=depth)
