"""
Range visualizer — 13×13 grid, compact HTML, light+dark mode support.
"""
RANKS = "AKQJT98765432"


def combo_to_grid_position(combo_str):
    """Get (row, col) in 13×13 grid for a combo."""
    if len(combo_str) == 2:
        i = RANKS.index(combo_str[0])
        return (i, i)
    r1, r2 = combo_str[0], combo_str[1]
    i1, i2 = RANKS.index(r1), RANKS.index(r2)
    return (i1, i2) if combo_str[2] == 's' else (i2, i1)


def range_to_grid(combo_set):
    """Convert combo set to 13×13 grid of (combo, included, is_pair, is_suited)."""
    s = set(combo_set)
    grid = []
    for i, r1 in enumerate(RANKS):
        row = []
        for j, r2 in enumerate(RANKS):
            if i < j:
                row.append((r1 + r2 + "s", r1 + r2 + "s" in s, False, True))
            elif i == j:
                row.append((r1 + r2, r1 + r2 in s, True, False))
            else:
                row.append((r2 + r1 + "o", r2 + r1 + "o" in s, False, False))
        grid.append(row)
    return grid


def grid_to_html(combo_set_or_grid, title="Range", highlight_combo=None):
    """Generate compact HTML table. Works in light and dark mode."""
    if isinstance(combo_set_or_grid, set) or (isinstance(combo_set_or_grid, list)
          and not isinstance(combo_set_or_grid[0], list)):
        grid = range_to_grid(set(combo_set_or_grid))
    else:
        grid = combo_set_or_grid

    # Use CSS classes for massive size reduction
    css = """
    <style>
    .rg-table { border-collapse: collapse; font-family: monospace; font-size: 10px; }
    .rg-table td { width: 26px; height: 17px; text-align: center; border: 1px solid #444; font-size: 8px; padding: 0; }
    .rg-hdr { color: #999; width: 26px; }
    .rg-lbl { color: #999; text-align: right; padding-right: 3px; }
    .rg-pair-in { background: #c0392b; color: #fff; }
    .rg-pair-out { background: #1a1a1a; color: #333; }
    .rg-suit-in { background: #1a4a6e; color: #6ab0e8; }
    .rg-suit-out { background: #0d0d0d; color: #222; }
    .rg-off-in { background: #1a4a2e; color: #5ac87a; }
    .rg-off-out { background: #0d0d0d; color: #1a1a1a; }
    .rg-hl { background: #f39c12 !important; color: #000 !important; font-weight: bold; }
    @media (prefers-color-scheme: light) {
      .rg-pair-out { background: #eee; color: #ccc; }
      .rg-suit-out { background: #eef; color: #ccd; }
      .rg-off-out { background: #efe; color: #cdc; }
      .rg-table td { border-color: #ddd; }
    }
    </style>
    """

    html = css + f'<b style="font-size:12px">{title}</b><br>'
    html += '<table class="rg-table"><tr><td></td>'
    html += ''.join(f'<td class="rg-hdr">{r}</td>' for r in RANKS)
    html += '</tr>'

    for i, row in enumerate(grid):
        html += f'<tr><td class="rg-lbl">{RANKS[i]}</td>'
        for cell in row:
            combo, inc, is_pair, is_suited = cell
            if is_pair:
                cls = "rg-pair-in" if inc else "rg-pair-out"
            elif is_suited:
                cls = "rg-suit-in" if inc else "rg-suit-out"
            else:
                cls = "rg-off-in" if inc else "rg-off-out"

            if highlight_combo and combo == highlight_combo:
                cls += " rg-hl"

            txt = combo if inc else ""
            html += f'<td class="{cls}">{txt}</td>'
        html += '</tr>'

    html += '</table>'
    html += ('<div style="font-size:9px;color:#888;margin-top:4px">'
            '<span style="color:#c0392b">▮</span>PP &nbsp;'
            '<span style="color:#6ab0e8">▮</span>Suited &nbsp;'
            '<span style="color:#5ac87a">▮</span>Off &nbsp;'
            '<span style="color:#f39c12">▮</span>Mâna ta</div>')
    return html


def narrow_range_html(initial, narrowed, title="Range Narrowing"):
    """Side-by-side range comparison."""
    return ('<div style="display:flex;gap:16px;flex-wrap:wrap">' +
            '<div>' + grid_to_html(set(initial), "Inițial") + '</div>' +
            '<div style="font-size:20px;color:#888;align-self:center">→</div>' +
            '<div>' + grid_to_html(set(narrowed), "Narrowed") + '</div>' +
            '</div>')


def range_stats(combo_set):
    """Range statistics."""
    s = set(combo_set)
    total = len(s)
    pairs = sum(1 for c in s if len(c) == 2)
    suited = sum(1 for c in s if len(c) == 3 and c[2] == 's')
    offsuit = sum(1 for c in s if len(c) == 3 and c[2] == 'o')
    return {
        "total_combos": total,
        "pairs": pairs, "suited": suited, "offsuit": offsuit,
        "total_hands": pairs * 6 + suited * 4 + offsuit * 12,
        "range_pct": round(total / 169 * 100, 1),
    }
