import sys
import re
import unicodedata
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from database import Neo4jManager

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

def normalize_party_name(party_name: str) -> str:
    if not party_name:
        return "S.PART."
    
    p = party_name.strip()
    
    # Remove sufixos estaduais como -MG, /MG, _MG, (MG), etc.
    p = re.sub(r'[-/_ ]+(mg|minas gerais|minas)$', '', p, flags=re.IGNORECASE).strip()
    p = re.sub(r'\(mg\)$', '', p, flags=re.IGNORECASE).strip()
    
    # Mapeamento para siglas canônicas
    PARTY_CANONICAL_MAP = {
        "REPUBLICANOS": "REPUBLICANOS",
        "REPUBLICANO": "REPUBLICANOS",
        "UNIAO": "UNIÃO",
        "UNIÃO": "UNIÃO",
        "PODEMOS": "PODE",
        "PODE": "PODE",
        "SOLIDARIEDADE": "SOLIDARIEDADE",
        "CIDADANIA": "CIDADANIA",
        "PATRIOTA": "PRD",
        "PTB": "PRD",
        "AVANTE": "AVANTE",
        "NOVO": "NOVO",
        "PSOL": "PSOL",
        "PCDB": "PCdoB",
        "PCDOB": "PCdoB",
        "PSDB": "PSDB",
        "MDB": "MDB",
        "PDT": "PDT",
        "PL": "PL",
        "PP": "PP",
        "PRD": "PRD",
        "PSD": "PSD",
        "PT": "PT",
        "PV": "PV",
        "REDE": "REDE",
    }
    
    def strip_accents(text: str) -> str:
        return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn").upper()
    
    clean_key = strip_accents(p.upper())
    if clean_key in PARTY_CANONICAL_MAP:
        return PARTY_CANONICAL_MAP[clean_key]
        
    return p.upper()

def run_migration():
    print("Iniciando normalização e unificação de nós de partidos no Neo4j...")
    db = Neo4jManager()
    
    with db.driver.session() as session:
        # 1. Pega todos os nós de Party atuais
        parties = session.run("MATCH (pty:Party) RETURN pty.name as name").data()
        party_names = [p['name'] for p in parties]
        print(f"Total de nós de Party encontrados: {len(party_names)}")
        print(f"Partidos atuais: {party_names}")

        merged_count = 0
        for old_name in party_names:
            canonical_name = normalize_party_name(old_name)
            if canonical_name != old_name:
                print(f"\n[Unificando] '{old_name}' -> '{canonical_name}'...")
                
                # Garante que o nó canônico existe com os labels corretos
                session.run("""
                MERGE (canon:Entity {name: $canonical_name})
                ON CREATE SET canon:Party
                ON MATCH SET canon:Party
                """, canonical_name=canonical_name)

                # Redireciona relacionamentos de entrada (ex: (p)-[r]->(old)) para o canon
                in_rels = session.run("""
                MATCH (source)-[r]->(old:Party {name: $old_name})
                RETURN id(r) as rel_id, type(r) as rel_type, source.name as source_name, properties(r) as props
                """, old_name=old_name).data()

                for r in in_rels:
                    rel_type = r['rel_type']
                    session.run(f"""
                    MATCH (source {{name: $source_name}}), (canon:Party {{name: $canonical_name}})
                    MERGE (source)-[r2:{rel_type}]->(canon)
                    SET r2 += $props
                    """, source_name=r['source_name'], canonical_name=canonical_name, props=r['props'])

                # Redireciona relacionamentos de saída (ex: (old)-[r]->(target)) para o canon
                out_rels = session.run("""
                MATCH (old:Party {name: $old_name})-[r]->(target)
                RETURN id(r) as rel_id, type(r) as rel_type, target.name as target_name, properties(r) as props
                """, old_name=old_name).data()

                for r in out_rels:
                    rel_type = r['rel_type']
                    session.run(f"""
                    MATCH (canon:Party {{name: $canonical_name}}), (target {{name: $target_name}})
                    MERGE (canon)-[r2:{rel_type}]->(target)
                    SET r2 += $props
                    """, target_name=r['target_name'], canonical_name=canonical_name, props=r['props'])

                # Deleta o nó antigo duplicado e seus relacionamentos remanescentes
                session.run("""
                MATCH (old:Party {name: $old_name})
                DETACH DELETE old
                """, old_name=old_name)

                merged_count += 1
                print(f"  [OK] '{old_name}' unificado com sucesso em '{canonical_name}'!")

        print(f"\nConcluído! Total de partidos unificados: {merged_count}")

        # Lista final dos partidos
        final_parties = session.run("""
        MATCH (pty:Party)
        OPTIONAL MATCH (p:Politician)-[r]->(pty)
        RETURN pty.name as name, count(r) as filiacoes
        ORDER BY pty.name ASC
        """).data()

        print("\n=== LISTA FINAL DE PARTIDOS CANÔNICOS NO NEO4J ===")
        for p in final_parties:
            print(f"  - {p['name']}: {p['filiacoes']} filiações")

    db.close()

if __name__ == "__main__":
    run_migration()
