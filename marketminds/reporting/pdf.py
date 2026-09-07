"""Render a completed analysis as a PDF.

The agents produce markdown, so this converts that markdown into ReportLab
flowables rather than shelling out to a browser: pure Python, no system
packages, and it works unchanged inside the slim container image.

One detail drives more of this file than you would expect — the **rupee
sign**. Every price in an Indian report is `₹`, and none of ReportLab's
built-in fonts contain U+20B9 (they predate the glyph, introduced in 2010).
A missing glyph renders as a black box, so the font search below looks for a
Unicode TTF and, if the environment genuinely has none, degrades the symbol
to "Rs." rather than printing squares over every price.
"""

from __future__ import annotations

import io
import logging
import os
import re
from datetime import datetime
from typing import Iterable, List, Optional, Sequence, Tuple

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

logger = logging.getLogger(__name__)

RUPEE = "\u20b9"

# Palette mirrors the web UI so a downloaded report and the screen agree.
INK = colors.HexColor("#1c1c1e")
INK_SOFT = colors.HexColor("#52525b")
INK_MUTED = colors.HexColor("#8b8b93")
ACCENT = colors.HexColor("#4f46e5")
LINE = colors.HexColor("#e7e5e1")
SURFACE = colors.HexColor("#f5f4f1")
BUY = colors.HexColor("#047857")
SELL = colors.HexColor("#be123c")
HOLD = colors.HexColor("#a16207")

# Fonts that carry U+20B9, most portable first. DejaVu ships in the image via
# fonts-dejavu-core; the rest cover a developer running this on a desktop.
_FONT_CANDIDATES: Sequence[Tuple[str, str]] = (
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
     "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
     "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ("C:/Windows/Fonts/calibri.ttf", "C:/Windows/Fonts/calibrib.ttf"),
    ("/System/Library/Fonts/Supplemental/Arial.ttf",
     "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
)

_FONT_CACHE: Optional[Tuple[str, str, bool]] = None


def _resolve_fonts() -> Tuple[str, str, bool]:
    """Register a Unicode font pair, returning (regular, bold, has_rupee).

    Falls back to Helvetica when no candidate exists. The caller uses the
    third element to decide whether the rupee sign can be printed at all.
    """
    global _FONT_CACHE
    if _FONT_CACHE is not None:
        return _FONT_CACHE

    for regular, bold in _FONT_CANDIDATES:
        if not (os.path.exists(regular) and os.path.exists(bold)):
            continue
        try:
            pdfmetrics.registerFont(TTFont("MMSans", regular))
            pdfmetrics.registerFont(TTFont("MMSans-Bold", bold))
            pdfmetrics.registerFontFamily(
                "MMSans", normal="MMSans", bold="MMSans-Bold",
                italic="MMSans", boldItalic="MMSans-Bold",
            )
            _FONT_CACHE = ("MMSans", "MMSans-Bold", True)
            logger.info("PDF fonts: using %s", regular)
            return _FONT_CACHE
        except Exception as exc:
            logger.info("Could not register %s: %s", regular, exc)

    logger.warning(
        "No Unicode TTF found; PDFs fall back to Helvetica and the rupee sign "
        "is written as 'Rs.'. Install fonts-dejavu-core to fix."
    )
    _FONT_CACHE = ("Helvetica", "Helvetica-Bold", False)
    return _FONT_CACHE


# --------------------------------------------------------------------------
# Markdown -> ReportLab
# --------------------------------------------------------------------------

_ESCAPES = ((("&", "&amp;"), ("<", "&lt;"), (">", "&gt;")))


def _escape(text: str) -> str:
    for old, new in _ESCAPES:
        text = text.replace(old, new)
    return text


def _inline(text: str, has_rupee: bool) -> str:
    """Convert inline markdown to the mini-HTML ReportLab paragraphs accept."""
    if not has_rupee:
        text = text.replace(RUPEE, "Rs.")
    text = _escape(text)
    # Order matters: bold before italic, so ** is not eaten by *. The negative
    # lookaheads are what keep asymmetric emphasis well formed — models write
    # things like "***Note:** ...*", and without them the bold and italic spans
    # cross into <b><i>x</b></i>, which the PDF renderer rejects outright.
    text = re.sub(r"\*\*\*(?!\*)(.+?)\*\*\*", r"<b><i>\1</i></b>", text)
    text = re.sub(r"\*\*(?!\*)(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"<i>\1</i>", text)
    text = re.sub(r"__(.+?)__", r"<b>\1</b>", text)
    text = re.sub(r"`(.+?)`", r'<font face="Courier">\1</font>', text)
    # Markdown links: keep the label, drop the URL (a PDF reader cannot follow
    # a bare reference usefully and the raw URLs are long and noisy).
    text = re.sub(r"\[(.+?)\]\((.+?)\)", r"\1", text)
    return text



def _para(text: str, style) -> Paragraph:
    """Build a Paragraph, falling back to plain text if the markup is invalid.

    The inline converter handles the malformed emphasis models actually emit,
    but it cannot anticipate every shape agent output takes. Losing bold on one
    line is acceptable; failing to produce the report is not.
    """
    try:
        return Paragraph(text, style)
    except Exception as exc:
        logger.info("Paragraph markup rejected, using plain text: %s", exc)
        return Paragraph(_escape(re.sub(r"<[^>]+>", "", text)), style)


_TABLE_ROW = re.compile(r"^\s*\|(.+)\|\s*$")
_TABLE_SEP = re.compile(r"^\s*\|[\s:\-|]+\|\s*$")


def _split_row(line: str) -> List[str]:
    inner = _TABLE_ROW.match(line).group(1)
    return [c.strip() for c in inner.split("|")]


def _build_table(rows: List[List[str]], styles, has_rupee: bool):
    """Render a markdown pipe table, wrapping every cell so it never clips."""
    if not rows:
        return None

    width = max(len(r) for r in rows)
    body = []
    for i, row in enumerate(rows):
        padded = row + [""] * (width - len(row))
        style = styles["th"] if i == 0 else styles["td"]
        body.append([_para(_inline(c, has_rupee), style) for c in padded])

    # Available text width on A4 with the margins set below.
    usable = A4[0] - 36 * mm
    table = Table(body, colWidths=[usable / width] * width, repeatRows=1)
    table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), SURFACE),
            ("GRID", (0, 0), (-1, -1), 0.4, LINE),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ])
    )
    return table


def markdown_to_flowables(md: str, styles: dict, has_rupee: bool) -> List:
    """Convert an agent's markdown report into printable flowables."""
    flowables: List = []
    lines = (md or "").replace("\r\n", "\n").split("\n")

    paragraph: List[str] = []
    bullets: List[str] = []
    table_rows: List[List[str]] = []
    in_code = False
    code: List[str] = []

    def flush_paragraph():
        if paragraph:
            flowables.append(_para(_inline(" ".join(paragraph), has_rupee), styles["body"]))
            flowables.append(Spacer(1, 4))
            paragraph.clear()

    def flush_bullets():
        if bullets:
            flowables.append(
                ListFlowable(
                    [ListItem(_para(_inline(b, has_rupee), styles["body"]), leftIndent=12)
                     for b in bullets],
                    bulletType="bullet", start="•", leftIndent=14,
                    bulletFontSize=6, bulletOffsetY=-2,
                )
            )
            flowables.append(Spacer(1, 5))
            bullets.clear()

    def flush_table():
        if table_rows:
            table = _build_table(table_rows, styles, has_rupee)
            if table is not None:
                flowables.append(Spacer(1, 3))
                flowables.append(table)
                flowables.append(Spacer(1, 7))
            table_rows.clear()

    def flush_code():
        if code:
            flowables.append(
                _para(_escape("\n".join(code)).replace("\n", "<br/>"), styles["code"])
            )
            flowables.append(Spacer(1, 5))
            code.clear()

    def flush_all():
        flush_paragraph(); flush_bullets(); flush_table(); flush_code()

    for raw in lines:
        line = raw.rstrip()

        if line.strip().startswith("```"):
            if in_code:
                flush_code()
            else:
                flush_paragraph(); flush_bullets(); flush_table()
            in_code = not in_code
            continue
        if in_code:
            code.append(raw)
            continue

        if _TABLE_SEP.match(line):
            continue                      # the |---|---| alignment row
        if _TABLE_ROW.match(line):
            flush_paragraph(); flush_bullets()
            table_rows.append(_split_row(line))
            continue
        flush_table()

        if not line.strip():
            flush_paragraph(); flush_bullets()
            continue

        heading = re.match(r"^(#{1,6})\s+(.*)$", line)
        if heading:
            flush_all()
            level = min(len(heading.group(1)), 4)
            flowables.append(Spacer(1, 6))
            flowables.append(_para(_inline(heading.group(2), has_rupee), styles[f"h{level}"]))
            flowables.append(Spacer(1, 3))
            continue

        if re.match(r"^\s*([-*_])\1{2,}\s*$", line):
            flush_all()
            flowables.append(Spacer(1, 4))
            flowables.append(HRFlowable(width="100%", thickness=0.5, color=LINE))
            flowables.append(Spacer(1, 6))
            continue

        bullet = re.match(r"^\s*[-*+]\s+(.*)$", line)
        if bullet:
            flush_paragraph()
            bullets.append(bullet.group(1))
            continue

        numbered = re.match(r"^\s*\d+[.)]\s+(.*)$", line)
        if numbered:
            flush_paragraph()
            bullets.append(numbered.group(1))
            continue

        quote = re.match(r"^\s*>\s?(.*)$", line)
        if quote:
            flush_all()
            flowables.append(_para(_inline(quote.group(1), has_rupee), styles["quote"]))
            flowables.append(Spacer(1, 4))
            continue

        flush_bullets()
        paragraph.append(line.strip())

    flush_all()
    return flowables


# --------------------------------------------------------------------------
# Document
# --------------------------------------------------------------------------

def _styles(regular: str, bold: str) -> dict:
    base = getSampleStyleSheet()["Normal"]

    def make(name, **kw):
        # Callers may override the face (headings use bold, code uses Courier),
        # so pull it from kwargs rather than passing it twice.
        kw.setdefault("fontName", regular)
        kw.setdefault("textColor", INK)
        kw.setdefault("alignment", TA_LEFT)
        return ParagraphStyle(name, parent=base, **kw)

    return {
        "title": make("mm-title", fontName=bold, fontSize=26, leading=30, spaceAfter=2),
        "subtitle": make("mm-subtitle", fontSize=11, leading=15, textColor=INK_MUTED),
        "rating": make("mm-rating", fontName=bold, fontSize=30, leading=34),
        "h1": make("mm-h1", fontName=bold, fontSize=16, leading=20, textColor=INK),
        "h2": make("mm-h2", fontName=bold, fontSize=13, leading=17, textColor=INK),
        "h3": make("mm-h3", fontName=bold, fontSize=11, leading=15, textColor=INK),
        "h4": make("mm-h4", fontName=bold, fontSize=10, leading=14, textColor=INK_SOFT),
        "body": make("mm-body", fontSize=9.5, leading=14, textColor=INK_SOFT),
        "quote": make("mm-quote", fontSize=9.5, leading=14, textColor=INK_MUTED,
                      leftIndent=10, borderPadding=0),
        "code": make("mm-code", fontName="Courier", fontSize=8, leading=11,
                     backColor=SURFACE, borderPadding=5, textColor=INK),
        "th": make("mm-th", fontName=bold, fontSize=8.5, leading=11, textColor=INK),
        "td": make("mm-td", fontSize=8.5, leading=11, textColor=INK_SOFT),
        "meta_k": make("mm-metak", fontSize=8, leading=11, textColor=INK_MUTED),
        "meta_v": make("mm-metav", fontName=bold, fontSize=9.5, leading=12, textColor=INK),
        "footer": make("mm-footer", fontSize=7.5, leading=10, textColor=INK_MUTED),
    }


def _rating_colour(rating: str):
    r = (rating or "").lower()
    if "overweight" in r or "buy" in r:
        return BUY
    if "underweight" in r or "sell" in r:
        return SELL
    return HOLD


def _page_furniture(ticker: str, regular: str):
    """Draw the footer — page number and the research-only disclaimer."""
    def draw(canvas, doc):
        canvas.saveState()
        canvas.setFont(regular, 7.5)
        canvas.setFillColor(INK_MUTED)
        canvas.setStrokeColor(LINE)
        canvas.line(18 * mm, 14 * mm, A4[0] - 18 * mm, 14 * mm)
        canvas.drawString(18 * mm, 10 * mm,
                          f"MarketMinds · {ticker} · research and educational use only, not financial advice")
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {canvas.getPageNumber()}")
        canvas.restoreState()
    return draw


def _cover(meta: dict, styles: dict, has_rupee: bool) -> List:
    """Title block: what was analysed, the call, and how it was produced."""
    rating = meta.get("rating") or "—"
    flow: List = [
        Spacer(1, 8),
        Paragraph(_escape(meta.get("ticker", "")), styles["title"]),
        Paragraph(
            f"Multi-agent equity research &nbsp;·&nbsp; analysed as of {_escape(str(meta.get('trade_date','')))}",
            styles["subtitle"],
        ),
        Spacer(1, 14),
    ]

    rating_style = ParagraphStyle(
        "mm-rating-c", parent=styles["rating"], textColor=_rating_colour(rating)
    )
    box = Table(
        [[Paragraph("FINAL POSITION RATING", styles["meta_k"])],
         [Paragraph(_escape(rating), rating_style)]],
        colWidths=[A4[0] - 36 * mm],
    )
    box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), SURFACE),
        ("BOX", (0, 0), (-1, -1), 0.5, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (0, 0), 10),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 12),
    ]))
    flow += [box, Spacer(1, 16)]

    pairs = [
        ("Exchange", meta.get("exchange") or "NSE"),
        ("Benchmark", meta.get("benchmark") or "^NSEI"),
        ("Provider", meta.get("provider") or "—"),
        ("Deep model", meta.get("deep_model") or "—"),
        ("Quick model", meta.get("quick_model") or "—"),
        ("Analyst team", meta.get("analysts") or "—"),
        ("Debate rounds", meta.get("rounds") or "—"),
        ("Generated", meta.get("generated") or ""),
    ]
    cells = []
    for i in range(0, len(pairs), 2):
        row = []
        for k, v in pairs[i:i + 2]:
            row.append(Paragraph(f"{_escape(k)}<br/><font size=9.5 color='#1c1c1e'>"
                                 f"<b>{_escape(str(v))}</b></font>", styles["meta_k"]))
        if len(row) == 1:
            row.append(Paragraph("", styles["meta_k"]))
        cells.append(row)

    usable = A4[0] - 36 * mm
    meta_table = Table(cells, colWidths=[usable / 2] * 2)
    meta_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ]))
    flow += [meta_table, Spacer(1, 10), HRFlowable(width="100%", thickness=0.5, color=LINE)]

    if meta.get("usage"):
        flow += [Spacer(1, 6), Paragraph(_escape(meta["usage"]), styles["footer"])]

    flow += [
        Spacer(1, 12),
        Paragraph(
            "This report was produced by an automated multi-agent system. It is "
            "research and educational material only, not financial, investment or "
            "trading advice. Output varies with the model, data quality and other "
            "non-deterministic factors. Do your own due diligence before risking capital.",
            styles["footer"],
        ),
    ]
    return flow


def build_run_pdf(
    *,
    ticker: str,
    trade_date: str,
    rating: Optional[str],
    sections: Iterable[Tuple[str, str]],
    meta: Optional[dict] = None,
) -> bytes:
    """Build the PDF for one run.

    ``sections`` is an ordered sequence of ``(heading, markdown)`` pairs; empty
    bodies are skipped so a partial run does not print blank pages.
    """
    regular, bold, has_rupee = _resolve_fonts()
    styles = _styles(regular, bold)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=20 * mm,
        title=f"MarketMinds — {ticker} ({trade_date})",
        author="MarketMinds",
        subject=f"Multi-agent equity research for {ticker}",
    )

    info = dict(meta or {})
    info.setdefault("ticker", ticker)
    info.setdefault("trade_date", trade_date)
    info.setdefault("rating", rating)
    info.setdefault("generated", datetime.now().strftime("%d %b %Y, %H:%M"))

    story: List = _cover(info, styles, has_rupee)

    first = True
    for heading, body in sections:
        if not (body or "").strip():
            continue
        story.append(PageBreak() if first else Spacer(1, 14))
        first = False
        story.append(
            KeepTogether([
                Paragraph(_escape(heading), styles["h1"]),
                Spacer(1, 2),
                HRFlowable(width="100%", thickness=0.6, color=ACCENT),
                Spacer(1, 8),
            ])
        )
        story.extend(markdown_to_flowables(body, styles, has_rupee))

    if first:
        story.append(PageBreak())
        story.append(Paragraph("No report sections were produced for this run.", styles["body"]))

    furniture = _page_furniture(ticker, regular)
    doc.build(story, onFirstPage=furniture, onLaterPages=furniture)
    return buffer.getvalue()


def run_pdf_filename(ticker: str, trade_date: str) -> str:
    """A filesystem-safe download name."""
    safe = re.sub(r"[^A-Za-z0-9._-]", "-", f"{ticker}-{trade_date}")
    return f"marketminds-{safe}.pdf"
