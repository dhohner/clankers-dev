from html import escape

COLUMNS = ("name", "qty")


def render_cell(value):
    if value is None:
        return "<td></td>"
    else:
        return "<td>" + escape(str(value)) + "</td>"


def render_header():
    return "<thead><tr>" + "".join(f"<th>{column}</th>" for column in COLUMNS) + "</tr></thead>"


def render_body(rows):
    out = ""
    for row in rows:
        out += "<tr>" + "".join([render_cell(row.get(column)) for column in COLUMNS]) + "</tr>"
    return "<tbody>" + out + "</tbody>"


def render_table(rows, loading=False):
    if loading:
        header = render_header()
        message = '<tr><td colspan="2" class="status">Loading</td></tr>'
        return '<table class="data">' + header + "<tbody>" + message + "</tbody></table>"
    if not rows:
        header = render_header()
        message = '<tr><td colspan="2" class="status">No items</td></tr>'
        return '<table class="data">' + header + "<tbody>" + message + "</tbody></table>"
    return '<table class="data">' + render_header() + render_body(rows) + "</table>"
