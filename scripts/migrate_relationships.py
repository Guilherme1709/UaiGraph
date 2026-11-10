import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from database import Neo4jManager

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

RELATION_TRANSLATION_MAP = {
    "MEMBER_OF": "FILIADO_A",
    "PROPOSED": "PROPOS",

    # Common legislative actions
    "AMENDS": "ALTERA",
    "ALTERS": "ALTERA",
    "MODIFIES": "MODIFICA",
    "REGULATES": "REGULAMENTA",
    "ESTABLISHES": "ESTABELECE",
    "INSTITUTES": "INSTITUI",
    "CREATES": "CRIA",
    "REQUIRES": "EXIGE",
    "REQUIRES_CREATION_OF": "SOLICITA_CRIACAO_DE",
    "CALLS_FOR_CREATION_OF": "SOLICITA_CRIACAO_DE",
    "ENSURES": "GARANTE",
    "SUGGESTS": "SUGERE",
    "SUPPORTS": "APOIA",
    "APPROVES": "APROVA",
    "APPROVED_FOR": "APROVADO_PARA",
    "REJECTED": "REJEITOU",
    "RECOGNIZES": "RECONHECE",
    
    # Author / committee roles
    "RELATOR_OF": "RELATOR_DE",
    "REQUESTS_INCLUSION_OF_COAUTHORSHIP_TO": "SOLICITA_COAUTORIA_EM",
    "REQUESTS_INCLUSION_OF": "SOLICITA_INCLUSAO_DE",
    "REQUESTS_WITHDRAWAL_OF_SIGNATURE": "SOLICITA_RETIRADA_ASSINATURA",
    
    # Requests / hearings
    "REQUESTED": "SOLICITOU",
    "REQUESTED_INFORMATION": "SOLICITOU_INFORMACAO",
    "REQUESTS_INFORMATION": "SOLICITA_INFORMACAO",
    "REQUESTED_INFO_FROM": "SOLICITOU_INFO_DE",
    "REQUESTS_INFORMATION_FROM": "SOLICITA_INFO_DE",
    "REQUESTS_INFO": "SOLICITA_INFO",
    "REQUESTED_INVITATION": "SOLICITOU_CONVITE",
    "REQUESTED_CONVOCATION": "SOLICITOU_CONVOCACAO",
    "REQUESTED_PRESENTATION": "SOLICITOU_APRESENTACAO",
    "REQUESTS_PUBLIC_HEARING": "SOLICITA_AUDIENCIA_PUBLICA",
    "REQUESTS_URGENCY_FOR": "SOLICITA_URGENCIA_PARA",
    "REQUESTED_URGENCY_FOR": "SOLICITOU_URGENCIA_PARA",
    
    # Thematic / Scope
    "APPLIES_TO": "APLICA_SE_A",
    "REFERS_TO": "REFERE_SE_A",
    "CONCERNS": "REFERE_SE_A",
    "RELATES_TO": "RELACIONADO_A",
    "RELATED_TO": "RELACIONADO_A",
    "ABOUT": "SOBRE",
    "INCLUDED_IN": "INCLUIDO_EM",
    "REFERRED_TO": "ENCAMINHADO_A",
    "LOCATED_IN": "LOCALIZADO_EM",
    
    # Honors and designations
    "GRANTS_TITLE": "CONCEDE_TITULO",
    "GRANTS_HONOR_TO": "CONCEDE_HONRARIA_A",
    "DESIGNATES_AS": "DESIGNA_COMO",
    "INSCRIBES": "INSCREVE",
    "INSCRIBES_IN": "INSCREVE_EM",
    
    # Technical & Constitutional
    "AUDITED_BY": "AUDITADO_POR",
    "ISSUED_BY": "EMITIDO_POR",
    "DECLARED_NO_FINANCIAL_IMPACT": "SEM_IMPACTO_FINANCEIRO",
    "DECLARED_CONSTITUTIONALITY": "DECLAROU_CONSTITUCIONALIDADE",
}

def migrate():
    db = Neo4jManager()
    with db.driver.session() as session:
        initial_types = session.run("CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType").data()
        existing_types = {r['relationshipType'] for r in initial_types}
        print(f"Tipos de relacionamento encontrados inicialmente: {len(existing_types)}")
        
        migrated_count = 0
        for old_rel, new_rel in RELATION_TRANSLATION_MAP.items():
            if old_rel in existing_types:
                # Conta quantas arestas existem com o tipo antigo
                count_res = session.run(f"MATCH ()-[r:{old_rel}]->() RETURN count(r) as c").single()
                count = count_res['c'] if count_res else 0
                if count > 0:
                    print(f"Migrando {count} arestas de {old_rel} -> {new_rel}...")
                    query = f"""
                    MATCH (a)-[r:{old_rel}]->(b)
                    MERGE (a)-[r2:{new_rel}]->(b)
                    ON CREATE SET r2 = properties(r)
                    DELETE r
                    """
                    session.run(query)
                    migrated_count += count

        print(f"\nMigração concluída! Total de arestas migradas: {migrated_count}")
        
        # Exibe os novos tipos de relacionamentos no banco
        final_types = session.run("MATCH ()-[r]->() RETURN type(r) as rel, count(r) as total ORDER BY total DESC").data()
        print("\nEstado final dos relacionamentos no Neo4j:")
        for r in final_types:
            print(f"  - {r['rel']}: {r['total']}")

    db.close()

if __name__ == "__main__":
    migrate()
