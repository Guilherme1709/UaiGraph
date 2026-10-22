"""
Testes unitários abrangentes para regras de normalização partidária e limpeza léxica.
"""

import unittest
from app.core.normalization import (
    normalize_party_name,
    remove_accents,
    strip_accents,
    PARTY_CANONICAL_MAP,
    KNOWN_PARTIES
)

class TestNormalization(unittest.TestCase):

    def test_canonical_acronyms(self):
        self.assertEqual(normalize_party_name("PT"), "PT")
        self.assertEqual(normalize_party_name("PL"), "PL")
        self.assertEqual(normalize_party_name("PSOL"), "PSOL")
        self.assertEqual(normalize_party_name("PSD"), "PSD")
        self.assertEqual(normalize_party_name("PSDB"), "PSDB")
        self.assertEqual(normalize_party_name("NOVO"), "NOVO")
        self.assertEqual(normalize_party_name("AVANTE"), "AVANTE")
        self.assertEqual(normalize_party_name("REPUBLICANOS"), "REPUBLICANOS")

    def test_full_names_to_acronyms(self):
        self.assertEqual(normalize_party_name("Partido dos Trabalhadores"), "PT")
        self.assertEqual(normalize_party_name("Partido Liberal"), "PL")
        self.assertEqual(normalize_party_name("Partido Socialismo e Liberdade"), "PSOL")
        self.assertEqual(normalize_party_name("Partido da Social Democracia Brasileira"), "PSDB")
        self.assertEqual(normalize_party_name("Movimento Democrático Brasileiro"), "MDB")
        self.assertEqual(normalize_party_name("União Brasil"), "UNIÃO")
        self.assertEqual(normalize_party_name("Podemos"), "PODE")
        self.assertEqual(normalize_party_name("Partido Verde"), "PV")
        self.assertEqual(normalize_party_name("Rede Sustentabilidade"), "REDE")

    def test_regional_suffixes_removal(self):
        self.assertEqual(normalize_party_name("pt-mg"), "PT")
        self.assertEqual(normalize_party_name("PL/MG"), "PL")
        self.assertEqual(normalize_party_name("PODE_MG"), "PODE")
        self.assertEqual(normalize_party_name("AVANTE (MG)"), "AVANTE")
        self.assertEqual(normalize_party_name("PSD Minas Gerais"), "PSD")
        self.assertEqual(normalize_party_name("PT - MINAS"), "PT")

    def test_accents_and_case_insensitivity(self):
        self.assertEqual(normalize_party_name("uniao"), "UNIÃO")
        self.assertEqual(normalize_party_name("União"), "UNIÃO")
        self.assertEqual(normalize_party_name("pcdob"), "PCdoB")
        self.assertEqual(normalize_party_name("PC DO B"), "PCdoB")

    def test_empty_and_unknown_parties(self):
        self.assertEqual(normalize_party_name(""), "S.PART.")
        self.assertEqual(normalize_party_name("   "), "S.PART.")
        self.assertEqual(normalize_party_name(None), "S.PART.")
        # Partido desconhecido é retornado em maiúsculas limpo
        self.assertEqual(normalize_party_name("PARTIDO_FICTICIO"), "PARTIDO_FICTICIO")

    def test_accent_helpers(self):
        self.assertEqual(remove_accents("Aécio Neves"), "aecio neves")
        self.assertEqual(remove_accents("Célia Xakriabá"), "celia xakriaba")
        self.assertEqual(strip_accents("União Brasil"), "UNIAO BRASIL")

    def test_known_parties_consistency(self):
        for party in KNOWN_PARTIES:
            self.assertEqual(normalize_party_name(party), party)

if __name__ == '__main__':
    unittest.main()
