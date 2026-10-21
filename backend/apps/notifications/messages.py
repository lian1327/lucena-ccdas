"""
What citizens receive. One SMS part (160 GSM-7 characters) per update wherever possible: the variable
part (office name, reason) is shortened before the message is allowed to spill into a second paid part.
"""
from django.utils import timezone

from . import conf
from .models import Notification
from .sms import clip, gsm_length, to_gsm

E = Notification.Event

SUBJECTS = {
    E.RECEIVED: "Natanggap ang iyong report",
    E.ASSIGNED: "Naipasa na sa opisina ang iyong report",
    E.IN_PROGRESS: "Inaaksyunan na ang iyong report",
    E.EXTENDED: "Na-extend ang target na petsa",
    E.RESOLVED: "Naayos na ang iyong report",
    E.REMINDER: "Naayos na ba talaga?",
    E.REOPENED: "Binuksan muli ang iyong report",
    E.CLOSED: "Isinara na ang iyong report",
    E.REJECTED: "Hindi maaaksyunan ang iyong report",
}


def track_link(ref):
    return f"{conf.site_url()}/t/{ref}"


def _date(dt):
    return f"{timezone.localtime(dt):%b %d}" if dt else ""


def _case(concern):
    case = getattr(concern, "case", None)
    if case is None and concern.duplicate_of_id:
        case = getattr(concern.duplicate_of, "case", None)
    return case


def office_label(concern, limit=30):
    case = _case(concern)
    if not case:
        return "ang City Hall"
    if case.level == "barangay":
        return f"Barangay {concern.barangay.name}"
    d = case.department
    if not d:
        return "ang City Hall"
    return d.name if len(d.name) <= limit else d.code


def _sms_variants(concern, event, history, extra):
    """Yield candidate texts from fullest to shortest; the first that fits one part wins."""
    ref = concern.reference_no
    link = track_link(ref)
    case = _case(concern)
    due = _date(case.due_at) if case else ""
    remarks = (history.remarks if history else "") or extra.get("reason", "")
    for office_limit, reason_limit in ((30, 70), (12, 45), (12, 25)):
        office = office_label(concern, office_limit)
        reason = clip(remarks, reason_limit)
        if event == E.RECEIVED:
            if concern.duplicate_of_id:
                yield (f"Natanggap ang report mo, Ref {ref}. May nauna nang nag-report nito kaya pinagsama, "
                       f"isang aksyon na lang. {link}")
            else:
                yield f"Natanggap ang report mo. Ref: {ref}. Subaybayan dito: {link}"
        elif event == E.ASSIGNED:
            if case and case.level == "external":
                yield f"{ref}: Sakop ng {office}. Inendorso na ng City Hall at susubaybayan namin. {link}"
            else:
                yield f"{ref}: Naipasa na sa {office}." + (f" Target na matapos: {due}." if due else "") + f" {link}"
        elif event == E.IN_PROGRESS:
            sched = case.scheduled_for if case else None
            yield f"{ref}: Inaaksyunan na ng {office}." + (f" Iskedyul: {sched:%b %d}." if sched else "") + f" {link}"
        elif event == E.EXTENDED:
            yield f"{ref}: Na-extend ang target sa {extra.get('due') or due}. Dahilan: {clip(extra.get('reason', ''), reason_limit)}. {link}"
        elif event == E.RESOLVED:
            yield f"{ref}: Naayos na ayon sa {office}. Tingnan ang larawan at sabihin kung talagang naayos: {link}"
        elif event == E.REMINDER:
            yield f"Naayos na ba talaga ang report {ref}? Pakisagot dito, isang minuto lang: {link}"
        elif event == E.REOPENED:
            yield f"{ref}: Binuksan muli ang kaso at babalikan ng {office}. {link}"
        elif event == E.CLOSED:
            yield f"{ref}: Isinara na ang report. Salamat sa pag-report! {link}"
        elif event == E.REJECTED:
            yield f"{ref}: Hindi maaaksyunan: {reason}. May tanong? Lumapit sa PACD ng City Hall. {link}"


def render_sms(concern, event, history=None, extra=None):
    sig = f" -{conf.get('SMS_SIGNATURE')}" if conf.get("SMS_SIGNATURE") else ""
    last = ""
    for text in _sms_variants(concern, event, history, extra or {}):
        last = to_gsm(text + sig)
        if gsm_length(last) <= 160:
            return last
    return last  # still too long: sent as 2 parts rather than dropping information


def render_email(concern, event, history=None, extra=None):
    extra = extra or {}
    ref = concern.reference_no
    name = (concern.reporter_name or "").split(" ")[0]
    subject = f"[{ref}] {SUBJECTS[event]}"
    lines = [f"Magandang araw{', ' + name if name else ''}!", ""]
    lines.append(render_sms(concern, event, history, extra).rsplit(" -", 1)[0])
    if history and history.remarks and history.changed_by_id and event != E.RECEIVED:
        lines += ["", f"Mensahe mula sa opisina: {history.remarks}"]
    lines += [
        "",
        f"Tingnan ang buong detalye: {track_link(ref)}",
        "",
        "Huwag sagutin ang email na ito. Para sa tanong, lumapit sa Public Assistance and Complaints Desk (PACD).",
        "Natanggap mo ito dahil inilagay mo ang email na ito sa iyong report (RA 10173, Data Privacy Act).",
        f"{conf.get('SMS_SIGNATURE')}",
    ]
    return subject, "\n".join(lines)
