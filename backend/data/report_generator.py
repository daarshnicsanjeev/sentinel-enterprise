"""
Compliance report PDF generator using reportlab.
Produces a single-page PDF summarising a Sentinel analysis result.
"""
import io
import json

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable

_DECISION_COLORS = {
    "APPROVED": colors.HexColor("#15803d"),
    "REJECTED": colors.HexColor("#b91c1c"),
    "ESCALATE": colors.HexColor("#d97706"),
    "BLOCKED":  colors.HexColor("#7c3aed"),
}
_RISK_COLORS = {
    "HIGH":   colors.HexColor("#b91c1c"),
    "MEDIUM": colors.HexColor("#d97706"),
    "LOW":    colors.HexColor("#15803d"),
}


def generate_pdf(record: dict) -> bytes:
    """Build a compliance report PDF for a history record and return raw bytes."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=20 * mm, bottomMargin=20 * mm,
    )
    styles = getSampleStyleSheet()
    story = []

    # ── Header ────────────────────────────────────────────────────────────────
    story.append(Paragraph("Project Sentinel — Compliance Report", styles["Title"]))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#334155")))
    story.append(Spacer(1, 6 * mm))

    # ── Metadata table ─────────────────────────────────────────────────────────
    decision = record.get("decision", "UNKNOWN")
    decision_color = _DECISION_COLORS.get(decision, colors.grey)
    score = record.get("evaluation_score", 0)
    score_pct = f"{float(score) * 100:.0f}%" if score else "—"

    meta_data = [
        ["Trace ID",    record.get("trace_id", "—")],
        ["Filename",    record.get("filename", "—")],
        ["Document Type", record.get("doc_type", "—")],
        ["Language",    record.get("language", "en").upper()],
        ["Tenant",      record.get("tenant_id", "default")],
        ["Analysed At", record.get("created_at", "—")],
        ["Faithfulness Score", score_pct],
        ["Hallucination Risk", record.get("hallucination_risk", "—").upper()],
    ]
    meta_table = Table(meta_data, colWidths=[55 * mm, 110 * mm])
    meta_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#64748b")),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.HexColor("#f8fafc"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 8 * mm))

    # ── Decision badge ─────────────────────────────────────────────────────────
    decision_style = ParagraphStyle(
        "Decision",
        parent=styles["Normal"],
        fontSize=16,
        fontName="Helvetica-Bold",
        textColor=colors.white,
        backColor=decision_color,
        borderPadding=(6, 12, 6, 12),
        alignment=1,  # CENTER
    )
    story.append(Paragraph(f"DECISION: {decision}", decision_style))
    story.append(Spacer(1, 8 * mm))

    # ── Clause results table ───────────────────────────────────────────────────
    story.append(Paragraph("Clause Verification Results", styles["Heading2"]))
    story.append(Spacer(1, 3 * mm))

    try:
        clause_results = json.loads(record.get("clause_results", "[]") or "[]")
    except (json.JSONDecodeError, TypeError):
        clause_results = []

    if clause_results:
        clause_header = [["Clause", "Risk", "Status", "Evidence (excerpt)"]]
        clause_rows = []
        for c in clause_results:
            risk = c.get("risk_level", "—")
            status = c.get("status", "—")
            evidence = (c.get("evidence", "") or "")[:80]
            clause_rows.append([
                c.get("clause", "—"),
                risk,
                status,
                evidence + ("…" if len(c.get("evidence", "") or "") > 80 else ""),
            ])
        clause_table = Table(
            clause_header + clause_rows,
            colWidths=[55 * mm, 18 * mm, 20 * mm, 72 * mm],
        )
        style = TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f8fafc"), colors.white]),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ])
        # Colour status cells
        for row_idx, c in enumerate(clause_results, start=1):
            status = c.get("status", "")
            risk = c.get("risk_level", "")
            status_color = colors.HexColor("#15803d") if status == "PRESENT" else colors.HexColor("#b91c1c")
            style.add("TEXTCOLOR", (2, row_idx), (2, row_idx), status_color)
            style.add("FONTNAME", (2, row_idx), (2, row_idx), "Helvetica-Bold")
            risk_color = _RISK_COLORS.get(risk, colors.grey)
            style.add("TEXTCOLOR", (1, row_idx), (1, row_idx), risk_color)
            style.add("FONTNAME", (1, row_idx), (1, row_idx), "Helvetica-Bold")
        clause_table.setStyle(style)
        story.append(clause_table)
    else:
        story.append(Paragraph("No clause results recorded.", styles["Normal"]))

    # ── Footer ─────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 10 * mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#334155")))
    footer_style = ParagraphStyle("Footer", parent=styles["Normal"], fontSize=7, textColor=colors.grey)
    story.append(Paragraph("Generated by Project Sentinel — AI Document Compliance Engine", footer_style))

    doc.build(story)
    return buf.getvalue()
