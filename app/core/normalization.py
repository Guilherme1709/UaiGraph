"""
Normalização de partidos políticos e regras de tratamento léxico.
Elimina inconsistências como PT/MG, PODE-MG, nomes por extenso e duplicidades.
"""

import re
import unicodedata
from typing import Set

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
    "PC DO B": "PCdoB",
    "PC-DO-B": "PCdoB",
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

KNOWN_PARTIES: Set[str] = {
    "REPUBLICANOS", "UNIÃO", "PODE", "SOLIDARIEDADE", "CIDADANIA", "PRD", "AVANTE", "NOVO",
    "PSOL", "PCdoB", "PSDB", "MDB", "PDT", "PL", "PP", "PSD", "PT", "PV", "REDE"
}

PARTY_PATTERNS = [
    (r'\b(pt|partido dos trabalhadores)\b', 'PT'),
    (r'\b(pl|partido liberal)\b', 'PL'),
    (r'\b(psol|partido socialismo e liberdade)\b', 'PSOL'),
    (r'\b(psd|partido social democr[aá]tico)\b', 'PSD'),
    (r'\b(psdb|partido da social democracia brasileira)\b', 'PSDB'),
    (r'\b(pp|progressistas|partido progressista)\b', 'PP'),
    (r'\b(mdb|movimento democr[aá]tico brasileiro)\b', 'MDB'),
    (r'\b(pdt|partido democr[aá]tico trabalhista)\b', 'PDT'),
    (r'\b(pcdob|pc do b|partido comunista do brasil)\b', 'PCdoB'),
    (r'\b(pv|partido verde)\b', 'PV'),
    (r'\b(rede|rede sustentabilidade)\b', 'REDE'),
    (r'\b(uni[aã]o|uni[aã]o brasil)\b', 'UNIÃO'),
    (r'\b(avante)\b', 'AVANTE'),
    (r'\b(novo|partido novo)\b', 'NOVO'),
    (r'\b(prd)\b', 'PRD'),
    (r'\b(pode|podemos)\b', 'PODE'),
    (r'\b(republicanos|republicano)\b', 'REPUBLICANOS'),
    (r'\b(solidariedade)\b', 'SOLIDARIEDADE'),
    (r'\b(cidadania)\b', 'CIDADANIA'),
]

GENERIC_IGNORE_ENTITIES: Set[str] = {
    'camara', 'câmara', 'camara dos deputados', 'câmara dos deputados',
    'congresso', 'congresso nacional', 'senado', 'senado federal',
    'deputado', 'deputados', 'deputada', 'deputadas',
    'partido', 'partidos', 'lei', 'leis', 'projeto', 'projetos',
    'governo', 'brasil', 'minas gerais', 'mg'
}

def remove_accents(text: str) -> str:
    """Remove marcas diacríticas (acentos) e retorna em minúsculas."""
    if not text:
        return ""
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn").lower()

def strip_accents(text: str) -> str:
    """Remove marcas diacríticas mantendo maiúsculas."""
    if not text:
        return ""
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn").upper()

def normalize_party_name(party_name: str) -> str:
    """Normaliza nomes e siglas partidárias para formato canônico, eliminando sufixos e variações."""
    if not party_name or not str(party_name).strip():
        return "S.PART."
    p = str(party_name).strip()
    p = re.sub(r'[-/_ ]+(mg|minas gerais|minas)$', '', p, flags=re.IGNORECASE).strip()
    p = re.sub(r'\(mg\)$', '', p, flags=re.IGNORECASE).strip()
    
    clean_key = strip_accents(p.upper())
    if clean_key in PARTY_CANONICAL_MAP:
        return PARTY_CANONICAL_MAP[clean_key]
        
    return p.upper()
