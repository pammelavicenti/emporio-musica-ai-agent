from __future__ import annotations

import html
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "submission_summary.md"
OUTPUT = (
    ROOT
    / "output"
    / "pdf"
    / "Pammela Vicenti Ribeiro - AI Engineer - Full-Stack para Aplicações com IA Generativa.pdf"
)

NAVY = colors.HexColor("#0B2647")
BLUE = colors.HexColor("#1A5D86")
CORAL = colors.HexColor("#F04C6A")
MUTED = colors.HexColor("#5E6A78")
LIGHT = colors.HexColor("#EEF3F7")


def inline_markup(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(
        r"\[([^\]]+)\]\((https://[^\s)]+)\)",
        r'<link href="\2" color="#1A5D86"><u>\1</u></link>',
        escaped,
    )
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
    escaped = re.sub(r"`(.+?)`", r"<font name='Courier'>\1</font>", escaped)
    return escaped


def footer(canvas, document) -> None:
    canvas.saveState()
    width, _ = A4
    canvas.setStrokeColor(LIGHT)
    canvas.line(22 * mm, 15 * mm, width - 22 * mm, 15 * mm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(22 * mm, 10 * mm, "Pammela Vicenti Ribeiro | Technical Challenge")
    canvas.drawRightString(width - 22 * mm, 10 * mm, f"Page {document.page}")
    canvas.restoreState()


def build() -> Path:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "TitleCustom",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=24,
        leading=29,
        textColor=NAVY,
        alignment=TA_LEFT,
        spaceAfter=8 * mm,
    )
    heading = ParagraphStyle(
        "HeadingCustom",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        textColor=BLUE,
        spaceBefore=5 * mm,
        spaceAfter=2.5 * mm,
        keepWithNext=True,
    )
    body = ParagraphStyle(
        "BodyCustom",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=14,
        textColor=NAVY,
        spaceAfter=3.5 * mm,
    )
    meta = ParagraphStyle(
        "MetaCustom",
        parent=body,
        backColor=LIGHT,
        borderColor=CORAL,
        borderWidth=0,
        borderPadding=8,
        leftIndent=0,
        rightIndent=0,
        spaceAfter=6 * mm,
    )

    document = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        rightMargin=22 * mm,
        leftMargin=22 * mm,
        topMargin=20 * mm,
        bottomMargin=22 * mm,
        title="Emporio da Musica AI Support Assistant - Technical Challenge Summary",
        author="Pammela Vicenti Ribeiro",
        subject="Artefact AI Engineer technical challenge",
    )

    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    story = []
    paragraph_parts: list[str] = []
    metadata_parts: list[str] = []

    def flush_paragraph() -> None:
        if paragraph_parts:
            story.append(Paragraph(inline_markup(" ".join(paragraph_parts)), body))
            paragraph_parts.clear()

    def flush_metadata() -> None:
        if metadata_parts:
            story.append(Paragraph("<br/>".join(metadata_parts), meta))
            metadata_parts.clear()

    seen_heading = False
    for raw in lines:
        line = raw.strip()
        if not line:
            flush_paragraph()
            continue
        if line.startswith("# "):
            flush_paragraph()
            story.append(Spacer(1, 4 * mm))
            story.append(Paragraph(inline_markup(line[2:]), title))
            continue
        if line.startswith("## "):
            flush_paragraph()
            flush_metadata()
            seen_heading = True
            heading_text = line[3:]
            if heading_text == "Validation":
                story.append(PageBreak())
            story.append(Paragraph(inline_markup(heading_text), heading))
            continue
        if not seen_heading and line.startswith("**"):
            metadata_parts.append(inline_markup(line))
            continue
        paragraph_parts.append(line)

    flush_paragraph()
    flush_metadata()
    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return OUTPUT


if __name__ == "__main__":
    print(build())
