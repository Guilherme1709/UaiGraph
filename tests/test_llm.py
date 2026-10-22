"""
Testes unitários para o módulo LLM: esquemas estruturados, prompts e utilitários de extração.
"""

import unittest
from pydantic import ValidationError
from app.llm.schemas import Triple, TripleList, ExtractedEntities
from app.llm.prompts import (
    get_triple_extraction_prompt,
    get_entity_extraction_prompt,
    get_grounded_answer_prompt
)
from app.llm.extraction import get_entity_from_question

class TestLLMModule(unittest.TestCase):

    def test_triple_model_validation(self):
        triple = Triple(
            subject="Nikolas Ferreira",
            subj_label="Politician",
            relation="FILIADO_A",
            obj="PL",
            obj_label="Party"
        )
        self.assertEqual(triple.subject, "Nikolas Ferreira")
        self.assertEqual(triple.relation, "FILIADO_A")

        triple_list = TripleList(triples=[triple])
        self.assertEqual(len(triple_list.triples), 1)

    def test_extracted_entities_model(self):
        ext = ExtractedEntities(entities=["Nikolas Ferreira", "PL"])
        self.assertEqual(len(ext.entities), 2)

        # JSON schema deve ser válido
        schema = ExtractedEntities.model_json_schema()
        self.assertIn("properties", schema)
        self.assertIn("entities", schema["properties"])

    def test_prompt_generation(self):
        text = "Deputado Aécio Neves apresentou PL 1234/2023."
        p_triple = get_triple_extraction_prompt(text)
        self.assertIn(text, p_triple)
        self.assertIn("UPPERCASE_SNAKE_CASE", p_triple)

        question = "Quem é o deputado Reginaldo Lopes?"
        p_entity = get_entity_extraction_prompt(question)
        self.assertIn(question, p_entity)
        self.assertIn("REGRAS MANDATÓRIAS", p_entity)

        p_answer = get_grounded_answer_prompt(context="Contexto de teste", question=question)
        self.assertIn("Contexto de teste", p_answer)
        self.assertIn("Minas Gerais (MG)", p_answer)

    def test_get_entity_from_question_fallback(self):
        # Pergunta mencionando explicitamente uma legenda sem chamar API (cai no regex fallback do extractor)
        ent = get_entity_from_question("Quais os deputados do PT em Minas Gerais?")
        # O extractor identifica 'PT' via regex ou retorna string
        self.assertIsInstance(ent, str)

if __name__ == '__main__':
    unittest.main()
