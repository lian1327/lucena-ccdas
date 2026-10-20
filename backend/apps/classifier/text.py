"""
Text normalisation for Filipino / English / Taglish complaints.

Kept deliberately simple and explainable: lowercase, remove links/numbers/phone numbers, undo common texting
abbreviations (pu→po, kc→kasi, d2→dito…), squeeze stretched letters ("bahaaa"→"baha"), strip punctuation.
Character n-grams in the model then absorb typos and spelling variants ("basra", "basura").
"""
import re

ABBREV = {
    "pu": "po", "kc": "kasi", "ksi": "kasi", "d2": "dito", "nmn": "naman", "lng": "lang", "lang": "lang", "sna": "sana",
    "pki": "paki", "ngaun": "ngayon", "wla": "wala", "ung": "yung", "pra": "para", "nde": "hindi", "di": "hindi",
    "hnd": "hindi", "hndi": "hindi", "bkt": "bakit", "tlga": "talaga", "tlg": "talaga", "sya": "siya", "cla": "sila",
    "kalsda": "kalsada", "basra": "basura", "asap": "agad", "pls": "please", "plz": "please", "ty": "salamat",
    "brgy": "barangay", "prk": "purok", "st": "street", "ave": "avenue",
}
_URL = re.compile(r"https?://\S+|www\.\S+")
_NUM = re.compile(r"\b(?:\+?63|0)9\d{9}\b|\d+")
_STRETCH = re.compile(r"([a-zñ])\1{2,}")
_PUNCT = re.compile(r"[^a-zñ\s]")


def normalize(text):
    t = (text or "").lower()
    t = _URL.sub(" ", t)
    t = _NUM.sub(" ", t)
    t = _STRETCH.sub(r"\1", t)
    t = _PUNCT.sub(" ", t.replace("-", " "))
    return " ".join(ABBREV.get(w, w) for w in t.split())
