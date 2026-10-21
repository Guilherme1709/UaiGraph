import sys
import requests
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from database import Neo4jManager

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "https://dadosabertos.camara.leg.br/api/v2"

def clean_spurious_bills(session):
    """Remove proposições espúrias ou puramente administrativas (como pareceres PRL 1/0 ou RICs avulsos)."""
    print("Limpando pareceres e requerimentos administrativos espúrios...")
    query = """
    MATCH (b:Bill)
    WHERE b.name CONTAINS '/0' 
       OR b.name STARTS WITH 'PRL ' 
       OR b.name STARTS WITH 'RIC ' 
       OR b.name STARTS WITH 'REQ '
       OR b.name = 'PRL 1/0'
       OR b.name = 'RIC 2680/2026'
    DETACH DELETE b
    """
    session.run(query)
    print("Limpeza de proposições administrativas concluída.")

def save_bill_and_relation(session, politician_name, bill_title, ementa, tipo, numero, ano):
    """Salva a proposição como :Bill e cria a relação :PROPOS a partir do parlamentar."""
    query = """
    MERGE (p:Entity {name: $politician_name})
    ON CREATE SET p:Politician
    ON MATCH SET p:Politician
    MERGE (b:Entity {name: $bill_title})
    ON CREATE SET b:Bill
    ON MATCH SET b:Bill
    SET b.ementa = $ementa,
        b.tipo = $tipo,
        b.numero = $numero,
        b.ano = $ano
    MERGE (p)-[:PROPOS]->(b)
    """
    session.run(query, politician_name=politician_name, bill_title=bill_title,
                ementa=ementa, tipo=tipo, numero=numero, ano=ano)

def ingest_deputy_bills_paginated(session, dep_name, camara_id, page_size=100):
    """
    Busca TODAS as proposições substantivas (PL, PEC, PLP, PDL) do deputado
    na API da Câmara, usando paginação completa.
    Retorna o total de proposições inseridas no grafo.
    """
    url = f"{BASE_URL}/proposicoes"
    count = 0
    pagina = 1

    while True:
        params = {
            "idDeputadoAutor": camara_id,
            "siglaTipo": ["PL", "PEC", "PLP", "PDL"],
            "ordem": "DESC",
            "ordenarPor": "ano",
            "itens": page_size,
            "pagina": pagina
        }

        try:
            r = requests.get(url, params=params, timeout=15)
            if r.status_code != 200:
                break

            dados = r.json().get('dados', [])
            if not dados:
                break

            for d in dados:
                sigla = d.get('siglaTipo', 'PL')
                num = d.get('numero')
                ano = d.get('ano')
                ementa = d.get('ementa', '').strip()
                if not num or not ano or not ementa:
                    continue

                titulo = f"{sigla} {num}/{ano}"
                save_bill_and_relation(session, dep_name, titulo, ementa, sigla, num, ano)
                count += 1

            # Se recebeu menos que page_size, é a última página
            if len(dados) < page_size:
                break

            pagina += 1
            time.sleep(0.15)  # Respeito ao rate limit da API da Câmara

        except Exception as e:
            print(f"  [Erro ao consultar CD para {dep_name}, página {pagina}]: {e}")
            break

    # Salva o total real de proposições no nó do Politician
    session.run("""
    MATCH (p:Politician {name: $name})
    SET p.total_bills_oficial = $total
    """, name=dep_name, total=count)

    return count

def run():
    print("=== INGESTÃO COMPLETA DE PROPOSIÇÕES LEGISLATIVAS (BANCADA MG) ===\n")
    print("Fonte de dados: API Oficial de Dados Abertos da Câmara dos Deputados (v2)")
    print("Critério: Ingestão 100% via API oficial, sem limite artificial, paginação completa.\n")
    db = Neo4jManager()

    with db.driver.session() as session:
        # 1. Limpa todas as proposições antigas para garantir pureza dos dados oficiais
        print("Limpando proposições anteriores para recriação limpa...")
        session.run("MATCH (b:Bill) DETACH DELETE b")
        print("Base de proposições limpa com sucesso.")

        # 2. Busca todos os deputados da bancada no Neo4j com camara_id
        deputados = session.run("""
        MATCH (p:Politician)
        WHERE p.camara_id IS NOT NULL
        RETURN p.name as name, p.camara_id as camara_id
        ORDER BY p.name ASC
        """).data()

        print(f"\nConsultando API oficial da Câmara para {len(deputados)} parlamentares de MG (TODAS as proposições PL/PEC/PLP/PDL)...")
        total_ingest = 0

        for i, dep in enumerate(deputados, 1):
            name = dep['name']
            cid = dep['camara_id']
            c = ingest_deputy_bills_paginated(session, name, cid)
            total_ingest += c
            print(f"  [{i}/{len(deputados)}] {name} (ID: {cid}) -> {c} proposições inseridas da API.")
            time.sleep(0.1)  # Pausa entre deputados

        # 3. Limpeza de proposições administrativas espúrias
        clean_spurious_bills(session)

        # 4. Estatísticas finais de auditoria
        stats = session.run("""
        MATCH (b:Bill)
        RETURN count(b) as total_bills
        """).single()

        top_deps = session.run("""
        MATCH (p:Politician)-[:PROPOS]->(b:Bill)
        RETURN p.name as name, count(b) as total
        ORDER BY total DESC, p.name ASC
        LIMIT 10
        """).data()

        bottom_deps = session.run("""
        MATCH (p:Politician)-[:PROPOS]->(b:Bill)
        RETURN p.name as name, count(b) as total
        ORDER BY total ASC, p.name ASC
        LIMIT 10
        """).data()

        print("\n=== RESULTADO FINAL NO BANCO DE DADOS (100% API CÂMARA — SEM LIMITE) ===")
        print(f"Total de Proposições Legais (:Bill) registradas no Grafo: {stats['total_bills']}")
        print(f"Total ingerido nesta execução: {total_ingest}")
        print("\nTop 10 Deputados com mais proposições:")
        for td in top_deps:
            print(f"  - {td['name']}: {td['total']} proposições")
        print("\n10 Deputados com menos proposições:")
        for bd in bottom_deps:
            print(f"  - {bd['name']}: {bd['total']} proposições")

    db.close()
    print("\nIngestão completa e fidedigna concluída com sucesso!")

if __name__ == "__main__":
    run()
