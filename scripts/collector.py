import sys
import requests
import os
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from engine import extract_triples
from database import Neo4jManager

class CamaraCollector:
    def __init__(self):
        self.base_url = "https://dadosabertos.camara.leg.br/api/v2"
        self.db = Neo4jManager()

    def get_deputados_mg(self):
        """Busca todos os deputados de Minas Gerais"""
        url = f"{self.base_url}/deputados?siglaUf=MG&ordem=ASC&ordenarPor=nome"
        response = requests.get(url)
        if response.status_code == 200:
            return response.json().get('dados', [])
        return []

    def get_deputado_detalhes(self, deputado_id: int):
        """Busca dados detalhados (gabinete, escolaridade, etc.) de um parlamentar"""
        try:
            url = f"{self.base_url}/deputados/{deputado_id}"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return response.json().get('dados', {})
        except Exception as e:
            print(f"[Collector] Erro ao obter detalhes do deputado {deputado_id}: {e}")
        return {}

    def get_proposicoes_deputado(self, deputado_id: int, limite: int = 6):
        """Busca projetos de lei e propostas de relevância (PL, PEC, PLP, PDL) do deputado"""
        try:
            url = f"{self.base_url}/proposicoes"
            params = {
                "idDeputadoAutor": deputado_id,
                "siglaTipo": ["PL", "PEC", "PLP", "PDL"],
                "ordem": "DESC",
                "ordenarPor": "ano",
                "itens": limite
            }
            response = requests.get(url, params=params, timeout=12)
            if response.status_code == 200:
                dados = response.json().get('dados', [])
                if not dados:
                    params.pop("siglaTipo", None)
                    r2 = requests.get(url, params=params, timeout=12)
                    if r2.status_code == 200:
                        dados = r2.json().get('dados', [])
                return dados
        except Exception as e:
            print(f"[Collector] Erro ao buscar proposições do deputado {deputado_id}: {e}")
        return []

    def sync_mg_politicians_metadata(self):
        """
        Sincroniza rapidamente todos os deputados de MG com suas fotos oficiais,
        partido, e-mail e ID da Câmara dos Deputados no Neo4j (leva apenas poucos segundos).
        """
        print("Sincronizando fotos e metadados dos deputados de Minas Gerais...")
        deputados = self.get_deputados_mg()
        print(f"Total de deputados recebidos da API: {len(deputados)}")
        
        for dep in deputados:
            nome = dep.get('nome')
            dep_id = dep.get('id')
            partido = dep.get('siglaPartido', 'S.PART.')
            photo_url = dep.get('urlFoto')
            email = dep.get('email')
            uf = dep.get('siglaUf', 'MG')

            self.db.save_politician_profile(
                name=nome,
                party=partido,
                photo_url=photo_url,
                email=email,
                camara_id=dep_id,
                uf=uf
            )
            print(f"  [OK] {nome} ({partido}) - Foto sincronizada")
        print("Metadados e fotos sincronizados com sucesso!")

    def run_mg_pipeline(self, extrair_com_llm=True):
        """Executa o fluxo completo de ingestão de MG"""
        print("Iniciando coleta de dados de Minas Gerais...")
        deputados = self.get_deputados_mg()
        print(f"Total de deputados encontrados: {len(deputados)}")
        
        for dep in deputados:
            nome = dep['nome']
            dep_id = dep['id']
            partido = dep['siglaPartido']
            photo_url = dep.get('urlFoto')
            email = dep.get('email')
            uf = dep.get('siglaUf', 'MG')
            
            print(f"Processando: {nome} ({partido})")
            
            # 1. Relação e perfil básico com foto oficial: Deputado -> FILIADO_A -> Partido
            self.db.save_politician_profile(
                name=nome,
                party=partido,
                photo_url=photo_url,
                email=email,
                camara_id=dep_id,
                uf=uf
            )
            
            # 2. Buscamos proposições reais recentes do deputado
            proposicoes = self.get_proposicoes_deputado(dep_id, limite=6)
            for prop in proposicoes:
                ementa = prop.get('ementa')
                if not ementa:
                    continue
                
                sigla_tipo = prop.get('siglaTipo', 'PL')
                num = prop.get('numero', '')
                ano = prop.get('ano', '')
                titulo_prop = f"{sigla_tipo} {num}/{ano}".strip() if num else ementa[:60]
                
                # Relaciona o deputado à proposição
                self.db.save_structured_triple(
                    subj=nome, subj_label="Politician",
                    rel="PROPOS",
                    obj=titulo_prop, obj_label="Bill"
                )
                
                # 3. Extração semântica com o LLM a partir da ementa
                if extrair_com_llm:
                    try:
                        texto_ementa = f"O deputado {nome} ({partido}) propôs a seguinte medida ({titulo_prop}): {ementa}"
                        triples = extract_triples(texto_ementa)
                        for t in triples:
                            self.db.save_structured_triple(
                                subj=t.subject, subj_label=t.subj_label,
                                rel=t.relation,
                                obj=t.obj, obj_label=t.obj_label
                            )
                    except Exception as e:
                        print(f"  [Aviso] LLM pulado para {titulo_prop}: {e}")
        
        print("\nPipeline de Minas finalizado com sucesso!")
        self.db.close()

if __name__ == "__main__":
    collector = CamaraCollector()
    collector.run_mg_pipeline(extrair_com_llm=True)
