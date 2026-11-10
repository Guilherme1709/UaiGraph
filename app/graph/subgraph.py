"""
Geração de subgrafos visuais estruturados para renderização frontend no Vis.js Network.
Otimizado para retorno rápido de nós e arestas com deduplicação e controle de limites.
"""

import logging
from typing import List, Optional, Callable
from neo4j import Driver

logger = logging.getLogger("graphpolitics.graph.subgraph")

class GraphVisualizer:
    """Extrai estruturas de subgrafos {nodes: [...], edges: [...]} prontas para o frontend."""

    def __init__(self, driver: Driver, resolve_fn: Optional[Callable[[str], Optional[str]]] = None):
        self._driver = driver
        self._resolve_fn = resolve_fn or (lambda x: x)

    def get_parties_subgraph(self, max_nodes: int = 40) -> dict:
        """Retorna subgrafo contendo os partidos e deputados para visualização geral da bancada."""
        with self._driver.session() as s:
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
        """
        canonical = self._resolve_fn(politician_or_party)
        target = canonical if canonical else politician_or_party

        with self._driver.session() as s:
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

    def get_bancada_bills_subgraph(self, max_nodes: int = 40) -> dict:
        """Gera subgrafo de proposições e seus autores para visualizações gerais."""
        with self._driver.session() as s:
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
        Retorna nós e arestas estruturados para visualização gráfica interativa (Vis.js Network).
        """
        nodes_dict = {}
        edges_set = set()
        edges_list = []

        safe_depth = max(1, min(int(depth or 1), 3))
        safe_max_nodes = max(5, min(int(max_nodes or 25), 350))

        resolved = []
        for e in entities:
            can = self._resolve_fn(e)
            if can and can not in resolved:
                resolved.append(can)

        if not resolved:
            return {"nodes": [], "edges": []}

        node_limit = int(max(35, min(safe_max_nodes * safe_depth, 400)))

        with self._driver.session() as session:
            # Caminhos e coautorias entre entidades (se houver 2+)
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

            # Relações diretas individuais
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

            missing_bill_ids = [n["id"] for n in nodes_dict.values() if n.get("category") == "Bill" and not n.get("ementa")]
            if missing_bill_ids:
                q_fix = "MATCH (b:Bill) WHERE b.name IN $ids RETURN b.name as name, b.ementa as ementa"
                for row in session.run(q_fix, ids=missing_bill_ids).data():
                    if row.get("ementa") and row["name"] in nodes_dict:
                        nodes_dict[row["name"]]["ementa"] = row["ementa"]

        sorted_nodes = sorted(nodes_dict.values(), key=lambda n: 0 if n.get("category") in ["Politician", "Party"] else 1)
        final_nodes = sorted_nodes[:node_limit]
        allowed_ids = {n["id"] for n in final_nodes}
        final_edges = [e for e in edges_list if e["from"] in allowed_ids and e["to"] in allowed_ids]

        return {
            "nodes": final_nodes,
            "edges": final_edges
        }
