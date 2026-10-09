"""Tiny dependency-free writer for text PDFs (used by the demo seed and tests)."""


def make_text_pdf(lines):
    def esc(s):
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    content = ["BT", "/F1 11 Tf", "14 TL", "50 790 Td"]
    for line in lines:
        content.append(f"({esc(line)}) Tj T*")
    content.append("ET")
    stream = "\n".join(content).encode("latin-1", "replace")
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


SAMPLE_REPORT = [
    "SAMPLE REPORT - fictional data for demonstration only",
    "Sunrise Diagnostics - Complete Blood Count",
    "Patient: Meena (sample)    Date: 02 Oct 2026",
    "",
    "Test                 Result        Reference range",
    "Hemoglobin 11.2 g/dL (12.0-15.5)",
    "Total WBC Count 7800 /cumm (4000-11000)",
    "Platelet Count 210 thou/µL (150-410)",
    "",
    "Prescription",
    "1. Tab. Metformin 500 mg twice daily after food",
    "2. Tab. Vitamin D3 60000 IU weekly",
    "3. Tab. Paracetamol 650mg SOS for fever",
    "",
    "Review after 4 weeks.",
]
