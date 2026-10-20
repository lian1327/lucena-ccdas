"""
python manage.py seed_reference_data            # departments + categories + sub-types
python manage.py seed_reference_data --lucena   # + the 33 barangays of Lucena City (names only)
python manage.py seed_reference_data --lucena --demo-users   # + one demo account per role

Safe to run repeatedly (update_or_create). Adjust offices/SLAs to the partner LGU.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.cases.models import Department
from apps.concerns.models import Category, Subcategory
from apps.geo.models import Barangay

# code, name, kind, [(division code, division name)]
DEPARTMENTS = [
    ("CEO", "City Engineering Office", "internal", [
        ("CEO-RDB", "Road, Drainage & Bridges Maintenance Division"),
        ("CEO-BE", "Building & Electrical Division"),
    ]),
    ("GSO", "General Services Office", "internal", [
        ("GSO-SL", "Streetlight & Electrical Maintenance Division"),
        ("GSO-FM", "Facilities Maintenance Division"),
    ]),
    ("CENRO", "City Environment and Natural Resources Office", "internal", [
        ("CENRO-SWM", "Solid Waste Management Division"),
        ("CENRO-ECM", "Environmental Compliance & Monitoring Division"),
    ]),
    ("POSO", "Public Order and Safety Office", "internal", [
        ("POSO-POE", "Public Order & Enforcement Division"),
    ]),
    ("CTMO", "City Traffic Management Office", "internal", [
        ("CTMO-ENF", "Traffic Enforcement Division"),
        ("CTMO-ENG", "Traffic Engineering & Signage Division"),
        ("CTMO-PT", "Public Transport (Tricycle/Jeepney) Regulation Division"),
    ]),
    ("BPLO", "Business Permits and Licensing Office", "internal", [
        ("BPLO-IE", "Inspection & Enforcement Division"),
        ("BPLO-LP", "Licensing & Processing Division"),
    ]),
    ("CDRRMO", "City Disaster Risk Reduction and Management Office", "internal", [
        ("CDRRMO-OPS", "Operations & Response Division"),
        ("CDRRMO-RP", "Research & Planning Division"),
    ]),
    ("CVO", "City Veterinary Office", "internal", [
        ("CVO-AC", "Animal Control Division"),
    ]),
    ("CADMIN", "Office of the City Administrator", "internal", [
        ("CADMIN-PACD", "Public Assistance & Complaints Desk"),
    ]),
    # External agencies: the LGU endorses and monitors; they don't use the platform.
    ("DPWH", "DPWH District Engineering Office", "external", []),
    ("ELEC", "Electric Distribution Utility", "external", []),
    ("WATER", "Water District", "external", []),
    ("LTO", "Land Transportation Office", "external", []),
    ("PNP-HPG", "PNP Highway Patrol Group", "external", []),
]

ARTA_DAYS = {"simple": 3, "complex": 7, "highly_technical": 20}

# LGU service standard. Resolution target = min(cap, ARTA class); response = first field action / make-safe.
# code, name, name_fil, description, response_hours, response_working_days, resolution_cap_days, color
PRIORITY_LEVELS = [
    ("P1", "Emergency", "Emergency", "Panganib sa buhay o kaligtasan. Make-safe agad (barricade, alis ng sagabal).",
     4, None, 3, "danger"),
    ("P2", "Urgent", "Agaran", "Malaking abala o maraming apektado; maaaring lumala.", None, 1, 7, "warning"),
    ("P3", "Standard", "Karaniwan", "Karaniwang reklamo; ayon sa ARTA class.", None, 3, None, "info"),
    ("P4", "Low", "Mababa", "Maliit ang epekto; maaaring isama sa regular na iskedyul.", None, 5, None, "secondary"),
]

# Each office's own receiving checklist (answered on acceptance). Editable per office in admin.
SCREENING = {
    "CEO": [
        "Nasa city o barangay road / drainage (hindi national road ng DPWH)?",
        "Kailangan ng site inspection bago aksyunan?",
        "Kailangan ng materyales na wala sa stock (procurement)?",
    ],
    "GSO": [
        "Pag-aari ng City ang poste/ilaw (hindi ng electric cooperative)?",
        "May available na bombilya / piyesa sa bodega?",
    ],
    "CENRO": [
        "Sakop ng city collection route ang lugar?",
        "May kilalang nagtapon / lumabag (para sa notice of violation)?",
    ],
    "CTMO": [
        "Nasa city road (hindi national highway na sakop ng PNP-HPG/DPWH)?",
        "Enforcement ba (hindi signage o traffic engineering)?",
        "May kaugnay na city traffic ordinance?",
    ],
    "POSO": ["Kailangan ng presensya ng enforcer sa lugar?", "Kailangan ng koordinasyon sa PNP?"],
    "CDRRMO": ["May agarang panganib sa buhay o ari-arian?", "Kailangan ng koordinasyon sa ibang opisina (CEO, utility)?"],
    "BPLO": ["Kilala ang pangalan / lokasyon ng negosyo?", "Kailangan ng joint inspection (BFP, sanitation)?"],
    "CVO": ["Kailangan ng hulihan (impounding) ng hayop?"],
}

# code, name, name_fil, icon, dept, division, ARTA class, severity_weight, description
CATEGORIES = [
    ("road_damage", "Road Damage", "Sirang Kalsada", "cone-striped", "CEO", "CEO-RDB", "highly_technical", 1.10,
     "Potholes, cracked pavement, damaged bridges or sidewalks."),
    ("streetlight", "Streetlight Issues", "Sirang Ilaw-Poste", "lightbulb", "GSO", "GSO-SL", "complex", 0.90,
     "Busted, flickering, or missing streetlights."),
    ("drainage", "Drainage Problems", "Baradong Kanal / Baha", "water", "CEO", "CEO-RDB", "complex", 1.10,
     "Clogged canals, flooding, open or broken manholes."),
    ("solid_waste", "Solid Waste Concerns", "Basura", "trash3", "CENRO", "CENRO-SWM", "simple", 1.00,
     "Uncollected garbage, illegal dumping, burning of waste."),
    ("public_safety", "Public Safety Concerns", "Kaligtasan ng Publiko", "shield-exclamation", "POSO", "POSO-POE", "simple", 1.40,
     "Hazards to people: fallen wires, unsafe structures, disturbances."),
    ("business_permit", "Business Permit Concerns", "Business Permit", "briefcase", "BPLO", "BPLO-IE", "complex", 0.70,
     "Unlicensed operations, permit processing issues."),
    ("traffic", "Traffic Concerns", "Trapiko", "stoplights", "CTMO", "CTMO-ENF", "simple", 1.00,
     "Congestion, illegal parking, missing traffic signs or signals."),
    ("other", "Other Community Issues", "Iba Pang Concern", "chat-square-dots", "CADMIN", "CADMIN-PACD", "complex", 0.80,
     "Any community concern not covered above."),
]

# Sub-types that belong to a different office than their category. Editable in admin.
SUBCATEGORY_ROUTING = {
    "missing_signs": ("CTMO", "CTMO-ENG"),
    "broken_signal": ("CTMO", "CTMO-ENG"),
    "pub_violation": ("CTMO", "CTMO-PT"),
    "fallen_tree": ("CDRRMO", "CDRRMO-OPS"),
    "unsafe_structure": ("CEO", "CEO-BE"),
    "stray_animals": ("CVO", "CVO-AC"),
}

# Fixed-date national holidays. Add movable ones (Holy Week, National Heroes Day, Eid) and
# local special days by proclamation each year in the admin.
FIXED_HOLIDAYS = [
    ("01-01", "New Year's Day"), ("04-09", "Araw ng Kagitingan"), ("05-01", "Labor Day"),
    ("06-12", "Independence Day"), ("08-21", "Ninoy Aquino Day"), ("11-01", "All Saints' Day"),
    ("11-30", "Bonifacio Day"), ("12-08", "Feast of the Immaculate Conception"), ("12-25", "Christmas Day"),
    ("12-30", "Rizal Day"), ("12-31", "Last Day of the Year"),
]

DEMO_PASSWORD = "Test#12345"
# username, first, last, role, dept, division, barangay
DEMO_USERS = [
    ("pacd.desk", "Liza", "Mendoza", "pacd", "CADMIN", "CADMIN-PACD", None),
    ("cityadmin", "Carlo", "Villanueva", "city_admin", "CADMIN", None, None),
    ("mayor", "Mayor's", "Office", "mayor", None, None, None),
    ("ceo.desk", "Grace", "Villamor", "office_desk", "CEO", None, None),
    ("ceo.head", "Engr. Roberto", "Santos", "dept_head", "CEO", None, None),
    ("ceo.rdb.chief", "Engr. Teresa", "Lim", "division_chief", "CEO", "CEO-RDB", None),
    ("ceo.staff", "Engr. Ana", "Reyes", "dept_staff", "CEO", "CEO-RDB", None),
    ("ceo.crew", "Mario", "Bautista", "dept_staff", "CEO", "CEO-RDB", None),
    ("gso.desk", "Joy", "Salazar", "office_desk", "GSO", None, None),
    ("gso.head", "Ramon", "Aquino", "dept_head", "GSO", None, None),
    ("gso.sl.chief", "Nestor", "Garcia", "division_chief", "GSO", "GSO-SL", None),
    ("gso.crew", "Jun", "Ramos", "dept_staff", "GSO", "GSO-SL", None),
    ("cenro.desk", "Mylene", "Ocampo", "office_desk", "CENRO", None, None),
    ("cenro.head", "Elena", "Torres", "dept_head", "CENRO", None, None),
    ("cenro.swm.chief", "Paolo", "Cruz", "division_chief", "CENRO", "CENRO-SWM", None),
    ("cenro.staff", "Ben", "Cruz", "dept_staff", "CENRO", "CENRO-SWM", None),
    ("ctmo.desk", "Rina", "Pascual", "office_desk", "CTMO", None, None),
    ("ctmo.head", "Col. Edgar", "Manalo", "dept_head", "CTMO", None, None),
    ("ctmo.enf.chief", "Arnel", "De Mesa", "division_chief", "CTMO", "CTMO-ENF", None),
    ("ctmo.enforcer", "Dennis", "Rivera", "dept_staff", "CTMO", "CTMO-ENF", None),
    ("ctmo.eng.chief", "Engr. Liza", "Ferrer", "division_chief", "CTMO", "CTMO-ENG", None),
    ("poso.desk", "Aileen", "Ramirez", "office_desk", "POSO", None, None),
    ("poso.head", "Rodrigo", "Valdez", "dept_head", "POSO", None, None),
    ("poso.chief", "Victor", "Lagman", "division_chief", "POSO", "POSO-POE", None),
    ("poso.officer", "Ronald", "Dimaano", "dept_staff", "POSO", "POSO-POE", None),
    ("bplo.desk", "Cristina", "Umali", "office_desk", "BPLO", None, None),
    ("bplo.head", "Atty. Marissa", "Tan", "dept_head", "BPLO", None, None),
    ("bplo.ie.chief", "Joel", "Mercado", "division_chief", "BPLO", "BPLO-IE", None),
    ("bplo.inspector", "Karen", "Sison", "dept_staff", "BPLO", "BPLO-IE", None),
    ("cdrrmo.desk", "Jessa", "Alvarez", "office_desk", "CDRRMO", None, None),
    ("cdrrmo.head", "Marlon", "Briones", "dept_head", "CDRRMO", None, None),
    ("cdrrmo.ops.chief", "Ariel", "Castro", "division_chief", "CDRRMO", "CDRRMO-OPS", None),
    ("cdrrmo.responder", "Mark", "Ilagan", "dept_staff", "CDRRMO", "CDRRMO-OPS", None),
    ("cvo.desk", "Daisy", "Robles", "office_desk", "CVO", None, None),
    ("cvo.head", "Dr. Paula", "Enriquez", "dept_head", "CVO", None, None),
    ("cvo.ac.chief", "Lito", "Avila", "division_chief", "CVO", "CVO-AC", None),
    ("cvo.catcher", "Boyet", "Llamas", "dept_staff", "CVO", "CVO-AC", None),
    ("brgy.gg", "Kagawad Rosa", "Dizon", "barangay", None, None, "Gulang-Gulang"),
    ("brgy.gg.kap", "Kap. Andres", "Navarro", "barangay", None, None, "Gulang-Gulang"),
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
        parser.add_argument("--demo-users", action="store_true",
                            help=f"Create one demo account per role (password {DEMO_PASSWORD}). Never in production.")

    @transaction.atomic
    def handle(self, *args, **opts):
        from datetime import date

        from apps.cases.models import Division, Holiday

        depts, divs = {}, {}
        for code, name, kind, divisions in DEPARTMENTS:
            depts[code], _ = Department.objects.update_or_create(code=code, defaults={
                "name": name, "kind": kind, "screening_checklist": SCREENING.get(code, []),
            })
            for dcode, dname in divisions:
                divs[dcode], _ = Division.objects.update_or_create(
                    code=dcode, defaults={"department": depts[code], "name": dname}
                )
        # Retired units from earlier versions (traffic moved from POSO to its own CTMO)
        Division.objects.filter(code__in=["POSO-TM"]).update(is_active=False)
        self.stdout.write(self.style.SUCCESS(f"Offices: {len(depts)} ({len(divs)} divisions)"))

        cat_div = {}
        for i, (code, name, fil, icon, dept, div, svc, weight, desc) in enumerate(CATEGORIES):
            Category.objects.update_or_create(code=code, defaults=dict(
                name=name, name_fil=fil, icon=icon, default_department=depts[dept], service_class=svc,
                sla_days=ARTA_DAYS[svc], severity_weight=weight, description=desc, sort_order=i,
            ))
            cat_div[code] = divs.get(div)
        self.stdout.write(self.style.SUCCESS(f"Categories: {len(CATEGORIES)} (ARTA classes set)"))

        n = 0
        for cat_code, subs in SUBCATEGORIES.items():
            cat = Category.objects.get(code=cat_code)
            for i, (code, name, fil) in enumerate(subs):
                dept_code, div_code = SUBCATEGORY_ROUTING.get(code, (None, None))
                Subcategory.objects.update_or_create(code=code, defaults=dict(
                    category=cat, name=name, name_fil=fil, sort_order=i,
                    default_department=depts.get(dept_code),
                    default_division=divs.get(div_code) or (None if dept_code else cat_div.get(cat_code)),
                ))
                n += 1
        self.stdout.write(self.style.SUCCESS(f"Subcategories: {n}"))

        from apps.cases.models import PriorityLevel

        for i, (code, name, fil, desc, hrs, wd, cap, color) in enumerate(PRIORITY_LEVELS):
            PriorityLevel.objects.update_or_create(code=code, defaults=dict(
                name=name, name_fil=fil, description=desc, response_hours=hrs, response_working_days=wd,
                resolution_cap_days=cap, color=color, sort_order=i,
            ))
        self.stdout.write(self.style.SUCCESS(f"Priority levels: {len(PRIORITY_LEVELS)}"))

        year = date.today().year
        h = 0
        for y in (year, year + 1):
            for md, name in FIXED_HOLIDAYS:
                Holiday.objects.update_or_create(date=date.fromisoformat(f"{y}-{md}"), defaults={"name": name})
                h += 1
        self.stdout.write(self.style.SUCCESS(f"Holidays: {h} fixed-date (add Holy Week & proclamations yearly)"))

        if opts["lucena"]:
            for i, name in enumerate(LUCENA_BARANGAYS, start=1):
                Barangay.objects.update_or_create(name=name, defaults={"code": f"LUC-{i:03d}"})
            self.stdout.write(self.style.SUCCESS(
                f"Barangays: {len(LUCENA_BARANGAYS)} (add center coordinates/population in admin)"
            ))

        if opts["demo_users"]:
            from apps.accounts.models import User

            for username, first, last, role, dept, div, brgy in DEMO_USERS:
                u, _ = User.objects.update_or_create(username=username, defaults=dict(
                    first_name=first, last_name=last, role=role,
                    department=depts.get(dept), division=divs.get(div),
                    barangay=Barangay.objects.filter(name=brgy).first() if brgy else None,
                ))
                u.set_password(DEMO_PASSWORD)
                u.save()
            self.stdout.write(self.style.WARNING(
                f"Demo users: {len(DEMO_USERS)} (password {DEMO_PASSWORD}) — delete before deployment"
            ))
