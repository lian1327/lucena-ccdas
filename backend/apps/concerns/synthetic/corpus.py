"""
Taglish text for synthetic concerns, written the way residents actually post or say it.
Doubles as seed text for the classification model (Module 3). Not real reports.
"""

# subcategory code -> report descriptions ({lm} = landmark)
DESCRIPTIONS = {
    # Road damage
    "pothole": [
        "Malaking lubak sa {lm}, delikado lalo na sa mga naka-motor tuwing gabi.",
        "Ang laki na ng butas sa kalsada sa {lm}. May sumemplang na tricycle kahapon.",
        "Pothole po sa {lm}, lumalalim tuwing umuulan. Sana po matapalan agad.",
        "Paki-ayos naman po yung lubak sa {lm}, sira na gulong ng ilang sasakyan.",
    ],
    "damaged_pavement": [
        "Bitak-bitak na ang semento ng kalsada sa {lm}, unti-unting gumuguho ang gilid.",
        "Sira na po ang pavement sa {lm}, lumulubog yung isang parte ng daan.",
        "Yung kalsada sa {lm} puro crack na, baka bumigay pag laging dinadaanan ng truck.",
    ],
    "damaged_sidewalk": [
        "Sira ang bangketa sa {lm}, napipilitang maglakad sa kalsada ang mga estudyante.",
        "May butas sa sidewalk sa {lm}, may natapilok nang senior citizen.",
    ],
    "damaged_bridge": [
        "May bitak ang maliit na tulay sa {lm}, umuuga kapag may dumadaang truck.",
        "Sira na ang railing ng culvert sa {lm}, delikado sa mga bata.",
    ],
    "road_obstruction": [
        "May tambak ng graba at buhangin sa gitna ng kalsada sa {lm}, ilang araw na.",
        "May nakaharang na sirang sasakyan sa {lm}, isang linggo nang hindi inaalis.",
    ],
    # Streetlight
    "light_out": [
        "Patay ang ilaw-poste sa {lm} mula pa noong isang linggo. Madilim at delikado.",
        "Ilang gabi nang walang ilaw sa {lm}, natatakot dumaan ang mga estudyante pauwi.",
        "Paki-check po yung streetlight sa {lm}, hindi na umiilaw.",
    ],
    "light_flickering": [
        "Kumukurap ang ilaw-poste sa {lm}, minsan namamatay buong gabi.",
        "Yung streetlight sa {lm} on and off, parang may sira sa wiring.",
    ],
    "no_streetlight": [
        "Wala talagang ilaw sa kahabaan ng {lm}, maraming naglalakad dito tuwing gabi.",
        "Sana po malagyan ng streetlight ang {lm}, may mga insidente na ng snatching.",
    ],
    "damaged_post": [
        "Nakatagilid na ang poste sa {lm}, baka bumagsak lalo na pag malakas ang hangin.",
        "Sira ang base ng poste ng ilaw sa {lm}, nakalantad ang mga wire.",
    ],
    # Drainage
    "clogged_canal": [
        "Barado ang kanal sa {lm}, umaapaw tuwing umuulan at bumabaha sa daan.",
        "Puno ng basura at putik ang kanal sa {lm}. Paki-declog po bago tag-ulan.",
        "Hindi na umaagos ang tubig sa kanal sa {lm}, nangangamoy na rin.",
    ],
    "flooding": [
        "Baha na naman sa {lm}, hanggang tuhod kahit konting ulan lang.",
        "Laging binabaha ang {lm} tuwing high tide at malakas ang ulan. Hindi makadaan ang mga sasakyan.",
        "Pumapasok na sa mga bahay ang baha sa {lm}. Taon-taon na lang ganito.",
    ],
    "open_manhole": [
        "Bukas ang manhole sa {lm}, walang takip! May nahulog nang motor kagabi.",
        "Nawawala ang takip ng manhole sa {lm}, napakadelikado lalo na sa gabi.",
    ],
    "damaged_drainage": [
        "Sira ang drainage pipe sa {lm}, tumatagas ang tubig papunta sa kalsada.",
        "Gumuho ang gilid ng kanal sa {lm}, lumalaki na ang butas.",
    ],
    "foul_canal": [
        "Napakabaho ng kanal sa {lm}, parang may patay na hayop o tumatagas na septic.",
        "Mabaho at maitim ang tubig sa kanal sa {lm}, maraming lamok.",
    ],
    # Solid waste
    "uncollected": [
        "Tatlong araw nang hindi nakokolekta ang basura sa {lm}, nangangamoy at nilalangaw na.",
        "Hindi dumaan ang garbage truck sa {lm} ngayong linggo. Tambak na ang basura.",
        "Walang koleksyon ng basura sa {lm} mula pa noong Lunes.",
    ],
    "illegal_dumping": [
        "May nagtatapon ng basura sa bakanteng lote sa {lm} tuwing gabi.",
        "Ginagawang tapunan ng construction debris ang gilid ng {lm}.",
    ],
    "burning": [
        "May nagsusunog ng basura sa {lm} tuwing umaga, masakit sa baga ang usok.",
        "Open burning sa {lm}, may mga batang may hika sa lugar.",
    ],
    "overflowing_bin": [
        "Umaapaw na ang basurahan sa {lm}, nakakalat na sa kalsada ang basura.",
        "Puno na ang collection point sa {lm}, kinakalkal na ng mga aso.",
    ],
    # Public safety
    "hanging_wires": [
        "Nakalaylay ang mga kable sa {lm}, abot-kamay na ng mga dumadaan.",
        "May kable ng kuryente na halos sumayad sa kalsada sa {lm}. Delikado!",
    ],
    "fallen_tree": [
        "May natumbang puno sa {lm} matapos ang malakas na hangin, harang sa daan.",
        "Nakatagilid na ang malaking puno sa {lm}, baka bumagsak sa mga bahay.",
    ],
    "unsafe_structure": [
        "May abandonadong gusali sa {lm} na unti-unting gumuguho, malapit sa paaralan.",
        "Sira ang pader sa {lm}, nakatagilid na at baka bumagsak sa naglalakad.",
    ],
    "stray_animals": [
        "Maraming asong gala sa {lm}, may nakagat nang bata noong isang araw.",
        "Pagala-gala ang mga baka at kambing sa kalsada sa {lm}, delikado sa mga sasakyan.",
    ],
    "disturbance": [
        "Gabi-gabing videoke hanggang madaling-araw sa {lm}, hindi makatulog ang mga tao.",
        "May grupong nag-iinuman sa {lm} at nanggugulo sa mga dumadaan.",
    ],
    # Business permit
    "no_permit": [
        "May bagong bukas na tindahan sa {lm} na mukhang walang permit, nagbebenta pa ng alak sa menor.",
        "May junk shop sa {lm} na walang business permit, nakaharang pa sa daan ang mga kalakal.",
    ],
    "sidewalk_vending": [
        "Sakop na ng mga tindero ang buong bangketa sa {lm}, sa kalsada na naglalakad ang tao.",
        "Nakaharang ang mga pwesto ng vendor sa {lm}, sumisikip ang daan.",
    ],
    "permit_processing": [
        "Dalawang linggo na ang renewal ng business permit ko pero wala pang update.",
        "Pabalik-balik na ako para sa permit, iba-iba ang hinihinging requirements.",
    ],
    # Traffic
    "illegal_parking": [
        "Laging may nakaparadang truck sa {lm}, sagabal sa daan at sa mga jeep.",
        "Double parking sa {lm} tuwing umaga, sobrang traffic tuloy.",
        "Ginagawang paradahan ang gilid ng {lm}, isang lane na lang ang nadadaanan.",
    ],
    "congestion": [
        "Sobrang traffic sa {lm} tuwing rush hour, walang nagmamando.",
        "Buhol-buhol ang trapiko sa {lm} tuwing labasan ng eskwela.",
    ],
    "missing_signs": [
        "Wala nang 'No Parking' sign sa {lm}, natumba noong bagyo.",
        "Kailangan po ng pedestrian lane at sign sa {lm}, maraming estudyanteng tumatawid.",
    ],
    "broken_signal": [
        "Sira ang stoplight sa {lm}, laging muntikang magbanggaan ang mga sasakyan.",
        "Kumukurap lang ang traffic light sa {lm}, walang sumusunod.",
    ],
    "pub_violation": [
        "Mga tricycle sa {lm} nagsasakay sa gitna ng kalsada, sanhi ng traffic.",
        "Sobra maningil ang ilang tricycle sa {lm}, hindi sumusunod sa taripa.",
    ],
    # Other
    "_other": [
        "Paki-tingnan po ang sitwasyon sa {lm}, ilang araw nang reklamo ng mga residente.",
        "May problema po sa {lm} na hindi namin alam kung saang opisina dapat ireport.",
    ],
}

STREETS = [
    "Quezon Ave", "Granja St", "Merchan St", "Gomez St", "Enriquez St", "Evangelista St", "Rizal St",
    "Zamora St", "Allarey St", "Diversion Rd", "Red-V", "Pleasantville Subd", "Bayview Subd", "Isabang Rd",
    "Dalahican Rd", "Talao-Talao Rd", "Ibabang Iyam Rd", "Lakas ng Bayan St",
]
NATIONAL_ROADS = ["Maharlika Hwy", "Diversion Rd (national)", "Lucena-Tayabas Rd"]
LANDMARKS = [
    "tapat ng chapel", "malapit sa 7-Eleven", "kanto ng sari-sari store", "harap ng elementary school",
    "likod ng palengke", "tabi ng barangay hall", "malapit sa covered court", "tapat ng botika",
    "kanto ng basketball court", "malapit sa simbahan", "tabi ng waiting shed", "harap ng health center",
    "malapit sa tulay", "papasok ng subdivision", "tapat ng terminal ng tricycle", "malapit sa poso",
]

FIRST_NAMES = [
    "Maria", "Jose", "Juan", "Ana", "Rosa", "Pedro", "Liza", "Mark", "Jenny", "Ramon", "Grace", "Paolo",
    "Carmela", "Noel", "Joy", "Arnel", "Rowena", "Dennis", "Kristine", "Edgar", "Marites", "Bong",
    "Cherry", "Rey", "Analyn", "Jun", "Glenda", "Rodel", "Mylene", "Romeo", "Lorna", "Jayson",
]
LAST_NAMES = [
    "Santos", "Reyes", "Cruz", "Bautista", "Garcia", "Mendoza", "Torres", "Villanueva", "Ramos", "Aquino",
    "Dela Cruz", "Navarro", "Salazar", "Castillo", "Mercado", "Pascual", "De Mesa", "Manalo", "Ocampo",
    "Lopez", "Rivera", "Dimaculangan", "Macasaet", "Abrenica", "Zaballero", "Alcala", "Obien", "Tolentino",
]

RESOLUTION = {
    "road_damage": ["Natapalan na ang lubak at na-compact ang aspalto.", "Naayos na ang nasirang bahagi ng kalsada."],
    "streetlight": ["Napalitan na ang bombilya at naayos ang wiring.", "Naayos na ang ilaw-poste; umiilaw na ito."],
    "drainage": ["Na-declog na ang kanal at inalis ang naipong basura at putik.",
                 "Nalinis at naayos ang daluyan ng tubig; inayos din ang takip ng manhole."],
    "solid_waste": ["Nakolekta na ang basura at nalinis ang lugar.", "Nilinis ang lugar at binigyan ng notice ang lumabag."],
    "public_safety": ["Inayos at inalis ang panganib sa lugar.", "Nakipag-ugnayan sa may-ari at naayos na ang problema."],
    "business_permit": ["Ininspeksyon ang negosyo at binigyan ng notice of violation.", "Naayos na ang permit; naipaalam sa aplikante."],
    "traffic": ["Nagtalaga ng traffic enforcer at nag-isyu ng tiket sa mga lumabag.", "Naikabit na ang traffic sign at naayos ang signal."],
    "other": ["Naaksyunan na ng kinauukulang opisina.", "Natugunan na ang reklamo at naipaalam sa nag-report."],
}
INSPECTION = [
    "Na-validate sa site; tugma sa report.", "Mas malaki ang pinsala kaysa sa inireport.",
    "Kailangan ng materyales mula sa bodega.", "Kailangan ng 2–3 tauhan at isang araw na trabaho.",
]
MAKE_SAFE = [
    "Nilagyan ng barricade at warning sign habang hinihintay ang pag-aayos.",
    "Pansamantalang tinakpan at nilagyan ng early warning device.",
    "Inalis ang sagabal sa daan at nilagyan ng cones.",
]
EXTENSION_REASONS = [
    "Hinihintay ang materyales mula sa supplier.", "Naantala dahil sa tuloy-tuloy na pag-ulan.",
    "Kailangan ng karagdagang inspeksyon at approval ng Department Head.", "Kulang ang kagamitan; naka-schedule ang backhoe.",
]
REJECT_REASONS = [
    "Walang nakitang problema sa lugar nang inspeksyunin.", "Pribadong ari-arian; hindi sakop ng LGU.",
    "Doble ng naunang report na naaksyunan na.", "Kulang ang impormasyon at hindi makontak ang nag-report.",
]
RETURN_REASONS = [
    "Hindi sakop ng aming opisina ayon sa screening.", "Utility ang may-ari ng pasilidad, hindi ang City.",
    "Mali ang kategorya; para ito sa ibang opisina.",
]
