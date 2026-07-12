"""Helpers for admin multi-table layouts and form record table cells."""


def table_block_keys(post):
    keys = set()
    for key in post:
        if key.startswith('tbl_') and key.endswith('_number'):
            keys.add(key[4:-7])
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


def parse_column_dropdowns(post, prefix, column_count):
    indices = set()
    marker = f'{prefix}_col_dd_'
    for key in post:
        if key.startswith(marker) and key.endswith('_col'):
            parts = key[len(marker):].split('_')
            if len(parts) == 2 and parts[0].isdigit():
                indices.add(int(parts[0]))
    dropdowns = []
    parsed_rows = []
    seen_cols = set()
    for index in sorted(indices):
        try:
            col = int(post.get(f'{prefix}_col_dd_{index}_col', 0))
        except (TypeError, ValueError):
            continue
        is_active = post.get(f'{prefix}_col_dd_{index}_active') == '1'
        options = [
            value.strip()
            for value in post.getlist(f'{prefix}_col_dd_{index}_options')
            if value.strip()
        ]
        if not options or col < 0 or col >= column_count:
            continue
        if col in seen_cols:
            dropdowns = [item for item in dropdowns if item['col'] != col]
            parsed_rows = [item for item in parsed_rows if item['col'] != col]
        seen_cols.add(col)
        entry = {'col': col, 'options': options, 'is_active': is_active}
        dropdowns.append(entry)
        parsed_rows.append({'index': index, **entry})
    return dropdowns, parsed_rows


def build_table_block(layout=None, key=None, parsed=None):
    if parsed:
        return parsed
    if layout:
        dropdown_rows = [
            {
                'index': index,
                'col': entry['col'],
                'options': entry['options'],
                'is_active': entry['is_active'],
            }
            for index, entry in enumerate(layout.normalized_column_dropdowns())
        ]
        return {
            'key': key or str(layout.pk),
            'layout_id': layout.pk,
            'table_number': layout.table_number,
            'table_name': layout.table_name,
            'notes': layout.notes,
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
        'notes': '',
        'row_count': 100,
        'column_rows': [{'label': '', 'is_active': True}],
        'dropdown_rows': [],
        'next_dropdown_index': 0,
    }


def block_from_post(post, key):
    prefix = f'tbl_{key}'
    try:
        table_number = int(post.get(f'{prefix}_number', 1))
        row_count = int(post.get(f'{prefix}_row_count', 100))
    except (TypeError, ValueError):
        return None
    columns = parse_columns(post, prefix)
    dropdowns, dropdown_rows = parse_column_dropdowns(post, prefix, len(columns))
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
        'notes': post.get(f'{prefix}_notes', '').strip(),
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
