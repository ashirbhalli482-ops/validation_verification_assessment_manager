"""Helpers for admin multi-table layouts and form record table cells."""


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


def parse_column_dropdowns(post, prefix, column_count, row_count=100):
    indices = set()
    marker = f'{prefix}_col_dd_'
    for key in post:
        if key.startswith(marker) and key.endswith('_col'):
            parts = key[len(marker):].split('_')
            if len(parts) == 2 and parts[0].isdigit():
                indices.add(int(parts[0]))
    dropdowns = []
    parsed_rows = []
    for index in sorted(indices):
        try:
            col = int(post.get(f'{prefix}_col_dd_{index}_col', 0))
        except (TypeError, ValueError):
            continue
        is_active = post.get(f'{prefix}_col_dd_{index}_active') == '1'
        rows = parse_rows_spec(post.get(f'{prefix}_col_dd_{index}_rows', ''), row_count)

        depends_raw = (post.get(f'{prefix}_col_dd_{index}_depends_on') or '').strip()
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
        map_parents = post.getlist(f'{prefix}_col_dd_{index}_map_parent')
        for map_index, parent_key in enumerate(map_parents):
            parent = parent_key.strip()
            if not parent:
                continue
            child_opts = [
                value.strip()
                for value in post.getlist(f'{prefix}_col_dd_{index}_map_opts_{map_index}')
                if value.strip()
            ]
            if child_opts:
                option_map[parent] = child_opts

        options = [
            value.strip()
            for value in post.getlist(f'{prefix}_col_dd_{index}_options')
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
        }
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
    }


def block_from_post(post, key, table_number=1):
    prefix = f'tbl_{key}'
    try:
        row_count = int(post.get(f'{prefix}_row_count', 100))
    except (TypeError, ValueError):
        return None
    columns = parse_columns(post, prefix)
    dropdowns, dropdown_rows = parse_column_dropdowns(post, prefix, len(columns), row_count)
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
        'next_dropdown_index': max([row['index'] for row in dropdown_rows], default=-1) + 1,
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
