"""
Content Credentials / AI-source markers in a photo file (Step 20).

What it can and cannot do:
  - Many AI image tools and some phone "AI edit" features write a marker into the file saying the image was
    generated or edited by AI: an IPTC "digital source type" (trainedAlgorithmicMedia, compositeWithTrained-
    AlgorithmicMedia) in the XMP metadata and/or a C2PA "Content Credentials" manifest carrying the same term.
  - Finding such a marker is strong evidence (nobody adds it to a real photo). NOT finding one proves nothing:
    markers are lost when a photo is screenshotted, re-saved, or sent through most chat apps.
  - The C2PA signature is not validated here (that needs the c2pa SDK and trust lists), so a manifest without an
    AI term is only reported as "has content credentials", never as "verified authentic".
The browser scans the ORIGINAL file before compressing it (compression strips metadata) and sends the result as
photo_meta.ai_marker; the server also scans what it receives. The more severe answer wins.
"""
GENERATED = "ai_generated"
EDITED = "ai_edited"
CREDENTIALS = "credentials"
ORDER = {None: 0, CREDENTIALS: 1, EDITED: 2, GENERATED: 3}

_GENERATED = (b"/trainedAlgorithmicMedia", b'"trainedAlgorithmicMedia', b">trainedAlgorithmicMedia",
              b"digitalsourcetype/algorithmicMedia")
_EDITED = (b"compositeWithTrainedAlgorithmicMedia", b"compositeSynthetic")
_C2PA = (b"c2pa", b"jumb")
MAX_SCAN = 16 * 1024 * 1024


def scan_bytes(data: bytes):
    if not data:
        return None
    if any(m in data for m in _GENERATED):
        return GENERATED
    if any(m in data for m in _EDITED):
        return EDITED
    if all(m in data for m in _C2PA):
        return CREDENTIALS
    return None


def scan_file(fileobj):
    """Scan an uploaded file without consuming it."""
    try:
        pos = fileobj.tell()
        fileobj.seek(0)
        data = fileobj.read(MAX_SCAN)
        fileobj.seek(pos)
    except (AttributeError, OSError, ValueError):
        return None
    return scan_bytes(data)


def combine(*markers):
    valid = [m for m in markers if m in ORDER]
    return max(valid, key=lambda m: ORDER[m]) if valid else None
