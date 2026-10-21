"""
GraphPoliticsRAG - Interface de Linha de Comando (CLI)
Permite realizar consultas interativas via terminal sobre a bancada mineira.
"""

import sys
import io

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from engine import extract_triples, get_entities_from_question, generate_final_answer
from database import Neo4jManager

db = Neo4jManager()

def ingest_news(news_list):
    for news in news_list:
        print(f"Processando notícia: {news[:50]}...")
        triples = extract_triples(news)
        
        for t in triples:
            db.save_structured_triple(
                subj=t.subject, 
                subj_label=t.subj_label, 
                rel=t.relation, 
                obj=t.obj, 
                obj_label=t.obj_label
            )
    print("Ingestão concluída.")

def ask_question(question: str) -> str:
    # 1. Identifica todas as entidades da pergunta (multi-entidade)
    entities = get_entities_from_question(question)
    print(f"\n[Entidades identificadas]: {', '.join(entities) if entities else 'Nenhuma'}")
    
    # 2. Busca contexto no grafo (multi-hop e shortest-path se houver 2+ entidades)
    context = db.get_context_for_entities(entities, depth=2)
    
    # 3. Gera resposta baseada estritamente nos fatos do grafo
    answer = generate_final_answer(context, question)
    return answer

if __name__ == "__main__":
    print("\n=== GraphPoliticsRAG - Assistente de Deputados Federais de MG ===")
    print("Inicializando e verificando esquema do Neo4j (constraints e índices)...")
    db.init_schema()
    print("Pronto para consultas!\n")
    
    while True:
        try:
            pergunta = input("\nQual a sua dúvida em relação aos deputados federais de MG? (digite 'sair' para encerrar)\n> ").strip()

            if not pergunta:
                continue

            if pergunta.lower() == 'sair':
                print("Encerrando...")
                break

            print(f"\n{ask_question(pergunta)}")
        except KeyboardInterrupt:
            print("\nEncerrando...")
            break
        except Exception as e:
            print(f"\nOcorreu um erro: {e}")

    db.close()
