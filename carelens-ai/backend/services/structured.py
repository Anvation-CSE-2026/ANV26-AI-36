"""Rule-based structured extraction. Deterministic: it only reports what the
text literally contains (lines that look like lab results or prescriptions)."""
import re

_UNIT = (r"(?:g/dL|g/dl|mg/dL|mg/dl|mmol/L|mEq/L|U/L|IU/L|ng/mL|pg/mL|µg/dL|mcg/dL|fL|pg|%|/µL|/uL|/cumm|"
         r"cells/cumm|million/cumm|thou/µL|lakhs/cumm|mm/hr|mm/h|sec|mIU/L|uIU/mL|µIU/mL|mg/L|mL|kg|cm|bpm|mmHg|10\^\d+/[µu]?L)")
_LAB_RE = re.compile(
    r"^\s*(?P<label>[A-Za-z][A-Za-z0-9 ()/%.,'-]{1,45}?)\s*[:\-]?\s+(?P<value>\d{1,6}(?:\.\d{1,3})?)\s*"
    rf"(?P<unit>{_UNIT})?\s*"
    rf"(?:\(?\s*(?:ref(?:erence)?\.?(?:\s*range)?\s*:?\s*)?(?P<lo>\d+(?:\.\d+)?)\s*(?:-|–|to)\s*(?P<hi>\d+(?:\.\d+)?)\s*(?:{_UNIT})?\)?)?\s*$",
    re.I,
)
_SKIP_LABEL = re.compile(r"\b(page|date|age|phone|mobile|tel|contact|id|no|number|ref|pin|year|time|sample|barcode|lab)\b", re.I)


def find_lab_values(text):
    out = []
    for line in text.splitlines():
        m = _LAB_RE.match(line)
        if not m:
            continue
        label = m.group("label").strip(" :-")
        if _SKIP_LABEL.search(label) or not (m.group("unit") or m.group("lo")):
            continue
        value = m.group("value")
        ref = f"{m.group('lo')}-{m.group('hi')}" if m.group("lo") else None
        flag = None
        if ref:
            v, lo, hi = float(value), float(m.group("lo")), float(m.group("hi"))
            flag = "below" if v < lo else "above" if v > hi else "within"
        out.append({"label": label, "value": value, "unit": m.group("unit"),
                    "reference_range": ref, "flag": flag, "source_line": line.strip()[:200]})
    return out[:80]


_FORMS = r"(?:tab(?:let)?s?|cap(?:sule)?s?|syp|syrup|inj(?:ection)?|oint(?:ment)?|drops?|susp(?:ension)?)"
_MED_RE = re.compile(
    rf"^\s*(?:\d{{1,2}}[.)]\s*)?{_FORMS}\.?\s+(?P<name>[A-Za-z][A-Za-z\-]{{2,}}(?:\s+[A-Za-z][A-Za-z0-9\-]*(?=\s+\d))?)\s*"
    r"(?P<dose>\d+(?:\.\d+)?\s*(?:mg|mcg|µg|g|ml|iu)\b(?:\s*/\s*\d+(?:\.\d+)?\s*(?:mg|ml))?)?(?P<rest>.*)$",
    re.I,
)
_FREQ = re.compile(r"\b(\d-\d-\d|once daily|twice daily|thrice daily|three times a day|two times a day|at night|bedtime|"
                   r"every morning|morning|od|bd|bid|tds|tid|qid|sos|weekly)\b", re.I)
_PURPOSE = re.compile(r"\bfor\s+(?!\d+\s*(?:day|week|month))(?P<p>[A-Za-z][A-Za-z \-]{2,50})\s*$", re.I)


def find_medicines(text):
    seen, out = set(), []
    for line in text.splitlines():
        m = _MED_RE.match(line)
        if not m:
            continue
        name = " ".join(m.group("name").split()).title()
        if name.lower() in seen:
            continue
        seen.add(name.lower())
        rest = m.group("rest").strip(" ,;-")
        freq = ", ".join(dict.fromkeys(f.lower() for f in _FREQ.findall(rest))) or None
        pm = _PURPOSE.search(rest)
        out.append({"name": name, "dosage": (m.group("dose") or "").strip() or None, "frequency": freq,
                    "instructions": rest[:200] or None,
                    # Only when the document itself says "for <purpose>".
                    "purpose": pm.group("p").strip() if pm else None})
    return out[:30]
