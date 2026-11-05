from __future__ import annotations

import unittest
from pathlib import Path

from emporio_agent.policies import PolicyStore


DATA_DIR = Path(__file__).resolve().parents[1] / "data"


class PolicyStoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policies = PolicyStore(DATA_DIR / "policy_sections.json")

    def test_contact_search_exposes_source_conflict(self) -> None:
        result = self.policies.search("Qual é o WhatsApp e endereço da loja?")
        self.assertEqual(result["status"], "ok")
        combined = " ".join(section["content"] for section in result["sections"])
        self.assertIn("3341-4444", combined)
        self.assertIn("3321-4500", combined)
        self.assertIn("divergem", combined)

    def test_payment_search_exposes_installment_conflict(self) -> None:
        result = self.policies.search("Posso parcelar em seis vezes?")
        self.assertEqual(result["sections"][0]["id"], "payments")
        self.assertIn("divergência", result["sections"][0]["content"])

    def test_cnpj_keyword_returns_the_actual_number(self) -> None:
        result = self.policies.search("Qual é o CNPJ da loja?")
        combined = " ".join(section["content"] for section in result["sections"])
        self.assertIn("12.345.678/0001-90", combined)

    def test_tracking_format_is_covered(self) -> None:
        result = self.policies.search("Qual é o formato do código de rastreamento?")
        combined = " ".join(section["content"] for section in result["sections"])
        self.assertIn("9 caracteres alfanuméricos", combined)
        self.assertIn("BR4K7M2X9P1BR", combined)

    def test_promotion_calendar_is_covered_without_claiming_current_status(self) -> None:
        result = self.policies.search("Quando ocorre a Semana do Músico?")
        combined = " ".join(section["content"] for section in result["sections"])
        self.assertIn("22 de novembro", combined)
        self.assertIn("CSV de promoções", combined)

    def test_service_response_time_is_covered(self) -> None:
        result = self.policies.search("Qual é o tempo de resposta do atendimento?")
        combined = " ".join(section["content"] for section in result["sections"])
        self.assertIn("5 minutos", combined)

    def test_policy_uncertainty_requires_manager_confirmation(self) -> None:
        result = self.policies.search("O que fazer em caso de dúvida na política?")
        combined = " ".join(section["content"] for section in result["sections"])
        self.assertIn("consultar a gerência", combined)

    def test_unknown_policy_question_is_a_no_result(self) -> None:
        result = self.policies.search("meteorologia quântica")
        self.assertEqual(result["status"], "no_results")


if __name__ == "__main__":
    unittest.main()
