"""Helpers for admin multi-table layouts and form record table cells."""

import ast
import operator
import re


def allowed_dropdown_values(layout, row_idx, col_idx, row_cells):
    """Return allowed options for a dropdown cell, or None if the cell is free text."""
    dropdown = layout.dropdown_for_cell(row_idx, col_idx)
    if not dropdown:
        return None
    if dropdown.get('depends_on_col') is not None:
        parent_col = dropdown['depends_on_col']
        parent_val = ''
        if isinstance(row_cells, (list, tuple)) and 0 <= parent_col < len(row_cells):
            parent_val = str(row_cells[parent_col] or '').strip()
        return list(dropdown.get('option_map', {}).get(parent_val, []))
    return list(dropdown.get('options', []))


def validate_table_cells(layout, cells):
    """Ensure dropdown cells only keep values allowed by admin config (incl. dependencies)."""
    col_count = len(layout.normalized_columns())
    validated = []
    for row_idx, row in enumerate(cells or []):
        row = list(row) if isinstance(row, (list, tuple)) else []
        new_row = []
        for col_idx in range(col_count):
            val = str(row[col_idx] if col_idx < len(row) else '').strip()
            temp_row = list(row)
            for i, v in enumerate(new_row):
                temp_row[i] = v
            allowed = allowed_dropdown_values(layout, row_idx, col_idx, temp_row)
            if allowed is not None and val and val not in allowed:
                val = ''
            new_row.append(val)
        validated.append(new_row)
    return validated


def table_block_keys(post):
    keys = set()
    for key in post:
        if key.startswith('tbl_') and key.endswith('_row_count'):
            keys.add(key[4:-10])
    return sorted(keys, key=_block_sort_key)


def _block_sort_key(key):
    if key.startswith('new'):
        return (1, int(key[3:] or 0))
    try:
        return (0, int(key))
    except ValueError:
        return (2, key)


def parse_columns(post, prefix):
    labels = post.getlist(f'{prefix}_column_headers')
    active_flags = post.getlist(f'{prefix}_column_active')
    columns = []
    for index, label in enumerate(labels):
        label = label.strip()
        if not label:
            continue
        is_active = active_flags[index] == '1' if index < len(active_flags) else True
        columns.append({'label': label, 'is_active': is_active})
    return columns


def parse_rows_spec(value, row_count):
    """Parse row text into 0-based indices.

    - Blank → all rows (empty list)
    - Single number N → first N rows (1..N)
    - '1,2,5' → specific rows
    - '1-3' → inclusive range
    """
    value = (value or '').strip()
    if not value:
        return []
    if value.isdigit():
        count = min(int(value), row_count)
        return list(range(max(0, count)))
    rows = []
    for part in value.replace(';', ',').split(','):
        part = part.strip()
        if not part:
            continue
        if '-' in part:
            ends = part.split('-', 1)
            try:
                start = int(ends[0].strip())
                end = int(ends[1].strip())
            except (TypeError, ValueError):
                continue
            if start > end:
                start, end = end, start
            for number in range(start, end + 1):
                if 1 <= number <= row_count:
                    rows.append(number - 1)
            continue
        try:
            number = int(part)
        except (TypeError, ValueError):
            continue
        if 1 <= number <= row_count:
            rows.append(number - 1)
    return sorted(set(rows))


def rows_display(rows):
    """Format 0-based row indices for the admin Rows field."""
    if not rows:
        return ''
    # Contiguous from row 1 → show as single count (first N rows)
    if rows[0] == 0 and rows == list(range(len(rows))):
        return str(len(rows))
    if rows == list(range(rows[0], rows[-1] + 1)):
        return f'{rows[0] + 1}-{rows[-1] + 1}'
    return ','.join(str(idx + 1) for idx in rows)


def parse_column_dropdowns(post, prefix, column_count, row_count=100, marker='col_dd'):
    indices = set()
    full_marker = f'{prefix}_{marker}_'
    for key in post:
        if key.startswith(full_marker) and key.endswith('_col'):
            parts = key[len(full_marker):].split('_')
            if len(parts) == 2 and parts[0].isdigit():
                indices.add(int(parts[0]))
    dropdowns = []
    parsed_rows = []
    for index in sorted(indices):
        try:
            col = int(post.get(f'{prefix}_{marker}_{index}_col', 0))
        except (TypeError, ValueError):
            continue
        is_active = post.get(f'{prefix}_{marker}_{index}_active') == '1'
        rows = parse_rows_spec(post.get(f'{prefix}_{marker}_{index}_rows', ''), row_count)

        depends_raw = (post.get(f'{prefix}_{marker}_{index}_depends_on') or '').strip()
        depends_on_col = None
        if depends_raw != '':
            try:
                depends_on_col = int(depends_raw)
            except (TypeError, ValueError):
                depends_on_col = None
            if (
                depends_on_col is None
                or depends_on_col < 0
                or depends_on_col >= column_count
                or depends_on_col == col
            ):
                depends_on_col = None

        option_map = {}
        map_parents = post.getlist(f'{prefix}_{marker}_{index}_map_parent')
        for map_index, parent_key in enumerate(map_parents):
            parent = parent_key.strip()
            if not parent:
                continue
            child_opts = [
                value.strip()
                for value in post.getlist(f'{prefix}_{marker}_{index}_map_opts_{map_index}')
                if value.strip()
            ]
            if child_opts:
                option_map[parent] = child_opts

        options = [
            value.strip()
            for value in post.getlist(f'{prefix}_{marker}_{index}_options')
            if value.strip()
        ]

        if depends_on_col is not None and option_map:
            options = []
            seen = set()
            for child_opts in option_map.values():
                for option in child_opts:
                    if option not in seen:
                        seen.add(option)
                        options.append(option)
            entry = {
                'col': col,
                'rows': rows,
                'options': options,
                'is_active': is_active,
                'depends_on_col': depends_on_col,
                'option_map': option_map,
            }
        else:
            if not options or col < 0 or col >= column_count:
                continue
            entry = {'col': col, 'rows': rows, 'options': options, 'is_active': is_active}

        if col < 0 or col >= column_count or not entry['options']:
            continue

        dropdowns.append(entry)
        parsed_rows.append({
            'index': index,
            'col': col,
            'rows': rows,
            'rows_text': rows_display(rows),
            'options': entry.get('options', options),
            'is_active': is_active,
            'depends_on_col': entry.get('depends_on_col'),
            'option_map': entry.get('option_map') or {},
            'option_map_items': [
                {'parent': key, 'options': vals}
                for key, vals in (entry.get('option_map') or {}).items()
            ],
        })
    return dropdowns, parsed_rows


def _summary_dropdown_rows(summary):
    rows = []
    for index, entry in enumerate(summary.get('dropdowns') or []):
        rows.append({
            'index': index,
            'col': entry['col'],
            'rows': entry.get('rows') or [],
            'rows_text': rows_display(entry.get('rows') or []),
            'options': entry.get('options') or [],
            'is_active': entry.get('is_active', True),
            'depends_on_table_col': entry.get('depends_on_table_col'),
            'depends_on_col': entry.get('depends_on_col'),
            'option_map': entry.get('option_map') or {},
            'option_map_items': [
                {'parent': key, 'options': vals}
                for key, vals in (entry.get('option_map') or {}).items()
            ],
        })
    return rows


def build_table_block(layout=None, key=None, parsed=None):
    if parsed:
        return parsed
    if layout:
        dropdown_rows = [
            {
                'index': index,
                'col': entry['col'],
                'rows': entry['rows'],
                'rows_text': rows_display(entry['rows']),
                'options': entry['options'],
                'is_active': entry['is_active'],
                'depends_on_col': entry.get('depends_on_col'),
                'option_map': entry.get('option_map') or {},
                'option_map_items': [
                    {'parent': key, 'options': vals}
                    for key, vals in (entry.get('option_map') or {}).items()
                ],
            }
            for index, entry in enumerate(layout.normalized_column_dropdowns())
        ]
        rating_letter = detect_rating_column_letter(layout)
        summary = layout.normalized_table_summary() or empty_table_summary(rating_letter)
        if not summary.get('enabled'):
            summary = empty_table_summary(rating_letter)
        summary_dropdown_rows = _summary_dropdown_rows(summary)
        return {
            'key': key or str(layout.pk),
            'layout_id': layout.pk,
            'table_number': layout.table_number,
            'table_name': layout.table_name,
            'table_heading': layout.table_heading,
            'notes': layout.notes,
            'table_note': layout.table_note,
            'row_count': layout.row_count,
            'column_rows': layout.normalized_columns() or [{'label': '', 'is_active': True}],
            'dropdown_rows': dropdown_rows,
            'next_dropdown_index': len(dropdown_rows),
            'table_summary': summary,
            'summary_dropdown_rows': summary_dropdown_rows,
            'next_summary_dropdown_index': len(summary_dropdown_rows),
        }
    empty_summary = empty_table_summary()
    return {
        'key': key or 'new0',
        'layout_id': None,
        'table_number': 1,
        'table_name': '',
        'table_heading': '',
        'notes': '',
        'table_note': '',
        'row_count': 100,
        'column_rows': [{'label': '', 'is_active': True}],
        'dropdown_rows': [],
        'next_dropdown_index': 0,
        'table_summary': empty_summary,
        'summary_dropdown_rows': [],
        'next_summary_dropdown_index': 0,
    }


def block_from_post(post, key, table_number=1):
    prefix = f'tbl_{key}'
    try:
        row_count = int(post.get(f'{prefix}_row_count', 100))
    except (TypeError, ValueError):
        return None
    columns = parse_columns(post, prefix)
    dropdowns, dropdown_rows = parse_column_dropdowns(post, prefix, len(columns), row_count)
    summary = parse_table_summary(post, prefix)
    summary_dropdown_rows = _summary_dropdown_rows(summary) if summary else []
    layout_id = post.get(f'{prefix}_id') or None
    if layout_id:
        try:
            layout_id = int(layout_id)
        except (TypeError, ValueError):
            layout_id = None
    return {
        'key': key,
        'layout_id': layout_id,
        'table_number': table_number,
        'table_name': post.get(f'{prefix}_name', '').strip(),
        'table_heading': post.get(f'{prefix}_heading', '').strip(),
        'notes': post.get(f'{prefix}_notes', '').strip(),
        'table_note': post.get(f'{prefix}_note', '').strip(),
        'row_count': row_count,
        'column_rows': columns or [{'label': '', 'is_active': True}],
        'dropdown_rows': dropdown_rows,
        'columns': columns,
        'cell_dropdowns': dropdowns,
        'table_summary': summary if summary.get('enabled') else empty_table_summary(),
        'summary_dropdown_rows': summary_dropdown_rows if summary.get('enabled') else [],
        'next_summary_dropdown_index': (
            max([row['index'] for row in summary_dropdown_rows], default=-1) + 1
            if summary.get('enabled') else 0
        ),
        'next_dropdown_index': max([row['index'] for row in dropdown_rows], default=-1) + 1,
    }


def parse_table_summary(post, prefix):
    """Parse optional table summary from admin POST fields."""
    from core.models import FormTableLayout

    enabled = post.get(f'{prefix}_summary_enabled') == '1'
    if not enabled:
        return {}

    # Title always mirrors the table name.
    title = (post.get(f'{prefix}_name') or '').strip()
    if not title:
        title = (post.get(f'{prefix}_summary_title') or '').strip()

    col_labels = post.getlist(f'{prefix}_summary_columns')
    col_subs = post.getlist(f'{prefix}_summary_column_subs')
    columns = []
    for index, raw_label in enumerate(col_labels):
        label = (raw_label or '').strip()
        if not label:
            continue
        subheader = ''
        if index < len(col_subs):
            subheader = (col_subs[index] or '').strip()
        columns.append({'label': label, 'subheader': subheader})
    if not columns:
        columns = [{'label': 'Column 1', 'subheader': ''}]

    row_indices = set()
    marker = f'{prefix}_summary_cell_'
    for key in post:
        if not key.startswith(marker):
            continue
        rest = key[len(marker):]
        parts = rest.split('_')
        if len(parts) >= 2 and parts[0].isdigit():
            row_indices.add(int(parts[0]))

    col_count = len(columns)
    rows = []
    for row_idx in sorted(row_indices):
        cells = []
        for col_idx in range(col_count):
            value = (post.get(f'{prefix}_summary_cell_{row_idx}_{col_idx}_value') or '').strip()
            formula = (post.get(f'{prefix}_summary_cell_{row_idx}_{col_idx}_formula') or '').strip()
            cells.append({'value': value, 'formula': formula})
        rows.append({'label': '', 'cells': cells})

    summary_row_count = max(len(rows), 1)
    header_labels = post.getlist(f'{prefix}_column_headers')
    table_col_count = len(header_labels) if header_labels else 1
    summary_dropdowns, _ = parse_summary_dropdowns(
        post,
        prefix,
        summary_col_count=col_count,
        table_col_count=max(table_col_count, 1),
        row_count=summary_row_count,
    )

    return FormTableLayout.normalize_table_summary({
        'enabled': True,
        'title': title,
        'columns': columns,
        'rows': rows or [{'label': '', 'cells': [{'value': '', 'formula': ''} for _ in columns]}],
        'dropdowns': summary_dropdowns,
    })


def parse_summary_dropdowns(post, prefix, summary_col_count, table_col_count, row_count=100):
    """Parse summary dropdowns; Depends on refers to main-table columns."""
    from core.models import FormTableLayout

    indices = set()
    marker = f'{prefix}_summary_dd_'
    for key in post:
        if key.startswith(marker) and key.endswith('_col'):
            parts = key[len(marker):].split('_')
            if len(parts) == 2 and parts[0].isdigit():
                indices.add(int(parts[0]))

    dropdowns = []
    parsed_rows = []
    for index in sorted(indices):
        try:
            col = int(post.get(f'{prefix}_summary_dd_{index}_col', 0))
        except (TypeError, ValueError):
            continue
        if col < 0 or col >= summary_col_count:
            continue
        is_active = post.get(f'{prefix}_summary_dd_{index}_active') == '1'
        rows = parse_rows_spec(post.get(f'{prefix}_summary_dd_{index}_rows', ''), row_count)

        depends_raw = (post.get(f'{prefix}_summary_dd_{index}_depends_on') or '').strip()
        depends_on_table_col = None
        if depends_raw != '':
            try:
                depends_on_table_col = int(depends_raw)
            except (TypeError, ValueError):
                depends_on_table_col = None
            if (
                depends_on_table_col is None
                or depends_on_table_col < 0
                or depends_on_table_col >= table_col_count
            ):
                depends_on_table_col = None

        option_map = {}
        map_parents = post.getlist(f'{prefix}_summary_dd_{index}_map_parent')
        for map_index, parent_key in enumerate(map_parents):
            parent = parent_key.strip()
            if not parent:
                continue
            child_opts = [
                value.strip()
                for value in post.getlist(f'{prefix}_summary_dd_{index}_map_opts_{map_index}')
                if value.strip()
            ]
            if child_opts:
                option_map[parent] = child_opts

        options = [
            value.strip()
            for value in post.getlist(f'{prefix}_summary_dd_{index}_options')
            if value.strip()
        ]

        entry = {
            'col': col,
            'rows': rows,
            'options': options,
            'is_active': is_active,
        }
        if depends_on_table_col is not None and option_map:
            entry['depends_on_table_col'] = depends_on_table_col
            entry['option_map'] = option_map
            flat = []
            seen = set()
            for child_opts in option_map.values():
                for option in child_opts:
                    if option not in seen:
                        seen.add(option)
                        flat.append(option)
            entry['options'] = flat

        normalized = FormTableLayout.normalize_summary_dropdown(entry)
        if not normalized:
            continue
        dropdowns.append(normalized)
        parsed_rows.append({
            'index': index,
            'col': normalized['col'],
            'rows': normalized.get('rows') or [],
            'rows_text': rows_display(normalized.get('rows') or []),
            'options': normalized.get('options') or [],
            'is_active': normalized.get('is_active', True),
            'depends_on_table_col': normalized.get('depends_on_table_col'),
            'depends_on_col': normalized.get('depends_on_col'),
            'option_map': normalized.get('option_map') or {},
            'option_map_items': [
                {'parent': key, 'options': vals}
                for key, vals in (normalized.get('option_map') or {}).items()
            ],
        })
    return dropdowns, parsed_rows


def _excel_letters(index):
    """0-based column index → Excel letters (0→A, 25→Z, 26→AA)."""
    if index < 0:
        return 'A'
    index += 1
    letters = ''
    while index:
        index, rem = divmod(index - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def detect_rating_column_letter(layout=None, columns=None, dropdowns=None):
    """
    Pick the main-table column letter whose dropdown options include High/Medium/Low.
    Falls back to D (4th column) — common for Bases Risk Rating.
    """
    cols = columns
    dds = dropdowns
    if layout is not None:
        cols = layout.normalized_columns()
        dds = layout.normalized_column_dropdowns()
    cols = cols or []
    markers = {'high', 'medium', 'low'}
    for dropdown in dds or []:
        if not dropdown.get('is_active', True):
            continue
        options = {str(opt).strip().lower() for opt in (dropdown.get('options') or [])}
        if markers & options:
            col_idx = int(dropdown.get('col', 0))
            if 0 <= col_idx < max(len(cols), col_idx + 1):
                return _excel_letters(col_idx)
    # Prefer a column whose label mentions rating.
    for idx, column in enumerate(cols):
        label = str((column or {}).get('label') or '').lower()
        if 'rating' in label:
            return _excel_letters(idx)
    return 'D'


def _default_summary_risk_row(label):
    """One default summary row; COUNTIF targets the main-table column with the same name."""
    return {
        'label': '',
        'cells': [
            {'value': label, 'formula': ''},
            {'value': '', 'formula': f'=COUNTIF("{label}","High")'},
            {'value': '', 'formula': f'=COUNTIF("{label}","Medium")'},
            {'value': '', 'formula': f'=COUNTIF("{label}","Low")'},
            # Same-row weighted average: High*3 + Medium*2 + Low*1 (admin-editable).
            {'value': '', 'formula': '=((B2*3)+(C2*2)+(D2*1))/(B2+C2+D2)'},
            {'value': '', 'formula': ''},  # Comments — left empty for managers
        ],
    }


def empty_table_summary(rating_col_letter='D'):
    """
    Default Excel-like summary shell (disabled until admin clicks Add Summary).

    Layout/formulas match the Boundary Risk Assessment example and are stored in
    FormTableLayout.table_summary so the admin can change every column, row, and
    formula. Nothing here is locked at fill/view time — only admin config is used.
    ``rating_col_letter`` is kept for call-site compatibility (unused).
    """
    return {
        'enabled': False,
        'title': '',
        'columns': [
            {'label': 'Results of Risk Assessment', 'subheader': ''},
            {'label': 'High', 'subheader': '1'},
            {'label': 'Medium', 'subheader': '2'},
            {'label': 'Low', 'subheader': '3'},
            {'label': 'Overall Risk Rating', 'subheader': ''},
            {'label': 'Comments', 'subheader': ''},
        ],
        'rows': [
            _default_summary_risk_row('Bases Risk Rating'),
            _default_summary_risk_row('Residual Risk Rating'),
        ],
        'dropdowns': [],
    }


def default_table_summary_seed_json():
    """JSON seed for admin UI 'Add Summary' (same structure as empty_table_summary)."""
    import json
    return json.dumps(empty_table_summary(), separators=(',', ':'))


_SUM_COL_RE = re.compile(r'^=SUM\(C(\d+)\)\s*$', re.IGNORECASE)
_CELL_REF_RE = re.compile(r'^=C(\d+)R(\d+)\s*$', re.IGNORECASE)
_COUNTIF_RE = re.compile(
    r'^=\s*COUNTIF\(\s*([^,]+)\s*,\s*[\'"]?([^\'")]+)[\'"]?\s*\)\s*$',
    re.IGNORECASE,
)
_COUNTIFS_RE = re.compile(r'^=\s*COUNTIFS\(\s*(.+)\s*\)\s*$', re.IGNORECASE)
_CN_RANGE_RE = re.compile(r'^C(\d+)$', re.IGNORECASE)
_EXCEL_COL_RE = re.compile(r'^\$?([A-Za-z]+)(?:\$?\d+)?(?::\$?[A-Za-z]+(?:\$?\d+)?)?$')
_SUMMARY_CELL_REF_RE = re.compile(r'\$?([A-Za-z]+)\$?\d+', re.IGNORECASE)
_SC_REF_RE = re.compile(r'SC(\d+)', re.IGNORECASE)

_AST_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def excel_column_to_index(letters):
    """Convert Excel column letters (A, B, ..., F, AA) to 0-based index."""
    letters = (letters or '').strip().upper()
    if not letters or not letters.isalpha():
        return None
    value = 0
    for char in letters:
        value = value * 26 + (ord(char) - ord('A') + 1)
    return value - 1


def resolve_main_table_column(range_expr, column_headers=None):
    """Resolve COUNTIF range to a 0-based main-table column index."""
    expr = (range_expr or '').strip()
    match = _CN_RANGE_RE.match(expr)
    if match:
        return int(match.group(1))
    if expr.isdigit():
        return int(expr)
    match = _EXCEL_COL_RE.match(expr)
    if match:
        return excel_column_to_index(match.group(1))
    # Named column: "Bases Risk Rating" or Bases Risk Rating
    name = _strip_formula_literal(expr).strip().lower()
    if name and column_headers:
        for index, header in enumerate(column_headers):
            if isinstance(header, dict):
                label = str(header.get('label') or '').strip().lower()
            else:
                label = str(header or '').strip().lower()
            if label and label == name:
                return index
    return None


def _format_number(value):
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        if value == int(value):
            return str(int(value))
        return str(round(value, 10)).rstrip('0').rstrip('.')
    return str(value)


def _safe_eval_arithmetic(expr):
    """Evaluate a sanitized arithmetic expression (+ - * / and parentheses)."""
    try:
        tree = ast.parse(expr, mode='eval')
    except SyntaxError:
        return None

    def _eval(node):
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.Num):  # pragma: no cover - older AST
            return node.n
        if isinstance(node, ast.UnaryOp) and type(node.op) in _AST_OPS:
            return _AST_OPS[type(node.op)](_eval(node.operand))
        if isinstance(node, ast.BinOp) and type(node.op) in _AST_OPS:
            left = _eval(node.left)
            right = _eval(node.right)
            if type(node.op) is ast.Div and right == 0:
                return 0.0
            return _AST_OPS[type(node.op)](left, right)
        raise ValueError('unsupported expression')

    try:
        result = _eval(tree)
    except (ValueError, TypeError, ZeroDivisionError):
        return None
    if result is None:
        return None
    return _format_number(result)


def countif_main_column(cells, col_index, criteria):
    """Count non-empty main-table cells in col_index matching criteria (case-insensitive)."""
    if col_index is None or col_index < 0:
        return '0'
    needle = str(criteria or '').strip().lower()
    total = 0
    for row in cells or []:
        if col_index >= len(row):
            continue
        value = str(row[col_index] or '').strip()
        if not value:
            continue
        if value.lower() == needle:
            total += 1
    return str(total)


def _split_formula_args(inner):
    """Split COUNTIFS(...) argument list, respecting quoted commas."""
    args = []
    current = []
    in_quote = None
    for char in inner or '':
        if in_quote:
            current.append(char)
            if char == in_quote:
                in_quote = None
            continue
        if char in ('"', "'"):
            in_quote = char
            current.append(char)
            continue
        if char == ',':
            args.append(''.join(current).strip())
            current = []
            continue
        current.append(char)
    if current or args:
        args.append(''.join(current).strip())
    return args


def _strip_formula_literal(value):
    text = str(value or '').strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ('"', "'"):
        return text[1:-1].strip()
    return text


def countifs_main(cells, pairs):
    """Count main-table rows matching all (column, criteria) pairs."""
    if not pairs:
        return '0'
    total = 0
    for row in cells or []:
        matched = True
        for col_index, criteria in pairs:
            if col_index is None or col_index < 0 or col_index >= len(row):
                matched = False
                break
            value = str(row[col_index] or '').strip()
            if not value or value.lower() != str(criteria).strip().lower():
                matched = False
                break
        if matched:
            total += 1
    return str(total)


def _retarget_countif_to_row_column(formula, row_label, column_headers):
    """
    If the summary row label matches a main-table column header, retarget a simple
    =COUNTIF(anyCol,...) to that column (e.g. Residual Risk Rating → column F).
    Leaves COUNTIFS and non-COUNTIF formulas unchanged.
    """
    formula = (formula or '').strip()
    label = (row_label or '').strip().lower()
    if not formula or not label or not column_headers:
        return formula
    upper = formula.upper()
    if not upper.startswith('=COUNTIF(') or upper.startswith('=COUNTIFS('):
        return formula
    target_idx = None
    for index, header in enumerate(column_headers):
        header_label = header.get('label') if isinstance(header, dict) else header
        if str(header_label or '').strip().lower() == label:
            target_idx = index
            break
    if target_idx is None:
        return formula
    letter = _excel_letters(target_idx)
    return re.sub(
        r'^(=\s*COUNTIF\(\s*)([^,]+)(,)',
        lambda match: match.group(1) + letter + ':' + letter + match.group(3),
        formula,
        count=1,
        flags=re.IGNORECASE,
    )


def evaluate_summary_formula(formula, cells, row_values=None, column_headers=None):
    """
    Evaluate admin formulas against the main table (and optional same-row summary values).

    Supported examples (admin-defined, not hardcoded):
      =COUNTIF($F$24:$F$114,"High")
      =COUNTIF(F:F,"Medium")
      =COUNTIF("Bases Risk Rating","High")
      =COUNTIFS(B:B,"Inherent Risk",F:F,"High")
      =SUM(C0)
      =C0R1
      =((B2*3)+(C2*2)+(D2*1))/(B2+C2+D2)   # same-row summary columns A=0,B=1,...
      =(SC1*3+SC2*2+SC3*1)/(SC1+SC2+SC3)
    """
    formula = (formula or '').strip()
    if not formula:
        return None
    if not formula.startswith('='):
        return None

    countifs = _COUNTIFS_RE.match(formula)
    if countifs:
        args = _split_formula_args(countifs.group(1))
        if len(args) < 2 or len(args) % 2 != 0:
            return '0'
        pairs = []
        for index in range(0, len(args), 2):
            col_index = resolve_main_table_column(args[index], column_headers=column_headers)
            criteria = _strip_formula_literal(args[index + 1])
            pairs.append((col_index, criteria))
        return countifs_main(cells, pairs)

    countif = _COUNTIF_RE.match(formula)
    if countif:
        col_index = resolve_main_table_column(countif.group(1), column_headers=column_headers)
        return countif_main_column(cells, col_index, countif.group(2))

    match = _SUM_COL_RE.match(formula)
    if match:
        col = int(match.group(1))
        total = 0.0
        found = False
        for row in cells or []:
            if col >= len(row):
                continue
            raw = str(row[col] or '').strip().replace(',', '')
            if not raw:
                continue
            try:
                total += float(raw)
                found = True
            except ValueError:
                continue
        if not found:
            return '0'
        return _format_number(total)

    match = _CELL_REF_RE.match(formula)
    if match:
        col = int(match.group(1))
        row = int(match.group(2))
        if row < len(cells or []) and col < len(cells[row]):
            return str(cells[row][col] or '')
        return ''

    # Arithmetic / weighted rating using same-row summary values.
    if row_values is None:
        return None
    expr = formula[1:].strip()

    def replace_sc(match_obj):
        idx = int(match_obj.group(1))
        raw = row_values[idx] if 0 <= idx < len(row_values) else 0
        try:
            return str(float(str(raw).replace(',', '') or 0))
        except ValueError:
            return '0'

    def replace_letter(match_obj):
        idx = excel_column_to_index(match_obj.group(1))
        if idx is None:
            return '0'
        raw = row_values[idx] if 0 <= idx < len(row_values) else 0
        try:
            return str(float(str(raw).replace(',', '') or 0))
        except ValueError:
            return '0'

    expr = _SC_REF_RE.sub(replace_sc, expr)
    expr = _SUMMARY_CELL_REF_RE.sub(replace_letter, expr)
    return _safe_eval_arithmetic(expr)


def _to_number(value):
    try:
        return float(str(value or '').replace(',', '').strip() or 0)
    except ValueError:
        return 0.0


def _unique_table_column_values(cells, col_idx):
    """Distinct non-empty values from a main-table column (row order preserved)."""
    values = []
    seen = set()
    for row in cells or []:
        if col_idx < 0 or col_idx >= len(row):
            continue
        value = str(row[col_idx] or '').strip()
        if not value or value in seen:
            continue
        seen.add(value)
        values.append(value)
    return values


def _options_from_option_map(option_map, parent_values):
    """Union child options for the given parent values (exact then trim-matched keys)."""
    option_map = option_map or {}
    options = []
    seen = set()
    for parent in parent_values or []:
        key = str(parent or '').strip()
        if not key:
            continue
        child_opts = option_map.get(key)
        if child_opts is None:
            for map_key, map_opts in option_map.items():
                if str(map_key or '').strip() == key:
                    child_opts = map_opts
                    break
        for option in child_opts or []:
            opt = str(option).strip()
            if opt and opt not in seen:
                seen.add(opt)
                options.append(opt)
    return options


def build_summary_display(layout, cells, stored_summary_cells=None, editable=False):
    """Return display-ready summary dict, or None when summary is disabled."""
    import json

    summary = layout.normalized_table_summary()
    if not summary.get('enabled'):
        return None

    title = (summary.get('title') or '').strip() or (layout.table_name or '').strip() or 'Summary'
    has_subheaders = any((col.get('subheader') or '').strip() for col in summary['columns'])
    lookup = layout.summary_dropdown_lookup()
    column_headers = layout.normalized_columns()

    # Pass 1: main-table formulas and static values.
    interim_rows = []
    for row_idx, row in enumerate(summary['rows']):
        display_cells = []
        pending = []
        row_label = ''
        if row.get('cells'):
            row_label = str(row['cells'][0].get('value') or '').strip()
        for col_idx, cell in enumerate(row['cells']):
            formula = _retarget_countif_to_row_column(
                cell.get('formula') or '', row_label, column_headers
            )
            value = cell.get('value') or ''
            if (
                stored_summary_cells
                and row_idx < len(stored_summary_cells)
                and col_idx < len(stored_summary_cells[row_idx])
                and stored_summary_cells[row_idx][col_idx] not in (None, '')
            ):
                value = str(stored_summary_cells[row_idx][col_idx]).strip()
            dropdown = layout.summary_dropdown_for_cell(row_idx, col_idx, lookup=lookup)
            admin_static = str(cell.get('value') or '').strip()
            computed = None
            if formula:
                computed = evaluate_summary_formula(
                    formula, cells, row_values=None, column_headers=column_headers
                )
            if computed is not None:
                display = computed
                needs_pass2 = False
                is_editable = False
            elif formula.startswith('='):
                display = ''
                needs_pass2 = True
                is_editable = False
            elif value:
                display = value
                # Static admin labels stay locked; empty admin cells (or dropdowns) stay fillable.
                is_editable = bool(
                    editable
                    and not formula
                    and (dropdown or not admin_static)
                )
                needs_pass2 = False
            else:
                display = ''
                needs_pass2 = False
                is_editable = bool(editable and not formula)
            payload = {
                'value': value,
                'formula': formula,
                'display': display,
                'needs_pass2': needs_pass2,
                'editable': is_editable,
                'input_type': (
                    'select' if (is_editable and dropdown) else (
                        'text' if is_editable else ''
                    )
                ),
                'dropdown': None,
            }
            if dropdown:
                depends_on_table_col = dropdown.get('depends_on_table_col')
                options = list(dropdown.get('options') or [])
                if depends_on_table_col is not None and dropdown.get('option_map'):
                    parent_values = _unique_table_column_values(cells, depends_on_table_col)
                    options = _options_from_option_map(dropdown['option_map'], parent_values)
                dd = {
                    'options': options,
                    'depends_on_col': dropdown.get('depends_on_col'),
                    'depends_on_table_col': depends_on_table_col,
                }
                if dropdown.get('option_map'):
                    dd['option_map'] = dropdown['option_map']
                    dd['option_map_json'] = json.dumps(dropdown['option_map'])
                payload['dropdown'] = dd
            display_cells.append(payload)
            pending.append(needs_pass2)
        interim_rows.append({
            'label': row.get('label') or '',
            'cells': display_cells,
            'pending': pending,
        })

    # Pass 2: arithmetic formulas that reference same-row summary results.
    display_rows = []
    for row_idx, row in enumerate(interim_rows):
        row_values = [_to_number(cell['display']) for cell in row['cells']]
        for col_idx, cell in enumerate(row['cells']):
            if not cell.get('needs_pass2'):
                continue
            computed = evaluate_summary_formula(
                cell['formula'], cells, row_values=row_values, column_headers=column_headers
            )
            if computed is not None:
                cell['display'] = computed
                row_values[col_idx] = _to_number(computed)
            elif cell['value']:
                cell['display'] = cell['value']
            else:
                # Never show raw formulas to managers; failed calc → 0.
                cell['display'] = '0'
            cell['editable'] = False
        display_rows.append({
            'label': row['label'],
            'row_index': row_idx,
            'cells': [
                {
                    'value': cell['value'],
                    'formula': cell['formula'],
                    'display': cell['display'] if cell['display'] != '' else '—',
                    'editable': cell['editable'],
                    'input_type': cell.get('input_type') or '',
                    'dropdown': cell['dropdown'],
                    'col': col_idx,
                    'row': row_idx,
                }
                for col_idx, cell in enumerate(row['cells'])
            ],
        })

    option_maps = {}
    for col_idx, configs in lookup.items():
        for cfg in configs:
            if cfg.get('option_map'):
                option_maps[str(col_idx)] = cfg['option_map']

    formula_grid = []
    static_grid = []
    for row in summary['rows']:
        row_label = ''
        if row.get('cells'):
            row_label = str(row['cells'][0].get('value') or '').strip()
        formula_grid.append([
            _retarget_countif_to_row_column(str(cell.get('formula') or ''), row_label, column_headers)
            for cell in (row.get('cells') or [])
        ])
        static_grid.append([
            str(cell.get('value') or '') for cell in (row.get('cells') or [])
        ])
    header_labels = [
        str(col.get('label') or '') for col in column_headers
    ]

    return {
        'title': title,
        'has_subheaders': has_subheaders,
        'columns': summary['columns'],
        'rows': display_rows,
        'layout_id': layout.pk,
        'option_maps': option_maps,
        'option_maps_json': json.dumps(option_maps) if option_maps else '',
        'formula_grid': formula_grid,
        'formula_grid_json': json.dumps(formula_grid),
        'static_grid': static_grid,
        'static_grid_json': json.dumps(static_grid),
        'column_headers': header_labels,
        'column_headers_json': json.dumps(header_labels),
        'editable': editable,
    }


def stored_cells_for_layout(data, layout, all_layouts=None):
    stored = (data or {}).get('table_cells')
    if isinstance(stored, dict):
        return stored.get(str(layout.pk))
    if isinstance(stored, list) and all_layouts is not None:
        layouts = list(all_layouts)
        if len(layouts) == 1 and layouts[0].pk == layout.pk:
            return stored
    return None
