"""
Range visualizer: 13×13 grid representation of poker ranges.
Generates HTML/SVG for Streamlit display.
"""
RANKS = "AKQJT98765432"


def range_to_grid(combo_set):
    """
    Convert a set of combo strings to a 13×13 grid.
    Returns list of rows, each cell is (combo_str, included, is_pair, is_suited).
    """
    grid = []
    for i, r1 in enumerate(RANKS):
        row = []
        for j, r2 in enumerate(RANKS):
            if i < j:
                combo = r1 + r2 + "s"
                included = combo in combo_set
                row.append((combo, included, False, True))
            elif i == j:
                combo = r1 + r2
                included = combo in combo_set
                row.append((combo, included, True, False))
            else:
                combo = r2 + r1 + "o"
                included = combo in combo_set
                row.append((combo, included, False, False))
        grid.append(row)
    return grid


def grid_to_html(combo_set_or_grid, title="Range", highlight_combo=None):
    """
    Convert grid or combo set to HTML table for Streamlit.
    Accepts either a pre-computed grid or a combo set.
    highlight_combo: combo string to highlight in blue.
    """
    if isinstance(combo_set_or_grid, set) or isinstance(combo_set_or_grid, list):
        grid = range_to_grid(set(combo_set_or_grid))
    else:
        grid = combo_set_or_grid

    colors = {
        (True, True): "#e74c3c",     # Pair included - red
        (True, False, True): "#3498db",  # Suited included - blue
        (True, False, False): "#2ecc71", # Offsuit included - green
        (False, True): "#2c2c2c",    # Pair excluded - dark
        (False, False, True): "#1a1a1a", # Suited excluded - very dark
        (False, False, False): "#252525", # Offsuit excluded - dark
    }

    html = f'<div style="font-family:monospace;font-size:11px;line-height:1.2">'
    html += f'<b>{title}</b><br>'

    # Header row
    html += '<table style="border-collapse:collapse">'
    html += '<tr><td></td>' + ''.join(f'<td style="width:32px;text-align:center;color:#888">{r}</td>' for r in RANKS) + '</tr>'

    for i, row in enumerate(grid):
        html += '<tr>'
        html += f'<td style="color:#888;text-align:right;padding-right:4px">{RANKS[i]}</td>'
        for j, cell in enumerate(row):
            combo, included, is_pair, is_suited = cell
            if is_pair:
                color = "#e74c3c" if included else "#2c2c2c"
                bg = "#e74c3c" if included else "#1a1a1a"
            elif is_suited:
                color = "#3498db" if included else "#555"
                bg = "#1a2a3a" if included else "#111"
            else:
                color = "#2ecc71" if included else "#444"
                bg = "#1a2a1a" if included else "#111"

            highlight = ""
            if highlight_combo and combo == highlight_combo:
                bg = "#f1c40f"
                color = "#000"

            html += (f'<td style="width:32px;height:22px;text-align:center;'
                    f'background:{bg};color:{color};border:1px solid #333;'
                    f'font-size:9px">{combo if included else ""}</td>')
        html += '</tr>'

    html += '</table></div>'

    # Legend
    html += ('<div style="margin-top:8px;font-size:10px;color:#888">'
            '<span style="color:#e74c3c">▮</span> Pereche &nbsp;'
            '<span style="color:#3498db">▮</span> Suited &nbsp;'
            '<span style="color:#2ecc71">▮</span> Offsuit &nbsp;'
            '<span style="color:#f1c40f">▮</span> Mâna ta</div>')

    return html


def range_stats(combo_set):
    """Calculate statistics about a range."""
    total = len(combo_set)
    pairs = sum(1 for c in combo_set if len(c) == 2)
    suited = sum(1 for c in combo_set if len(c) == 3 and c[2] == 's')
    offsuit = sum(1 for c in combo_set if len(c) == 3 and c[2] == 'o')

    return {
        "total_combos": total,
        "pairs": pairs,
        "suited": suited,
        "offsuit": offsuit,
        "total_hands": pairs * 6 + suited * 4 + offsuit * 12,
        "range_pct": round(total / 169 * 100, 1),
    }


def narrow_range_html(initial_range_set, narrowed_range_set, title="Range Narrowing"):
    """
    Show initial range and narrowed range side by side.
    """
    html = '<div style="display:flex;gap:20px">'
    html += '<div>' + grid_to_html(set(initial_range_set), "Range inițial") + '</div>'
    html += '<div style="font-size:24px;color:#888;align-self:center">→</div>'
    html += '<div>' + grid_to_html(set(narrowed_range_set), "După narrowing") + '</div>'
    html += '</div>'
    return html


def combo_to_grid_position(combo_str):
    """Get (row, col) in the 13×13 grid for a combo string."""
    if len(combo_str) == 2:  # Pair
        r = combo_str[0]
        i = RANKS.index(r)
        return (i, i)

    r1, r2 = combo_str[0], combo_str[1]
    i1, i2 = RANKS.index(r1), RANKS.index(r2)

    if combo_str[2] == 's':
        return (i1, i2)  # i1 < i2 for suited
    else:
        return (i2, i1)  # i2 < i1 for offsuit
