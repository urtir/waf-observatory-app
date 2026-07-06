import re
from datetime import datetime
from pathlib import Path
from textwrap import wrap
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import HRFlowable, Paragraph, Preformatted, SimpleDocTemplate, Spacer, Table, TableStyle


def _apply_inline_md(text: str) -> str:
    parts = []
    last = 0
    for m in re.finditer(r"\*\*(.+?)\*\*|`(.+?)`|\*(.+?)\*", text):
        parts.append(text[last:m.start()])
        if m.group(1) is not None:
            parts.append(f"<b>{m.group(1)}</b>")
        elif m.group(2) is not None:
            parts.append(f'<font face="Courier">{m.group(2)}</font>')
        elif m.group(3) is not None:
            parts.append(f"<i>{m.group(3)}</i>")
        last = m.end()
    parts.append(text[last:])
    return "".join(parts)


def _md_to_reportlab(text: str) -> list:
    text = text.replace("<", "&lt;").replace(">", "&gt;")
    lines = text.split("\n")
    flowables = []
    para_lines = []

    def flush_para():
        if para_lines:
            joined = " ".join(para_lines)
            joined = _apply_inline_md(joined)
            flowables.append(Paragraph(joined, _md_body_style))
            para_lines.clear()

    for line in lines:
        stripped = line.strip()

        if not stripped:
            flush_para()
            continue

        if stripped.startswith("### "):
            flush_para()
            heading_text = _apply_inline_md(stripped[4:])
            flowables.append(Paragraph(heading_text, _md_h3_style))
            flowables.append(Spacer(1, 0.1 * cm))
        elif stripped.startswith("## "):
            flush_para()
            heading_text = _apply_inline_md(stripped[3:])
            flowables.append(Paragraph(heading_text, _md_h2_style))
            flowables.append(Spacer(1, 0.15 * cm))
        elif stripped.startswith("# "):
            flush_para()
            heading_text = _apply_inline_md(stripped[2:])
            flowables.append(Paragraph(heading_text, _md_h1_style))
            flowables.append(Spacer(1, 0.2 * cm))
        elif stripped.startswith("---") or stripped.startswith("***"):
            flush_para()
            flowables.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))
        elif stripped.startswith("- ") or stripped.startswith("* "):
            flush_para()
            item_text = _apply_inline_md(stripped[2:])
            flowables.append(Paragraph(f"\u2022  {item_text}", _md_bullet_style))
        elif re.match(r"^\d+\.\s", stripped):
            flush_para()
            item_text = re.sub(r"^\d+\.\s", "", stripped)
            item_text = _apply_inline_md(item_text)
            num = re.match(r"^(\d+)", stripped).group(1)
            flowables.append(Paragraph(f"{num}.  {item_text}", _md_bullet_style))
        else:
            para_lines.append(stripped)

    flush_para()
    return flowables


def _fmt_float(value: object, digits: int = 4) -> str:
    if value is None:
        return "N/A"
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return str(value)


def _safe_text(value: object) -> str:
    return str(value or "").strip()


def _wrap_raw_log_text(text: str, width: int = 88) -> str:
    wrapped_lines: list[str] = []
    for line in text.splitlines():
        chunks = wrap(
            line,
            width=width,
            replace_whitespace=False,
            drop_whitespace=False,
            break_long_words=True,
            break_on_hyphens=True,
        )
        if not chunks:
            wrapped_lines.append("")
        else:
            wrapped_lines.extend(chunks)
    return "\n".join(wrapped_lines)


def _normalize_paragraph_text(text: str) -> str:
    return " ".join(text.split())


def export_analysis_to_pdf(output_path: Path, rows: list[dict], title: str, executive_summary: str | None = None) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=1.6 * cm,
        rightMargin=1.6 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title=title,
        author="WAF Observatory",
    )

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=19,
        spaceAfter=8,
    )
    h2 = ParagraphStyle(
        "SectionTitle",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=14,
        spaceAfter=4,
        spaceBefore=8,
    )
    normal = ParagraphStyle(
        "Body",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        alignment=TA_JUSTIFY,
        wordWrap="LTR",
    )
    small = ParagraphStyle(
        "Small",
        parent=normal,
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#333333"),
    )
    raw_style = ParagraphStyle(
        "RawLabel",
        parent=normal,
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=11,
        textColor=colors.HexColor("#1f4e79"),
    )
    raw_block_style = ParagraphStyle(
        "RawBlock",
        parent=small,
        fontName="Courier",
        fontSize=7.1,
        leading=8.8,
        leftIndent=0.35 * cm,
        rightIndent=0.35 * cm,
        borderColor=colors.HexColor("#d0d7de"),
        borderWidth=0.5,
        borderPadding=6,
        backColor=colors.HexColor("#fbfcfe"),
    )
    analysis_block_style = ParagraphStyle(
        "AnalysisBlock",
        parent=normal,
        leftIndent=0.35 * cm,
        rightIndent=0.35 * cm,
        borderColor=colors.HexColor("#d0d7de"),
        borderWidth=0.5,
        borderPadding=6,
        backColor=colors.white,
    )
    golden_block_style = ParagraphStyle(
        "GoldenBlock",
        parent=normal,
        leftIndent=0.35 * cm,
        rightIndent=0.35 * cm,
        borderColor=colors.HexColor("#d0d7de"),
        borderWidth=0.5,
        borderPadding=6,
        backColor=colors.HexColor("#f8fafc"),
    )

    story = []
    story.append(Paragraph(escape(title), h1))
    story.append(
        Paragraph(
            f"Dicetak pada: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Total transaksi: {len(rows)}",
            small,
        )
    )
    story.append(Spacer(1, 0.35 * cm))

    for idx, row in enumerate(rows, start=1):
        tx_id = _safe_text(row.get("tx_id")) or "-"
        model_key = _safe_text(row.get("model_key")) or "-"
        latency_ms = _fmt_float(row.get("latency_ms"), 3)

        story.append(Paragraph(f"Transaksi #{idx} - TXID: {escape(tx_id)}", h2))

        meta_data = [
            ["Record ID", _safe_text(row.get("id")) or "-"],
            ["Model", model_key],
            ["Latency (ms)", latency_ms],
        ]
        meta_table = Table(meta_data, colWidths=[3.2 * cm, 12.0 * cm])
        meta_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f3f6fa")),
                    ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#0b3a60")),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d0d7de")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(meta_table)
        story.append(Spacer(1, 0.2 * cm))

        raw_log = _safe_text(row.get("raw_log")) or "(raw log kosong)"
        wrapped_raw_log = _wrap_raw_log_text(raw_log)
        story.append(Paragraph("Raw Log", raw_style))
        story.append(Preformatted(wrapped_raw_log, raw_block_style))
        story.append(Spacer(1, 0.2 * cm))

        story.append(Paragraph("Penjelasan (Generated Summary)", raw_style))
        generated_summary = escape(_normalize_paragraph_text(_safe_text(row.get("generated_summary")) or "(kosong)"))
        story.append(Paragraph(generated_summary, analysis_block_style))

        golden_summary = _safe_text(row.get("golden_summary"))
        if golden_summary:
            story.append(Spacer(1, 0.1 * cm))
            story.append(Paragraph("Referensi (Golden Summary)", raw_style))
            story.append(Paragraph(escape(_normalize_paragraph_text(golden_summary)), golden_block_style))

        if idx < len(rows):
            story.append(Spacer(1, 0.45 * cm))
            sep = Table([[""]], colWidths=[15.2 * cm], rowHeights=[0.02 * cm])
            sep.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#d9dee5"))]))
            story.append(sep)
            story.append(Spacer(1, 0.35 * cm))

    doc.build(story)
    return output_path


def export_analysis_to_pdf_with_summary(output_path: Path, rows: list[dict], title: str, executive_summary: str | None = None) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=1.6 * cm,
        rightMargin=1.6 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title=title,
        author="WAF Observatory",
    )

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=19,
        spaceAfter=8,
    )
    h2 = ParagraphStyle(
        "SectionTitle",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=14,
        spaceAfter=4,
        spaceBefore=8,
    )
    normal = ParagraphStyle(
        "Body",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        alignment=TA_JUSTIFY,
        wordWrap="LTR",
    )
    small = ParagraphStyle(
        "Small",
        parent=normal,
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#333333"),
    )
    exec_summary_style = ParagraphStyle(
        "ExecSummary",
        parent=normal,
        fontSize=9,
        leading=13,
        alignment=TA_JUSTIFY,
        leftIndent=0.2 * cm,
        rightIndent=0.2 * cm,
        spaceBefore=4,
        spaceAfter=4,
    )

    global _md_body_style, _md_h1_style, _md_h2_style, _md_h3_style, _md_bullet_style
    _md_body_style = ParagraphStyle(
        "MDBody",
        parent=exec_summary_style,
        spaceBefore=2,
        spaceAfter=6,
    )
    _md_h1_style = ParagraphStyle(
        "MDH1",
        parent=exec_summary_style,
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        spaceBefore=10,
        spaceAfter=4,
    )
    _md_h2_style = ParagraphStyle(
        "MDH2",
        parent=exec_summary_style,
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        spaceBefore=8,
        spaceAfter=3,
    )
    _md_h3_style = ParagraphStyle(
        "MDH3",
        parent=exec_summary_style,
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=12,
        spaceBefore=6,
        spaceAfter=2,
    )
    _md_bullet_style = ParagraphStyle(
        "MDBullet",
        parent=exec_summary_style,
        leftIndent=1.0 * cm,
        firstLineIndent=-0.5 * cm,
        spaceBefore=1,
        spaceAfter=1,
    )

    raw_style = ParagraphStyle(
        "RawLabel",
        parent=normal,
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=11,
        textColor=colors.HexColor("#1f4e79"),
    )
    raw_block_style = ParagraphStyle(
        "RawBlock",
        parent=small,
        fontName="Courier",
        fontSize=7.1,
        leading=8.8,
        leftIndent=0.35 * cm,
        rightIndent=0.35 * cm,
        borderColor=colors.HexColor("#d0d7de"),
        borderWidth=0.5,
        borderPadding=6,
        backColor=colors.HexColor("#fbfcfe"),
    )
    analysis_block_style = ParagraphStyle(
        "AnalysisBlock",
        parent=normal,
        leftIndent=0.35 * cm,
        rightIndent=0.35 * cm,
        borderColor=colors.HexColor("#d0d7de"),
        borderWidth=0.5,
        borderPadding=6,
        backColor=colors.white,
    )
    golden_block_style = ParagraphStyle(
        "GoldenBlock",
        parent=normal,
        leftIndent=0.35 * cm,
        rightIndent=0.35 * cm,
        borderColor=colors.HexColor("#d0d7de"),
        borderWidth=0.5,
        borderPadding=6,
        backColor=colors.HexColor("#f8fafc"),
    )

    story = []
    story.append(Paragraph(escape(title), h1))
    story.append(
        Paragraph(
            f"Dicetak pada: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Total transaksi: {len(rows)}",
            small,
        )
    )
    story.append(Spacer(1, 0.35 * cm))

    for idx, row in enumerate(rows, start=1):
        tx_id = _safe_text(row.get("tx_id")) or "-"
        model_key = _safe_text(row.get("model_key")) or "-"
        latency_ms = _fmt_float(row.get("latency_ms"), 3)

        story.append(Paragraph(f"Transaksi #{idx} - TXID: {escape(tx_id)}", h2))

        meta_data = [
            ["Record ID", _safe_text(row.get("id")) or "-"],
            ["Model", model_key],
            ["Latency (ms)", latency_ms],
        ]
        meta_table = Table(meta_data, colWidths=[3.2 * cm, 12.0 * cm])
        meta_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f3f6fa")),
                    ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#0b3a60")),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d0d7de")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(meta_table)
        story.append(Spacer(1, 0.2 * cm))

        raw_log = _safe_text(row.get("raw_log")) or "(raw log kosong)"
        wrapped_raw_log = _wrap_raw_log_text(raw_log)
        story.append(Paragraph("Raw Log", raw_style))
        story.append(Preformatted(wrapped_raw_log, raw_block_style))
        story.append(Spacer(1, 0.2 * cm))

        story.append(Paragraph("Penjelasan (Generated Summary)", raw_style))
        generated_summary = escape(_normalize_paragraph_text(_safe_text(row.get("generated_summary")) or "(kosong)"))
        story.append(Paragraph(generated_summary, analysis_block_style))

        golden_summary = _safe_text(row.get("golden_summary"))
        if golden_summary:
            story.append(Spacer(1, 0.1 * cm))
            story.append(Paragraph("Referensi (Golden Summary)", raw_style))
            story.append(Paragraph(escape(_normalize_paragraph_text(golden_summary)), golden_block_style))

        if idx < len(rows):
            story.append(Spacer(1, 0.45 * cm))
            sep = Table([[""]], colWidths=[15.2 * cm], rowHeights=[0.02 * cm])
            sep.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#d9dee5"))]))
            story.append(sep)
            story.append(Spacer(1, 0.35 * cm))

    if executive_summary:
        story.append(Spacer(1, 0.6 * cm))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1f4e79")))
        story.append(Spacer(1, 0.3 * cm))
        story.append(Paragraph("Executive Summary", h1))
        story.append(
            Paragraph(
                f"Ringkasan komprehensif dari {len(rows)} transaksi log serangan yang dianalisis.",
                small,
            )
        )
        story.append(Spacer(1, 0.3 * cm))

        md_flowables = _md_to_reportlab(executive_summary)
        story.extend(md_flowables)

    doc.build(story)
    return output_path


def export_single_analysis_to_pdf(output_path: Path, row: dict) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=1.6 * cm,
        rightMargin=1.6 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title="Detail Analisis WAF",
        author="WAF Observatory",
    )

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=19,
        spaceAfter=8,
    )
    h2 = ParagraphStyle(
        "SectionTitle",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=14,
        spaceAfter=4,
        spaceBefore=8,
    )
    normal = ParagraphStyle(
        "Body",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        alignment=TA_JUSTIFY,
        wordWrap="LTR",
    )
    small = ParagraphStyle(
        "Small",
        parent=normal,
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#333333"),
    )
    raw_style = ParagraphStyle(
        "RawLabel",
        parent=normal,
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=11,
        textColor=colors.HexColor("#1f4e79"),
    )
    raw_block_style = ParagraphStyle(
        "RawBlock",
        parent=small,
        fontName="Courier",
        fontSize=7.1,
        leading=8.8,
        leftIndent=0.35 * cm,
        rightIndent=0.35 * cm,
        borderColor=colors.HexColor("#d0d7de"),
        borderWidth=0.5,
        borderPadding=6,
        backColor=colors.HexColor("#fbfcfe"),
    )
    analysis_block_style = ParagraphStyle(
        "AnalysisBlock",
        parent=normal,
        leftIndent=0.35 * cm,
        rightIndent=0.35 * cm,
        borderColor=colors.HexColor("#d0d7de"),
        borderWidth=0.5,
        borderPadding=6,
        backColor=colors.white,
    )

    story = []
    tx_id = _safe_text(row.get("tx_id")) or "-"
    story.append(Paragraph(escape(f"Detail Analisis - TXID: {tx_id}"), h1))
    story.append(
        Paragraph(
            f"Dicetak pada: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            small,
        )
    )
    story.append(Spacer(1, 0.35 * cm))

    meta_data = [
        ["Record ID", _safe_text(row.get("id")) or "-"],
        ["TXID", tx_id],
        ["Model", _safe_text(row.get("model_key")) or "-"],
        ["Latency (ms)", _fmt_float(row.get("latency_ms"), 3)],
        ["Waktu", _safe_text(row.get("created_at")) or "-"],
    ]
    meta_table = Table(meta_data, colWidths=[3.2 * cm, 12.0 * cm])
    meta_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f3f6fa")),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#0b3a60")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d0d7de")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(meta_table)
    story.append(Spacer(1, 0.3 * cm))

    raw_log = _safe_text(row.get("raw_log")) or "(raw log kosong)"
    wrapped_raw_log = _wrap_raw_log_text(raw_log)
    story.append(Paragraph("Raw Log", raw_style))
    story.append(Preformatted(wrapped_raw_log, raw_block_style))
    story.append(Spacer(1, 0.3 * cm))

    story.append(Paragraph("Penjelasan (Generated Summary)", raw_style))
    generated_summary = escape(_normalize_paragraph_text(_safe_text(row.get("generated_summary")) or "(kosong)"))
    story.append(Paragraph(generated_summary, analysis_block_style))

    golden_summary = _safe_text(row.get("golden_summary"))
    if golden_summary:
        story.append(Spacer(1, 0.15 * cm))
        golden_block_style = ParagraphStyle(
            "GoldenBlock",
            parent=normal,
            leftIndent=0.35 * cm,
            rightIndent=0.35 * cm,
            borderColor=colors.HexColor("#d0d7de"),
            borderWidth=0.5,
            borderPadding=6,
            backColor=colors.HexColor("#f8fafc"),
        )
        story.append(Paragraph("Referensi (Golden Summary)", raw_style))
        story.append(Paragraph(escape(_normalize_paragraph_text(golden_summary)), golden_block_style))

    doc.build(story)
    return output_path


def export_compare_stats_to_pdf(
    output_path: Path,
    title: str,
    summary_rows: list[dict],
    shapiro_rows: list[dict],
    descriptive_rows: list[dict],
    inferential_rows: list[dict],
    highlights: list[dict],
    conclusions: list[str],
    interpretations: list[dict],
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=1.6 * cm,
        rightMargin=1.6 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title=title,
        author="WAF Observatory",
    )

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle(
        "DocTitleCompare",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=19,
        spaceAfter=8,
    )
    h2 = ParagraphStyle(
        "SectionTitleCompare",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=14,
        spaceAfter=4,
        spaceBefore=8,
    )
    normal = ParagraphStyle(
        "BodyCompare",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        alignment=TA_JUSTIFY,
    )
    small = ParagraphStyle(
        "SmallCompare",
        parent=normal,
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#333333"),
    )

    def _table(data: list[list[str]], col_widths: list[float]) -> Table:
        table = Table(data, colWidths=col_widths)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f6fa")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0b3a60")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d0d7de")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        return table

    story = []
    story.append(Paragraph(escape(title), h1))
    story.append(
        Paragraph(
            f"Dicetak pada: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
            f"Metrik diuji: {len(inferential_rows)}",
            small,
        )
    )
    story.append(Spacer(1, 0.35 * cm))

    if highlights:
        story.append(Paragraph("Ringkasan Cepat per Metrik", h2))
        hdata = [["Metric", "Winner", "Signifikan", "p-holm", "Effect Size", "Uji"]]
        for row in highlights:
            hdata.append(
                [
                    _safe_text(row.get("metric")) or "-",
                    _safe_text(row.get("winner")) or "-",
                    _safe_text(row.get("significant")) or "-",
                    _safe_text(row.get("p_holm")) or "-",
                    _safe_text(row.get("effect_size")) or "-",
                    _safe_text(row.get("test")) or "-",
                ]
            )
        story.append(_table(hdata, [2.5 * cm, 1.9 * cm, 2.0 * cm, 2.0 * cm, 2.2 * cm, 4.6 * cm]))
        story.append(Spacer(1, 0.2 * cm))

    if conclusions:
        story.append(Paragraph("Kesimpulan Utama", h2))
        for idx, item in enumerate(conclusions, start=1):
            story.append(Paragraph(f"{idx}. {escape(_safe_text(item))}", normal))
        story.append(Spacer(1, 0.15 * cm))

    if interpretations:
        story.append(Paragraph("Interpretasi Siap Pakai per Metrik", h2))
        for idx, item in enumerate(interpretations, start=1):
            story.append(Paragraph(f"{idx}. {escape(_safe_text(item.get('text')))}", small))
        story.append(Spacer(1, 0.15 * cm))

    if summary_rows:
        story.append(Paragraph("Ringkasan Metrik per Model", h2))
        data = [["Model", "Rows", "R1", "R2", "RL", "METEOR", "BERT", "Latency"]]
        for row in summary_rows:
            data.append(
                [
                    _safe_text(row.get("model")) or "-",
                    _safe_text(row.get("rows_requested")) or "-",
                    _fmt_float(row.get("rouge1_f1"), 6),
                    _fmt_float(row.get("rouge2_f1"), 6),
                    _fmt_float(row.get("rougel_f1"), 6),
                    _fmt_float(row.get("meteor"), 6),
                    _fmt_float(row.get("bertscore_f1"), 6),
                    _fmt_float(row.get("latency_ms"), 3),
                ]
            )
        story.append(_table(data, [3.7 * cm, 1.0 * cm, 1.3 * cm, 1.3 * cm, 1.3 * cm, 1.6 * cm, 1.6 * cm, 1.6 * cm]))
        story.append(Spacer(1, 0.2 * cm))

    if shapiro_rows:
        story.append(Paragraph("Uji Normalitas Shapiro-Wilk", h2))
        data = [["Metric", "N", "W", "p", "Status"]]
        for row in shapiro_rows:
            data.append(
                [
                    _safe_text(row.get("metric")) or "-",
                    _safe_text(row.get("n_diff")) or "-",
                    _fmt_float(row.get("shapiro_W"), 6),
                    _fmt_float(row.get("shapiro_p"), 6),
                    _safe_text(row.get("normality")) or "-",
                ]
            )
        story.append(_table(data, [3.1 * cm, 1.2 * cm, 3.0 * cm, 3.0 * cm, 3.7 * cm]))
        story.append(Spacer(1, 0.2 * cm))

    if descriptive_rows:
        story.append(Paragraph("Statistik Deskriptif Berpasangan", h2))
        data = [["Metric", "N", "Mean Q", "Std Q", "Mean G", "Std G", "Diff Q-G"]]
        for row in descriptive_rows:
            data.append(
                [
                    _safe_text(row.get("metric")) or "-",
                    _safe_text(row.get("n_pairs")) or "-",
                    _fmt_float(row.get("qwen_mean"), 6),
                    _fmt_float(row.get("qwen_std"), 6),
                    _fmt_float(row.get("gemma_mean"), 6),
                    _fmt_float(row.get("gemma_std"), 6),
                    _fmt_float(row.get("diff_mean_qwen_minus_gemma"), 6),
                ]
            )
        story.append(_table(data, [2.8 * cm, 1.0 * cm, 2.0 * cm, 2.0 * cm, 2.0 * cm, 2.0 * cm, 2.0 * cm]))
        story.append(Spacer(1, 0.2 * cm))

    if inferential_rows:
        story.append(Paragraph("Uji Inferensial Final", h2))
        data = [["Metric", "Test", "Statistic", "p", "p-holm", "Sig", "Effect"]]
        for row in inferential_rows:
            sig = "Ya" if str(row.get("significant") or "False").lower() == "true" else "Tidak"
            effect = f"{_fmt_float(row.get('effect_size'), 4)} ({_safe_text(row.get('effect_size_type'))})"
            data.append(
                [
                    _safe_text(row.get("metric")) or "-",
                    _safe_text(row.get("test")) or "-",
                    _fmt_float(row.get("statistic"), 6),
                    _fmt_float(row.get("p_value"), 6),
                    _fmt_float(row.get("p_holm"), 6),
                    sig,
                    effect,
                ]
            )
        story.append(_table(data, [2.2 * cm, 3.0 * cm, 2.2 * cm, 1.8 * cm, 1.8 * cm, 1.3 * cm, 3.0 * cm]))

    doc.build(story)
    return output_path
