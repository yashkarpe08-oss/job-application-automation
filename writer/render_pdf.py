#!/usr/bin/env python3
"""Render a CV or cover letter from a JSON spec into an ATS-friendly PDF.

    python writer/render_pdf.py cv     spec.json out.pdf
    python writer/render_pdf.py letter spec.json out.pdf

Single column, standard font, real text (no images), contact details as
plain text. Options in the spec ("font_size", "space") let the writer agent
tune the page count.

CV spec:
  {"name", "contact": [..], "sections": [
     {"title", "paragraph": str} |
     {"title", "entries": [{"heading", "sub", "dates", "bullets": [..]}]} |
     {"title", "lines": [str, ...]}  ("Label: text" lines get a bold label)
  ]}
Letter spec:
  {"name", "contact": [..], "date", "recipient": [..], "greeting",
   "paragraphs": [..], "closing", "signature": [..]}
"""

import json
import sys
from xml.sax.saxutils import escape

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (CondPageBreak, KeepTogether, ListFlowable, ListItem,
                                Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)
from reportlab.platypus.flowables import HRFlowable

FONT_DIR = "/usr/share/fonts/truetype/crosextra"
try:
    pdfmetrics.registerFont(TTFont("Body", f"{FONT_DIR}/Carlito-Regular.ttf"))
    pdfmetrics.registerFont(TTFont("Body-Bold", f"{FONT_DIR}/Carlito-Bold.ttf"))
    pdfmetrics.registerFont(TTFont("Body-Italic", f"{FONT_DIR}/Carlito-Italic.ttf"))
    from reportlab.pdfbase.pdfmetrics import registerFontFamily
    registerFontFamily("Body", normal="Body", bold="Body-Bold", italic="Body-Italic", boldItalic="Body-Bold")
    BODY, BOLD = "Body", "Body-Bold"
except Exception:  # fall back to built-in Helvetica
    BODY, BOLD = "Helvetica", "Helvetica-Bold"

ACCENT = HexColor("#1F3864")


def styles(size, space):
    lead = size * 1.3
    return {
        "name": ParagraphStyle("name", fontName=BOLD, fontSize=size + 9, leading=size + 12,
                               alignment=TA_CENTER, textColor=ACCENT),
        "contact": ParagraphStyle("contact", fontName=BODY, fontSize=size - 0.5, leading=lead,
                                  alignment=TA_CENTER),
        "h": ParagraphStyle("h", fontName=BOLD, fontSize=size + 1.5, leading=size + 4,
                            textColor=ACCENT, spaceBefore=space * 1.6, spaceAfter=1),
        "body": ParagraphStyle("body", fontName=BODY, fontSize=size, leading=lead, spaceAfter=space * 0.5),
        "entry": ParagraphStyle("entry", fontName=BOLD, fontSize=size, leading=lead),
        "sub": ParagraphStyle("sub", fontName=BODY, fontSize=size, leading=lead, textColor=HexColor("#404040")),
        "bullet": ParagraphStyle("bullet", fontName=BODY, fontSize=size, leading=lead),
        "letter": ParagraphStyle("letter", fontName=BODY, fontSize=size, leading=lead * 1.05,
                                 spaceAfter=space * 1.4),
    }


def t(s):
    return escape(str(s))


def label_line(s):
    if ": " in s:
        k, v = s.split(": ", 1)
        return f"<b>{t(k)}:</b> {t(v)}"
    return t(s)


def header(spec, st):
    out = [Paragraph(t(spec["name"]), st["name"]), Spacer(1, 2)]
    out.append(Paragraph("  |  ".join(t(c) for c in spec["contact"]), st["contact"]))
    out.append(Spacer(1, 3))
    out.append(HRFlowable(width="100%", thickness=0.8, color=ACCENT, spaceAfter=2))
    return out


def build_cv(spec, out):
    size, space = spec.get("font_size", 10.5), spec.get("space", 4)
    st = styles(size, space)
    width = A4[0] - 36 * mm
    flow = header(spec, st)
    for sec in spec["sections"]:
        head = [Paragraph(t(sec["title"]).upper(), st["h"]),
                HRFlowable(width="100%", thickness=0.4, color=HexColor("#A0A0A0"), spaceAfter=space)]
        if "paragraph" in sec:
            flow += [KeepTogether(head + [Paragraph(t(sec["paragraph"]), st["body"])])]
        elif "lines" in sec:
            flow += [KeepTogether(head + [Paragraph(label_line(l), st["body"]) for l in sec["lines"]])]
        else:
            first = True
            for e in sec["entries"]:
                row = Table([[Paragraph(t(e["heading"]), st["entry"]),
                              Paragraph(t(e.get("dates", "")), ParagraphStyle("d", parent=st["sub"], alignment=2))]],
                            colWidths=[width * 0.72, width * 0.28])
                row.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                         ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                                         ("VALIGN", (0, 0), (-1, -1), "TOP")]))
                block = [row]
                if e.get("sub"):
                    block.append(Paragraph(t(e["sub"]), st["sub"]))
                if e.get("bullets"):
                    block.append(ListFlowable(
                        [ListItem(Paragraph(t(b), st["bullet"]), leftIndent=10, value="•") for b in e["bullets"]],
                        bulletType="bullet", start="•", leftIndent=10, bulletFontSize=size - 1))
                block.append(Spacer(1, space))
                # Keep a job title with at least its first lines; never orphan a heading.
                flow.append(CondPageBreak(40 * mm))
                flow.append(KeepTogether((head if first else []) + block))
                first = False
    doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=spec.get("top_margin", 15) * mm, bottomMargin=15 * mm,
                            title=f"{spec['name']} CV", author=spec["name"])
    doc.build(flow)


def build_letter(spec, out):
    size, space = spec.get("font_size", 11), spec.get("space", 4)
    st = styles(size, space)
    flow = header(spec, st) + [Spacer(1, space * 3)]
    flow.append(Paragraph(t(spec["date"]), st["letter"]))
    if spec.get("recipient"):
        flow.append(Paragraph("<br/>".join(t(r) for r in spec["recipient"]), st["letter"]))
    if spec.get("subject"):
        flow.append(Paragraph(f"<b>{t(spec['subject'])}</b>", st["letter"]))
    flow.append(Paragraph(t(spec["greeting"]), st["letter"]))
    flow += [Paragraph(t(p), st["letter"]) for p in spec["paragraphs"]]
    sign = [Paragraph(t(spec["closing"]), st["letter"]),
            Paragraph("<br/>".join(t(s) for s in spec["signature"]), st["letter"])]
    flow.append(KeepTogether(sign))
    doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=22 * mm, rightMargin=22 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm,
                            title=f"{spec['name']} cover letter", author=spec["name"])
    doc.build(flow)


if __name__ == "__main__":
    kind, spec_path, out = sys.argv[1:4]
    spec = json.load(open(spec_path, encoding="utf-8"))
    (build_cv if kind == "cv" else build_letter)(spec, out)
    print(out)
