"""Generate form-record PDF downloads (portrait / landscape)."""
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape, portrait
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

GREEN = colors.HexColor('#8bc34a')
GREEN_BORDER = colors.HexColor('#6fa032')
BLUE = colors.HexColor('#00AEEF')
BLUE_BORDER = colors.HexColor('#0099d6')
WHITE = colors.white

_LOGO_CANDIDATES = (
    Path(__file__).resolve().parent / 'static' / 'core' / 'img' / 'logos' / 'logo-opt.png',
    Path(__file__).resolve().parent.parent / 'staticfiles' / 'core' / 'img' / 'logos' / 'logo-opt.png',
)


def _logo_path():
    for path in _LOGO_CANDIDATES:
        if path.is_file():
            return path
    return None


def _text(value):
    text = str(value if value is not None else '').strip()
    return text or '—'


def _p(text, style):
    safe = (
        _text(text)
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
    )
    return Paragraph(safe, style)


def _header_context(record, company=None, form_owner='VVB'):
    form_def = record.form_definition
    project = record.project
    company_name = company.name if company else (project.company_name if project else '—')
    issue_date = company.issue_date.strftime('%Y-%m-%d') if company and company.issue_date else '—'
    version = company.version if company and company.version else '—'
    doc_title = form_def.code
    if form_def.name:
        doc_title = f'{form_def.code} ({form_def.name})'

    project_info = None
    if project:
        report = '—'
        if project.report_type and project.year:
            report = f'{project.report_type}-{project.year}'
        elif project.report_type:
            report = project.report_type
        elif project.year:
            report = str(project.year)
        project_info = {
            'project_number': project.project_number or '—',
            'client': project.company_name or '—',
            'phase': project.get_phase_display() or '—',
            'report': report,
            'facility': project.location or '—',
            'document_type': project.get_document_type_display() or '—',
        }

    return {
        'company_name': company_name,
        'issue_date': issue_date,
        'doc_title': doc_title,
        'owner': form_owner or 'VVB',
        'version': version,
        'status': record.get_status_display(),
        'project': project_info,
    }


def _header_height(has_project):
    """Reserved top space so body content never overlaps repeating headers."""
    # company/logo block + green bar + optional project title/blue bar + gap
    height = 30 * mm + 10 * mm
    if has_project:
        height += 6 * mm + 16 * mm
    height += 4 * mm
    return height


def _draw_colored_bar(canvas, x, y, width, height, bg, border, pairs, font_size=7.5):
    """Draw a labeled key/value bar. ``pairs`` is list of (label, value)."""
    canvas.setFillColor(bg)
    canvas.setStrokeColor(border)
    canvas.setLineWidth(0.6)
    canvas.rect(x, y, width, height, fill=1, stroke=1)

    if not pairs:
        return

    cells = []
    for label, value in pairs:
        cells.append((_text(label), True))
        cells.append((_text(value), False))

    weights = []
    for text, is_label in cells:
        weights.append(1.0 if is_label else max(1.5, 0.07 * max(len(text), 4)))
    total_w = sum(weights) or 1
    col_widths = [width * (w / total_w) for w in weights]

    cursor = x
    mid_y = y + height / 2 - font_size / 2.5
    for index, ((text, is_label), col_w) in enumerate(zip(cells, col_widths)):
        canvas.setFillColor(WHITE)
        canvas.setFont('Helvetica-BoldOblique' if is_label else 'Helvetica-Oblique', font_size)
        # Clip long text roughly to cell width.
        max_chars = max(4, int(col_w / (font_size * 0.45)))
        shown = text if len(text) <= max_chars else text[: max_chars - 1] + '…'
        canvas.drawString(cursor + 2.2, mid_y, shown)
        cursor += col_w
        if index < len(cells) - 1:
            canvas.setStrokeColor(colors.Color(1, 1, 1, alpha=0.55))
            canvas.setLineWidth(0.4)
            canvas.line(cursor, y + 1, cursor, y + height - 1)


def _draw_branding_block(canvas, right, top):
    """Draw logo + Assessment Manager titles, right-aligned like the web header."""
    logo_path = _logo_path()
    # Match web .form-doc-logo (~52px tall); keep square aspect of logo-opt.png.
    logo_size = 15 * mm
    logo_x = right - logo_size
    logo_bottom = top - logo_size

    if logo_path is not None:
        try:
            canvas.drawImage(
                ImageReader(str(logo_path)),
                logo_x,
                logo_bottom,
                width=logo_size,
                height=logo_size,
                preserveAspectRatio=True,
                mask='auto',
                anchor='c',
            )
        except Exception:
            logo_path = None
            canvas.setFillColor(colors.HexColor('#00B0F0'))
            canvas.setFont('Helvetica-Bold', 11)
            canvas.drawRightString(right, top - 6 * mm, 'VA')

    # Titles stacked under the logo (same order/style as form_grey_header.html)
    title_y = logo_bottom - 4.2 * mm
    canvas.setFillColor(colors.HexColor('#1f2d3d'))
    canvas.setFont('Helvetica-Bold', 9)
    canvas.drawRightString(right, title_y, 'Assessment Manager')
    canvas.setFillColor(colors.HexColor('#5c6670'))
    canvas.setFont('Helvetica-Oblique', 7.5)
    canvas.drawRightString(right, title_y - 3.8 * mm, 'Product of EHSS & C MAC')
    return title_y - 3.8 * mm


def _draw_page_headers(canvas, doc, header):
    canvas.saveState()
    page_width, page_height = doc.pagesize
    left = doc.leftMargin
    right = page_width - doc.rightMargin
    usable = page_width - doc.leftMargin - doc.rightMargin
    top = page_height - 7 * mm

    # Company + Document Control (every page, left)
    canvas.setFillColor(colors.HexColor('#1f2d3d'))
    canvas.setFont('Helvetica-Bold', 13)
    canvas.drawString(left, top - 5 * mm, _text(header['company_name']))
    canvas.setFillColor(colors.HexColor('#5c6670'))
    canvas.setFont('Helvetica-Oblique', 8)
    canvas.drawString(left, top - 9.5 * mm, 'Document Control')

    # Logo + product branding (every page, right) — matches web form header
    brand_bottom = _draw_branding_block(canvas, right, top)

    # Keep green bar below both left titles and right branding block.
    green_top_limit = min(top - 14 * mm, brand_bottom - 3 * mm)
    green_h = 8 * mm
    green_y = green_top_limit - green_h
    green_pairs = [
        ('Issue Date:', header['issue_date']),
        ('Document Name:', header['doc_title']),
        ('Owner:', header['owner']),
        ('Version:', header['version']),
    ]
    _draw_colored_bar(
        canvas, left, green_y, usable, green_h, GREEN, GREEN_BORDER, green_pairs, font_size=7,
    )

    if header.get('project'):
        project = header['project']
        canvas.setFillColor(colors.HexColor('#5c6670'))
        canvas.setFont('Helvetica-Oblique', 8)
        canvas.drawString(left, green_y - 5 * mm, 'Project Control')

        blue_h = 7 * mm
        row1_y = green_y - 13 * mm
        row2_y = green_y - 20 * mm
        _draw_colored_bar(
            canvas,
            left,
            row1_y,
            usable,
            blue_h,
            BLUE,
            BLUE_BORDER,
            [
                ('Project #:', project['project_number']),
                ('Client:', project['client']),
                ('Phase:', project['phase']),
            ],
            font_size=7,
        )
        _draw_colored_bar(
            canvas,
            left,
            row2_y,
            usable,
            blue_h,
            BLUE,
            BLUE_BORDER,
            [
                ('Report Type & Year:', project['report']),
                ('Facility:', project['facility']),
                ('Document Type:', project['document_type']),
            ],
            font_size=7,
        )

    # Page number footer
    canvas.setFillColor(colors.HexColor('#666666'))
    canvas.setFont('Helvetica', 8)
    canvas.drawRightString(
        page_width - doc.rightMargin,
        8 * mm,
        f'Page {doc.page}',
    )
    canvas.restoreState()


def _make_table(data, col_count, page_width, left_margin=12 * mm, right_margin=12 * mm):
    if not data or col_count < 1:
        return None
    usable = page_width - left_margin - right_margin
    col_width = usable / float(col_count)
    table = Table(data, colWidths=[col_width] * col_count, repeatRows=1)
    table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.85, 0.85, 0.85)),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.black),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    return table


def build_form_record_pdf(
    record,
    table_sections,
    company=None,
    form_owner='VVB',
    orientation='portrait',
):
    """Return PDF bytes for a form record in portrait or landscape."""
    orientation = (orientation or 'portrait').strip().lower()
    if orientation not in ('portrait', 'landscape'):
        orientation = 'portrait'

    page_size = landscape(A4) if orientation == 'landscape' else portrait(A4)
    page_width = page_size[0]
    header = _header_context(record, company=company, form_owner=form_owner)
    top_margin = _header_height(bool(header.get('project')))

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=page_size,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=top_margin,
        bottomMargin=14 * mm,
        title=f'{record.form_definition.code} Form',
    )

    styles = getSampleStyleSheet()
    section_style = ParagraphStyle(
        'FormPdfSection',
        parent=styles['Heading3'],
        fontSize=10,
        leading=12,
        spaceBefore=8,
        spaceAfter=4,
        alignment=TA_LEFT,
    )
    body_style = ParagraphStyle(
        'FormPdfBody',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,
        spaceAfter=2,
        alignment=TA_LEFT,
    )

    story = []
    story.append(_p(f'Status: {header["status"]}', body_style))
    story.append(Spacer(1, 4))

    for section in table_sections or []:
        layout = section.get('layout')
        if layout is None:
            continue
        if layout.table_heading:
            story.append(_p(layout.table_heading, section_style))
        if layout.notes:
            story.append(_p(layout.notes, body_style))
        if layout.table_name:
            story.append(_p(layout.table_name, section_style))

        headers = section.get('table_headers') or []
        rows = section.get('table_rows') or []
        if headers and rows:
            table_data = [[_p(h, body_style) for h in headers]]
            for row in rows:
                table_data.append([
                    _p(cell.get('value') if isinstance(cell, dict) else cell, body_style)
                    for cell in row
                ])
            built = _make_table(table_data, len(headers), page_width)
            if built:
                story.append(built)
                story.append(Spacer(1, 6))

        summaries = section.get('table_summaries') or []
        if not summaries and section.get('table_summary'):
            summaries = [section['table_summary']]
        for summary in summaries:
            if not summary:
                continue
            columns = summary.get('columns') or []
            title = summary.get('title') or (layout.table_name if layout else 'Summary') or 'Summary'
            story.append(_p(title, section_style))
            if not columns:
                continue
            header_labels = [
                col.get('label') if isinstance(col, dict) else str(col)
                for col in columns
            ]
            table_data = [[_p(label, body_style) for label in header_labels]]
            if any((col.get('subheader') if isinstance(col, dict) else '') for col in columns):
                table_data.append([
                    _p((col.get('subheader') if isinstance(col, dict) else '') or '', body_style)
                    for col in columns
                ])
            for row in summary.get('rows') or []:
                cells = row.get('cells') or []
                table_data.append([
                    _p(cell.get('display') if isinstance(cell, dict) else cell, body_style)
                    for cell in cells
                ])
            built = _make_table(table_data, len(header_labels), page_width)
            if built:
                story.append(built)
                story.append(Spacer(1, 8))

        if layout.table_note:
            story.append(_p(layout.table_note, body_style))

    if len(story) <= 2:
        story.append(_p('No form content available.', body_style))

    def _on_page(canvas, doc_obj):
        _draw_page_headers(canvas, doc_obj, header)

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    return buffer.getvalue()
