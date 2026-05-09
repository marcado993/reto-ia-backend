import logging
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.health_plan import HealthPlan
from app.models.hospital import Hospital
from app.models.service import MedicalService
from app.schemas.copago import CopagoResult

logger = logging.getLogger(__name__)


class CopagoService:
    def __init__(self, db: Session):
        self.db = db

    def calculate(
        self,
        plan_id: int,
        service_type: str,
        specialty: str | None = None,
        hospital_id: int | None = None,
    ) -> CopagoResult:
        plan = self.db.query(HealthPlan).filter(HealthPlan.id == plan_id).first()
        if not plan:
            raise ValueError(f"Plan {plan_id} not found")

        base_cost = self._get_base_cost(service_type, specialty, hospital_id)

        if plan.is_public:
            return CopagoResult(
                plan_nombre=plan.name,
                plan_tipo=plan.type,
                service_type=service_type,
                costo_base=float(base_cost),
                copago_estimado=0.0,
                moneda="USD",
                metodo="Cobertura total - seguro publico",
                desglose=f"Su plan {plan.name} cubre el 100% del servicio. Copago: $0.00",
                deducible_restante=None,
            )

        copago = plan.copago_for_service(service_type, float(base_cost))
        metodo = self._determine_method(plan, service_type)

        cobertura_pct = round((1 - float(plan.copago_pct)) * 100, 0) if plan.copago_pct else 100
        if plan.copago_consulta_usd and service_type == "consulta":
            desglose = (
                f"Su plan {plan.name} tiene copago fijo de ${float(plan.copago_consulta_usd):.2f} "
                f"para consultas. Costo base del servicio: ${float(base_cost):.2f}."
            )
        elif plan.copago_emergencia_usd and service_type == "emergencia":
            desglose = (
                f"Su plan {plan.name} tiene copago fijo de ${float(plan.copago_emergencia_usd):.2f} "
                f"para emergencias. Costo base del servicio: ${float(base_cost):.2f}."
            )
        else:
            desglose = (
                f"Su plan {plan.name} cubre el {cobertura_pct:.0f}% "
                f"(${float(base_cost) * (1 - float(plan.copago_pct)):.2f}). "
                f"Usted paga el {float(plan.copago_pct)*100:.0f}% = ${copago:.2f}. "
                f"Costo base: ${float(base_cost):.2f}."
            )

        deducible_restante = None
        if plan.deductible_usd and float(plan.deductible_usd) > 0:
            deducible_restante = float(plan.deductible_usd)

        return CopagoResult(
            plan_nombre=plan.name,
            plan_tipo=plan.type,
            service_type=service_type,
            costo_base=float(base_cost),
            copago_estimado=round(copago, 2),
            moneda="USD",
            metodo=metodo,
            desglose=desglose,
            deducible_restante=deducible_restante,
        )

    def _get_base_cost(
        self, service_type: str, specialty: str | None, hospital_id: int | None
    ) -> Decimal:
        if hospital_id:
            hospital = self.db.query(Hospital).filter(Hospital.id == hospital_id).first()
            if hospital and specialty:
                cost = hospital.get_cost(specialty)
                if cost is not None:
                    return Decimal(str(cost))
            if hospital and hospital.specialty_costs:
                general = hospital.specialty_costs.get("medicina_general")
                if general is not None:
                    return Decimal(str(general))

        if specialty:
            service = self.db.query(MedicalService).filter(
                MedicalService.specialty.ilike(specialty)
            ).first()
            if service and service.base_cost_usd:
                return service.base_cost_usd

        default_costs = {"consulta": Decimal("40"), "emergencia": Decimal("80"), "hospitalizacion": Decimal("200")}
        return default_costs.get(service_type, Decimal("40"))

    @staticmethod
    def _determine_method(plan: HealthPlan, service_type: str) -> str:
        if plan.is_public:
            return "cobertura_total"
        if service_type == "consulta" and plan.copago_consulta_usd:
            return "copago_fijo"
        if service_type == "emergencia" and plan.copago_emergencia_usd:
            return "copago_fijo"
        if plan.copago_pct and float(plan.copago_pct) > 0:
            return "coaseguro_porcentual"
        return "copago_fijo"