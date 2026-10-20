"""
Compositional Taglish complaint generator for the synthetic data (Module 3 training/evaluation).

Why: 72 fixed templates are memorised by any classifier (100% accuracy, meaningless). Real reports vary in
wording, language mix, spelling, length and politeness, and some are genuinely ambiguous. This builds each
description from parts:

    [opener] + problem phrase (per sub-type, Tagalog / English / Taglish) + [where] + [detail] + [impact] + [request]

then applies "texting noise": abbreviations (po→pu, kasi→kc, dito→d2), dropped punctuation, ALL CAPS,
character typos, repeated letters. A share of reports also mention a second issue (e.g. flooding *because*
of garbage), which is honest label noise.

Accuracy measured on this data is still optimistic. The hand-written challenge set (ml/challenge_set.csv)
and, above all, real LGU reports are the fair tests. Chapter 4 should report all three.
"""
import random
import re

OPENERS = ["", "", "", "Good day po.", "Magandang araw po.", "Hello po,", "Pa-report lang po.", "Gusto ko lang po i-report na",
           "Sir/Ma'am,", "Concern lang po:", "Paki-aksyunan po:", "Ask ko lang po,", "Reklamo lang po.", "Hi LGU,",
           "Good evening po.", "Mga sir,", "Sa kinauukulan,", "Pls help po.", "Report ko lang po"]
REQUESTS = ["", "", "Sana po maaksyunan agad.", "Salamat po.", "Pakiayos na po.", "Sana mapansin.", "Please fix asap.",
            "Paki-check naman po.", "Matagal na po ito.", "Ilang beses na kaming nag-report.", "Thank you po.",
            "Sana po bago umulan maayos na.", "Wala pa ring aksyon hanggang ngayon.", "Pakibilisan po sana.",
            "Kawawa po ang mga residente.", "Nakakaperwisyo na po talaga."]
WHERE = ["sa {lm}", "dito sa {lm}", "malapit sa {lm}", "tapat ng {lm}", "sa may {lm}", "along {lm}", "near {lm}", "sa harap ng {lm}"]

IMPACT = {
    "road_damage": ["Delikado sa mga naka-motor.", "May naaksidente na po dito.", "Nasisira ang gulong ng mga sasakyan.",
                    "Lalo pong lumalala kapag umuulan.", "Mabagal tuloy ang trapiko.", "Dangerous lalo na sa gabi."],
    "streetlight": ["Ang dilim po sa gabi, nakakatakot dumaan.", "May mga holdapan na po dito dahil madilim.",
                    "Delikado sa mga estudyanteng umuuwi ng gabi.", "Pitch dark po buong kalye.", "Hindi makita ang daan."],
    "drainage": ["Bumabaha tuwing umuulan.", "Ang baho na po, may mga lamok pa.", "Pumapasok ang tubig sa mga bahay.",
                 "Hindi madaanan kapag malakas ang ulan.", "Baka magka-dengue ang mga bata."],
    "solid_waste": ["Ang baho na po at pinupuntahan ng aso at daga.", "Kalat-kalat na ang basura sa daan.",
                    "Nakakahiya sa mga dumadaan.", "Baka magkasakit ang mga bata.", "Umaabot na sa kalsada ang basura."],
    "public_safety": ["Delikado po sa mga bata.", "Baka may madisgrasya.", "Natatakot po ang mga residente.",
                      "Hindi na po kami makatulog.", "Emergency po ito."],
    "business_permit": ["Unfair po sa mga legal na negosyo.", "Wala pong pakialam ang may-ari.", "Ilang buwan na pong ganito.",
                        "Abala po sa mga naglalakad.", "Sana po ma-inspect."],
    "traffic": ["Sobrang traffic po tuwing umaga at hapon.", "Late na kami lagi sa trabaho.", "Delikado sa mga tumatawid.",
                "Walang enforcer na nagbabantay.", "Nagkakagulo ang mga sasakyan."],
    "other": ["Sana po matulungan kami.", "Hindi po namin alam kung saan magrereklamo.", "Paki-refer na lang po sa tamang opisina."],
}

# Problem phrases per sub-type (Tagalog, English and Taglish mixed on purpose)
PROBLEM = {
    "pothole": ["may malaking lubak", "ang laki ng butas sa kalsada", "pothole na lumalalim", "may butas sa gitna ng daan",
                "malalim na lubak", "big pothole", "sira-sira ang kalsada, puro lubak", "may hukay sa kalsada na di natatakpan",
                "nagkalubak-lubak na ang daan", "may lubak na parang maliit na pool kapag umuulan"],
    "damaged_pavement": ["bitak-bitak na ang semento ng kalsada", "cracked na ang pavement", "nabakbak ang aspalto",
                         "sira na ang semento ng daan", "lumubog ang kalsada", "uneven na ang road surface",
                         "nagbitak at umangat ang semento", "nadudurog na ang concrete ng kalye"],
    "damaged_sidewalk": ["sira ang bangketa", "basag-basag ang sidewalk", "wala nang madaanan sa bangketa dahil sira",
                         "lumubog ang sidewalk", "broken sidewalk tiles", "nawasak ang gilid ng bangketa",
                         "may butas ang bangketa, delikado sa naglalakad"],
    "damaged_bridge": ["sira na ang tulay", "may bitak ang culvert", "lumulubog na ang tulay", "nabubulok na ang kahoy ng tulay",
                       "damaged bridge railing", "gumuho ang gilid ng tulay", "umaalog ang footbridge"],
    "road_obstruction": ["may nakaharang sa kalsada", "tambak ng buhangin at graba sa daan", "nakatiwangwang ang construction materials sa kalye",
                         "may nakaparadang sirang truck na nakaharang", "harang sa daan na walang warning", "road blocked by debris",
                         "may tambak ng lupa sa gitna ng kalsada"],
    "light_out": ["patay ang ilaw ng poste", "walang ilaw ang streetlight", "streetlight not working", "ilang gabi nang patay ang ilaw",
                  "sira ang ilaw sa poste", "hindi na umiilaw ang street light", "pundido ang ilaw sa kanto",
                  "patay lahat ng ilaw sa poste dito"],
    "light_flickering": ["kumikislap-kislap ang ilaw ng poste", "patay-sindi ang streetlight", "flickering street light",
                         "nagbi-blink ang ilaw buong gabi", "minsan umiilaw minsan hindi ang poste", "malabo at kumukurap ang ilaw"],
    "no_streetlight": ["walang streetlight sa buong kalye", "kailangan ng ilaw sa poste dito", "walang poste ng ilaw",
                       "no street lights along the road", "madilim kasi walang ilaw na nakakabit", "request po ng streetlight"],
    "damaged_post": ["nakatagilid ang poste ng ilaw", "sira ang poste, parang babagsak", "nabangga ang poste ng ilaw",
                     "leaning lamp post", "kinakalawang at bumibigay na ang poste", "bumagsak ang poste ng streetlight"],
    "clogged_canal": ["barado ang kanal", "baradong drainage", "puno ng basura ang kanal kaya di umaagos", "clogged na ang canal",
                      "hindi umaagos ang tubig sa kanal", "barado ng putik at plastik ang estero", "nakabara ang imburnal",
                      "barado ang daluyan ng tubig"],
    "flooding": ["bumabaha", "baha na naman", "lubog sa baha ang kalsada", "flooded na ang street", "hanggang tuhod ang baha",
                 "pumasok na ang baha sa bahay", "laging binabaha kahit konting ulan", "hindi humuhupa ang baha"],
    "open_manhole": ["walang takip ang manhole", "bukas ang manhole", "open manhole sa daan", "nawala ang takip ng imburnal",
                     "may butas ng manhole na walang cover", "nakanganga ang manhole, delikado"],
    "damaged_drainage": ["sira ang drainage", "gumuho ang kanal", "basag ang takip ng kanal", "damaged drainage cover",
                         "nasira ang daluyan ng tubig", "bumigay ang pader ng kanal"],
    "foul_canal": ["ang baho ng kanal", "mabaho ang estero", "amoy imburnal buong lugar", "foul smell from the canal",
                   "naiipon ang maruming tubig sa kanal at umaalingasaw", "ang baho po ng tubig sa drainage"],
    "uncollected": ["hindi nakukuha ang basura", "ilang araw nang walang dumadaang garbage truck", "di pa kinokolekta ang basura",
                    "garbage not collected for a week", "naiipon na ang basura kasi walang pick-up", "hindi dumaan ang trak ng basura",
                    "tambak na ang basura, walang kumukuha"],
    "illegal_dumping": ["may nagtatapon ng basura sa bakanteng lote", "illegal dumping sa tabi ng ilog", "ginagawang tapunan ng basura ang gilid ng kalsada",
                        "may nagtatapon ng construction debris dito", "tinatapon ang basura sa sapa", "people dumping garbage at night"],
    "burning": ["may nagsusunog ng basura", "open burning ng basura sa likod-bahay", "sinusunog ang plastik, ang usok",
                "garbage burning every morning", "usok mula sa nagsusunog ng basura", "nagsisiga ng basura ang kapitbahay"],
    "overflowing_bin": ["umaapaw ang basurahan", "puno na ang garbage bin", "overflowing na ang collection point",
                        "umaabot na sa kalsada ang laman ng basurahan", "punong-puno ang drum ng basura", "sobra-sobra na ang basura sa MRF"],
    "hanging_wires": ["nakalaylay ang mga kable", "mababa na ang kawad ng kuryente", "hanging wires sa kalsada", "nakabitin ang sirang kable",
                      "laylay ang mga wire, sumasabit sa sasakyan", "may putol na kable na nakalawit", "naglawit ang kable ng cable/internet"],
    "fallen_tree": ["may natumbang puno", "bumagsak ang puno sa kalsada", "fallen tree blocking the road", "nakatagilid na ang puno, babagsak na",
                    "natumbang sanga ng puno sa daan", "malaking puno na delikadong matumba"],
    "unsafe_structure": ["delikadong gusali na parang guguho", "may sirang pader na babagsak", "abandoned building na delikado",
                         "bitak-bitak ang pader ng lumang bahay", "unsafe structure malapit sa paaralan", "nakatagilid na ang lumang bodega"],
    "stray_animals": ["maraming asong gala", "stray dogs na nangangagat", "mga asong pagala-gala sa kalye", "may asong nangagat ng bata",
                      "dumarami ang pusang gala", "stray dogs chasing motorcycles", "mga aso na walang may-ari"],
    "disturbance": ["sobrang ingay ng videoke hanggang madaling araw", "maingay ang kapitbahay gabi-gabi", "nag-iinuman sa kalye at nag-iingay",
                    "loud music until 2am", "may nag-aaway at nagsisigawan", "ingay ng mga nagkakarera ng motor"],
    "no_permit": ["walang business permit ang tindahan", "may negosyong walang permit", "operating without permit",
                  "bagong bukas na tindahan, walang permit", "illegal na negosyo sa residential area", "walang permit ang junk shop"],
    "sidewalk_vending": ["nakaharang ang mga vendor sa bangketa", "sidewalk vendors sa daan", "ginawang tindahan ang sidewalk",
                         "mga tindero sa bangketa, wala nang madaanan", "nagtitinda sa kalsada mismo", "obstruction ng mga ambulant vendor"],
    "permit_processing": ["ang tagal ng business permit ko", "delayed ang renewal ng permit", "pabalik-balik ako sa BPLO", "hanggang ngayon wala pa ang permit ko",
                          "matagal ang processing ng mayor's permit", "follow up po sa permit application"],
    "illegal_parking": ["may nakaparadang sasakyan sa daan", "illegal parking sa kanto", "double parking sa harap ng tindahan",
                        "ginagawang paradahan ang kalsada", "nakaharang ang nakaparadang van", "parking sa no parking zone"],
    "congestion": ["sobrang traffic", "heavy traffic tuwing rush hour", "buhol-buhol ang trapiko", "stuck sa traffic ng isang oras",
                   "masikip ang daloy ng sasakyan", "traffic jam dahil sa mga nakatigil na tricycle"],
    "missing_signs": ["walang traffic sign", "nawala ang stop sign", "walang pedestrian lane", "faded na ang road markings",
                      "kailangan ng signage sa kurbada", "natumba ang karatula ng no entry"],
    "broken_signal": ["sira ang traffic light", "patay ang stoplight", "traffic light not working", "naka-blink lang ang traffic light",
                      "pula lagi ang ilaw ng stoplight", "hindi gumagana ang traffic signal sa intersection"],
    "pub_violation": ["overcharging ang tricycle", "ang taas maningil ng driver ng jeep", "tricycle driver na bastos", "colorum na tricycle",
                      "hindi nagbibigay ng sukli ang driver", "nagsasakay sa hindi terminal", "reckless driving ng jeep"],
    "_other": ["may problema sa tubig", "walang tubig ilang araw na", "maingay na pabrika", "kailangan ng tulong para sa mga nasunugan",
               "mga batang palaboy sa kalsada", "may tagas ang tubo ng tubig", "humingi po ng assistance", "nawawalang alagang aso"],
}
# phrases that pull reports toward another issue (honest ambiguity in real reports)
CROSS = {
    "flooding": ["kasi barado ang kanal", "dahil sa mga basura sa drainage"],
    "clogged_canal": ["kaya bumabaha", "kasi tinatapunan ng basura"],
    "uncollected": ["kaya bumabara na sa kanal", "at umaapaw na ang basurahan"],
    "fallen_tree": ["at nakaharang sa kalsada", "tinamaan ang kable ng kuryente"],
    "hanging_wires": ["dahil sa natumbang puno", "sa may poste ng ilaw"],
    "congestion": ["dahil sa mga illegal na nakaparada", "kasi sira ang traffic light"],
    "illegal_parking": ["kaya traffic", "sa may bangketa pa"],
    "pothole": ["kaya bumabaha dito", "dahil sa sirang drainage"],
    "light_out": ["kaya madilim at may nangyayaring nakawan", "pati traffic light patay"],
    "sidewalk_vending": ["kaya traffic", "walang permit pa yata"],
}
ABBREV = [(r"\bpo\b", "pu"), (r"\bkasi\b", "kc"), (r"\bdito\b", "d2"), (r"\bnaman\b", "nmn"), (r"\blang\b", "lng"),
          (r"\bsana\b", "sna"), (r"\bpaki\b", "pki"), (r"\bngayon\b", "ngaun"), (r"\bmga\b", "mga"), (r"\bwala\b", "wla"),
          (r"\bkalsada\b", "kalsda"), (r"\bbasura\b", "basra"), (r"\byung\b", "ung"), (r"\bpara\b", "pra")]


def _typo(word, rng):
    if len(word) < 5:
        return word
    i = rng.randrange(1, len(word) - 1)
    op = rng.random()
    if op < .4:
        return word[:i] + word[i + 1:]                    # drop
    if op < .7:
        return word[:i] + word[i + 1] + word[i] + word[i + 2:]  # swap
    return word[:i] + word[i] * 2 + word[i:]              # double


def noisy(text, rng):
    """Texting style: abbreviations, typos, dropped punctuation, caps, stretched letters."""
    if rng.random() < .35:
        for pat, rep in ABBREV:
            if rng.random() < .5:
                text = re.sub(pat, rep, text, flags=re.I)
    words = text.split()
    words = [_typo(w, rng) if rng.random() < .04 else w for w in words]
    text = " ".join(words)
    if rng.random() < .25:
        text = re.sub(r"[.,!]", "", text)
    if rng.random() < .1:
        text = re.sub(r"([aeiou])\b", lambda m: m.group(1) * rng.randint(2, 4), text, count=1)
    if rng.random() < .06:
        text = text.upper()
    elif rng.random() < .3:
        text = text.lower()
    return text


def compose(sub_code, cat_code, lm, rng=None, legacy=None):
    rng = rng or random.Random()
    if legacy and rng.random() < .2:  # keep some of the original hand-written templates
        return noisy(rng.choice(legacy).format(lm=lm), rng)
    core = rng.choice(PROBLEM.get(sub_code, PROBLEM["_other"]))
    parts = [rng.choice(OPENERS)]
    where = rng.choice(WHERE).format(lm=lm)
    parts.append(f"{core} {where}." if rng.random() < .75 else f"{where.capitalize()}, {core}.")
    if sub_code in CROSS and rng.random() < .25:
        parts[-1] = parts[-1].rstrip(".") + " " + rng.choice(CROSS[sub_code]) + "."
    if rng.random() < .6:
        parts.append(rng.choice(IMPACT.get(cat_code, IMPACT["other"])))
    if rng.random() < .25:
        parts.append(rng.choice(["Ilang linggo na po ito.", "Since last month pa.", "Kahapon lang nangyari.", "Mga 3 araw na.",
                                 "Paulit-ulit na lang.", "Pangalawang beses na itong nangyari."]))
    parts.append(rng.choice(REQUESTS))
    text = " ".join(p for p in parts if p).strip()
    text = text[0].upper() + text[1:]
    return noisy(text, rng)
