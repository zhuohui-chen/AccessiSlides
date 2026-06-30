"""PDF summary export for the accessibility ledger."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from audit.ledger import ledger_rows


def export_ledger_pdf(ledger_path: Path, output_path: Path) -> Path:
    """Export a compact PDF summary of ledger status and top issues."""
    rows = ledger_rows(ledger_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(output_path), pagesize=LETTER, rightMargin=0.6 * inch, leftMargin=0.6 * inch)
    styles = getSampleStyleSheet()
    story = [Paragraph("PowerPoint Accessibility Remediation Summary", styles["Title"]), Spacer(1, 0.2 * inch)]

    risk_counts = Counter(str(row.get("risk_level")) for row in rows)
    status_counts = Counter(str(row.get("status")) for row in rows)
    summary_data = [["Metric", "Count"]]
    for key, value in sorted(risk_counts.items()):
        summary_data.append([f"Risk: {key}", str(value)])
    for key, value in sorted(status_counts.items()):
        summary_data.append([f"Status: {key}", str(value)])
    summary_table = Table(summary_data, colWidths=[3.5 * inch, 1.0 * inch])
    summary_table.setStyle(_table_style())
    story.extend([summary_table, Spacer(1, 0.25 * inch)])

    story.append(Paragraph("Itemized Issues", styles["Heading2"]))
    issue_data = [["ID", "Slide", "Risk", "Status", "Issue"]]
    for row in rows[:50]:
        issue_data.append(
            [
                str(row.get("item_id", "")),
                str(row.get("slide_number", "")),
                str(row.get("risk_level", "")),
                str(row.get("status", "")),
                Paragraph(str(row.get("issue_description", "")), styles["BodyText"]),
            ]
        )
    if len(rows) > 50:
        issue_data.append(["...", "", "", "", f"{len(rows) - 50} additional items omitted from PDF summary."])
    issue_table = Table(issue_data, colWidths=[1.0 * inch, 0.5 * inch, 0.7 * inch, 1.0 * inch, 3.5 * inch])
    issue_table.setStyle(_table_style())
    story.append(issue_table)
    doc.build(story)
    return output_path


def _table_style() -> TableStyle:
    """Return a consistent table style for PDF reports."""
    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]
    )
