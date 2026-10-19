"""
python manage.py seed_reference_data            # departments + categories + sub-types
python manage.py seed_reference_data --lucena   # + the 33 barangays of Lucena City (names only)

Safe to run repeatedly (update_or_create). Adjust offices/SLAs to the partner LGU.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.cases.models import Department
from apps.concerns.models import Category, Subcategory
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

# category code → [(subcategory code, name, name_fil)]
SUBCATEGORIES = {
    "road_damage": [
        ("pothole", "Pothole", "Lubak"),
        ("damaged_pavement", "Cracked or damaged pavement", "Sirang semento ng kalsada"),
        ("damaged_sidewalk", "Damaged sidewalk", "Sirang bangketa"),
        ("damaged_bridge", "Damaged bridge or culvert", "Sirang tulay o culvert"),
        ("road_obstruction", "Debris or obstruction on road", "May harang sa daan"),
    ],
    "streetlight": [
        ("light_out", "Streetlight not working", "Patay na ilaw-poste"),
        ("light_flickering", "Flickering streetlight", "Kumukurap na ilaw"),
        ("no_streetlight", "No streetlight in area", "Walang ilaw sa lugar"),
        ("damaged_post", "Damaged or leaning post", "Sira o nakatagilid na poste"),
    ],
    "drainage": [
        ("clogged_canal", "Clogged canal", "Barado ang kanal"),
        ("flooding", "Flooding", "Baha"),
        ("open_manhole", "Open or missing manhole cover", "Bukas na manhole"),
        ("damaged_drainage", "Damaged drainage", "Sirang drainage"),
        ("foul_canal", "Foul-smelling canal", "Mabahong kanal"),
    ],
    "solid_waste": [
        ("uncollected", "Uncollected garbage", "Hindi nakolektang basura"),
        ("illegal_dumping", "Illegal dumping", "Ilegal na pagtatapon ng basura"),
        ("burning", "Burning of garbage", "Pagsusunog ng basura"),
        ("overflowing_bin", "Overflowing bin or collection point", "Umaapaw na basurahan"),
    ],
    "public_safety": [
        ("hanging_wires", "Hanging or fallen wires", "Nakalaylay na kable"),
        ("fallen_tree", "Leaning or fallen tree", "Nakatagilid o natumbang puno"),
        ("unsafe_structure", "Unsafe structure", "Delikadong istruktura"),
        ("stray_animals", "Stray animals", "Asong gala o pagala-galang hayop"),
        ("disturbance", "Disturbance or noise", "Gulo o ingay"),
    ],
    "business_permit": [
        ("no_permit", "Business without permit", "Negosyong walang permit"),
        ("sidewalk_vending", "Stall obstructing sidewalk or road", "Tindahang nakaharang sa daan"),
        ("permit_processing", "Permit processing concern", "Problema sa pagproseso ng permit"),
    ],
    "traffic": [
        ("illegal_parking", "Illegal parking", "Ilegal na paradahan"),
        ("congestion", "Heavy traffic or congestion", "Masikip na trapiko"),
        ("missing_signs", "Missing or damaged traffic sign", "Sira o walang traffic sign"),
        ("broken_signal", "Broken traffic light", "Sirang stoplight"),
        ("pub_violation", "Tricycle or jeepney violation", "Paglabag ng tricycle o jeep"),
    ],
}

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

        n = 0
        for cat_code, subs in SUBCATEGORIES.items():
            cat = Category.objects.get(code=cat_code)
            for i, (code, name, fil) in enumerate(subs):
                Subcategory.objects.update_or_create(
                    code=code, defaults=dict(category=cat, name=name, name_fil=fil, sort_order=i)
                )
                n += 1
        self.stdout.write(self.style.SUCCESS(f"Subcategories: {n}"))

        if opts["lucena"]:
            for i, name in enumerate(LUCENA_BARANGAYS, start=1):
                Barangay.objects.update_or_create(name=name, defaults={"code": f"LUC-{i:03d}"})
            self.stdout.write(self.style.SUCCESS(
                f"Barangays: {len(LUCENA_BARANGAYS)} (add center coordinates/population in admin)"
            ))
