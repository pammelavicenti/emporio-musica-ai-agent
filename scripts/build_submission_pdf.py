"""Build the complete English README/documentation PDF required by the form.

Optional build dependencies: reportlab and markdown-it-py.
No credentials, runtime configuration, or raw tool JSON are read.
"""
from __future__ import annotations

import hashlib
import html
import re
import textwrap
from pathlib import Path
from urllib.parse import quote, urljoin

import reportlab
from markdown_it import MarkdownIt
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable, LongTable, PageBreak, Paragraph, Preformatted,
    SimpleDocTemplate, Spacer, TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "https://github.com/pammelavicenti/emporio-musica-ai-agent"
OUTPUT = ROOT / "output/pdf/Pammela Vicenti Ribeiro - AI Engineer - Full-Stack para Aplicações com IA Generativa.pdf"
SOURCE_FILES = ["README.md", "docs/data_quality_notes.md", "docs/conversation_review.md"]
CONVERSATIONS = {
    "01_catalog_continuity": "e1741dafdb2a97ea91b14c196111274c3c88210230e9729679c1a9bac96bdf84",
    "02_order_lookup": "a606213f3cdcbabd90d7c74fea94ecc237c9d61e30f2f8a9d1690c3d1060c53b",
    "03_return_policy_continuity": "6c895810c051f3a4e7a933b4941293a27f55fc96646b4e75d6713b944c4507de",
    "04_out_of_scope": "9b8ac361df2175dc59697b963b53cabc999f795178457fe99c7f7ae7969887ee",
}
NAVY, BLUE = colors.HexColor("#0B2647"), colors.HexColor("#1A5D86")
GRAY, LIGHT = colors.HexColor("#596879"), colors.HexColor("#F0F4F8")
WIDTH = A4[0] - 40 * mm
MARKDOWN = MarkdownIt("commonmark").enable("table")


def styles():
    fonts = Path(reportlab.__file__).parent / "fonts"
    for name, filename in (("Body", "Vera.ttf"), ("BodyBold", "VeraBd.ttf"),
                           ("BodyItalic", "VeraIt.ttf"), ("BodyBoldItalic", "VeraBI.ttf")):
        pdfmetrics.registerFont(TTFont(name, str(fonts / filename)))
    pdfmetrics.registerFontFamily("Body", normal="Body", bold="BodyBold",
                                  italic="BodyItalic", boldItalic="BodyBoldItalic")
    body = ParagraphStyle("Body", fontName="Body", fontSize=8.8, leading=13,
                          textColor=NAVY, spaceAfter=6, splitLongWords=True,
                          allowWidows=0, allowOrphans=0)
    return {
        "body": body,
        "h1": ParagraphStyle("H1", parent=body, fontName="BodyBold", fontSize=19, leading=24,
                             spaceBefore=4, spaceAfter=13, keepWithNext=True),
        "h2": ParagraphStyle("H2", parent=body, fontName="BodyBold", fontSize=12, leading=16,
                             textColor=BLUE, spaceBefore=12, spaceAfter=7, keepWithNext=True),
        "h3": ParagraphStyle("H3", parent=body, fontName="BodyBold", fontSize=10, leading=14,
                             spaceBefore=8, spaceAfter=5, keepWithNext=True),
        "source": ParagraphStyle("Source", parent=body, fontSize=8, textColor=GRAY,
                                 spaceAfter=10, keepWithNext=True),
        "list": ParagraphStyle("List", parent=body, leftIndent=12, bulletIndent=0, spaceAfter=4),
        "quote": ParagraphStyle("Quote", parent=body, leftIndent=10, borderColor=BLUE,
                                borderWidth=0.5, borderPadding=6, backColor=LIGHT, spaceAfter=10),
        "cell": ParagraphStyle("Cell", parent=body, fontSize=8, leading=11, spaceAfter=0),
        "code": ParagraphStyle("Code", fontName="Courier", fontSize=7.2, leading=10,
                               textColor=NAVY, backColor=LIGHT, borderPadding=7,
                               spaceBefore=5, spaceAfter=10),
    }


def link_target(target: str, source: str) -> str:
    if target.startswith(("https://", "http://", "mailto:")):
        return target
    base = REPOSITORY + "/blob/main/" + quote(source, safe="/")
    return urljoin(base, quote(target, safe="/#%"))


def inline(tokens, source: str) -> str:
    result = []
    for token in tokens or []:
        if token.type == "text":
            result.append(html.escape(token.content))
        elif token.type == "code_inline":
            result.append('<font name="Courier" size="8">' + html.escape(token.content) + "</font>")
        elif token.type in {"strong_open", "strong_close", "em_open", "em_close"}:
            tag = "b" if token.type.startswith("strong") else "i"
            result.append(f"<{'/' if token.nesting < 0 else ''}{tag}>")
        elif token.type == "link_open":
            target = html.escape(link_target(token.attrGet("href"), source), quote=True)
            result.append(f'<link href="{target}" color="#1A5D86"><u>')
        elif token.type == "link_close":
            result.append("</u></link>")
        elif token.type == "hardbreak":
            result.append("<br/>")
        elif token.type == "softbreak":
            result.append(" ")
        else:
            raise ValueError(f"Unsupported inline Markdown token: {token.type}")
    return "".join(result)


def render(markdown: str, source: str, style) -> list:
    tokens = MARKDOWN.parse(markdown)
    story, lists = [], []
    pending_bullet, quoted, i = None, False, 0
    while i < len(tokens):
        token = tokens[i]
        if token.type == "heading_open":
            level = min(int(token.tag[1]), 3)
            story.append(Paragraph(inline(tokens[i + 1].children, source), style[f"h{level}"]))
            i += 3
            continue
        if token.type in {"bullet_list_open", "ordered_list_open"}:
            lists.append(None if token.type == "bullet_list_open" else int(token.attrGet("start") or 1))
        elif token.type in {"bullet_list_close", "ordered_list_close"}:
            lists.pop()
        elif token.type == "list_item_open":
            pending_bullet = "-" if lists[-1] is None else f"{lists[-1]}."
            if lists[-1] is not None:
                lists[-1] += 1
        elif token.type == "list_item_close":
            pending_bullet = None
        elif token.type == "blockquote_open":
            quoted = True
        elif token.type == "blockquote_close":
            quoted = False
        elif token.type == "paragraph_open":
            text = inline(tokens[i + 1].children, source)
            paragraph_style = style["quote" if quoted else "list" if lists else "body"]
            story.append(Paragraph(text, paragraph_style, bulletText=pending_bullet))
            pending_bullet = None
            i += 3
            continue
        elif token.type in {"fence", "code_block"}:
            max_chars = int((WIDTH - 16) / pdfmetrics.stringWidth("M", "Courier", style["code"].fontSize))
            lines = []
            for line in token.content.rstrip("\n").splitlines():
                lines.extend(textwrap.wrap(line, width=max_chars, replace_whitespace=False,
                                           drop_whitespace=False, break_on_hyphens=False) or [""])
            story.append(Preformatted("\n".join(lines), style["code"]))
        elif token.type == "table_open":
            rows, row = [], []
            i += 1
            while tokens[i].type != "table_close":
                if tokens[i].type == "tr_open":
                    row = []
                elif tokens[i].type == "inline":
                    row.append(Paragraph(inline(tokens[i].children, source), style["cell"]))
                elif tokens[i].type == "tr_close":
                    rows.append(row)
                i += 1
            table = LongTable(rows, colWidths=[WIDTH / len(rows[0])] * len(rows[0]), repeatRows=1, hAlign="LEFT")
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), LIGHT), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CCD6E0")),
                ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]))
            story.extend([table, Spacer(1, 8)])
        elif token.type == "hr":
            story.append(HRFlowable(width="100%", color=LIGHT))
        else:
            raise ValueError(f"Unsupported block Markdown token: {token.type}")
        i += 1
    return story


def documents():
    docs = [(p, (ROOT / p).read_text(encoding="utf-8"), False) for p in SOURCE_FILES]
    for name, expected_hash in CONVERSATIONS.items():
        source = f"examples/reviewed/{name}.md"
        original = (ROOT / source).read_bytes()
        if hashlib.sha256(original).hexdigest() != expected_hash:
            raise ValueError(f"Review the English translation after source changes: {source}")
        translated = (ROOT / f"docs/translations/{name}.en.md").read_text(encoding="utf-8")
        text = original.decode("utf-8")
        for label in ("Customer", "Assistant"):
            assert text.count(f"**{label}:**") == translated.count(f"**{label}:**"), source
        # Bind translations to source facts; changing a transcript requires re-review.
        for pattern in (r"R\$\s*[\d.,]+", r"\(ID: \d+\)", r"gemini-[\w.\-]+",
                        r"\d{4}-\d{2}-\d{2}T[^\s]+", r"\d{2}/\d{2}/\d{4}",
                        r"[\w.]+@[\w.]+", r"BRJL\d+BR"):
            assert re.findall(pattern, text) == re.findall(pattern, translated), (source, pattern)
        docs.append((source, translated, True))
    return docs


class DocumentationPDF(SimpleDocTemplate):
    def afterFlowable(self, flowable):
        if hasattr(flowable, "source_key"):
            key = flowable.source_key
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(flowable.source_label, key, level=0)
            self.notify("TOCEntry", (0, flowable.source_label, self.page, key))


def footer(canvas, document):
    canvas.saveState()
    canvas.setStrokeColor(LIGHT)
    canvas.line(20 * mm, 16 * mm, A4[0] - 20 * mm, 16 * mm)
    canvas.setFont("Body", 7)
    canvas.setFillColor(GRAY)
    canvas.drawString(20 * mm, 11 * mm, "Pammela Vicenti Ribeiro | README and Documentation")
    canvas.drawRightString(A4[0] - 20 * mm, 11 * mm, f"Page {document.page}")
    canvas.restoreState()


def build() -> Path:
    style = styles()
    docs = documents()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    document = DocumentationPDF(str(OUTPUT), pagesize=A4, rightMargin=20 * mm, leftMargin=20 * mm,
                                topMargin=18 * mm, bottomMargin=23 * mm,
                                title="Emporio da Musica - Complete README and Documentation",
                                author="Pammela Vicenti Ribeiro", lang="en-US")
    story = [
        Spacer(1, 12 * mm), Paragraph("Project README<br/>and Documentation", style["h1"]),
        Paragraph("<b>Pammela Vicenti Ribeiro</b><br/>AI Engineer - Full-Stack for Generative AI Applications", style["body"]),
        Spacer(1, 6 * mm), Paragraph("Empório da Música AI Support Assistant", style["h2"]),
        Paragraph(f'Public repository: <link href="{REPOSITORY}" color="#1A5D86"><u>{REPOSITORY}</u></link>', style["body"]),
        Paragraph("This document contains the complete README, data-quality notes, conversation review, and four real conversation transcripts, in that order. Markdown headings, lists, links, code blocks, and tables are formatted for reading.", style["body"]),
        Paragraph("The documentation is reproduced in full. The conversations were originally executed in Brazilian Portuguese and are presented as complete English translations. These translations are not new model executions. Product names, identifiers, timestamps, and BRL values are retained; the original reviewed files remain unchanged in the repository. The verification e-mail is synthetic challenge data. No credentials or raw tool JSON are included.", style["quote"]),
        Paragraph("Contents", style["h2"]),
    ]
    toc = TableOfContents()
    toc.levelStyles = [ParagraphStyle("TOC", parent=style["body"], leading=16, spaceBefore=4, rightIndent=20)]
    story.append(toc)
    for index, (source, content, translated) in enumerate(docs, start=1):
        story.append(PageBreak())
        label = f"{index}. {source}"
        banner = Paragraph(html.escape(label), style["source"])
        banner.source_key, banner.source_label = f"source-{index}", label
        story.append(banner)
        if translated:
            story.append(Paragraph("Complete English translation of the original real Portuguese transcript. Original source unchanged.", style["source"]))
        story.extend(render(content, source, style))
    document.multiBuild(story, onFirstPage=footer, onLaterPages=footer)
    return OUTPUT


if __name__ == "__main__":
    print(build())

