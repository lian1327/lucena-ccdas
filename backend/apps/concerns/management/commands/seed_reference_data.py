"""
python manage.py seed_reference_data            # departments + categories
python manage.py seed_reference_data --lucena   # + the 33 barangays of Lucena City (names only)

Safe to run repeatedly (update_or_create). Adjust offices/SLAs to the partner LGU.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.cases.models import Department
from apps.concerns.models import Category
from apps.geo.models import Barangay

DEPARTMENTS = [
    ("CEO", "City Engineering Office"),
    ("GSO", "General Services Office"),
    ("CENRO", "City Environment and Natural Resources Office"),
    ("POSO", "Public Order and Safety Office"),
    ("BPLO", "Business Permits and Licensing Office"),
    ("TMO", "Traffic Management Office"),
    ("CDRRMO", "City Disaster Risk Reduction and Management Office"),
    ("CADMIN", "Office of the City Administrator"),
]

# code, name, name_fil, icon, dept, severity_weight, sla_days, description
CATEGORIES = [
    ("road_damage", "Road Damage", "Sirang Kalsada", "cone-striped", "CEO", 1.10, 14,
     "Potholes, cracked pavement, damaged bridges or sidewalks."),
    ("streetlight", "Streetlight Issues", "Sirang Ilaw-Poste", "lightbulb", "GSO", 0.90, 5,
     "Busted, flickering, or missing streetlights."),
    ("drainage", "Drainage Problems", "Baradong Kanal / Baha", "water", "CEO", 1.10, 10,
     "Clogged canals, flooding, open or broken manholes."),
    ("solid_waste", "Solid Waste Concerns", "Basura", "trash3", "CENRO", 1.00, 3,
     "Uncollected garbage, illegal dumping, burning of waste."),
    ("public_safety", "Public Safety Concerns", "Kaligtasan ng Publiko", "shield-exclamation", "POSO", 1.40, 1,
     "Hazards to people: fallen wires, unsafe structures, disturbances."),
    ("business_permit", "Business Permit Concerns", "Business Permit", "briefcase", "BPLO", 0.70, 7,
     "Unlicensed operations, permit processing issues."),
    ("traffic", "Traffic Concerns", "Trapiko", "stoplights", "TMO", 1.00, 3,
     "Congestion, illegal parking, missing traffic signs or signals."),
    ("other", "Other Community Issues", "Iba Pang Concern", "chat-square-dots", "CADMIN", 0.80, 7,
     "Any community concern not covered above."),
]

LUCENA_BARANGAYS = [f"Barangay {i}" for i in range(1, 12)] + [
    "Barra", "Bocohan", "Cotta", "Dalahican", "Domoit", "Gulang-Gulang",
    "Ibabang Dupay", "Ibabang Iyam", "Ibabang Talim", "Ilayang Dupay", "Ilayang Iyam", "Ilayang Talim",
    "Isabang", "Market View", "Mayao Castillo", "Mayao Crossing", "Mayao Kanluran", "Mayao Parada",
    "Mayao Silangan", "Ransohan", "Salinas", "Talao-Talao",
]


class Command(BaseCommand):
    help = "Seed departments, concern categories, and optionally Lucena City barangays."

    def add_arguments(self, parser):
        parser.add_argument("--lucena", action="store_true", help="Also seed Lucena City barangays.")

    @transaction.atomic
    def handle(self, *args, **opts):
        depts = {}
        for code, name in DEPARTMENTS:
            depts[code], _ = Department.objects.update_or_create(code=code, defaults={"name": name})
        self.stdout.write(self.style.SUCCESS(f"Departments: {len(depts)}"))

        for i, (code, name, fil, icon, dept, weight, sla, desc) in enumerate(CATEGORIES):
            Category.objects.update_or_create(code=code, defaults=dict(
                name=name, name_fil=fil, icon=icon, default_department=depts[dept],
                severity_weight=weight, sla_days=sla, description=desc, sort_order=i,
            ))
        self.stdout.write(self.style.SUCCESS(f"Categories: {len(CATEGORIES)}"))

        if opts["lucena"]:
            for i, name in enumerate(LUCENA_BARANGAYS, start=1):
                Barangay.objects.update_or_create(name=name, defaults={"code": f"LUC-{i:03d}"})
            self.stdout.write(self.style.SUCCESS(
                f"Barangays: {len(LUCENA_BARANGAYS)} (add center coordinates/population in admin)"
            ))
