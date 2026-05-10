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
        service_name: str | None = None,
    ) -> CopagoResult:
        """Calcula el copago.

        - `service_type`: "consulta" | "emergencia" | "hospitalizacion" → manda
          la regla del plan (copago fijo o porcentual).
        - `service_name`: nombre del servicio específico dentro de la especialidad
          (p.ej. "ecocardiograma"). Si está, se usa para conseguir el `base_cost`
          del hospital, no el de la consulta default.
        """
        plan = self.db.query(HealthPlan).filter(HealthPlan.id == plan_id).first()
        if not plan:
            raise ValueError(f"Plan {plan_id} not found")

        base_cost, service_label = self._get_base_cost_and_label(
            service_type, specialty, hospital_id, service_name
        )

        if plan.is_public:
            desglose = (
                f"Su plan {plan.name} cubre el 100% del servicio "
                f"({service_label}). Costo base referencial: ${float(base_cost):.2f}. "
                f"Usted paga: $0.00."
            )
            return CopagoResult(
                plan_nombre=plan.name,
                plan_tipo=plan.type,
                service_type=service_type,
                costo_base=float(base_cost),
                copago_estimado=0.0,
                moneda="USD",
                metodo="Cobertura total - seguro publico",
                desglose=desglose,
                deducible_restante=None,
            )

        copago = plan.copago_for_service(service_type, float(base_cost))
        metodo = self._determine_method(plan, service_type)

        cobertura_pct = round((1 - float(plan.copago_pct)) * 100, 0) if plan.copago_pct else 100
        if plan.copago_consulta_usd and service_type == "consulta":
            desglose = (
                f"Su plan {plan.name} tiene copago fijo de ${float(plan.copago_consulta_usd):.2f} "
                f"para consultas. Servicio: {service_label}. Costo base: ${float(base_cost):.2f}."
            )
        elif plan.copago_emergencia_usd and service_type == "emergencia":
            desglose = (
                f"Su plan {plan.name} tiene copago fijo de ${float(plan.copago_emergencia_usd):.2f} "
                f"para emergencias. Servicio: {service_label}. Costo base: ${float(base_cost):.2f}."
            )
        else:
            desglose = (
                f"Su plan {plan.name} cubre el {cobertura_pct:.0f}% del servicio "
                f"({service_label}, costo base ${float(base_cost):.2f}). "
                f"Usted paga el {float(plan.copago_pct)*100:.0f}% = ${copago:.2f}."
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

    # ──────────────────────────────────────────────────────────
    def _get_base_cost_and_label(
        self,
        service_type: str,
        specialty: str | None,
        hospital_id: int | None,
        service_name: str | None,
    ) -> tuple[Decimal, str]:
        """Devuelve (base_cost, label_human_readable) para el servicio."""
        # 1) Si hay hospital_id + especialidad, usar su tarifario expandido
        if hospital_id:
            hospital = self.db.query(Hospital).filter(Hospital.id == hospital_id).first()
            if hospital and specialty:
                price = hospital.get_service_price(specialty, service_name)
                label = self._lookup_label(hospital, specialty, service_name)
                if price is not None:
                    return Decimal(str(price)), label

        # 2) Tabla MedicalService por especialidad
        if specialty:
            service = (
                self.db.query(MedicalService)
                .filter(MedicalService.specialty.ilike(specialty))
                .first()
            )
            if service and service.base_cost_usd:
                return service.base_cost_usd, service.description or specialty

        # 3) Defaults por tipo
        defaults = {
            "consulta": (Decimal("40"), "Consulta médica"),
            "emergencia": (Decimal("80"), "Atención de emergencia"),
            "hospitalizacion": (Decimal("200"), "Hospitalización"),
        }
        return defaults.get(service_type, (Decimal("40"), "Consulta médica"))

    @staticmethod
    def _lookup_label(hospital: Hospital, specialty: str, service_name: str | None) -> str:
        services = hospital.list_services(specialty)
        if not services:
            return specialty.replace("_", " ").title()
        if service_name:
            for s in services:
                if s["name"] == service_name:
                    return s["label"]
        # default: consulta
        for s in services:
            if s["name"] == "consulta":
                return s["label"]
        return services[0]["label"]

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
