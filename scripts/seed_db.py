import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal, Base, engine
from app.models.symptom import Symptom
from app.models.specialty import Specialty
from app.models.health_plan import HealthPlan
from app.models.hospital import Hospital
from app.models.medical_rule import MedicalRule
from app.models.service import MedicalService

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def seed_symptoms(db):
    db.query(Symptom).delete()
    data = json.loads((DATA_DIR / "seed_symptoms.json").read_text(encoding="utf-8"))
    for item in data:
        symptom = Symptom(
            name=item["name"],
            icd11_code=item.get("hpo_id"),
            synonyms=item.get("synonyms", []),
            body_system=item.get("body_part", ""),
            severity_default=item.get("severity_default", "media"),
            related_specialties=item.get("related_specialties", []),
            urgency_rules=item.get("urgency_rules", []),
            description=item.get("description", ""),
        )
        db.add(symptom)
    db.commit()
    print(f"Seeded {len(data)} symptoms")


def seed_specialties(db):
    db.query(Specialty).delete()
    data = json.loads((DATA_DIR / "seed_specialties.json").read_text(encoding="utf-8"))
    for item in data:
        specialty = Specialty(
            name=item["name"],
            description=item.get("description", ""),
            related_symptoms=item.get("related_symptoms", []),
            icd11_chapter=item.get("icd11_chapter"),
        )
        db.add(specialty)
    db.commit()
    print(f"Seeded {len(data)} specialties")


def seed_health_plans(db):
    db.query(HealthPlan).delete()
    data = json.loads((DATA_DIR / "seed_health_plans.json").read_text(encoding="utf-8"))
    for item in data:
        plan = HealthPlan(
            name=item["name"],
            type=item["type"],
            is_public=item.get("is_public", False),
            copago_consulta_usd=item.get("copago_consulta_usd"),
            copago_emergencia_usd=item.get("copago_emergencia_usd"),
            copago_pct=item.get("copago_pct", 0),
            deductible_usd=item.get("deductible_usd", 0),
            max_oop_usd=item.get("max_oop_usd", 0),
            provider_network=item.get("provider_network", ""),
            exempt_services=item.get("exempt_services", []),
        )
        db.add(plan)
    db.commit()
    print(f"Seeded {len(data)} health plans")


def seed_hospitals(db):
    db.query(Hospital).delete()
    data = json.loads((DATA_DIR / "seed_hospitals.json").read_text(encoding="utf-8"))
    for item in data:
        hospital = Hospital(
            name=item["name"],
            type=item.get("type", "general"),
            network=item.get("network", ""),
            zone=item.get("zone", ""),
            lat=item.get("lat"),
            lon=item.get("lon"),
            specialty_costs=item.get("specialty_costs", {}),
        )
        db.add(hospital)
    db.commit()
    print(f"Seeded {len(data)} hospitals")


def seed_rules(db):
    db.query(MedicalRule).delete()
    data = json.loads((DATA_DIR / "seed_rules.json").read_text(encoding="utf-8"))
    for item in data:
        rule = MedicalRule(
            name=item["name"],
            description=item.get("description", ""),
            conditions=item.get("conditions", {}),
            result=item.get("result", {}),
            priority=item.get("priority", 5),
        )
        db.add(rule)
    db.commit()
    print(f"Seeded {len(data)} medical rules")


def seed_services(db):
    db.query(MedicalService).delete()
    data = json.loads((DATA_DIR / "seed_services.json").read_text(encoding="utf-8"))
    for item in data:
        service = MedicalService(
            code=item["code"],
            description=item["description"],
            service_type=item["service_type"],
            specialty=item.get("specialty"),
            base_cost_usd=item.get("base_cost_usd", 0),
        )
        db.add(service)
    db.commit()
    print(f"Seeded {len(data)} medical services")


def main():
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        seed_symptoms(db)
        seed_specialties(db)
        seed_health_plans(db)
        seed_hospitals(db)
        seed_rules(db)
        seed_services(db)
        print("\nAll data seeded successfully!")
    except Exception as e:
        print(f"Error seeding: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()