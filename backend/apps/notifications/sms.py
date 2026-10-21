"""SMS text helpers: Philippine mobile numbers, the GSM-7 alphabet, and message parts (credits)."""
import math
import re
import unicodedata

_PH = re.compile(r"^(?:\+?63|0)?(9\d{9})$")

# GSM 03.38 basic set (1 unit each) and extension set (2 units each: ESC + char)
GSM_BASIC = set(
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà"
)
GSM_EXT = set("^{}\\[~]|€")
_REPLACE = {
    "‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", "…": "...",
    " ": " ", "•": "-", "·": "-", "→": "->", "⚠": "!", "✓": "", "º": "",
}


def normalize_ph_mobile(value):
    """'0917 123 4567', '+639171234567', '639171234567' → '639171234567'. None if not a PH mobile number."""
    digits = re.sub(r"[^\d+]", "", value or "")
    m = _PH.match(digits)
    return f"63{m.group(1)}" if m else None


def to_gsm(text):
    """Keep messages in GSM-7 so each part holds 160 characters (Unicode drops it to 70)."""
    out = []
    for ch in text:
        ch = _REPLACE.get(ch, ch)
        for c in ch:
            if c in GSM_BASIC or c in GSM_EXT:
                out.append(c)
            else:
                plain = unicodedata.normalize("NFKD", c).encode("ascii", "ignore").decode()
                out.append(plain if plain else "")
    return re.sub(r"[ \t]+", " ", "".join(out)).strip()


def gsm_length(text):
    return sum(2 if c in GSM_EXT else 1 for c in text)


def segments(text):
    n = gsm_length(text)
    return 1 if n <= 160 else math.ceil(n / 153)


def clip(text, limit):
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: max(0, limit - 3)].rstrip(" ,.;:") + "..."
