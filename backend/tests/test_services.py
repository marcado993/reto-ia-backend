import pytest
from unittest.mock import MagicMock, patch
from app.services.rule_engine import RuleEngine
from app.services.copago_service import CopagoService
from app.services.hospital_service import HospitalService
from app.services.nlp_service import NLPService


class TestRuleEngine:
    def test_emergency_cardiac_rule(self):
        mock_db = MagicMock()
        rule = RuleEngine(mock_db)
        mock_rule = MagicMock()
        mock_rule.name = "emergencia_cardiaca"
        mock_rule.conditions = {"symptoms": ["dolor toracico", "disnea"], "all_required": True}
        mock_rule.result = {"urgency": "alta", "specialties": ["cardiologia"], "alert": "Emergencia cardiaca"}
        mock_rule.priority = 1
        mock_rule.matches.return_value = True
        mock_db.query.return_value.order_by.return_value.all.return_value = [mock_rule]

        result = rule.evaluate(["dolor toracico", "disnea"], "intenso")
        assert result["urgency"] == "alta"
        assert "cardiologia" in result["specialties"]

    def test_no_matching_rules_returns_default(self):
        mock_db = MagicMock()
        mock_db.query.return_value.order_by.return_value.all.return_value = []
        rule = RuleEngine(mock_db)
        result = rule.evaluate(["dolor lumbar"], "leve")
        assert result["urgency"] == "media"


class TestCopagoService:
    def test_public_plan_zero_copago(self):
        mock_db = MagicMock()
        mock_plan = MagicMock()
        mock_plan.is_public = True
        mock_plan.name = "IESS"
        mock_plan.type = "public"
        mock_plan.copago_for_service.return_value = 0.0
        mock_db.query.return_value.filter.return_value.first.return_value = mock_plan

        service = CopagoService(mock_db)
        result = service.calculate(plan_id=1, service_type="consulta")
        assert result.copago_estimado == 0.0

    def test_private_plan_fixed_copago(self):
        mock_db = MagicMock()
        mock_plan = MagicMock()
        mock_plan.is_public = False
        mock_plan.name = "Bupa Essential"
        mock_plan.type = "private"
        mock_plan.copago_consulta_usd = 6.0
        mock_plan.copago_emergencia_usd = 25.0
        mock_plan.copago_pct = 0.20
        mock_plan.deductible_usd = 500
        mock_plan.copago_for_service.return_value = 6.0
        mock_db.query.return_value.filter.return_value.first.return_value = mock_plan

        service = CopagoService(mock_db)
        result = service.calculate(plan_id=3, service_type="consulta")
        assert result.copago_estimado == 6.0


class TestNLPService:
    def test_symptom_model_matches(self):
        mock_symptom = MagicMock()
        mock_symptom.name = "dolor toracico"
        mock_symptom.synonyms = ["dolor de pecho", "presion en el pecho"]
        assert mock_symptom.matches("dolor de pecho") is True
        assert mock_symptom.matches("dolor toracico") is True
        assert mock_symptom.matches("dolor de cabeza") is False


class TestHospitalService:
    def test_haversine_calculation(self):
        dist = HospitalService._haversine_km(-0.1807, -78.4678, -0.1930, -78.4815)
        assert 1.0 < dist < 3.0